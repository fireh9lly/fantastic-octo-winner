#!/usr/bin/env python3
"""Inventory every firmware address the build depends on and translate it from V1.7.8 to V1.8.3.

  port_inventory.py OLD_CODE_BIN NEW_CODE_BIN OUT.tsv

Scans the device-side sources (patch tables, hooks, device C/asm, build tool constants, build.sh) for addresses,
classifies each by the memory it points into (V1.7.8 layout), translates it with tools/xlate.py and writes one row
per distinct (address, module) with every place it is used. Rows marked REVIEW need a human look.
"""
import collections, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import xlate  # noqa: E402

SOURCES = ["tools/patch_code.py", "tools/build_hook.py", "tools/build_helpers.py", "tools/build_overlay.py",
           "tools/extend_module.py", "tools/build_module.py", "build.sh", "game/stock.h"]
SOURCES += sorted("hooks/" + f for f in os.listdir(os.path.join(ROOT, "hooks")))
SOURCES += sorted("game/device/" + f for f in os.listdir(os.path.join(ROOT, "game/device")))
ADDR = re.compile(r"0[xX](0?[0-9A-Fa-f]{7,8})\b")
MOD_HINT = re.compile(r"(?:\bmodule\s+|\bm)(\d{1,3})\b|^\s*\((\d{1,3}),\s*0x", re.I)

# V1.7.8 memory map (docs/HARDWARE.md; module table)
M0_CODE = (0x03050000, 0x0307E300)
GAP = (0x0307E300, 0x03080E9C)            # stock working area between module 0 and the overlay window
OVERLAY = (0x03080E9C, 0x0309F7CC)
OURS = (0x0309F7CC, 0x030A0000)           # amuletOS's own RAM (slot 2, tables) and stock's reset magic

# files whose stock addresses all belong to one module (unless a line says otherwise)
FILE_MODULE = {"game/device/m21_ext.S": 21, "game/device/m21_ext.c": 21, "game/device/m22_ext.S": 22,
               "game/device/m22_ext.c": 22, "game/device/npui.c": 27, "hooks/np_title.S": 27,
               "hooks/settings_game.S": 32, "hooks/amu_inq.S": 12, "hooks/d1_diag.S": 12, "hooks/h0_inquiry.S": 12,
               "hooks/h0a_pass.S": 12, "tools/build_hook.py": 12}
# addresses whose module is only stated in nearby comments (checked by hand against docs/HARDWARE.md)
ADDRESS_MODULE = {0x03080EAC: 4, 0x03080FEC: 4,                       # panel driver: DMA completion, push op
                  0x03081AA4: 10, 0x03081AA5: 10,                     # USB control: send (target of m12's call)
                  0x03082F4E: 11,                                     # USB audio
                  0x0308BF84: 33, 0x0308C8EE: 33, 0x0308DDD0: 33, 0x0308D86E: 33,   # music engine
                  0x0308DD48: 33, 0x0308DF12: 33, 0x0308DF1A: 33, 0x0308DF26: 33, 0x0308DF40: 33,
                  0x0308DFB8: 33, 0x0308DFC4: 33, 0x0308DFFA: 33, 0x0308E014: 33}
# memory-layout boundaries (not code): (description, function of the new module table)
LAYOUT = {0x03083F0C: ("end of module 27 = Now Playing overlay slot start", lambda m: m[27]["ce"] + m[27]["cs"]),
          0x03084664: ("start of module 18 = Now Playing overlay slot end", lambda m: m[18]["ce"]),
          0x0308FF84: ("Game Boy sound ring end = module 33 start + 16 KB", lambda m: m[33]["ce"] + 0x4000),
          0x0308FFBC: ("start of the decoder front-ends (module 40)", lambda m: m[40]["ce"])}
TUPLE = re.compile(r"\(\s*(\d{1,3})\s*,\s*(?=0x|[A-Za-z_])")
BLOCK = re.compile(r"^(def |    \"[a-z0-9_]+\": )", re.M)


def scan(rel, text):
    """(address, module or None, line) for every address in a source file"""
    out = []
    line_at = lambda pos: text.count("\n", 0, pos) + 1
    if rel == "tools/patch_code.py":
        # patch entries are (module, address, ...) tuples; addresses belong to the module of the nearest preceding
        # tuple in the same patch (block), or of the block's first tuple for constants defined before it
        starts = [m.start() for m in BLOCK.finditer(text)] + [len(text)]
        for b0, b1 in zip(starts, starts[1:]):
            block = text[b0:b1]
            tuples = [(m.start(), int(m.group(1))) for m in TUPLE.finditer(block)]
            for m in ADDR.finditer(block):
                if "#" in block[block.rfind("\n", 0, m.start()) + 1:m.start()]:
                    continue                          # in a comment
                prev = [mod for pos, mod in tuples if pos < m.start()]
                mod = prev[-1] if prev else (tuples[0][1] if tuples else None)
                out.append((int(m.group(1), 16), mod, line_at(b0 + m.start())))
        return out
    default = FILE_MODULE.get(rel)
    for n, line in enumerate(text.splitlines(), 1):
        code = line.split("#")[0] if rel.endswith((".py", ".sh")) else line
        for m in ADDR.finditer(code):
            h = MOD_HINT.search(line)
            mod = next((int(g) for g in h.groups() if g), None) if h else default
            out.append((int(m.group(1), 16), mod, n))
    return out


