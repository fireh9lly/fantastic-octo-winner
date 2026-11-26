#!/usr/bin/env python3
"""Apply named byte patches to an unpacked code.bin, checking the original bytes first.

  patch_code.py SRC_DIR OUT_DIR PATCH[,PATCH...]

Copies SRC_DIR (an unpacked image) to OUT_DIR and patches OUT_DIR/code.bin.
Each patch entry: (module, run address, original bytes hex or None, new bytes hex).
"""
import json, os, shutil, struct, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARM = r"C:\Users\Admin\tools\arm-gnu-toolchain\arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi\bin"
BASE = 0x03050000
NOP2 = "00bf00bf"          # two Thumb NOPs, replaces one 4-byte BL

PATCHES = {
    # Settings survive a firmware install (build 38): after an update module 1's boot config load (0x03082090) saw
    # the "FWUP" marker, cleared it and went to the CRC check without reading the saved block 0, so every setting
    # (language, library fingerprint...) fell back to its default. Now the update path reads block 0 like a normal
    # boot; a bad CRC still gives the defaults.
    "keep_settings": [(1, 0x030821B4, "cae7", "c4e7")],          # b 0x0308214C -> b 0x03082140 (block read)
    # Always start in English (build 39): the boot config load takes the language from the saved block's +0x10
    # (0x03082306, then checked against the enabled-language list). amuletOS art has English baked in, so any other
    # language only mixes scripts; and a reset (install before build 38, Settings reset) no longer leaves the owner
    # hunting through Chinese menus. ldrb.w r0, [sp, #0x40] -> movs r0, #2 (English); nop.
    "english": [(1, 0x03082306, "9df84000", "022000bf")],
    # B in Now Playing goes to the main menu (build 40). Stock (m27 key handler): B press (0x40000040) ->
    # 0x030838B0: clear 0x115, popup checks (messages 1, 0x50 / 0x51), then by source: Folders (0x63) / 6 -> folder
    # browser, else the Music list. Owner: always the main menu. After the popup checks, jump to the Menu key's own
    # path (0x0308389C: TaskSwitch(10, {1}) = main menu; the carousel keeps its own position).
    "np_back_home": [(27, 0x030838E2, "2b4c", "bfe0")],   # ldr r4, =record -> b 0x03083A64 (= hold B: TaskSwitch(0, {0}), main menu).
    # Build 40 branched to 0x0308389C = Select's TaskSwitch(10): the playback options screen (owner on 49: B opened
    # options, B there came back, B opened them again; hold B, event 0x20000040, was the only way out).
    # Stock Now Playing (module 27). Info box: line 1 artist (0x15e), line 2 album (0x25c),
    # line 3 genre (0x35a), each drawn by text 0x03063F76 with a fallback 0x030644A0 when empty.
    # Owner: show only artist and song title. Skip the album and genre draws (areas stay cleared).
    "np_hide_album_genre": [
        (27, 0x03082A78, "e1f77dfa", NOP2),   # line 2 album text
        (27, 0x03082AF2, "e1f7d5fc", NOP2),   # line 2 empty fallback
        (27, 0x03082AC6, "e1f756fa", NOP2),   # line 3 genre text
        (27, 0x03082B04, "e1f7ccfc", NOP2),   # line 3 empty fallback
    ],
    # Build 18 tried this; 0x03048450 turned out to be the file name, not the title. Superseded by np_title_tag.
    "np_title_not_filename": [
        (27, 0x03083550, "fc480203", "50840403"),   # literal pool word 0x030248FC -> 0x03048450
    ],
    # Format line ("16bit 44.1KHz 320Kbps") at (145, 60): skip its background strip and its text.
    "np_hide_format": [
        (27, 0x0308296E, "e2f7d7f9", NOP2),   # image 69 strip at (145, 60)
        (27, 0x03082996, "e1f7eefa", NOP2),   # format text
    ],
    # Main menu (module 21) Games tile (index 1, handler 0x03081960): TaskSwitch(0xA, &7) opened the game
    # list (task 10 page 7). Open task 15 (module 82 = Blockz) directly, no argument.
    "menu_games_to_blockz": [
        (21, 0x03081966, "6946", "0021"),     # mov r1, sp -> movs r1, #0
        (21, 0x03081968, "0a20", "0f20"),     # movs r0, #0xa -> movs r0, #0xf
    ],
    # Build 55: the stock games still in the firmware quit with TaskSwitch(10, &7), the stock game list, which also
    # lists the games whose modules we reuse (opening one of those would crash). They come back to task 20, the
    # Games screen (game/device/gbprobe.c), instead: movs r0, #0xa -> movs r0, #0x14 before each exit call.
    "games_back": [(m, a, "0a20", "1420") for m, a in (
        (81, 0x03081E6E), (83, 0x030820B8), (84, 0x03082146), (85, 0x030834FC), (101, 0x0308229E),
        (102, 0x03082054), (103, 0x03082748), (104, 0x03083A06), (105, 0x03082484), (106, 0x030827BA),
        (107, 0x03082398), (108, 0x03083F72), (109, 0x03082668), (109, 0x03083FA4))],
}

