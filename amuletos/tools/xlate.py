#!/usr/bin/env python3
"""Translate firmware addresses between two official AP30 images (e.g. V1.7.8 -> V1.8.3).

  xlate.py OLD_CODE_BIN NEW_CODE_BIN stats                 match statistics per module
  xlate.py OLD_CODE_BIN NEW_CODE_BIN addr MODULE ADDR      translate one address (MODULE: number, or 'ram')

How it works
  1. Functions (tools/fwmap.py's finder) are matched module by module on a *normalised* instruction sequence:
     branch/call targets outside the function, pc-relative literal offsets and literal-pool contents are masked,
     because those change whenever code moves. Identical sequences match exactly; changed functions are aligned
     with difflib (instruction level) when they are similar enough.
  2. Every matched pair yields evidence for data and cross-module code: the literal values the two functions load
     at the same instruction (RAM addresses, module-0 functions...) and the targets of the same call.
  3. Code addresses are translated by instruction index inside the matched function; literal-pool words through
     the instruction that loads them; RAM addresses from the literal evidence (exact, or the same shift as the
     nearest known addresses on both sides).
Every answer carries how it was found, so doubtful ones can be reviewed by hand.
"""
import bisect, collections, difflib, functools, hashlib, os, pickle, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone, fwmap  # noqa: E402

BASE = fwmap.BASE
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"), "ap30-xlate")
BRANCH = ("b", "bl", "blx", "cbz", "cbnz")


def _md():
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    md.detail = True
    md.skipdata = True
    return md


class Image:
    """one code.bin: modules, functions, normalised instruction streams"""

    def __init__(self, path):
        self.d = open(path, "rb").read()
        key = hashlib.sha256(self.d).hexdigest()[:16] + "-v3"
        os.makedirs(CACHE, exist_ok=True)
        cp = os.path.join(CACHE, key + ".pkl")
        if os.path.exists(cp):
            self.mods, self.funcs = pickle.load(open(cp, "rb"))
        else:
            self.mods, funcs, _ = fwmap.analyse(self.d)
            fstarts = {a for (_, a) in funcs}
            self.pools = {mi: self._pools(mi, fstarts) for mi in range(len(self.mods))}
            self.funcs = {}                           # module -> sorted list of function dicts
            for (mi, a), f in funcs.items():
                self.funcs.setdefault(mi, []).append(self._norm(mi, a, f["end"]))
            for mi in self.funcs:
                self.funcs[mi].sort(key=lambda f: f["addr"])
            pickle.dump((self.mods, self.funcs), open(cp, "wb"))
        self.starts = {mi: [f["addr"] for f in fs] for mi, fs in self.funcs.items()}

    def word(self, mi, a):
        o = fwmap.exec_to_file(self.mods[mi], a)
        return struct.unpack_from("<I", self.d, o)[0] if o is not None and o + 4 <= len(self.d) else None

    def _pools(self, mi, fstarts=()):
        """every literal-pool word in the module (pools are often shared by neighbouring functions). Words that
        would overlap a function start are dropped: those come from data mis-decoded as a pc-relative load."""
        m = self.mods[mi]
        if not m["cs"]:
            return set()
        o = m["cl"] - BASE
        lits = set()
        for x in _md().disasm(self.d[o:o + m["cs"]], m["ce"]):
            if x.id and x.mnemonic.startswith("ldr") and len(x.operands) > 1 and \
                    x.operands[1].type == capstone.arm.ARM_OP_MEM and x.operands[1].mem.base == capstone.arm.ARM_REG_PC:
                la = ((x.address + 4) & ~3) + x.operands[1].mem.disp
                if not any(la <= fs < la + 4 for fs in (la, la + 2) if fs in fstarts) and la + 2 not in fstarts:
                    lits.add(la)
        return lits

    def _norm(self, mi, a, end):
        m = self.mods[mi]
        o = m["cl"] - BASE + (a - m["ce"])
        code = self.d[o:o + (end - a)]
        ins = list(_md().disasm(code, a))
        lits = {la for la in self.pools[mi] if a - 4 < la < end}   # pool words anywhere in this range
        for x in ins:
            if x.id and x.mnemonic.startswith("ldr") and len(x.operands) > 1 and \
                    x.operands[1].type == capstone.arm.ARM_OP_MEM and x.operands[1].mem.base == capstone.arm.ARM_REG_PC:
                lits.add(((x.address + 4) & ~3) + x.operands[1].mem.disp)
        toks, addrs, lit_of, ext_of = [], [], {}, {}
        for x in ins:
            if any(la <= x.address < la + 4 or x.address <= la < x.address + x.size for la in lits):
                continue                              # literal pool, not code
            mn, ops = x.mnemonic, x.operands if x.id else []
            t = None
            if not x.id:
                t = "DATA:" + x.bytes.hex()
            elif mn.startswith(BRANCH) and ops and ops[-1].type == capstone.arm.ARM_OP_IMM:
                tgt = ops[-1].imm
                t = mn + (" @%x" % (tgt - a) if a <= tgt < end else " EXT")
                if not (a <= tgt < end):
                    ext_of[len(toks)] = tgt
            elif mn.startswith("ldr") and len(ops) > 1 and ops[1].type == capstone.arm.ARM_OP_MEM \
                    and ops[1].mem.base == capstone.arm.ARM_REG_PC:
                la = ((x.address + 4) & ~3) + ops[1].mem.disp
                t = mn + " " + x.op_str.split(",")[0] + ", LIT"
                lit_of[len(toks)] = la
            elif mn.startswith(("adr", "add", "sub")) and len(ops) >= 2 and any(
                    o.type == capstone.arm.ARM_OP_REG and o.reg == capstone.arm.ARM_REG_PC for o in ops[1:2]):
                tgt = ((x.address + 4) & ~3) + (ops[-1].imm if ops[-1].type == capstone.arm.ARM_OP_IMM else 0) * \
                    (-1 if mn.startswith("sub") else 1)
                t = mn + " " + x.op_str.split(",")[0] + (", PC@%x" % (tgt - a) if a <= tgt < end else ", PCEXT")
                if not (a <= tgt < end):
                    ext_of[len(toks)] = tgt
            else:
                t = mn + " " + x.op_str
            toks.append(t)
            addrs.append(x.address)
        return dict(mod=mi, addr=a, end=end, toks=toks, addrs=addrs, lit_of=lit_of, ext_of=ext_of,
                    sig=hashlib.sha1("\n".join(toks).encode()).hexdigest())

    def func_at(self, mi, a):
        st = self.starts.get(mi, [])
        i = bisect.bisect_right(st, a) - 1
        if i >= 0:
            f = self.funcs[mi][i]
            if a < f["end"] or a < (self.funcs[mi][i + 1]["addr"] if i + 1 < len(st) else f["end"]):
                return f
        return None