def game_exit(x, mi, a):
    """stock games quit with movs r0, #0xa just before bl TaskSwitch: re-find those sites by pattern (Hidizs changed
    the games in V1.8.3), pairing old and new sites in order when the counts agree"""
    import capstone
    ts_old = 0x030680D4
    ts_new = x.code(0, ts_old)[0]
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    md.detail = True
    md.skipdata = True                            # keep going past data embedded in the module
    def exits(img, ts):
        m = img.mods[mi]
        code = img.d[m["cl"] - xlate.BASE:m["cl"] - xlate.BASE + m["cs"]]
        ins = [i for i in md.disasm(code, m["ce"]) if i.id]
        return [i.address for k, i in enumerate(ins) if i.mnemonic == "movs" and i.op_str == "r0, #0xa" and
                any(j.mnemonic == "bl" and j.operands[0].imm == ts for j in ins[k + 1:k + 4])]
    eo, en = exits(x.o, ts_old), exits(x.n, ts_new)
    if a in eo and len(eo) == len(en):
        return en[eo.index(a)], f"game exit pattern (movs r0,#0xa; bl TaskSwitch), site {eo.index(a) + 1} of {len(eo)}"
    return None, f"game exit pattern: {len(eo)} old / {len(en)} new sites"


def region(a):
    if M0_CODE[0] <= a < M0_CODE[1]: return "m0-code"
    if 0x03004000 <= a < M0_CODE[0]: return "ram"
    if GAP[0] <= a < GAP[1]: return "ram-gap"
    if OVERLAY[0] <= a < OVERLAY[1]: return "overlay"
    if OURS[0] <= a < OURS[1]: return "ours"
    if 0x01000000 <= a < 0x01100000: return "coreB"
    if a >= 0x40000000: return "periph"
    return "other"


def main():
    old, new, out = sys.argv[1:4]
    x = xlate.load(old, new)
    uses = collections.defaultdict(list)          # (addr, module hint) -> ["file:line", ...]
    for rel in SOURCES:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        for a, mod, n in scan(rel, open(path, encoding="utf-8", errors="replace").read()):
            if region(a) != "other":
                uses[(a, mod)].append(f"{rel}:{n}")
    rows = []
    for (a, mod), where in sorted(uses.items(), key=lambda kv: (kv[0][0], -1 if kv[0][1] is None else kv[0][1])):
        reg = region(a)
        new_a, how, flag = None, "", ""
        if a in ADDRESS_MODULE and mod in (None, FILE_MODULE.get(where[0].split(":")[0])):
            mod = ADDRESS_MODULE[a]
        if a in LAYOUT:
            desc, f = LAYOUT[a]
            new_a, how = f(x.n.mods), "layout: " + desc
        elif reg in ("coreB", "periph"):
            new_a, how = a, "hardware / core B: unchanged"
        elif reg == "ours":
            how, flag = "amuletOS-owned RAM: re-plan for V1.8.3 (resident area moved/shrank)", "REVIEW"
        elif reg == "m0-code":
            new_a, how = x.code(0, a)
            if new_a is None:
                new_a, how2 = x.value(a)
                how = how2 + " | code: " + how
        elif reg in ("ram", "ram-gap"):
            new_a, how = x.value(a)
        elif reg == "overlay":
            cands = [mod] if mod is not None else [mi for mi, ms in enumerate(x.o.mods) if ms["cs"] and ms["ce"] <= a < ms["ce"] + ms["cs"]]
            res = {}
            for mi in cands:
                r = x.code(mi, a)
                if r[0] is not None:
                    res[mi] = r
            vals = {r[0] for r in res.values()}
            if len(vals) == 1:
                new_a = vals.pop()
                how = ("module %d: " % mod if mod is not None else f"all {len(res)} modules agree: ") + next(iter(res.values()))[1]
            elif res:
                how, flag = "modules disagree: " + "; ".join(f"m{mi}->{r[0]:#x}" for mi, r in res.items()), "REVIEW"
            elif mod is not None and 81 <= mod <= 112 and game_exit(x, mod, a)[0] is not None:
                new_a, how = game_exit(x, mod, a)
            elif mod is not None and x.lit_word(mod, a)[0] is not None:
                new_a, how = x.lit_word(mod, a)
            else:
                how, flag = f"no translation (module hint {mod})", "REVIEW"
        if new_a is None and not flag:
            flag = "REVIEW"
        if "CHECK" in how or "conflict" in how or "aligned" in how:
            flag = flag or "CHECK"
        rows.append((f"{a:#010x}", "" if mod is None else str(mod), reg, "" if new_a is None else f"{new_a:#010x}",
                     "" if new_a is None else f"{new_a - a:+#x}", flag, how, " ".join(where)))
    with open(out, "w") as f:
        f.write("old\tmodule\tregion\tnew\tshift\tflag\thow\tused at\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
    c = collections.Counter(r[5] or "ok" for r in rows)
    print(f"{len(rows)} addresses: {dict(c)} -> {out}")


if __name__ == "__main__":
    main()
