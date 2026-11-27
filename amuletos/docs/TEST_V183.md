# On-device test: first V1.8.3 build (amuletOS v0.3 features, orange theme, USB DAC fix)

The first image of this fork to run on a player. Everything below has only been checked on the PC: the build packs and
verifies, the code was reviewed against both firmware versions and the PC tests pass. Work through it in order and
note anything odd, with a photo where it helps. Stop at the first crash or freeze and say what you did just before.

**Build:** `./build.sh ~/Downloads/HIFIYF23.IMG BUILD_DIR 2620271114000000` (official V1.8.3, SHA-256 `79d186f5…`),
stamp 27 Nov build 14: the build number must beat the installed one's (13), it counts before the date.

## Before flashing

- [ ] Keep a way back: loader mode (D-pad corner + A + B while plugging in USB) and `tools/rkwrite.py` restore have
      worked before. To go back with a normal update instead, ask for a re-stamped image (stock, or the orange theme
      with the DAC fix): the player only installs a newer stamp than the one it has.
- [ ] Charge the player.

## Install and boot

- [ ] Copy `HIFIYF23.IMG` to the player's root over File transfer, update as usual; it restarts.
- [ ] Boot: Hidizs logo in orange on black, then the main menu (Music card).
- [ ] Settings kept from before (volume, gain, filter, sleep timer...); menus in English.
- [ ] The first boot may rebuild the library once (the fingerprint store is new). Let it finish.

## Main menu (carousel)

- [ ] Left / Right go through Now Playing, Music, Blockz, Games, Library and wrap around.
- [ ] Now Playing is greyed out until something has played, then normal.
- [ ] A opens each card; B / Menu come back. Start opens Settings.
- [ ] Status band: battery, volume and other icons readable on the orange band.

## Music and Now Playing

- [ ] Music menu: Now playing, All Music, Artist, Album, Genre, Favorites, Playlists, Update. Text readable.
- [ ] Play a track: Now Playing shows the cover (or the note placeholder), artist in orange, album, the big title
      (scrolls when long), elapsed / remaining time, track n / total, progress bar.
- [ ] Next / Previous / seek; pause and play; volume wheel (the volume pop-up is the stock dial in orange).
- [ ] B from Now Playing goes to the main menu.
- [ ] An album of FLAC files plays without gaps between tracks (V1.8.3's gapless).
- [ ] Music keeps playing while you browse menus.

## Library scan skip

- [ ] Power off and on again with the card unchanged: no "Updating Library" this time.
- [ ] Music → Update: the library rebuilds.
- [ ] Add or delete a file over USB, unplug: the library rebuilds.

## Playlists

- [ ] Music → Playlists lists the `.m3u` / `.m3u8` files in `/_Playlists/`.
- [ ] Open one: it plays; Next / Previous stay in the playlist; shuffle mode picks other entries.

## Blockz and Games

- [ ] Blockz starts, plays, keeps the music going; quitting returns to the menu.
- [ ] Games lists `.gb` files from `/_gb/` and the built-in games; a Game Boy game runs with sound; hold Select to
      quit. A built-in game starts and returns to Games.
- [ ] Settings → Game opens the Games screen.

## USB

- [ ] File transfer on the laptop: the disk is called AMULETOS; copying works.
- [ ] **DAC on the phone**: pick DAC, the phone finds the DAC within a second or so, and sound plays.
- [ ] Pull the cable out in DAC mode, plug in again, DAC again: still works. Then File transfer still works.
- [ ] DAC on the laptop.

## Stock screens (text on black)

The stock lists and settings draw their text in light colours now (the dark theme's text patches). Look for any
text that is dark on dark, or hard to read:
- [ ] Library card (folder browser), Settings pages, Bluetooth if you can reach it, sleep timer, date and time.
- [ ] Pop-ups: delete / confirm dialogs, low battery, "Updating Library", "Charging".
- [ ] Known risk inherited from v0.3: a Settings path that would open stock's old radio / recording screen (task 5)
      lands in amuletOS's Now Playing code instead. If any Settings item leads to a blank screen or a crash, note
      which one.

## Power

- [ ] Power off (Goodbye in orange) and on; charging screen while plugged into a charger.

## Not in this build (on purpose)

The D-pad home menu, visualiser, new themes and icons, Peak, wheel-click play/pause, better fonts: later steps.
The menu icons and the stock font are stand-ins until we design those together.
