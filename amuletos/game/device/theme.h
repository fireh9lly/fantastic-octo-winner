/* UI colours drawn by amuletOS's own code (Now Playing npui.c, Playlists playlists.c, Games gbprobe.c), 0xRRGGBB.
 * The images come from art/orange.py and must match: same values there (THEME).
 *
 * Owner's orange theme on black (2026-11-27), from their dark theme (header orange, brown rules and selection,
 * white text) with the bright orange accent of their orange theme. A test-build look: the real theme design
 * comes later (PLAN.md, themes). amuletOS's Pocket values are in git history (before this file). */
#ifndef THEME_H
#define THEME_H

#define TH_BG       0x000000   /* screen and list rows */
#define TH_PANEL    0x141414   /* framed panels (Now Playing) */
#define TH_BAND     0xd66000   /* status band */
#define TH_RULE     0x943e00   /* rules under the band and the header, footer band */
#define TH_HEAD     0x632900   /* list header row */
#define TH_TEXT     0xffffff
#define TH_DIM      0x9a9a9a
#define TH_ACCENT   0xff8200   /* artist, progress bar, selection edge, list icons */
#define TH_TRACK    0x3a3a3a   /* progress bar track */
#define TH_ROWLINE  0x292929   /* list row separators */
#define TH_SEL      0x943e00   /* selected list row */

#define TH565(h) ((uint16_t)((((h) >> 19) & 0x1F) << 11 | (((h) >> 10) & 0x3F) << 5 | (((h) >> 3) & 0x1F)))

#endif
