#!/usr/bin/env python3
"""Review the CHECK rows of the V1.7.8 -> V1.8.3 address table (addresses inside functions Hidizs changed).

  port_review.py OLD_CODE_BIN NEW_CODE_BIN ADDRESSES_TSV PATCH_SRC_DIR OUT.tsv [--show]

PATCH_SRC_DIR is a build's input to tools/patch_code.py (BUILD_DIR/d1h_e), so the generated patches can be listed.
Every use of a CHECK address is sorted into:
  not built   the file isn't part of build.sh's image (old diagnostics hooks, the disabled timing log);
  checked     the address lies inside a patch whose original bytes patch_code.py compares at build time, or is
              build_hook.py's BL site (it checks the BL's target): a wrong translation stops the build;
  review      nothing checks it (a branch or call target, a function pointer, a RAM address, a patch without
              original bytes): compared here instruction by instruction around the old and the new address.
For a code address in a changed function, the window of 6 normalised instructions before and after it (branch
targets, literal offsets and pool contents masked, as tools/xlate.py matches functions) is compared between the
two images; "window k/n" counts identical positions and "at" says whether the instruction itself is identical.
--show prints the side-by-side windows of everything not fully identical.
"""
import argparse, collections, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xlate  # noqa: E402

NOT_BUILT = ("hooks/h0_inquiry.S", "hooks/h0a_pass.S", "hooks/d1_diag.S", "game/device/timing.S",
             "game/device/timing.c")
PATCH_NAMES = ("np_v4,np_hide_format,menu_games_to_blockz,lib_skip,menu_carousel,music_update,playlists,"
               "keep_settings,english,np_back_home,games_back,settings_game").split(",")   # build.sh
W = 6


def patch_line_names():
    """patch_code.py line number -> patch name (the PATCHES key or generator function it belongs to)"""
    names, cur = {}, None
    for n, line in enumerate(open(os.path.join(HERE, "patch_code.py")), 1):
        m = re.match(r'^    "([a-z0-9_]+)": \[', line) or re.match(r"^def ([a-z0-9_]+)\(", line)
        if m:
            cur = m.group(1)
        elif re.match(r"^(\S)", line) and not line.startswith(("def ", "#", "}")):
            cur = None
        names[n] = cur
    return names


def in_comment(path, ln, value):
    """True when every occurrence of the address on that source line is inside a comment"""
    line = open(path, encoding="utf-8", errors="replace").read().split("\n")[ln - 1]
    toks = [m for m in re.finditer(r"0[xX]0?([0-9A-Fa-f]{7,8})", line) if int(m.group(1), 16) == value]
    if not toks:
        return False
    def comment_at(pos):
        before = line[:pos]
        if path.endswith(".S"):
            return "@" in before
        if path.endswith(".py"):
            return "#" in before
        if "//" in before or (before.rfind("/*") > before.rfind("*/")):
            return True
        return bool(re.match(r"\s*\*(\s|/|$)", line))     # " * ..." inside a block comment begun on an earlier line
    return all(comment_at(m.start()) for m in toks)


