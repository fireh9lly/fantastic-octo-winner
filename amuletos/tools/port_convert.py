#!/usr/bin/env python3
"""One-time conversion of the firmware source from V1.7.8 addresses to V1.8.3 (kept for provenance).

  port_convert.py TREE ADDRESSES_TSV PATCHES_JSON

Rewrites TREE in place:
  1. every address listed in ADDRESSES_TSV (tools/port_inventory.py output, reviewed) on the lines it lists, in the
     same textual style;
  2. the code.bin file-layout constants (V1.8.3: the 16 KB zero gap moved +0x4D0 to 0x5805C..0x5C05C, the stock
     games' file span 87..99 is 0x968BC..0xA68C0, module 12's BL site follows its translated run address);
  3. every patch's expected original bytes that tools/port_patches.py found "relocated" (PATCHES_JSON), replaced by
     the bytes really in V1.8.3. Patches reported DIFFERENT stop the conversion.
Addresses in docs/ (amuletOS's notes) stay V1.7.8; docs/port/v183_addresses.tsv maps them.
"""
import collections, json, os, re, sys

ADDR = re.compile(r"0[xX](0?[0-9A-Fa-f]{7,8})\b")


def fmt(tok, v):
    body = tok[2:]
    s = f"{v:0{len(body)}x}" if len(body) >= 8 else f"{v:x}"
    return tok[:2] + (s.upper() if body.upper() == body and any(c.isalpha() for c in body) else s)


def main():
    tree, tsv, pj = sys.argv[1:4]
    report = json.load(open(pj))
    bad = [r for r in report if r["status"] == "DIFFERENT"]
    assert not bad, f"{len(bad)} patches differ: review them first"

    # 1. addresses
    edits = {}
    for row in [l.rstrip("\n").split("\t") for l in open(tsv)][1:]:
        old, new, used = row[0], row[3], row[7]
        if new:
            for w in used.split():
                f, n = w.rsplit(":", 1)
                edits.setdefault((f, int(n)), {})[int(old, 16)] = int(new, 16)
    count = 0
    for f in sorted({f for f, _ in edits}):
        p = os.path.join(tree, f)
        lines = open(p, encoding="utf-8").read().split("\n")
        for (ff, n), m in edits.items():
            if ff != f:
                continue
            def sub(mt, m=m):
                nonlocal count
                v = int(mt.group(1), 16)
                if v in m:
                    count += 1
                    return fmt(mt.group(0), m[v])
                return mt.group(0)
            lines[n - 1] = ADDR.sub(sub, lines[n - 1])
        open(p, "w", encoding="utf-8").write("\n".join(lines))
    print(f"1. {count} addresses in {len({f for f, _ in edits})} files")

    # 2. code.bin layout
    layout = [("tools/build_hook.py", "GAP_FILE, GAP_SIZE = 0x57B8C, 0x4000", "GAP_FILE, GAP_SIZE = 0x5805C, 0x4000"),
              ("tools/build_overlay.py", "GAP = (0x57B8C, 0x5BB8C)", "GAP = (0x5805C, 0x5C05C)"),
              ("tools/build_helpers.py", "FILE_END = 0x58800 ", "FILE_END = 0x58CD0 "),
              ("build.sh", "game/device/blockz.c --at 0x58800", "game/device/blockz.c --at 0x58CD0"),
              ("build.sh", "--at 0x5B400", "--at 0x5B8D0"),
              ("build.sh", "--span 0x95578:0xa3ec0", "--span 0x968bc:0xa68c0")]
    for f, a, b in layout:
        p = os.path.join(tree, f)
        s = open(p).read()
        assert a in s, (f, a)
        open(p, "w").write(s.replace(a, b))
    p = os.path.join(tree, "tools/build_hook.py")
    s = open(p).read()
    site = re.search(r'"amu":\s*\("amu_inq.S",\s*"amu_send",\s*HOOK_RUN,\s*2,\s*(0x[0-9A-Fa-f]+),\s*0x81750', s).group(1)
    s = s.replace("0x81750", hex(0x818F8 + int(site, 16) - 0x03083AE0))      # module 12: cl + run offset
    open(p, "w").write(s)
    print(f"2. layout constants (module 12 BL site {site} at code.bin {0x818F8 + int(site, 16) - 0x03083AE0:#x})")

    # 3. expected original bytes
    p = os.path.join(tree, "tools/patch_code.py")
    s = open(p).read()
    m = collections.defaultdict(set)
    for r in report:
        if r["status"] == "relocated" and r["patch"] != "settings_game":
            m[r["old_bytes"]].add(r["new_bytes"])
    n = 0
    for old, news in m.items():
        assert len(news) == 1, (old, news)
        new = news.pop()
        c = s.count('"' + old + '"')
        assert c >= 1, old
        s, n = s.replace('"' + old + '"', '"' + new + '"'), n + c
    # settings_game keeps the stock launch code of tasks 21..24 as one string (its prefix is checked): replaced by
    # the V1.8.3 bytes of the whole span, verified equivalent (four TaskSwitch calls relocated)
    old_stock = ('stock = ("9248002104701520e4f756fa012500f06bb98e48002104701620e4f74dfa012500f062b9"   # tasks 21, 22\n'
                 '             "8948002104701720e4f744fa012500f059b98548002104701820e4f73bfa012500f050b9")  # tasks 23, 24')
    new_stock = ('stock = ("9248002104701520e4f77cf9012500f06bb98e48002104701620e4f773f9012500f062b9"   # tasks 21, 22\n'
                 '             "8948002104701720e4f76af9012500f059b98548002104701820e4f761f9012500f050b9")  # tasks 23, 24')
    assert s.count(old_stock) == 1
    s = s.replace(old_stock, new_stock)
    open(p, "w").write(s)
    print(f"3. {n} expected-bytes strings + settings_game stock span updated to V1.8.3")


if __name__ == "__main__":
    main()