# ---- patches built from assembly ----
HOOK_AT, HOOK_END = 0x03082A30, 0x03082ACA   # module 27 dead code once np_hide_album_genre is applied

def thumb_bl(src, dst):
    off = dst - (src + 4)
    assert -(1 << 24) <= off < (1 << 24) and not off & 1
    s = (off >> 24) & 1; i1 = (off >> 23) & 1; i2 = (off >> 22) & 1
    imm10 = (off >> 12) & 0x3FF; imm11 = (off >> 1) & 0x7FF
    j1 = (~i1 ^ s) & 1; j2 = (~i2 ^ s) & 1
    return struct.pack("<HH", 0xF000 | (s << 10) | imm10, 0xD000 | (j1 << 13) | (j2 << 11) | imm11)

def thumb_bw(src, dst):
    """B.W (T4): same layout as BL with bit 14 of the second halfword clear"""
    hi, lo = struct.unpack("<HH", thumb_bl(src, dst))
    return struct.pack("<HH", hi, lo & ~0x4000)

def thumb_b16(src, dst):
    off = dst - (src + 4)
    assert -2048 <= off < 2048 and not off & 1
    return struct.pack("<H", 0xE000 | ((off >> 1) & 0x7FF))

def assemble(src, addr):
    """assemble hooks/<src>.S linked at addr; returns (bytes, symbols)."""
    with tempfile.TemporaryDirectory() as t:
        o, e, b = (os.path.join(t, n) for n in ("h.o", "h.elf", "h.bin"))
        for cmd in ([os.path.join(ARM, "arm-none-eabi-as.exe"), "-mcpu=cortex-m3", "-mthumb", "-o", o,
                     os.path.join(ROOT, "hooks", src + ".S")],
                    [os.path.join(ARM, "arm-none-eabi-ld.exe"), "-Ttext=" + hex(addr), "-o", e, o],
                    [os.path.join(ARM, "arm-none-eabi-objcopy.exe"), "-O", "binary", "-j", ".text", e, b]):
            subprocess.run(cmd, check=True)
        nm = subprocess.run([os.path.join(ARM, "arm-none-eabi-nm.exe"), e], capture_output=True, text=True).stdout
        syms = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines()) if len(f) == 3}
        return open(b, "rb").read(), syms

def np_title_tag():
    """Scrolling line shows the title tag, else the file name (hooks/np_title.S). Needs np_hide_album_genre."""
    code, sym = assemble("np_title", HOOK_AT)
    assert HOOK_AT + len(code) <= HOOK_END, f"hook is {len(code)} B, room for {HOOK_END - HOOK_AT}"
    nop = bytes.fromhex("00bf")
    return [
        (27, 0x03082A2E, "0020", thumb_b16(0x03082A2E, 0x03082ACA).hex()),   # after line 1: straight to the epilogue
        (27, HOOK_AT, None, code.hex()),                                       # helpers in the now-dead code
        (27, 0x0308349A, "2e48e0f759fc", (thumb_bl(0x0308349A, sym["np_fill_strlen"]) + nop).hex()),
        (27, 0x03083466, "02a9a8f800400223384a0846e0f780fd", (thumb_bl(0x03083466, sym["np_fill_draw"]) + nop * 6).hex()),
        (27, 0x03083554, "50840403", "e0850403"),                              # mode-0 literal 0x03048450 -> title
    ]

SRC_DIR = None   # set by main: generated patches may read SRC_DIR/helpers.json (tools/build_helpers.py)

