#include "ClaudeUsageData.h"

#include <ArduinoJson.h>

#include <cctype>
#include <cstdio>
#include <cstring>

namespace claude_usage {
namespace {

bool readDigits(const char*& p, const int count, int& out) {
  out = 0;
  for (int i = 0; i < count; ++i) {
    if (!isdigit(static_cast<unsigned char>(p[i]))) return false;
    out = out * 10 + (p[i] - '0');
  }
  p += count;
  return true;
}

// Days from 1970-01-01 to the civil date (Howard Hinnant's algorithm).
int64_t daysFromCivil(int year, const unsigned month, const unsigned day) {
  year -= month <= 2 ? 1 : 0;
  const int era = (year >= 0 ? year : year - 399) / 400;
  const unsigned yoe = static_cast<unsigned>(year - era * 400);
  const unsigned doy = (153 * (month > 2 ? month - 3 : month + 9) + 2) / 5 + day - 1;
  const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return static_cast<int64_t>(era) * 146097 + static_cast<int64_t>(doe) - 719468;
}

void readWindow(JsonVariantConst node, ClaudeUsageWindow& out) {
  out = ClaudeUsageWindow{};
  if (!node.is<JsonObjectConst>()) return;
  JsonVariantConst utilization = node["utilization"];
  if (!utilization.is<float>()) return;
  // Read as floating point: producers emit both 35 and 35.0 (see esp32-pitfalls.md).
  out.utilization = utilization.as<float>();
  out.present = true;
  const char* resetsAt = node["resets_at"] | static_cast<const char*>(nullptr);
  uint32_t epoch = 0;
  if (resetsAt && parseIso8601(resetsAt, epoch)) out.resetsAt = epoch;
}

void copyTrimmed(const char* src, char* dst, const size_t dstSize) {
  if (dstSize == 0) return;
  dst[0] = '\0';
  if (!src) return;
  while (*src && isspace(static_cast<unsigned char>(*src))) ++src;
  size_t len = strlen(src);
  while (len > 0 && isspace(static_cast<unsigned char>(src[len - 1]))) --len;
  if (len >= dstSize) len = dstSize - 1;
  memcpy(dst, src, len);
  dst[len] = '\0';
}

}  // namespace

bool parseIso8601(const char* text, uint32_t& epochOut) {
  if (!text) return false;
  const char* p = text;
  int year = 0, month = 0, day = 0, hour = 0, minute = 0, second = 0;
  if (!readDigits(p, 4, year) || *p++ != '-') return false;
  if (!readDigits(p, 2, month) || *p++ != '-') return false;
  if (!readDigits(p, 2, day)) return false;
  if (*p != 'T' && *p != 't' && *p != ' ') return false;
  ++p;
  if (!readDigits(p, 2, hour) || *p++ != ':') return false;
  if (!readDigits(p, 2, minute)) return false;
  if (*p == ':') {
    ++p;
    if (!readDigits(p, 2, second)) return false;
  }
  if (*p == '.') {
    ++p;
    while (isdigit(static_cast<unsigned char>(*p))) ++p;  // fractional seconds are dropped
  }
  int offsetSeconds = 0;
  if (*p == 'Z' || *p == 'z') {
    ++p;
  } else if (*p == '+' || *p == '-') {
    const int sign = *p == '-' ? -1 : 1;
    ++p;
    int offH = 0, offM = 0;
    if (!readDigits(p, 2, offH)) return false;
    if (*p == ':') ++p;
    if (isdigit(static_cast<unsigned char>(*p)) && !readDigits(p, 2, offM)) return false;
    offsetSeconds = sign * (offH * 3600 + offM * 60);
  } else if (*p != '\0') {
    return false;
  }
  if (*p != '\0') return false;
  if (month < 1 || month > 12 || day < 1 || day > 31 || hour > 23 || minute > 59 || second > 60) return false;

  const int64_t epoch = daysFromCivil(year, static_cast<unsigned>(month), static_cast<unsigned>(day)) * 86400 +
                        hour * 3600 + minute * 60 + second - offsetSeconds;
  if (epoch <= 0 || epoch > 0xFFFFFFFFLL) return false;
  epochOut = static_cast<uint32_t>(epoch);
  return true;
}

bool parseUsageJson(const char* json, const size_t length, ClaudeUsageSnapshot& out) {
  out = ClaudeUsageSnapshot{};
  if (!json || length == 0) return false;

  // Keep only the four windows we display; the endpoint also returns
  // extra-usage/billing objects we do not need to hold in DRAM.
  JsonDocument filter;
  for (const char* key : {"five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet"}) {
    filter[key]["utilization"] = true;
    filter[key]["resets_at"] = true;
  }

  JsonDocument doc;
  const DeserializationError error = deserializeJson(doc, json, length, DeserializationOption::Filter(filter));
  if (error) return false;

  readWindow(doc["five_hour"], out.session);
  readWindow(doc["seven_day"], out.weekly);
  readWindow(doc["seven_day_opus"], out.weeklyOpus);
  readWindow(doc["seven_day_sonnet"], out.weeklySonnet);
  return out.hasAny();
}

bool parseConfig(const char* text, const size_t length, ClaudeUsageConfig& out) {
  out = ClaudeUsageConfig{};
  if (!text || length == 0) return false;

  size_t start = 0;
  while (start < length && isspace(static_cast<unsigned char>(text[start]))) ++start;
  if (start == length) return false;

  if (text[start] != '{') {
    // Bare token file: the whole content (trimmed) is the token.
    char buffer[sizeof(out.token)];
    const size_t n = length - start < sizeof(buffer) - 1 ? length - start : sizeof(buffer) - 1;
    memcpy(buffer, text + start, n);
    buffer[n] = '\0';
    copyTrimmed(buffer, out.token, sizeof(out.token));
    return out.hasToken();
  }

  JsonDocument doc;
  if (deserializeJson(doc, text, length)) return false;
  copyTrimmed(doc["token"] | "", out.token, sizeof(out.token));
  copyTrimmed(doc["url"] | "", out.url, sizeof(out.url));
  return out.hasToken() || out.url[0] != '\0';
}

void formatDuration(const int64_t seconds, char* buffer, const size_t bufferSize) {
  if (!buffer || bufferSize == 0) return;
  if (seconds < 60) {
    snprintf(buffer, bufferSize, "<1m");
    return;
  }
  const int64_t minutes = seconds / 60;
  const int64_t hours = minutes / 60;
  const int64_t days = hours / 24;
  if (days > 0) {
    snprintf(buffer, bufferSize, "%dd %dh", static_cast<int>(days), static_cast<int>(hours % 24));
  } else if (hours > 0) {
    snprintf(buffer, bufferSize, "%dh %dm", static_cast<int>(hours), static_cast<int>(minutes % 60));
  } else {
    snprintf(buffer, bufferSize, "%dm", static_cast<int>(minutes));
  }
}

int fillPermille(const float utilization) {
  if (!(utilization > 0.0f)) return 0;  // also catches NaN
  if (utilization >= 100.0f) return 1000;
  return static_cast<int>(utilization * 10.0f + 0.5f);
}

}  // namespace claude_usage
