#pragma once

#include <cstddef>
#include <cstdint>

// Pure data + parsing for the Claude Usage app. No Arduino, storage or
// network dependencies, so it compiles in host tests.
//
// The usage document is the JSON returned by Anthropic's OAuth usage endpoint
// (the same numbers Claude Code's /usage screen shows):
//
//   {
//     "five_hour":        {"utilization": 6.0,  "resets_at": "2026-11-01T04:59:59.94+00:00"},
//     "seven_day":        {"utilization": 35.0, "resets_at": "2026-11-06T03:59:59.94+00:00"},
//     "seven_day_opus":   {"utilization": 0.0,  "resets_at": null},
//     "seven_day_sonnet": null,
//     ...
//   }
//
// A relay that forwards this document unchanged is accepted as well.

struct ClaudeUsageWindow {
  bool present = false;      // object existed and carried a utilization value
  float utilization = 0.0f;  // percent of the limit used, 0..100 (may exceed 100)
  uint32_t resetsAt = 0;     // UTC epoch seconds, 0 when unknown
};

struct ClaudeUsageSnapshot {
  ClaudeUsageWindow session;       // "five_hour": the current rolling session window
  ClaudeUsageWindow weekly;        // "seven_day": weekly limit, all models
  ClaudeUsageWindow weeklyOpus;    // "seven_day_opus" (optional)
  ClaudeUsageWindow weeklySonnet;  // "seven_day_sonnet" (optional)
  bool hasAny() const { return session.present || weekly.present; }
};

struct ClaudeUsageConfig {
  // Bearer token. For the Anthropic endpoint this is a Claude OAuth access
  // token (sk-ant-oat01-...); for a relay it is whatever key the relay expects.
  char token[512] = {0};
  // Endpoint URL; empty means the Anthropic endpoint.
  char url[256] = {0};
  bool hasToken() const { return token[0] != '\0'; }
};

namespace claude_usage {

inline constexpr const char* kDefaultUrl = "https://api.anthropic.com/api/oauth/usage";
inline constexpr const char* kBetaHeader = "anthropic-beta";
inline constexpr const char* kBetaValue = "oauth-2025-04-20";

// Parse an ISO-8601 timestamp such as "2026-11-01T04:59:59.943648+00:00" or
// "2026-11-01T04:59:59Z" into UTC epoch seconds. Returns false when malformed.
bool parseIso8601(const char* text, uint32_t& epochOut);

// Parse the usage JSON document. Returns false when it is not JSON or has
// neither a session nor a weekly window.
bool parseUsageJson(const char* json, size_t length, ClaudeUsageSnapshot& out);

// Parse the SD config file. Accepts {"token": "...", "url": "..."}; a file
// containing only a bare token (no JSON) is accepted too. Whitespace trimmed.
bool parseConfig(const char* text, size_t length, ClaudeUsageConfig& out);

// "2h 14m", "3d 4h", "12m", "<1m". `seconds` <= 0 yields "<1m".
void formatDuration(int64_t seconds, char* buffer, size_t bufferSize);

// Clamp a utilization percentage to a 0..1000 permille fill for bars.
int fillPermille(float utilization);

}  // namespace claude_usage
