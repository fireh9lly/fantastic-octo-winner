#!/usr/bin/env python3
"""Check every code patch's expected original bytes against the new firmware, allowing for relocation.

  port_patches.py OLD_TREE OLD_BUILD_DIR NEW_TREE NEW_BUILD_DIR OLD_CODE_BIN NEW_CODE_BIN PATCH[,PATCH...] [--json OUT]

OLD_TREE / NEW_TREE: source trees (V1.7.8 addresses / translated addresses); *_BUILD_DIR: the unpacked directory
patch_code.py would read (helpers.json, npui.json, e21.json, e22.json), e.g. build/d1h_e.

Both trees' patch lists are generated in the same order, so entry k of each is the same patch. For each entry the
V1.7.8 original bytes are compared with the bytes actually found at the translated site in the new image:
  identical     same bytes
  relocated     same instructions; branch/call targets and literal values differ exactly by the translation
  DIFFERENT     anything else: needs a human
For "relocated" entries the new original bytes are reported (and written with --json) so the patch table can be
updated to the new firmware's real bytes.
"""
import importlib.util, json, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone, xlate  # noqa: E402


def load_patch_code(tree, build_dir):
    spec = importlib.util.spec_from_file_location("pc_" + str(abs(hash(tree))), os.path.join(tree, "tools", "patch_code.py"))
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.join(tree, "tools"))
    spec.loader.exec_module(m)
    sys.path.pop(0)
    m.SRC_DIR = build_dir
    return m


def entries(pc, names):
    out = []
    for name in names:
        for e in (pc.GENERATED[name]() if name in pc.GENERATED else pc.PATCHES[name]):
            out.append((name,) + tuple(e))
    return out


def insns(data, addr):
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB | capstone.CS_MODE_MCLASS)
    md.detail = True
    md.skipdata = True
    return list(md.disasm(data, addr))


def equivalent(x, mod, old_addr, old_bytes, new_addr, new_bytes):
    """(ok, why): same instructions up to relocation"""
    if len(old_bytes) != len(new_bytes):
        return False, "length differs"
    if len(old_bytes) == 4 and old_addr % 4 == 0:              # a literal word (pointer)
        ov, nv = struct.unpack("<I", old_bytes)[0], struct.unpack("<I", new_bytes)[0]
        tv, how = x.value(ov)
        if tv == nv:
            return True, f"literal {ov:#x} -> {nv:#x} ({how})"
    a, b = insns(old_bytes, old_addr), insns(new_bytes, new_addr)
    if len(a) != len(b):
        return False, "instruction count differs"
    why = []
    for i, j in zip(a, b):
        if i.bytes == j.bytes:
            continue
        if not (i.id and j.id) or i.mnemonic != j.mnemonic:
            return False, f"{i.mnemonic} {i.op_str} vs {j.mnemonic} {j.op_str}"
        io, jo = i.operands, j.operands
        if i.mnemonic.startswith(("b", "cbz", "cbnz")) and io and io[-1].type == capstone.arm.ARM_OP_IMM:
            t = io[-1].imm
            mt = 0 if 0x03050000 <= t < 0x0307E300 else mod
            nt, how = x.code(mt, t)
            if nt is None or (nt & ~1) != jo[-1].imm:
                return False, f"{i.mnemonic} to {t:#x} -> expected {nt and hex(nt)}, found {jo[-1].imm:#x}"
            why.append(f"{i.mnemonic} {t:#x}->{jo[-1].imm:#x}")
            continue
        if i.mnemonic.startswith("ldr") and len(io) > 1 and io[1].type == capstone.arm.ARM_OP_MEM \
                and io[1].mem.base == capstone.arm.ARM_REG_PC:
            ov = x.o.word(mod, ((i.address + 4) & ~3) + io[1].mem.disp)
            nv = x.n.word(mod, ((j.address + 4) & ~3) + jo[1].mem.disp)
            tv, how = x.value(ov) if ov is not None else (None, "")
            if i.op_str.split(",")[0] == j.op_str.split(",")[0] and tv is not None and tv == nv:
                why.append(f"ldr literal {ov:#x}->{nv:#x}")
                continue
            return False, f"literal load {ov and hex(ov)} -> expected {tv and hex(tv)}, found {nv and hex(nv)}"
        return False, f"{i.mnemonic} {i.op_str} vs {j.mnemonic} {j.op_str}"
    return True, "; ".join(why)


def main():
    old_tree, old_build, new_tree, new_build, old_bin, new_bin, names = sys.argv[1:8]
    names = names.split(",")
    x = xlate.load(old_bin, new_bin)
    old_e = entries(load_patch_code(old_tree, old_build), names)
    new_e = entries(load_patch_code(new_tree, new_build), names)
    assert len(old_e) == len(new_e), f"patch lists differ in length: {len(old_e)} vs {len(new_e)}"
    report, counts = [], {}
    for (name, mod, oa, oold, _), (name2, mod2, na, nold, _) in zip(old_e, new_e):
        assert name == name2 and mod == mod2, (name, name2, mod, mod2)
        if oold is None:
            st, why, have = "dead-code", "no original bytes checked", None
        else:
            n = len(oold) // 2
            o = xlate.fwmap.exec_to_file(x.n.mods[mod], na)
            have = x.n.d[o:o + n].hex() if o is not None else None
            if have == oold:
                st, why = "identical", ""
            elif have is None:
                st, why = "DIFFERENT", f"{na:#x} is outside module {mod}"
            else:
                ok, why = equivalent(x, mod, oa, bytes.fromhex(oold), na, bytes.fromhex(have))
                st = "relocated" if ok else "DIFFERENT"
        counts[st] = counts.get(st, 0) + 1
        report.append(dict(patch=name, module=mod, old=f"{oa:#x}", new=f"{na:#x}", status=st, why=why,
                           old_bytes=oold, new_bytes=have))
        if st not in ("identical", "dead-code"):
            print(f"{st:9s} {name:22s} m{mod:<3} {oa:#x} -> {na:#x}  {why}")
    print("summary:", counts)
    if "--json" in sys.argv:
        json.dump(report, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)


if __name__ == "__main__":
    main()
