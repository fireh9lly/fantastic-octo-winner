#pragma once

#include <cstdint>

#include "ClaudeUsageData.h"
#include "activities/Activity.h"

struct Rect;

// Shows Claude plan usage: the current 5-hour session window and the weekly
// limit, each as a percentage bar with time-to-reset.
//
// Configuration lives on the SD card in /claude-usage.json (see
// src/activities/apps/claude-usage/README.md). Wi-Fi is brought up on demand
// through the shared picker and torn down on exit if this app started it.
class ClaudeUsageActivity final : public Activity {
 public:
  explicit ClaudeUsageActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
      : Activity("ClaudeUsage", renderer, mappedInput) {}

  void onEnter() override;
  void onExit() override;
  void loop() override;
  bool skipLoopDelay() override { return state_ == State::Fetching; }
  void render(RenderLock&&) override;

  static constexpr const char* kConfigPath = "/claude-usage.json";

 private:
  enum class State : uint8_t {
    NoConfig,  // config file missing or empty
    Fetching,  // next loop() renders "Updating…" then blocks on the request
    Ready,     // snapshot_ holds data (possibly with a refresh error notice)
    Error,     // no data yet and the last attempt failed
  };

  enum class Problem : uint8_t {
    None,
    WifiFailed,
    NoMemory,
    Unauthorized,
    Http,
    Network,
    BadResponse,
  };

  // Re-fetch automatically while the app stays open and online.
  static constexpr uint32_t kAutoRefreshMs = 5UL * 60UL * 1000UL;

  ClaudeUsageConfig config_;
  ClaudeUsageSnapshot snapshot_;
  State state_ = State::NoConfig;
  Problem problem_ = Problem::None;
  int lastHttpStatus_ = 0;
  uint32_t fetchedAtEpoch_ = 0;  // wall clock of last success, 0 if unknown
  uint32_t fetchedAtMs_ = 0;     // millis() of last success
  bool hasSnapshot_ = false;
  bool broughtWifiUp_ = false;
  bool clockSyncTried_ = false;
  bool waitForInputRelease_ = false;

  bool loadConfig();
  void requestRefresh();
  void launchWifiSelection();
  void doFetch();
  void teardownOwnedWifi();
  bool consumeInputReleaseBarrier();
  Rect refreshButtonRect() const;

  void drawWindow(const Rect& bounds, const char* title, const ClaudeUsageWindow& window, uint32_t now,
                  bool showResetDate) const;
  void drawCompactWindow(int x, int y, int width, const char* title, const ClaudeUsageWindow& window) const;
  void drawCenteredMessage(const Rect& content, const char* title, const char* detail,
                           const char* detail2 = nullptr) const;
  const char* problemText() const;
};
