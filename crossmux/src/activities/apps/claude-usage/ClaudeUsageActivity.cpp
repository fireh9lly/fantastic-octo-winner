#include "ClaudeUsageActivity.h"

#include <Arduino.h>
#include <GfxRenderer.h>
#include <HalClock.h>
#include <HalStorage.h>
#include <I18n.h>
#include <Logging.h>
#include <Memory.h>
#include <WiFi.h>
#include <esp_wifi.h>

#include <algorithm>
#include <cstdio>
#include <ctime>
#include <string>

#include "CrossPointSettings.h"
#include "MappedInputManager.h"
#include "NetworkStartup.h"
#include "activities/apps/GameUi.h"
#include "activities/network/WifiSelectionActivity.h"
#include "components/UITheme.h"
#include "fontIds.h"
#include "network/HttpDownloader.h"
#include "util/TimeUtils.h"

namespace {

// The usage document is ~600 bytes; cap the body so a misbehaving relay
// cannot grow the heap. Parsing uses a filtered JsonDocument (a few hundred bytes).
constexpr size_t kMaxBodyBytes = 8192;
constexpr size_t kInitialBodyReserve = 1024;
// The token file is tiny; refuse anything that is clearly not a config.
constexpr size_t kMaxConfigBytes = 2048;

constexpr int kBarHeight = 22;
constexpr int kCompactBarHeight = 10;

bool isConnected() { return WiFi.status() == WL_CONNECTED; }

// "15:00" / "3:00 PM" for a UTC epoch in the configured timezone, optionally
// prefixed with the ISO-style "MM-DD " date used elsewhere in CrossMux.
bool formatLocal(const uint32_t epoch, const bool withDate, char* buffer, const size_t size) {
  std::tm local{};
  if (epoch == 0 || !TimeUtils::getLocalDateTime(epoch, local)) return false;
  char clock[12];
  if (SETTINGS.clockFormat == 1) {
    const int hour12 = local.tm_hour % 12 == 0 ? 12 : local.tm_hour % 12;
    snprintf(clock, sizeof(clock), "%d:%02d %s", hour12, local.tm_min, local.tm_hour < 12 ? "AM" : "PM");
  } else {
    snprintf(clock, sizeof(clock), "%02d:%02d", local.tm_hour, local.tm_min);
  }
  if (withDate) {
    snprintf(buffer, size, "%02d-%02d %s", local.tm_mon + 1, local.tm_mday, clock);
  } else {
    snprintf(buffer, size, "%s", clock);
  }
  return true;
}

void formatPercent(const float utilization, char* buffer, const size_t size) {
  const float shown = utilization < 0.0f ? 0.0f : utilization;
  snprintf(buffer, size, "%d%%", static_cast<int>(shown + 0.5f));
}

}  // namespace

void ClaudeUsageActivity::onEnter() {
  Activity::onEnter();
  snapshot_ = ClaudeUsageSnapshot{};
  hasSnapshot_ = false;
  problem_ = Problem::None;
  lastHttpStatus_ = 0;
  fetchedAtEpoch_ = 0;
  fetchedAtMs_ = 0;
  broughtWifiUp_ = false;
  clockSyncTried_ = false;
  waitForInputRelease_ = mappedInput.isPressed(MappedInputManager::Button::Confirm);

  if (!loadConfig()) {
    state_ = State::NoConfig;
    requestUpdate();
    return;
  }
  requestRefresh();
}

void ClaudeUsageActivity::onExit() {
  teardownOwnedWifi();
  // The token is a credential: do not leave it in a freed heap block.
  memset(config_.token, 0, sizeof(config_.token));
  Activity::onExit();
}