class Xlate:
    def __init__(self, old_path, new_path):
        self.o, self.n = Image(old_path), Image(new_path)
        self.match = {}            # (mod, old addr) -> (new func, kind, ratio, index map or None)
        self.lit = collections.defaultdict(collections.Counter)    # old literal value -> Counter(new values)
        self.ext = collections.defaultdict(collections.Counter)    # old external target -> Counter(new)
        for mi in set(self.o.funcs) | set(self.n.funcs):
            self._match_module(mi)

    def _match_module(self, mi):
        of, nf = self.o.funcs.get(mi, []), self.n.funcs.get(mi, [])
        by_sig = collections.defaultdict(list)
        for f in nf:
            by_sig[f["sig"]].append(f)
        used = set()
        seen = collections.Counter()
        for f in of:                                   # exact: same normalised code (k-th occurrence for duplicates)
            cands = by_sig.get(f["sig"], [])
            k = seen[f["sig"]]; seen[f["sig"]] += 1
            if k < len(cands):
                g = cands[k]
                self.match[(mi, f["addr"])] = (g, "exact", 1.0, None)
                used.add(g["addr"])
                self._evidence(f, g, None)
        # changed functions: align with the most similar unused new function in a window around the expected place
        anchors = sorted((f["addr"], m[0]["addr"]) for (mm, a), m in self.match.items() if mm == mi
                         for f in [self.o.func_at(mi, a)] if f)
        for f in of:
            if (mi, f["addr"]) in self.match:
                continue
            i = bisect.bisect_left([a for a, _ in anchors], f["addr"])
            delta = (anchors[i - 1][1] - anchors[i - 1][0]) if i > 0 else (anchors[0][1] - anchors[0][0] if anchors else 0)
            exp = f["addr"] + delta
            best = None
            for g in nf:
                if g["addr"] in used or abs(g["addr"] - exp) > 0x800:
                    continue
                sm = difflib.SequenceMatcher(None, f["toks"], g["toks"], autojunk=False)
                if sm.real_quick_ratio() < 0.6 or sm.quick_ratio() < 0.6:
                    continue
                r = sm.ratio()
                if r >= 0.6 and (best is None or r > best[0]):
                    best = (r, g, sm)
            if best:
                r, g, sm = best
                imap = {}
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "equal":
                        for k in range(i2 - i1):
                            imap[i1 + k] = j1 + k
                self.match[(mi, f["addr"])] = (g, "aligned", r, imap)
                used.add(g["addr"])
                self._evidence(f, g, imap)

    def _evidence(self, f, g, imap):
        pairs = ((i, i) for i in range(len(f["toks"]))) if imap is None else imap.items()
        for i, j in pairs:
            if i in f["lit_of"] and j in g["lit_of"]:
                a, b = self.o.word(f["mod"], f["lit_of"][i]), self.n.word(g["mod"], g["lit_of"][j])
                if a is not None and b is not None:
                    self.lit[a][b] += 1
            if i in f["ext_of"] and j in g["ext_of"]:
                self.ext[f["ext_of"][i]][g["ext_of"][j]] += 1

    # ---- translation ----
    def code(self, mi, a):
        """code address in module mi -> (new, how). Odd addresses (Thumb pointers / bx targets) keep their bit;
        an address inside an instruction keeps its offset from that instruction's start."""
        if a & 1:
            b, how = self.code(mi, a & ~1)
            return (None if b is None else b | 1), how + " (+thumb bit)"
        f = self.o.func_at(mi, a)
        if f is not None and a not in f["addrs"]:
            prev = [i for i, ia in enumerate(f["addrs"]) if ia < a]
            if prev and a - f["addrs"][prev[-1]] < 4 and not any(la <= a < la + 4 for la in f["lit_of"].values()):
                ia = f["addrs"][prev[-1]]
                b, how = self.code(mi, ia)
                return (None if b is None else b + (a - ia)), how + f" (+{a - ia} inside the instruction at {ia:#x})"
        if f is None:
            return None, "no function at this address in the old image"
        m = self.match.get((mi, f["addr"]))
        if m is None:
            return None, f"function {f['addr']:#x} has no match"
        g, kind, r, imap = m
        if a in f["addrs"]:
            i = f["addrs"].index(a)
            j = i if imap is None else imap.get(i)
            if j is None:
                return None, f"instruction changed in aligned function ({kind} {r:.2f})"
            return g["addrs"][j], f"{kind} function {f['addr']:#x}->{g['addr']:#x}" + ("" if kind == "exact" else f" ({r:.2f})")
        for i, la in f["lit_of"].items():                  # a literal-pool word: follow the instruction that loads it
            if la == a:
                j = i if imap is None else imap.get(i)
                if j is not None and j in g["lit_of"]:
                    return g["lit_of"][j], f"literal of {kind} function {f['addr']:#x}->{g['addr']:#x}"
        if kind == "exact" and f["end"] - f["addr"] == g["end"] - g["addr"]:
            return g["addr"] + (a - f["addr"]), f"offset inside exact function {f['addr']:#x}->{g['addr']:#x} (not an instruction start)"
        return None, f"inside {kind} function {f['addr']:#x} but not an instruction or literal"

    def lit_word(self, mi, a):
        """a literal-pool word in module mi, located by its value: every aligned copy of the old value in the old
        module is paired, in order, with every copy of the translated value in the new module (counts must agree)"""
        v = self.o.word(mi, a)
        if v is None:
            return None, "no word there"
        nv, how = self.value(v)
        if nv is None:
            return None, f"value {v:#x} has no translation ({how})"
        def where(img, val):
            m = img.mods[mi]
            return [m["ce"] + k for k in range(0, m["cs"] - 3, 4)
                    if struct.unpack_from("<I", img.d, m["cl"] - BASE + k)[0] == val]
        old_at, new_at = where(self.o, v), where(self.n, nv)
        if a not in old_at or len(old_at) != len(new_at):
            return None, f"value {v:#x}: {len(old_at)} copies before, {nv:#x}: {len(new_at)} after"
        return new_at[old_at.index(a)], f"literal word {v:#x}->{nv:#x}, copy {old_at.index(a) + 1} of {len(old_at)} ({how})"

    def value(self, a):
        """an address used as data (RAM, or a code pointer loaded as a literal) -> (new, how)"""
        if a in self.lit:
            c = self.lit[a]
            (b, n), = c.most_common(1)
            return b, f"literal evidence {n}x" + ("" if len(c) == 1 else f" (conflicts: {dict(c)})")
        for a2 in (a | 1, a & ~1):                         # thumb function pointer vs plain address
            if a2 != a and a2 in self.lit:
                b, how = self.value(a2)
                return b - (a2 - a), how + " (thumb bit)"
        if a in self.ext:
            (b, n), = self.ext[a].most_common(1)
            return b, f"call-target evidence {n}x"
        ks = sorted(k for k in self.lit if len(self.lit[k]) == 1)
        i = bisect.bisect_left(ks, a)
        lo = ks[i - 1] if i > 0 else None
        hi = ks[i] if i < len(ks) else None
        dl = (self.lit[lo].most_common(1)[0][0] - lo) if lo is not None else None
        dh = (self.lit[hi].most_common(1)[0][0] - hi) if hi is not None else None
        if dl is not None and dl == dh:
            return a + dl, f"shift {dl:+#x} (same as known {lo:#x} and {hi:#x})"
        if dl is not None and a - lo <= 0x40:
            return a + dl, f"shift {dl:+#x} from {lo:#x} (+{a - lo:#x}) only; next known {hi and hex(hi)} differs: CHECK"
        return None, f"no evidence (neighbours {lo and hex(lo)} {dl and hex(dl)} / {hi and hex(hi)} {dh and hex(dh)})"

    def stats(self):
        rows = []
        for mi in sorted(self.o.funcs):
            fs = self.o.funcs[mi]
            ex = sum(1 for f in fs if self.match.get((mi, f["addr"]), (0, ""))[1] == "exact")
            al = sum(1 for f in fs if self.match.get((mi, f["addr"]), (0, ""))[1] == "aligned")
            rows.append((mi, len(fs), ex, al, len(fs) - ex - al))
        return rows


