# Changelog

## v0.3 (2026-11-22): first public release

Built on the official Hidizs AP30 firmware V1.7.8 (installed with the patcher; stamp 2026-11-07, build 60).

- **Look:** Pocket-style interface (white screens, ink lines, colour accents, a faint dot grid), a new UI font,
  restyled menus, lists, volume, USB, charging and status screens. Boot screen shows the version.
- **Main menu:** one level with five cards (Now Playing, Music, Blockz, Games, Library), bigger cards and page
  dots. Left / Right move and wrap, Start opens Settings, a fresh boot starts on Music, and Now Playing is greyed
  out and does nothing while no music is loaded.
- **Now Playing:** new screen: double-size title that scrolls when long (file name when there is no title tag),
  artist and album wrapping on the right, cover art, progress bar, elapsed / remaining time, track n of total.
  B returns to the main menu.
- **Music menu:** Playlists (M3U from `/_Playlists/`), Favorites, and Update (rebuilds the library on demand).
  Directory List removed (the Library card browses folders).
- **Library:** the scan is skipped at boot when the card hasn't changed.
- **Settings** survive firmware updates; the menus always come up in English.
- **Blockz:** new block game replacing the stock one: hard drop, ghost piece, hold on the volume wheel, own
  background music from `/_blockgame/` when nothing is playing.
- **Games (experimental):** Game Boy emulator (Peanut-GB with minigb_apu sound) for `.gb` files in `/_gb/`:
  full-screen picture with a DMG LCD look, volume wheel in game, hold Select to quit. ROMs are paged from the card
  so games up to 2 MB run. No saves, no Game Boy Color. The Games screen also lists the 13 built-in games still in
  the firmware; Settings → Game opens the same screen.
- **USB name:** the player shows up as "AMULETOS AP30 0.3".
- **Install:** browser and Python patchers that apply amuletOS to the official V1.7.8 file (no Hidizs firmware in
  the download), with SHA-256 checks on input and output, and a way back to the official firmware.