bool ClaudeUsageActivity::loadConfig() {
  config_ = ClaudeUsageConfig{};
  if (!Storage.exists(kConfigPath)) {
    LOG_INF("CLAUDE", "No config at %s", kConfigPath);
    return false;
  }
  std::string text;
  if (!Storage.readFileToString("CLAUDE", kConfigPath, kMaxConfigBytes, text)) {
    LOG_ERR("CLAUDE", "Could not read %s", kConfigPath);
    return false;
  }
  const bool ok = claude_usage::parseConfig(text.data(), text.size(), config_);
  // Scrub the transient copy of the token before the string frees its buffer.
  std::fill(text.begin(), text.end(), '\0');
  if (!ok || !config_.hasToken()) {
    LOG_ERR("CLAUDE", "Config has no token");
    return false;
  }
  return true;
}

void ClaudeUsageActivity::requestRefresh() {
  problem_ = Problem::None;
  if (isConnected()) {
    NetworkStartup::prepare(renderer);
    state_ = State::Fetching;
    requestUpdate();
    return;
  }
  launchWifiSelection();
}

void ClaudeUsageActivity::launchWifiSelection() {
  // ActivityManager owns the picker across frames; stack lifetime is insufficient.
  auto wifi = makeUniqueNoThrow<WifiSelectionActivity>(renderer, mappedInput, true);
  if (!wifi) {
    LOG_ERR("CLAUDE", "OOM: WifiSelectionActivity (%u bytes)", static_cast<unsigned>(sizeof(WifiSelectionActivity)));
    problem_ = Problem::NoMemory;
    state_ = hasSnapshot_ ? State::Ready : State::Error;
    requestUpdate();
    return;
  }

  broughtWifiUp_ = true;
  startActivityForResult(std::move(wifi), [this](const ActivityResult& result) {
    // The release that closed the picker must not also trigger Refresh here.
    waitForInputRelease_ = mappedInput.isPressed(MappedInputManager::Button::Back) ||
                           mappedInput.isPressed(MappedInputManager::Button::Confirm) ||
                           mappedInput.isPressed(MappedInputManager::Button::NavPrevious) ||
                           mappedInput.isPressed(MappedInputManager::Button::NavNext);
    if (result.isCancelled || !isConnected()) {
      LOG_INF("CLAUDE", "Wi-Fi selection cancelled or failed");
      problem_ = Problem::WifiFailed;
      state_ = hasSnapshot_ ? State::Ready : State::Error;
      return;
    }
    state_ = State::Fetching;
  });
}

void ClaudeUsageActivity::teardownOwnedWifi() {
  if (!broughtWifiUp_) return;
  WiFi.disconnect(false);
  delay(100);
  WiFi.mode(WIFI_OFF);
  esp_wifi_deinit();
  broughtWifiUp_ = false;
}

