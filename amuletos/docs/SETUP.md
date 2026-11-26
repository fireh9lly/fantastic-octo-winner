# amuletOS setup guide

Two parts: installing amuletOS on the AP30, then setting up the SD card so Playlists, Blockz music and Games
find your files.

## Part 1: Install

### What you need

- The AP30, charged (at least half; see the warning below).
- A computer with a USB cable for the AP30.
- The official AP30 firmware **V1.7.8** from the [Hidizs download center](https://hidizs.net/pages/download-center).
  Unzip it if it comes as a .zip: you want the file `HIFIYF18.IMG` (about 28 MB).
- The amuletOS patcher from the [latest release](https://github.com/dharma-dingo/amuletOS/releases/latest):
  `amuletOS-0.3-patcher.html` (any browser) or `amuletos_patch.py` (Python 3.8+).

### Steps

1. **Make the amuletOS file.** Open `amuletOS-0.3-patcher.html` in your browser (double-click it; it works
   offline). Keep "Install amuletOS 0.3" selected, choose the official `HIFIYF18.IMG`, then press
   "Save HIFIYF18.IMG". If the page says the file isn't the official V1.7.8, download it again from Hidizs.
   With Python instead: `python amuletos_patch.py HIFIYF18.IMG` writes `amuletOS-0.3/HIFIYF18.IMG`.
2. **Connect the AP30.** Turn it on normally, then plug it into the computer. The player switches to its USB
   transfer screen and the computer shows its storage. **No button combination is needed.** If the player asks
   how to connect, pick file transfer (storage), not USB DAC. Don't press B on the transfer screen: that ends
   the connection.
3. **Copy the file.** The computer shows up to two drives: the AP30's **internal storage** (small, about
   220 MB) and the SD card (if one is inserted). Copy the new `HIFIYF18.IMG` to the **top level of the internal
   storage**, not into a folder and not onto the SD card. Keep the name exactly `HIFIYF18.IMG`.
4. **Eject and unplug.** Eject the drive in your computer (Windows: Safely Remove; macOS: Eject), then unplug
   the cable.
5. **Let it install.** The player installs the update and restarts. The screen can stay dark or show an
   updating screen for a minute or two; don't turn it off. When it's done the file is gone from the internal
   storage and the amuletOS boot screen shows **v0.3**.

Your settings carry over. If you changed the music on the card since the last start, the library rebuilds once.

### If it doesn't install

- **Low battery:** with a low battery the updater can swallow the file without installing anything. Charge the
  player and copy the file again.
- **Wrong place or name:** the file must be `HIFIYF18.IMG` at the top level of the internal storage.
- **Older than what's installed:** the AP30 only installs a file stamped newer than its current firmware. The
  patcher's output is always newer than the official V1.7.8. If you already ran a newer amuletOS build, install
  that or a later release instead.

### About the button combination (loader mode)

Holding a d-pad corner (diagonal) with A and B while plugging in puts the AP30 into **loader mode**: a black
screen and an unknown USB device on the computer. Installing amuletOS never needs it. It is only for recovering a
player that no longer starts, by writing a firmware image directly with developer tools and a USB driver; see
"Loader mode" in [HANDOFF.md](HANDOFF.md). If you got into it by accident, hold the power button about 10 seconds,
unplug, and start the player normally.

### Going back to the official firmware

In the patcher choose "Go back to the official firmware" with your official `HIFIYF18.IMG` (or run
`python amuletos_patch.py --stock HIFIYF18.IMG`), then copy the result the same way as in steps 2 to 5. This is
needed because the AP30 won't take the official file as it is (its stamp is older than amuletOS's). Afterwards,
going back to amuletOS needs a later amuletOS release than v0.3.

## Part 2: Set up the SD card

### The card

- **Format: exFAT.** Playlists and Games read the card themselves and need exFAT. Cards of 64 GB and more come
  formatted that way; a 32 GB or smaller card is usually FAT32 and needs reformatting (back it up first). Music
  playback and Blockz music also work on FAT32.
- The player's library covers the first 256 GB of a card.

### Where things go

Folder names don't care about upper or lower case.

```
SD card
├── Artist/                     your music, organised however you like (see below)
│   └── Album/
│       ├── 01 - Song.flac
│       └── cover.jpg
├── _Playlists/                 playlists (Music → Playlists)
│   ├── Morning Run.m3u8
│   └── Road Trip.m3u
├── _blockgame/                 Blockz background music
│   └── any audio files
└── _gb/                        Game Boy games (Games → Emu)
    ├── Some Game.gb
    └── Another Game.gb
```

### Music

- Anywhere on the card, in any folders. Artist / Album folders with tagged files work best: Music → Artist,
  Album and Genre come from the tags; the Library card browses folders.
- Now Playing shows the title, artist and album tags, and the file name when a file has no title tag.
- After adding music, the library updates on the next start. Music → **Update** rebuilds it straight away.

### Playlists: `/_Playlists/`

- `.m3u` or `.m3u8` files (plain or extended M3U, UTF-8). The file name is the playlist's name in the list.
- One track per line. Paths can be relative to the playlist ("../Artist/Album/01 - Song.flac") or start at the
  card's root ("/Artist/Album/01 - Song.flac"); `/` and `\` both work. Lines starting with `#` are ignored.
- Up to **24 playlists** are listed, and the player keeps the **first 24 tracks** of each.
- Open Music → Playlists and press A on one: it starts from the first track, and Next / Previous follow the
  playlist.

### Blockz music: `/_blockgame/`

- If nothing is playing when you open Blockz, it shuffles the audio files in `/_blockgame/` (up to 24) until you
  leave the game. MP3 is the safest choice.
- If music is already playing, Blockz keeps it going instead.
- The MUSIC box in the game shows what it's doing ("NO DIR" means the folder is missing, "EMPTY" means it holds
  no audio files).

### Game Boy games: `/_gb/` (experimental)

- Original Game Boy games as `.gb` files, up to 2 MB each, up to **24** listed. They appear under Games → Emu.
- Games made only for the Game Boy Color are shown greyed out and don't start (some colourised `.gb` hacks are
  Color-only too).
- Controls: the d-pad and A / B / Start / Select as on a Game Boy, the volume wheel for volume. **Hold Select**
  for 1.5 seconds to quit.
- No saves yet: progress is lost when you quit.
- Use only games you own the right to play.