@functools.lru_cache(None)
def load(old, new):
    return Xlate(old, new)


def main():
    a = sys.argv[1:]
    x = load(a[0], a[1])
    if a[2] == "stats":
        tot = [0, 0, 0, 0]
        for mi, n, ex, al, no in x.stats():
            tot = [t + v for t, v in zip(tot, (n, ex, al, no))]
            if al or no:
                print(f"m{mi:<3} {n:4d} functions: {ex} exact, {al} aligned, {no} unmatched")
        print(f"all modules: {tot[0]} functions: {tot[1]} exact, {tot[2]} aligned, {tot[3]} unmatched")
        print(f"literal evidence: {len(x.lit)} distinct old values, {sum(1 for c in x.lit.values() if len(c) > 1)} with conflicts")
    elif a[2] == "diff":                                  # diff MODULE FUNC_ADDR: what changed in a matched function
        mi, fa = int(a[3]), int(a[4], 16)
        f = x.o.func_at(mi, fa)
        g, kind, r, imap = x.match[(mi, f["addr"])]
        print(f"m{mi} {f['addr']:#x} -> {g['addr']:#x}: {kind} {r:.2f}")
        sm = difflib.SequenceMatcher(None, f["toks"], g["toks"], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                print(f"  {tag}:")
                for i in range(i1, i2): print(f"    - {f['addrs'][i]:#x} {f['toks'][i]}")
                for j in range(j1, j2): print(f"    + {g['addrs'][j]:#x} {g['toks'][j]}")
    elif a[2] == "addr":
        mi, addr = a[3], int(a[4], 16)
        r = x.value(addr) if mi == "ram" else x.code(int(mi), addr)
        if r[0] is None and mi != "ram":
            r = x.lit_word(int(mi), addr)
        print(r[0] if r[0] is None else hex(r[0]), r[1])


if __name__ == "__main__":
    main()