void ClaudeUsageActivity::doFetch() {
  if (!isConnected()) {
    problem_ = Problem::WifiFailed;
    state_ = hasSnapshot_ ? State::Ready : State::Error;
    return;
  }

  // "Resets in" needs wall-clock time; sync once per visit if it is not set.
  if (!clockSyncTried_ && TimeUtils::getCurrentValidTimestamp() == 0) {
    clockSyncTried_ = true;
    if (!halClock.syncNow()) LOG_ERR("CLAUDE", "Clock sync failed; reset countdowns unavailable");
  }

  if (!HttpDownloader::hasMemoryForTls()) {
    problem_ = Problem::NoMemory;
    state_ = hasSnapshot_ ? State::Ready : State::Error;
    return;
  }

  const char* url = config_.url[0] != '\0' ? config_.url : claude_usage::kDefaultUrl;

  // One short-lived heap string for the response body; released when this
  // function returns. A fixed static buffer was rejected because it would
  // pin 8KB of DRAM for the whole firmware lifetime.
  std::string body;
  body.reserve(kInitialBodyReserve);
  bool overflow = false;

  HttpDownloader::FetchOptions options;
  options.bearer = config_.token;
  options.accept = "application/json";
  options.headers.emplace_back(claude_usage::kBetaHeader, claude_usage::kBetaValue);
  int status = 0;
  options.statusOut = &status;

  LOG_INF("CLAUDE", "Fetching usage (free heap %u)", static_cast<unsigned>(ESP.getFreeHeap()));
  const bool ok = HttpDownloader::fetchUrl(
      url,
      [&body, &overflow](const uint8_t* data, const size_t len) {
        if (body.size() + len > kMaxBodyBytes) {
          overflow = true;
          return false;
        }
        body.append(reinterpret_cast<const char*>(data), len);
        return true;
      },
      options);
  // The bearer copy in options is a credential too.
  std::fill(options.bearer.begin(), options.bearer.end(), '\0');

  lastHttpStatus_ = status;
  if (!ok) {
    if (status == 401 || status == 403) {
      problem_ = Problem::Unauthorized;
    } else if (status == 0) {
      problem_ = Problem::Network;
    } else if (overflow) {
      problem_ = Problem::BadResponse;
    } else {
      problem_ = Problem::Http;
    }
    LOG_ERR("CLAUDE", "Usage fetch failed: status=%d overflow=%d", status, overflow ? 1 : 0);
    state_ = hasSnapshot_ ? State::Ready : State::Error;
    return;
  }

  ClaudeUsageSnapshot parsed;
  if (!claude_usage::parseUsageJson(body.data(), body.size(), parsed)) {
    LOG_ERR("CLAUDE", "Unrecognised usage response (%u bytes)", static_cast<unsigned>(body.size()));
    problem_ = Problem::BadResponse;
    state_ = hasSnapshot_ ? State::Ready : State::Error;
    return;
  }

  snapshot_ = parsed;
  hasSnapshot_ = true;
  problem_ = Problem::None;
  fetchedAtEpoch_ = TimeUtils::getCurrentValidTimestamp();
  fetchedAtMs_ = millis();
  state_ = State::Ready;
  LOG_INF("CLAUDE", "Session %.0f%%, weekly %.0f%%", static_cast<double>(snapshot_.session.utilization),
          static_cast<double>(snapshot_.weekly.utilization));
}

bool ClaudeUsageActivity::consumeInputReleaseBarrier() {
  if (!waitForInputRelease_) return false;
  const bool anyPressed = mappedInput.isPressed(MappedInputManager::Button::Back) ||
                          mappedInput.isPressed(MappedInputManager::Button::Confirm) ||
                          mappedInput.isPressed(MappedInputManager::Button::NavPrevious) ||
                          mappedInput.isPressed(MappedInputManager::Button::NavNext);
  if (!anyPressed) waitForInputRelease_ = false;
  return true;
}

Rect ClaudeUsageActivity::refreshButtonRect() const {
  const auto& metrics = UITheme::getInstance().getMetrics();
  return gameTouchActionRect(renderer.getScreenWidth(), renderer.getScreenHeight(), metrics.contentSidePadding,
                             metrics.menuSpacing, metrics.menuRowHeight, 0, 1);
}

void ClaudeUsageActivity::loop() {
  if (state_ == State::Fetching) {
    // Paint "Updating…" before blocking on TLS + HTTP.
    requestUpdateAndWait();
    doFetch();
    requestUpdate();
    return;
  }

  if (consumeInputReleaseBarrier()) return;

  if (mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    activityManager.goToApps();
    return;
  }

  if (state_ == State::NoConfig) {
    // Let the user drop the file in via USB/web transfer and retry without leaving.
    if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
      if (loadConfig()) requestRefresh();
      requestUpdate();
    }
    return;
  }

  bool refresh = mappedInput.wasReleased(MappedInputManager::Button::Confirm);
  if (!refresh && mappedInput.hasTouch()) {
    const Rect button = refreshButtonRect();
    refresh = mappedInput.wasTapInRect(button.x, button.y, button.width, button.height);
  }
  if (!refresh && state_ == State::Ready && problem_ == Problem::None && isConnected() &&
      millis() - fetchedAtMs_ >= kAutoRefreshMs) {
    refresh = true;
  }
  if (refresh) requestRefresh();
}

