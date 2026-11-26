#!/usr/bin/env python3
"""xref.py CODE_BIN FUNCTIONS_TSV ADDR [DEPTH]  - print the caller tree of a run address (BL/B.W/literal pointer refs)."""
import sys, csv, struct, capstone
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fwmap
d=open(sys.argv[1],'rb').read(); mods=fwmap.load_modules(d); B=fwmap.BASE
funcs={}
for r in csv.DictReader(open(sys.argv[2]),delimiter='\t'):
    funcs.setdefault(int(r['mod']),[]).append((int(r['addr'],16),int(r['size']),r['hint'],r['strings'][:70]))
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS); md.detail=True; md.skipdata=True
ins={}
for m in mods:
    if m['cs']:
        off=m['cl']-B; ins[m['i']]=list(md.disasm(d[off:off+m['cs']],m['ce']))
def owner(mi,a):
    for fa,sz,h,s in funcs.get(mi,[]):
        if fa<=a<fa+sz: return fa,h,s
    return None,'',''
def callers(t):
    out=set()
    for mi,L in ins.items():
        m=mods[mi]
        for x in L:
            if x.mnemonic in('bl','b.w','b','blx') and x.operands and x.operands[0].type==capstone.arm.ARM_OP_IMM and x.operands[0].imm==t:
                out.add((mi,owner(mi,x.address)[0],'call'))
            if x.mnemonic.startswith('ldr') and len(x.operands)>1 and x.operands[1].type==capstone.arm.ARM_OP_MEM and x.operands[1].mem.base==capstone.arm.ARM_REG_PC:
                lo=fwmap.exec_to_file(m,((x.address+4)&~3)+x.operands[1].mem.disp)
                if lo is not None and lo+4<=len(d) and struct.unpack_from('<I',d,lo)[0] in (t,t|1):
                    out.add((mi,owner(mi,x.address)[0],'ptr'))
    return sorted(out,key=lambda r:(r[0],r[1] or 0))
def walk(t,depth,ind=0,seen=set()):
    for mi,fa,kind in callers(t):
        if fa is None: continue
        _,h,s=owner(mi,fa)
        print('  '*ind+f'<- m{mi} {fa:08X} [{kind}] {h} :: {s}')
        if depth>1 and (mi,fa) not in seen:
            seen.add((mi,fa)); walk(fa,depth-1,ind+1,seen)
t=int(sys.argv[3],16); print(f'{t:08X}'); walk(t,int(sys.argv[4]) if len(sys.argv)>4 else 3)