def checked_ranges(src):
    import patch_code
    patch_code.SRC_DIR = src
    out = collections.defaultdict(list)            # module -> [(start, end, patch name)]
    unchecked = collections.defaultdict(list)
    for name in PATCH_NAMES:
        entries = patch_code.GENERATED[name]() if name in patch_code.GENERATED else patch_code.PATCHES[name]
        for mod, addr, old, new in entries:
            if old is None:
                unchecked[mod].append((addr, addr + len(new) // 2, name))
            else:
                out[mod].append((addr, addr + len(old) // 2, name))
    return out, unchecked


def window(x, mi, a, b):
    """normalised instructions around a (old) and b (new): (pairs, matches, n, same_at)"""
    f = x.o.func_at(mi, a & ~1)
    m = x.match.get((mi, f["addr"])) if f else None
    if not f or not m or (a & ~1) not in f["addrs"]:
        return None
    g, kind, r, imap = m
    i = f["addrs"].index(a & ~1)
    j = g["addrs"].index(b & ~1) if (b & ~1) in g["addrs"] else None
    if j is None:
        return None
    pairs = []
    for d in range(-W, W + 1):
        ti = f["toks"][i + d] if 0 <= i + d < len(f["toks"]) else None
        tj = g["toks"][j + d] if 0 <= j + d < len(g["toks"]) else None
        if ti is None and tj is None:
            continue
        pairs.append((d, ti, tj))
    same = sum(1 for _, ti, tj in pairs if ti == tj)
    return pairs, same, len(pairs), f["toks"][i] == g["toks"][j], kind, r


def main():
    p = argparse.ArgumentParser()
    p.add_argument("old"); p.add_argument("new"); p.add_argument("tsv"); p.add_argument("src"); p.add_argument("out")
    p.add_argument("--show", action="store_true")
    a = p.parse_args()
    x = xlate.load(a.old, a.new)
    ranges, unchecked = checked_ranges(a.src)
    rows = [l.rstrip("\n").split("\t") for l in open(a.tsv)][1:]
    pnames = patch_line_names()
    root = os.path.dirname(HERE)
    out, stats = [], collections.Counter()
    for r in rows:
        if r[5] != "CHECK":
            continue
        old, mod, reg, new = int(r[0], 16), r[1], r[2], int(r[3], 16)
        mi = 0 if reg == "m0-code" else (int(mod) if mod else None)     # a module hint on a module-0 address is the caller's
        kinds = collections.Counter()
        for w in r[7].split():
            f, ln = w.rsplit(":", 1)
            if f in NOT_BUILT:
                kinds["not built"] += 1
            elif f == "tools/patch_code.py" and pnames.get(int(ln)) not in PATCH_NAMES:
                kinds["not built"] += 1                # a superseded or dev-only patch (not in build.sh)
            elif f != "tools/patch_code.py" and in_comment(os.path.join(root, f), int(ln), new):
                kinds["comment"] += 1
            elif f == "tools/build_hook.py":
                kinds["checked"] += 1                  # HOOKS: only "amu" is built; its BL site + target are checked
            elif f == "tools/patch_code.py" and mod and any(s <= new < e for s, e, _ in ranges[int(mod)]):
                kinds["checked"] += 1
            else:
                kinds["review"] += 1
        verdict, note = ("review" if kinds["review"] else "checked" if kinds["checked"] else
                         "not built" if kinds["not built"] else "comment only"), ""
        if verdict == "review":
            if reg in ("ram", "ram-gap"):
                note = r[6]
            else:
                wnd = window(x, mi, old, new) if mi is not None else None
                if wnd is None:
                    note = "no instruction window (" + r[6][:60] + ")"
                else:
                    pairs, same, n, at, kind, score = wnd
                    note = f"window {same}/{n}, at {'same' if at else 'DIFFERENT'} ({kind} {score:.2f})"
                    if a.show and same < n:
                        print(f"\n== {r[0]} -> {r[3]} m{mi} {note}  [{r[7][:80]}]")
                        for d, ti, tj in pairs:
                            mark = "  " if ti == tj else "!!"
                            print(f"  {mark} {d:+3d}  {str(ti)[:38]:<38} | {str(tj)[:38]}")
        stats[verdict] += 1
        out.append((r[0], mod, reg, r[3], verdict, note, " ".join(f"{k}:{v}" for k, v in sorted(kinds.items())), r[7]))
    with open(a.out, "w") as fo:
        fo.write("old\tmodule\tregion\tnew\tverdict\tcomparison\tuses by kind\tused at\n")
        for o in out:
            fo.write("\t".join(o) + "\n")
    print(f"\n{sum(stats.values())} CHECK rows: {dict(stats)} -> {a.out}")
    # patches without original bytes (written blind): their sites need the same review
    for mi, lst in sorted(unchecked.items()):
        for s, e, name in lst:
            print(f"patch without original bytes: {name} module {mi} {s:#x}..{e:#x}")


if __name__ == "__main__":
    main()