const char* ClaudeUsageActivity::problemText() const {
  switch (problem_) {
    case Problem::WifiFailed:
      return tr(STR_CLAUDE_USAGE_ERR_WIFI);
    case Problem::NoMemory:
      return tr(STR_CLAUDE_USAGE_ERR_MEMORY);
    case Problem::Unauthorized:
      return tr(STR_CLAUDE_USAGE_ERR_AUTH);
    case Problem::Network:
      return tr(STR_CLAUDE_USAGE_ERR_NETWORK);
    case Problem::BadResponse:
      return tr(STR_CLAUDE_USAGE_ERR_RESPONSE);
    case Problem::Http:
      return tr(STR_CLAUDE_USAGE_ERR_HTTP);
    case Problem::None:
      break;
  }
  return "";
}

void ClaudeUsageActivity::drawCenteredMessage(const Rect& content, const char* title, const char* detail,
                                              const char* detail2) const {
  const int titleHeight = renderer.getLineHeight(UI_12_FONT_ID);
  const int detailHeight = renderer.getLineHeight(UI_10_FONT_ID);
  const int gap = std::max(6, UITheme::getInstance().getMetrics().verticalSpacing / 2);
  const int lines = (detail && detail[0] ? 1 : 0) + (detail2 && detail2[0] ? 1 : 0);
  const int blockHeight = titleHeight + lines * (gap + detailHeight);
  int y = content.y + std::max(0, (content.height - blockHeight) / 2);
  UITheme::drawCenteredText(renderer, content, UI_12_FONT_ID, y, title, true, EpdFontFamily::BOLD);
  y += titleHeight + gap;
  if (detail && detail[0]) {
    const std::string fitted = renderer.truncatedText(UI_10_FONT_ID, detail, content.width);
    UITheme::drawCenteredText(renderer, content, UI_10_FONT_ID, y, fitted.c_str());
    y += detailHeight + gap;
  }
  if (detail2 && detail2[0]) {
    const std::string fitted = renderer.truncatedText(UI_10_FONT_ID, detail2, content.width);
    UITheme::drawCenteredText(renderer, content, UI_10_FONT_ID, y, fitted.c_str());
  }
}

void ClaudeUsageActivity::drawWindow(const Rect& bounds, const char* title, const ClaudeUsageWindow& window,
                                     const uint32_t now, const bool showResetDate) const {
  const int titleHeight = renderer.getLineHeight(UI_12_FONT_ID);
  const int bigHeight = renderer.getLineHeight(NOTOSANS_18_FONT_ID);
  const int gap = std::max(6, UITheme::getInstance().getMetrics().verticalSpacing / 2);

  // Title on the left, large percentage on the right, bottoms aligned.
  const int rowHeight = std::max(titleHeight, bigHeight);
  int y = bounds.y;
  const std::string fittedTitle = renderer.truncatedText(UI_12_FONT_ID, title, bounds.width * 2 / 3,
                                                         EpdFontFamily::BOLD);
  renderer.drawText(UI_12_FONT_ID, bounds.x, y + rowHeight - titleHeight, fittedTitle.c_str(), true,
                    EpdFontFamily::BOLD);
  char percent[8];
  if (window.present) {
    formatPercent(window.utilization, percent, sizeof(percent));
  } else {
    snprintf(percent, sizeof(percent), "--");
  }
  const int percentWidth = renderer.getTextWidth(NOTOSANS_18_FONT_ID, percent, EpdFontFamily::BOLD);
  renderer.drawText(NOTOSANS_18_FONT_ID, bounds.x + bounds.width - percentWidth, y + rowHeight - bigHeight, percent,
                    true, EpdFontFamily::BOLD);
  y += rowHeight + gap;

  // Usage bar: outline plus solid fill, with quarter ticks for scale.
  renderer.drawRect(bounds.x, y, bounds.width, kBarHeight, 2, true);
  const int inner = bounds.width - 6;
  const int fill = window.present ? inner * claude_usage::fillPermille(window.utilization) / 1000 : 0;
  if (fill > 0) renderer.fillRect(bounds.x + 3, y + 3, fill, kBarHeight - 6, true);
  for (int q = 1; q < 4; ++q) {
    const int tx = bounds.x + 3 + inner * q / 4;
    // Ticks draw white over the fill and black over empty track.
    const bool overFill = tx < bounds.x + 3 + fill;
    renderer.drawLine(tx, y + kBarHeight - 7, tx, y + kBarHeight - 4, !overFill);
  }
  y += kBarHeight + gap;

  // "Resets in 2h 14m · 15:00"
  char line[96];
  line[0] = '\0';
  if (window.present && window.resetsAt != 0) {
    char when[24];
    const bool haveWhen = formatLocal(window.resetsAt, showResetDate, when, sizeof(when));
    if (now != 0) {
      char duration[16];
      claude_usage::formatDuration(static_cast<int64_t>(window.resetsAt) - static_cast<int64_t>(now), duration,
                                   sizeof(duration));
      if (haveWhen) {
        snprintf(line, sizeof(line), "%s %s · %s", tr(STR_CLAUDE_USAGE_RESETS_IN), duration, when);
      } else {
        snprintf(line, sizeof(line), "%s %s", tr(STR_CLAUDE_USAGE_RESETS_IN), duration);
      }
    } else if (haveWhen) {
      snprintf(line, sizeof(line), "%s %s", tr(STR_CLAUDE_USAGE_RESETS_AT), when);
    }
  } else if (window.present) {
    snprintf(line, sizeof(line), "%s", tr(STR_CLAUDE_USAGE_NOT_STARTED));
  } else {
    snprintf(line, sizeof(line), "%s", tr(STR_CLAUDE_USAGE_UNAVAILABLE));
  }
  const std::string fitted = renderer.truncatedText(UI_10_FONT_ID, line, bounds.width);
  renderer.drawText(UI_10_FONT_ID, bounds.x, y, fitted.c_str());
}

