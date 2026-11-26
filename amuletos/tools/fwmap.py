#!/usr/bin/env python3
"""Build a searchable index of an unpacked AP30 code.bin.

  fwmap.py CODE_BIN OUTDIR

Writes OUTDIR/functions.tsv  (module, address, size, calls, name hint, strings referenced)
       OUTDIR/strings.tsv    (string, run address, referencing functions)
       OUTDIR/modules.tsv    (module table)

How it works: decodes the 113-entry module table (code/data load, exec, size),
disassembles each module's code as Thumb-2, finds function starts (BL targets and
PUSH {..lr} prologues), resolves PC-relative literal loads, and when a literal
points at printable text in the same module (or the resident module 0), records
the string against the function. Overlays share run addresses, so every lookup
is done module-first.
"""
import os, re, struct, sys
import capstone

BASE = 0x03050000

def load_modules(d):
    n = struct.unpack_from("<I", d, 4)[0]
    mods = []
    for i in range(n):
        cl, ce, cs, dl, de, ds, ze, zs = struct.unpack_from("<8I", d, 8 + 32 * i)
        mods.append(dict(i=i, cl=cl, ce=ce, cs=cs, dl=dl, de=de, ds=ds, ze=ze, zs=zs))
    return mods

def exec_to_file(m, a):
    if m["ce"] <= a < m["ce"] + m["cs"]: return m["cl"] - BASE + (a - m["ce"])
    if m["de"] <= a < m["de"] + m["ds"]: return m["dl"] - BASE + (a - m["de"])
    return None

PRINT = re.compile(rb"[\x20-\x7e\t\r\n]{4,200}")

def string_at(d, off):
    if off is None or off < 0 or off >= len(d): return None
    m = PRINT.match(d, off)
    if not m: return None
    end = m.end()
    if end < len(d) and d[end] != 0: return None
    s = m.group().decode()
    return s if sum(c.isalpha() for c in s) >= 3 else None

def thumb_bl_target(ins):
    if ins.mnemonic in ("bl", "blx") and ins.operands and ins.operands[0].type == capstone.arm.ARM_OP_IMM:
        return ins.operands[0].imm
    return None

def analyse(d):
    mods = load_modules(d)
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    md.detail = True
    md.skipdata = True
    funcs, strings = {}, {}
    for m in mods:
        if not m["cs"]: continue
        off = m["cl"] - BASE
        code = d[off:off + m["cs"]]
        ins = list(md.disasm(code, m["ce"]))
        starts = set()
        for k, x in enumerate(ins):
            if x.mnemonic in ("push", "push.w") and "lr" in x.op_str: starts.add(x.address)
            t = thumb_bl_target(x)
            if t is not None and m["ce"] <= t < m["ce"] + m["cs"]: starts.add(t & ~1)
        order = sorted(starts)
        idx = {a: n for n, a in enumerate(order)}
        cur = None
        for x in ins:
            if x.address in idx:
                cur = (m["i"], x.address)
                funcs[cur] = dict(mod=m["i"], addr=x.address, end=x.address, calls=0, strs=[])
            if cur is None: continue
            f = funcs[cur]; f["end"] = x.address + x.size
            if thumb_bl_target(x) is not None: f["calls"] += 1
            if x.mnemonic in ("adr", "adr.w") and len(x.operands) >= 2:
                # ARMCC addresses most strings PC-relative: target = Align(PC,4) + imm
                t = ((x.address + 4) & ~3) + x.operands[1].imm
                s = string_at(d, exec_to_file(m, t))
                if s:
                    if s not in f["strs"]: f["strs"].append(s)
                    strings.setdefault((s, t), set()).add(f"m{m['i']}:{f['addr']:08X}")
                continue
            if x.mnemonic.startswith("ldr") and x.operands and len(x.operands) > 1:
                op = x.operands[1]
                if op.type == capstone.arm.ARM_OP_MEM and op.mem.base == capstone.arm.ARM_REG_PC:
                    la = ((x.address + 4) & ~3) + op.mem.disp
                    lo = exec_to_file(m, la)
                    if lo is None or lo + 4 > len(d): continue
                    v = struct.unpack_from("<I", d, lo)[0]
                    for mm in (m, mods[0]):
                        s = string_at(d, exec_to_file(mm, v))
                        if s:
                            if s not in f["strs"]: f["strs"].append(s)
                            strings.setdefault((s, v), set()).add(f"m{m['i']}:{f['addr']:08X}")
                            break
    return mods, funcs, strings

def hint(strs):
    for s in strs:
        mm = re.search(r"([\w]+)\.c\b", s)
        if mm: return mm.group(1)
    for s in strs:
        mm = re.match(r"\s*([A-Za-z_][\w ]{3,30})", s)
        if mm: return mm.group(1).strip().replace(" ", "_")
    return ""

def main():
    code_bin, out = sys.argv[1], sys.argv[2]
    d = open(code_bin, "rb").read()
    mods, funcs, strings = analyse(d)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "modules.tsv"), "w") as f:
        f.write("mod\tcode_exec\tcode_size\tcode_file\tdata_exec\tdata_size\tzi_exec\tzi_size\n")
        for m in mods:
            f.write(f"{m['i']}\t{m['ce']:08X}\t{m['cs']:X}\t{m['cl']-BASE:X}\t{m['de']:08X}\t{m['ds']:X}\t{m['ze']:08X}\t{m['zs']:X}\n")
    clean = lambda s: s.replace("\t", " ").replace("\r", " ").replace("\n", "\\n")
    with open(os.path.join(out, "functions.tsv"), "w") as f:
        f.write("mod\taddr\tsize\tcalls\thint\tstrings\n")
        for k in sorted(funcs):
            x = funcs[k]
            f.write(f"{x['mod']}\t{x['addr']:08X}\t{x['end']-x['addr']}\t{x['calls']}\t{hint(x['strs'])}\t{' | '.join(clean(s) for s in x['strs'][:8])}\n")
    with open(os.path.join(out, "strings.tsv"), "w") as f:
        f.write("string\taddr\tfunctions\n")
        for (s, v), fs in sorted(strings.items()):
            f.write(f"{clean(s)}\t{v:08X}\t{' '.join(sorted(fs))}\n")
    named = sum(1 for x in funcs.values() if x["strs"])
    print(f"{len(mods)} modules, {len(funcs)} functions ({named} reference strings), {len(strings)} distinct strings -> {out}")

if __name__ == "__main__":
    main()