def syms():
    """slot-2 helpers (helpers.json) plus the screen module extensions (e21.json, e22.json; tools/extend_module.py)"""
    h = {}
    for f in ("helpers.json", "e21.json", "e22.json"):
        p = os.path.join(SRC_DIR, f)
        if os.path.exists(p): h.update(json.load(open(p)))
    return h

def np_v2():
    """Now Playing with the slot-2 helpers (game/device/np_helpers.c): artist wraps onto line 2,
    album moves to line 3 (genre gone), scrolling line shows the title with file-name fallback.
    Retired: its helpers were removed from slot 2 in build 33 (restore them from git e86d06a to use this)."""
    h = json.load(open(os.path.join(SRC_DIR, "helpers.json")))
    assert "np_artist" in h, "np_v2/np_v3 need the v0.2 slot-2 helpers (removed in build 33; see git e86d06a)"
    nop = bytes.fromhex("00bf")
    return [
        (27, 0x03082A2A, "e1f7a4fa", thumb_bl(0x03082A2A, h["np_artist"]).hex()),          # line 1: artist, 2 lines
        (27, 0x03082A2E, "0020", thumb_b16(0x03082A2E, 0x03082A7C).hex()),                  # skip line 2 code
        (27, 0x03082A90, "b1f85a13", "b1f85c12"),                                           # line 3 source: genre -> album
        (27, 0x0308349A, "2e48e0f759fc", (thumb_bl(0x0308349A, h["np_title_width"]) + nop).hex()),
        (27, 0x03083466, "02a9a8f800400223384a0846e0f780fd", (thumb_bl(0x03083466, h["np_title_draw"]) + nop * 6).hex()),
        (27, 0x03083554, "50840403", "e0850403"),                                           # mode-0 literal -> title
    ]

def np_v3():
    """np_v2 plus: artist at y 49 and album at y 91, both wrapping over two lines (np_helpers.c LIFT);
    empty-string fallbacks skipped (they would draw at the old line positions)."""
    h = json.load(open(os.path.join(SRC_DIR, "helpers.json")))
    return np_v2() + [
        (27, 0x03082AC6, "e1f756fa", thumb_bl(0x03082AC6, h["np_album"]).hex()),           # line 3 draw -> album helper
        (27, 0x03082AE0, "e1f7defc", thumb_bl(0x03082AE0, h["np_clear_artist"]).hex()),    # line 1 empty: clear lifted lines
        (27, 0x03082B04, "e1f7ccfc", NOP2),                                                 # line 3 empty fallback
    ]

def lib_skip():
    """Library scan skip (game/device/libscan.c): module 5 builds only when the SD card's fingerprint changed;
    stock's config save appends the fingerprint; Folders "Update Library?" Yes always rebuilds."""
    h = json.load(open(os.path.join(SRC_DIR, "helpers.json")))
    nop = bytes.fromhex("00bf")
    return [
        # m5 service: strh r4,[r5,#0x42]; strb r4,[r5,#0x64]; bl Build; movw r0,#0x18d; bl Post -> bl lib_gate
        (5, 0x03081754, "a5f8424085f86440fff764ff40f28d10e6f7b6fb",
         (thumb_bl(0x03081754, h["lib_gate"]) + nop * 8).hex()),
        (0, 0x0306D5C0, "fff79eff", thumb_bl(0x0306D5C0, h["cfg_write"]).hex()),     # SaveSysConfig block write
        (31, 0x0308219E, "a5f84290", thumb_bl(0x0308219E, h["lib_force"]).hex()),   # strh sb,[r5,#0x42]
        (1, 0x030827EA, "eaf789fe", thumb_bl(0x030827EA, h["cfg_boot_write"]).hex()),  # boot config rewrite
    ]