void ClaudeUsageActivity::drawCompactWindow(const int x, const int y, const int width, const char* title,
                                            const ClaudeUsageWindow& window) const {
  char percent[8];
  formatPercent(window.utilization, percent, sizeof(percent));
  const int percentWidth = renderer.getTextWidth(UI_10_FONT_ID, percent, EpdFontFamily::BOLD);
  const int labelWidth = std::max(0, width / 2 - 8);
  const std::string label = renderer.truncatedText(UI_10_FONT_ID, title, labelWidth);
  renderer.drawText(UI_10_FONT_ID, x, y, label.c_str());

  const int lineHeight = renderer.getLineHeight(UI_10_FONT_ID);
  const int barX = x + width / 2;
  const int barWidth = std::max(10, width / 2 - percentWidth - 10);
  const int barY = y + (lineHeight - kCompactBarHeight) / 2;
  renderer.drawRect(barX, barY, barWidth, kCompactBarHeight, 1, true);
  const int fill = (barWidth - 4) * claude_usage::fillPermille(window.utilization) / 1000;
  if (fill > 0) renderer.fillRect(barX + 2, barY + 2, fill, kCompactBarHeight - 4, true);
  renderer.drawText(UI_10_FONT_ID, x + width - percentWidth, y, percent, true, EpdFontFamily::BOLD);
}

