# Claude Usage

Shows your Claude plan usage: the current 5-hour session and the weekly limit.
These are the same numbers Claude Code's `/usage` screen shows. Each one is drawn
as a percentage with a bar and a "Resets in 2h 14m · 15:00" line. If your plan
reports separate weekly Opus or Sonnet limits, they appear as smaller rows.

| Button  | Action                                       |
|---------|----------------------------------------------|
| Back    | Return to Apps                               |
| Confirm | Refresh now (Retry when no token is set up)  |

While the app is open and online it also refreshes on its own every 5 minutes.
Wi-Fi comes up through the shared picker when you open the app. If the app
started Wi-Fi, it turns it off again when you leave.

## Configuration: `/claude-usage.json` on the SD card

```json
{ "token": "<bearer token>", "url": "<optional endpoint>" }
```

A file that holds only a bare token, with no JSON, works too.

There are two ways to set it up:

1. **Relay (recommended).** Run `claude_usage_relay.py` on the computer where you
   use Claude Code. It reads Claude Code's own login, which Claude Code keeps
   refreshed, and serves the usage JSON on your LAN behind a random key. The
   relay prints the exact file to copy:
   `{"url": "http://192.168.1.20:8787/usage", "token": "<relay key>"}`.
   The device never holds your Claude credentials.
2. **Direct.** Leave out `url` and set `token` to a Claude OAuth access token
   (`sk-ant-oat01-…`). The device then calls
   `https://api.anthropic.com/api/oauth/usage` itself. Access tokens copied from
   `~/.claude/.credentials.json` expire within hours. A long-lived
   `claude setup-token` token is the thing to try, but it may lack the scope
   this endpoint needs. If the app says "Token rejected", use the relay.

The endpoint is the undocumented one Claude Code uses. Anthropic may change it
without notice.

## Resources

- Heap: one response `std::string` (capped at 8 KB, about 600 B in practice) and a
  filtered `JsonDocument`, both freed when `doFetch()` returns. The config is a
  fixed ~770 B member of the Activity, and the token is zeroed in `onExit()`.
- TLS goes through `HttpDownloader` (wolfSSL), gated by
  `HttpDownloader::hasMemoryForTls()`.
- No SD writes.
