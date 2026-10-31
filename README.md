# Claude Usage for CrossMux

A [CrossMux](https://github.com/0x1abin/crossmux) app that shows your Claude
plan usage on the e-ink reader:

- **Current session**: the rolling 5-hour window. Shows the percent used, a bar,
  and "Resets in 2h 14m · 15:00".
- **This week**: the weekly limit across all models, with its reset date and time.
- **Week · Opus / Week · Sonnet**: smaller rows that appear only when your plan
  reports per-model weekly limits.

These are the same numbers Claude Code's `/usage` screen shows.

```
┌──────────────────────────────────┐
│          Claude Usage            │
├──────────────────────────────────┤
│ Current session              6%  │
│ [██░░░░░░░░░░░░░░░░░░░░░░░░░░░]  │
│ Resets in 2h 14m · 15:00         │
│                                  │
│ This week                   35%  │
│ [██████████░░░░░░░░░░░░░░░░░░░]  │
│ Resets in 3d 4h · 11-06 04:00    │
│                                  │
│ Week · Opus      [░░░░░░░░]  0%  │
│                                  │
│          Updated 14:03           │
├──────────────────────────────────┤
│  Back   Refresh                  │
└──────────────────────────────────┘
```

Confirm refreshes. While the app is open it also refreshes on its own every 5
minutes. Back returns to Apps, and Wi-Fi is turned off again if the app turned
it on.

## What's in this repo

| Path | What it is |
|---|---|
| `patches/0001-Add-Claude-Usage-app.patch` | The complete change against CrossMux `main` (`6b5566c`). Apply it with `git am`. |
| `crossmux/` | The same change as plain files, laid out in CrossMux's tree, for browsing or copying by hand. |
| `relay/claude_usage_relay.py` | Optional LAN relay that runs on your computer (Python stdlib only). |
| `sd/claude-usage.example.json` | Example `/claude-usage.json` for the SD card. |

## 1. Build and flash the firmware

```bash
git clone --recursive https://github.com/0x1abin/crossmux
cd crossmux
git am /path/to/fantastic-octo-winner/patches/0001-Add-Claude-Usage-app.patch
pio run -e default -t upload        # X3/X4. Pick your board's env from platformio.ini
```

The app shows up in **Apps** as "Claude Usage" and is visible by default. You can
hide it in Settings → App Visibility.

## 2. Give it a token (`/claude-usage.json` on the SD card)

### Option A: relay (recommended)

Run this on the computer where you use Claude Code:

```bash
python3 relay/claude_usage_relay.py --check   # one-off test: prints your usage JSON
python3 relay/claude_usage_relay.py           # serve it on your LAN, port 8787
```

The relay reads Claude Code's own login (`~/.claude/.credentials.json`, or the
macOS Keychain). Claude Code keeps that login refreshed, so it never goes stale
the way a copied token does. On startup the relay prints the file to save on the
SD card:

```json
{ "url": "http://192.168.1.20:8787/usage", "token": "<random relay key>" }
```

The reader only ever sees that random relay key, never your Claude credentials.
If you haven't used Claude Code for a while and its access token has expired,
run any `claude` command and Claude Code will refresh it.

### Option B: direct, no computer needed

```json
{ "token": "sk-ant-oat01-..." }
```

With no `url`, the reader calls `https://api.anthropic.com/api/oauth/usage`
itself. The catch is the token:

- `accessToken` from `~/.claude/.credentials.json` works, but it expires within
  hours.
- A long-lived token from `claude setup-token` is worth trying. It may not have
  the scope this endpoint needs. If the app shows **Token rejected**, switch to
  the relay.

> The usage endpoint is the undocumented one Claude Code itself uses, so
> Anthropic may change it without notice. The token in `/claude-usage.json` is a
> credential. Anyone holding the SD card can read it, which is another reason to
> prefer the relay key.

## Error screens

| Message | Meaning |
|---|---|
| No Claude token found | `/claude-usage.json` is missing or empty. Add it, then press Retry. |
| Token rejected | HTTP 401/403. The token expired, has the wrong scope, or the relay key is wrong. |
| Server returned an error · HTTP 503 | The relay can't read Claude Code's login. Run `relay … --check` on the computer to see why. |
| Could not reach the server | DNS, TLS or connection failure. Check the relay URL and that both devices are on the same network. |
| Not enough memory for HTTPS | Too little free heap for TLS. Open the app straight after a reboot. |

If a refresh fails after a successful load, the last numbers stay on screen and
the error replaces the "Updated" footer.

## Testing done

- Host unit tests for the parser: ISO-8601 timestamps with offsets and fractions,
  `null` windows, integer vs float percentages, bare-token config, duration
  formatting, and bar clamping.
- The patch applies cleanly to CrossMux `main` (`6b5566c`). A full firmware build
  was still running when this was committed. The result will follow in a later commit.
- Relay smoke test: wrong key gives 401, a missing Claude login gives 503 with a
  reason, and an unknown path gives 404.
- **Not yet tested on a physical reader or against a live Claude account.**
  The first real run on your device is the end-to-end check.