void ClaudeUsageActivity::render(RenderLock&&) {
  const auto& metrics = UITheme::getInstance().getMetrics();
  const Rect safe = UITheme::getInstance().getScreenSafeArea(renderer, true, false);
  const bool touch = mappedInput.hasTouch() && state_ != State::NoConfig && state_ != State::Fetching;
  const int touchReserve = touch ? metrics.menuRowHeight + metrics.verticalSpacing : 0;
  const int contentTop = safe.y + metrics.topPadding + metrics.headerHeight + metrics.verticalSpacing;
  const Rect content{safe.x + metrics.contentSidePadding, contentTop,
                     std::max(1, safe.width - metrics.contentSidePadding * 2),
                     std::max(1, safe.y + safe.height - contentTop - metrics.verticalSpacing - touchReserve)};

  renderer.clearScreen();
  GUI.drawHeader(renderer, Rect{safe.x, safe.y + metrics.topPadding, safe.width, metrics.headerHeight},
                 tr(STR_CLAUDE_USAGE_TITLE));

  const uint32_t now = TimeUtils::getCurrentValidTimestamp();

  if (state_ == State::NoConfig) {
    drawCenteredMessage(content, tr(STR_CLAUDE_USAGE_NO_CONFIG), tr(STR_CLAUDE_USAGE_NO_CONFIG_HINT), kConfigPath);
  } else if (!hasSnapshot_ && state_ == State::Fetching) {
    drawCenteredMessage(content, tr(STR_CLAUDE_USAGE_UPDATING), nullptr);
  } else if (!hasSnapshot_) {
    const char* hint = problem_ == Problem::Unauthorized ? tr(STR_CLAUDE_USAGE_ERR_AUTH_HINT) : nullptr;
    char status[32];
    if (!hint && lastHttpStatus_ > 0) {
      snprintf(status, sizeof(status), "HTTP %d", lastHttpStatus_);
      hint = status;
    }
    drawCenteredMessage(content, problemText(), hint);
  } else {
    const int sectionGap = std::max(16, metrics.verticalSpacing * 2);
    const int windowHeight = std::max(renderer.getLineHeight(NOTOSANS_18_FONT_ID), renderer.getLineHeight(UI_12_FONT_ID)) +
                             kBarHeight +
                             renderer.getLineHeight(UI_10_FONT_ID) + 2 * std::max(6, metrics.verticalSpacing / 2);
    int y = content.y;
    drawWindow(Rect{content.x, y, content.width, windowHeight}, tr(STR_CLAUDE_USAGE_SESSION), snapshot_.session, now,
               false);
    y += windowHeight + sectionGap;
    drawWindow(Rect{content.x, y, content.width, windowHeight}, tr(STR_CLAUDE_USAGE_WEEKLY), snapshot_.weekly, now,
               true);
    y += windowHeight + sectionGap;

    // Per-model weekly limits, only when the plan reports them.
    const int lineHeight = renderer.getLineHeight(UI_10_FONT_ID);
    const int rowStep = lineHeight + std::max(4, metrics.verticalSpacing / 2);
    const int footerTop = content.y + content.height - lineHeight;
    if (snapshot_.weeklyOpus.present && y + rowStep <= footerTop) {
      drawCompactWindow(content.x, y, content.width, tr(STR_CLAUDE_USAGE_WEEKLY_OPUS), snapshot_.weeklyOpus);
      y += rowStep;
    }
    if (snapshot_.weeklySonnet.present && y + rowStep <= footerTop) {
      drawCompactWindow(content.x, y, content.width, tr(STR_CLAUDE_USAGE_WEEKLY_SONNET), snapshot_.weeklySonnet);
      y += rowStep;
    }

    // Footer: freshness, or the refresh problem while keeping old numbers.
    char footer[96];
    if (state_ == State::Fetching) {
      snprintf(footer, sizeof(footer), "%s", tr(STR_CLAUDE_USAGE_UPDATING));
    } else if (problem_ != Problem::None) {
      snprintf(footer, sizeof(footer), "%s", problemText());
    } else {
      char when[16];
      if (formatLocal(fetchedAtEpoch_, false, when, sizeof(when))) {
        snprintf(footer, sizeof(footer), "%s %s", tr(STR_CLAUDE_USAGE_UPDATED), when);
      } else {
        footer[0] = '\0';
      }
    }
    if (footer[0]) {
      const std::string fitted = renderer.truncatedText(UI_10_FONT_ID, footer, content.width);
      UITheme::drawCenteredText(renderer, content, UI_10_FONT_ID, footerTop, fitted.c_str());
    }
  }

  if (touch) GUI.drawActionButton(renderer, refreshButtonRect(), tr(STR_CLAUDE_USAGE_REFRESH));

  if (state_ != State::Fetching) {
    const char* confirm = state_ == State::NoConfig ? tr(STR_RETRY) : tr(STR_CLAUDE_USAGE_REFRESH);
    const auto labels = mappedInput.mapLabels(tr(STR_BACK), confirm, "", "");
    GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  }
  renderer.displayBuffer();
}