def np_v4():
    """v0.3 Now Playing layout A (game/device/npui.c in slot 28, loaded by np_load in slot 2): artist (2 lines) and
    album (3 lines) in the right panel, double-size scrolling title, m:ss / -m:ss times, n/total counter, own
    progress bar. Use instead of np_v2/np_v3 (needs helpers.json and npui.json in SRC_DIR)."""
    h = json.load(open(os.path.join(SRC_DIR, "helpers.json")))
    u = json.load(open(os.path.join(SRC_DIR, "npui.json")))
    nop = bytes.fromhex("00bf")
    def region(at, end, fn, back):          # bl fn; b.w back; NOP to the end of the replaced region
        code = thumb_bl(at, u[fn]) + thumb_bw(at + 4, back)
        return (code + nop * ((end - at - len(code)) // 2)).hex()
    return [
        (27, 0x03081654, "e6f746bf", thumb_bw(0x03081654, h["np_load"]).hex()),           # init tail: load slot 28
        (27, 0x03082A2A, "e1f7a4fa", thumb_bl(0x03082A2A, u["np_artist"]).hex()),         # info box line 1: artist
        (27, 0x03082A2E, "0020", thumb_b16(0x03082A2E, 0x03082A7C).hex()),                 # skip line 2 code
        (27, 0x03082A90, "b1f85a13", "b1f85c12"),                                          # line 3 source: album
        (27, 0x03082AC6, "e1f756fa", thumb_bl(0x03082AC6, u["np_album"]).hex()),          # line 3 draw: album
        (27, 0x03082AE0, "e1f7defc", thumb_bl(0x03082AE0, u["np_clear_artist"]).hex()),   # line 1 empty: clear
        (27, 0x030829B2, "e1f79bff", thumb_bl(0x030829B2, u["np_clear_info"]).hex()),     # stock line clears ran
        (27, 0x030829BC, "e1f796ff", NOP2),                                                # past the panel border
        (27, 0x030829C6, "e1f791ff", NOP2),                                                # (build 34)
        (27, 0x03082B04, "e1f7ccfc", NOP2),                                                # line 3 empty fallback
        (27, 0x0308344C, "adf80840adf80c90adf80a50adf80e60ac2200211c20e1f75dfc02a9a8f800400223384a0846e0f780fd3fe0",
         region(0x0308344C, 0x03083478, "np_title_new", 0x030834F8)),                     # title line, mode 1
        (27, 0x03083478, "adf80840adf80c90adf80a50adf80e6008a91c20e1f71ff9ac2200211c20e1f743fc2e48e0f759fcbdf8201088421ad9bdf80890294d4ff01e0c69f30f01bdf80a90cde9005c352664f30f0202a869f31f416bf31f4266f30f03e0f7d8fe4420e4f7fcfc02e04420e4f719fd02a9a8f800400223194a0846e0f741fd",
         region(0x03083478, 0x030834F4, "np_title_new", 0x030834F4)), # title line, mode 0
        (27, 0x0308350E, "e0f76dfe", thumb_bl(0x0308350E, u["np_title_step"]).hex()),     # scroller step
        (27, 0x03083114, "fff7f9fc", thumb_bl(0x03083114, u["np_time"]).hex()),           # position
        (27, 0x0308341E, "fff774fb", thumb_bl(0x0308341E, u["np_time"]).hex()),           # length
        (27, 0x0308316A, "e1f7d9fd", NOP2),                                                # counter clear image 0x38
        (27, 0x0308317A, "fff74efa", thumb_bl(0x0308317A, u["np_count"]).hex()),          # n/total
        (27, 0x03083208, "daf8440001283068",
         (thumb_bl(0x03083208, u["np_progress"]) + thumb_bw(0x0308320C, 0x030833DA)).hex()),  # progress bar
    ]

def menu_carousel():
    """v0.3 one-level main menu (module 21): items 0 Now Playing, 1 Music, 2 Blockz, 3 Games, 4 Library
    (art/pocket.py; Games added in build 54: stock's dead tile code 0x03081996 calls m21_ext.c menu_games, task 20);
    Left/Right wrap over five, Up/Down do nothing, Start opens Settings (Setup page), position kept in RAM by
    m21_ext.S. Use with menu_games_to_blockz (item 2 runs the old Games action, task 15)."""
    h = syms()
    T = 0x030818B4                                   # tbb table of the tile action routine 0x0308188E
    tb = lambda a: (a - T) // 2
    np_handler = (thumb_bl(0x030819D0, h["menu_np"])                  # Now Playing if the player runs; return 1
                  + bytes.fromhex("07b00120bde8f08300bf00bf00bf00bf"))
    return [
        (21, T, "035661718e84", bytes([tb(0x030819D0), tb(0x030818BA), tb(0x03081960), tb(0x03081996),
                                      tb(0x03081976), tb(0x030819BC)]).hex()),
        (21, 0x030819D0, "adf8001069460a20e6f77cfb07b00120bde8f083", np_handler.hex()),  # old item 4 -> Now Playing
        (21, 0x03081996, "6948017005208df80000adf8",                                     # old item 3 -> Games
         (thumb_bl(0x03081996, h["menu_games"]) + bytes.fromhex("07b00120bde8f083")).hex()),
        (21, 0x03081CF8, "b8f80000032808d2401c80b2a8f80000",                             # Right: +1 of 5
         (bytes.fromhex("0120") + thumb_bl(0x03081CFA, h["menu_step"]) + thumb_b16(0x03081CFE, 0x03081CD6)
          + bytes.fromhex("00bf") * 4).hex()),
        (21, 0x03081D24, "b8f80000032888bf401e08bf0520dad2002800e0",                     # Left: +4 of 5
         (bytes.fromhex("0420") + thumb_bl(0x03081D26, h["menu_step"]) + thumb_b16(0x03081D2A, 0x03081CD6)
          + bytes.fromhex("00bf") * 6).hex()),
        (21, 0x03081CDE, "b8f8", thumb_b16(0x03081CDE, 0x03081D74).hex()),               # Up/Down: nothing
        (21, 0x03081BA6, "4ff4bd70e6f793f9e849d9f80000d6f762f8",                         # Start: Settings page 4
         (bytes.fromhex("0420adf8000069460a20") + thumb_bl(0x03081BB0, 0x030680D4)
          + bytes.fromhex("0126") + thumb_b16(0x03081BB6, 0x03081D74)).hex()),
        (21, 0x030815D4, "21780180", thumb_bl(0x030815D4, h["menu_idx_init"]).hex()),    # init: our position
        (21, 0x03081B8A, "00f0f3b8", thumb_bw(0x03081B8A, h["menu_key_more"]).hex()),    # Start press -> Settings
    ]

def timing():
    """v0.4 timing log (build 57): player thread init (MusicInit) and Audio Start (module 33) branch to slot-2 stubs
    (game/device/timing.S) that log them and replay the replaced push. Module 0's sites are hooked at run time
    (m21_ext.c tlog_install)."""
    h = syms()
    return [
        (33, 0x0308DDD0, "2de9f043", thumb_bw(0x0308DDD0, h["t_music"]).hex()),
        (33, 0x0308C8EE, "2de9f04f", thumb_bw(0x0308C8EE, h["t_astart"]).hex()),
    ]

def music_update():
    """Music menu (module 22) gets an eighth item, "Update", running stock's index-8 library update, forced past
    the fingerprint check (libscan.c lib_force). The 8-entry table lives in slot 2 (np_stub.S music_menu)."""
    h = syms()
    t = struct.pack("<I", h["music_menu"]).hex()
    return [
        (22, 0x03081B28, "483b0203", t), (22, 0x03081F6C, "483b0203", t), (22, 0x03082174, "483b0203", t),
        (22, 0x0308165A, "072604462e70", "082604462e70"),          # 8 items (41..53: 9 with Games)
        (22, 0x030816EC, "0728ccbf2e712871", "0728c8bf07202871"),  # still 7 rows per page
        (22, 0x030818D8, "a7f84290", thumb_bl(0x030818D8, h["lib_force"]).hex()),
    ]

def playlists():
    """v0.3 M3U playlists (build 35): Music menu row "Playlists" (9th entry, action 0x50 -> task 19 = module 86,
    game/device/playlists.c) and the song-change hook (0x0305E930 -> np_helpers.c pl_step). Apply after
    music_update. Directory List was removed (build 37); build 41 adds a temporary ninth row, Games (the Game Boy
    probe, action 0x51 -> task 20)."""
    h = syms()
    return [
        (0, 0x0305E930, "2de9f84f", thumb_bw(0x0305E930, h["pl_step_hook"]).hex()),     # source step entry
        (22, 0x0308197E, "07b02846", thumb_bw(0x0308197E, h["pl_menu_exit"]).hex()),    # select routine exit
        # still 8 items: Playlists added, Directory List removed (owner, build 37)
        (22, 0x03081F54, "e2f7a4fa", thumb_bl(0x03081F54, h["m22_row_text"]).hex()),   # row text: icon + text
        (22, 0x03082034, "e2f734fa", thumb_bl(0x03082034, h["m22_row_text"]).hex()),   # (selection change)
        # player thread init (build 36): while a playlist is active skip stock's Folders count / seek, which use the
        # browser's stale folder state (build 35: endless Loading)
        (33, 0x0308DF12, "b7f8f200632805d0", (thumb_bw(0x0308DF12, h["pl_init_count"]) + bytes.fromhex("00bf00bf")).hex()),
        (33, 0x0308DFB8, "b7f8f200632818bf06281ad0",
         (thumb_bw(0x0308DFB8, h["pl_init_seek"]) + bytes.fromhex("00bf") * 4).hex()),
    ]

def settings_game():
    """Settings > Game opens the Games screen (build 56, hooks/settings_game.S). Stock: the item (text 0x110) opens
    the stock game list (texts 0x111..0x12d), which also lists the games on reused tasks: 15 Blockz, 19 Playlists,
    20..32 the Games screen span (a launch there jumps into the middle of gbprobe.c). The key handler's enter step
    (m32 0x0308247C: child text id, bl 0x03081C8E) goes to the stub, which TaskSwitch(20)es for 0x110. The stub
    sits in the launch cases for tasks 21..31; the menu cases (32-bit offsets from 0x03083770, index id - 0x7f) of
    every task 21..32 game now point at the task-20 case (0x03083C0A, TaskSwitch(0x14)), in case the list is ever
    reached another way (Settings page 7)."""
    T, AT, END, GAMES = 0x03083770, 0x03083C1C, 0x03083CE0, 0x03083C0A
    code, sym = assemble("settings_game", AT)
    assert AT + len(code) <= END, f"stub is {len(code)} B, room for {END - AT}"
    cases = {0x118: 0x03083C1C, 0x117: 0x03083C2E, 0x11A: 0x03083C40, 0x11B: 0x03083C52, 0x11C: 0x03083C64,
             0x11D: 0x03083C76, 0x11E: 0x03083C88, 0x11F: 0x03083C9A, 0x120: 0x03083CAC, 0x128: 0x03083CBE,
             0x121: 0x03083CD0, 0x122: 0x03083CE0}                        # text id -> launch case (tasks 21..32)
    stock = ("9248002104701520e4f756fa012500f06bb98e48002104701620e4f74dfa012500f062b9"   # tasks 21, 22
             "8948002104701720e4f744fa012500f059b98548002104701820e4f73bfa012500f050b9")  # tasks 23, 24
    assert len(code) <= len(stock) // 2
    off = lambda a: struct.pack("<i", a - T).hex()
    return [(32, T + (i - 0x7F) * 4, off(a), off(GAMES)) for i, a in cases.items()] + [
        (32, AT, stock[:2 * len(code)], code.hex()),                        # launch cases for tasks 21..
        (32, 0x0308247C, "6179a068102202eb4101405afff701fc",               # ldrb; ldr; movs; add.w; ldrh; bl enter
         (thumb_bw(0x0308247C, sym["settings_enter"]) + bytes.fromhex("00bf") * 6).hex()),
    ]

GENERATED = {"timing": timing, "settings_game": settings_game, "playlists": playlists, "menu_carousel": menu_carousel, "music_update": music_update, "np_title_tag": np_title_tag, "np_v2": np_v2, "np_v3": np_v3, "np_v4": np_v4, "lib_skip": lib_skip}

def file_off(code, mod, addr):
    cl, ce, cs = struct.unpack_from("<3I", code, 8 + 32 * mod)
    assert ce <= addr < ce + cs, f"{addr:#x} outside module {mod}"
    return cl - BASE + (addr - ce)

def apply(code: bytearray, names):
    for name in names:
        entries = GENERATED[name]() if name in GENERATED else PATCHES[name]
        for mod, addr, old, new in entries:
            o = file_off(code, mod, addr)
            n = len(new) // 2
            if code[o:o + n].hex() == new:
                print(f"  {name} {addr:#x}: already applied"); continue
            if old is not None:
                have = code[o:o + len(old) // 2].hex()
                assert have == old, f"{name} {addr:#x}: expected {old}, found {have}"
            code[o:o + n] = bytes.fromhex(new)
            print(f"  {name} {addr:#x}: {old or '(dead code)'} -> {new[:40]}{'...' if len(new) > 40 else ''}")

def main():
    global SRC_DIR
    src, out, names = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
    SRC_DIR = src
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(src):
        if os.path.isfile(os.path.join(src, f)) and f != "HIFIYF18.IMG":
            shutil.copy(os.path.join(src, f), out)
    p = os.path.join(out, "code.bin")
    code = bytearray(open(p, "rb").read())
    apply(code, names)
    open(p, "wb").write(code)

if __name__ == "__main__":
    main()
