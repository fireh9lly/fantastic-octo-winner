#!/usr/bin/env python3
"""fwdis.py CODE_BIN MODULE ADDR [LEN] [--all] - disassemble with literal and ADR-string annotations."""
import os, sys, struct, capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fwmap
d=open(sys.argv[1],'rb').read(); mods=fwmap.load_modules(d); B=fwmap.BASE
mi=int(sys.argv[2]); s=int(sys.argv[3],16); n=int(sys.argv[4],0) if len(sys.argv)>4 and not sys.argv[4].startswith('--') else 0x100
stop='--all' not in sys.argv
m=mods[mi]; off=m['cl']-B
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS); md.detail=True; md.skipdata=True
for x in md.disasm(d[off+(s-m['ce']):off+(s-m['ce'])+n],s):
    extra=''
    if x.id and x.mnemonic.startswith('ldr') and len(x.operands)>1 and x.operands[1].type==capstone.arm.ARM_OP_MEM and x.operands[1].mem.base==capstone.arm.ARM_REG_PC:
        lo=fwmap.exec_to_file(m,((x.address+4)&~3)+x.operands[1].mem.disp)
        if lo is not None and lo+4<=len(d): extra=f'  ; ={struct.unpack_from("<I",d,lo)[0]:#010x}'
    if x.id and x.mnemonic in('adr','adr.w'):
        t=((x.address+4)&~3)+x.operands[1].imm; st=fwmap.string_at(d,fwmap.exec_to_file(m,t)); extra=f'  ; "{(st or "")[:50].strip()}"' if st else f'  ; ->{t:#x}'
    print(f'  {x.address:08x}: {x.mnemonic:8} {x.op_str}{extra}')
    if stop and x.mnemonic.startswith('pop') and 'pc' in x.op_str: break
    if stop and x.mnemonic=='bx' and x.op_str=='lr': break
