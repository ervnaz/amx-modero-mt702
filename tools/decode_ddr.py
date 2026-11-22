regs={}
for line in open('ddr-regs.txt'):
    line=line.strip()
    if not line or line.startswith('#') or line.startswith('###'): continue
    a,v=line.split()
    regs[int(a,16)]=int(v,16)
def R(a): return regs.get(a,0)
def bits(v,hi,lo): return (v>>lo)&((1<<(hi-lo+1))-1)

MDCTL=R(0x021b0000); MDPDC=R(0x021b0004); MDOTC=R(0x021b0008)
MDCFG0=R(0x021b000c); MDCFG1=R(0x021b0010); MDCFG2=R(0x021b0014)
MDMISC=R(0x021b0018); MDREF=R(0x021b0020); MDRWD=R(0x021b002c)
MDOR=R(0x021b0030); MDASP=R(0x021b0040)

print("==== GEOMETRY (MDCTL=0x%08x) ===="%MDCTL)
row=bits(MDCTL,26,24); col=bits(MDCTL,22,20); bl=bits(MDCTL,19,19); dsiz=bits(MDCTL,17,16)
print(" SDE0=%d SDE1=%d  ROW=%d(->%d bits)  COL=%d(->%d bits)  BL=%s  DSIZ=%d(->%d-bit bus)"%(
  bits(MDCTL,31,31),bits(MDCTL,30,30),row,row+11,col,[9,10,11,12,8,0,0,0][col],"8" if bl else "4",dsiz,[16,32,64,0][dsiz]))
print(" CS0_END(MDASP)=0x%02x -> density boundary"%bits(MDASP,6,0))

print("==== TIMING ====")
print(" MDCFG0=0x%08x: tRFC=%d tXS=%d tXP=%d tXPDLL=%d tFAW=%d tCL=%d(CL=%d)"%(
  MDCFG0,bits(MDCFG0,31,24)+1,bits(MDCFG0,23,16)+1,bits(MDCFG0,15,13)+1,bits(MDCFG0,12,9)+1,bits(MDCFG0,8,4)+1,bits(MDCFG0,3,0),bits(MDCFG0,3,0)+3))
print(" MDCFG1=0x%08x: tRCD=%d tRP=%d tRC=%d tRAS=%d tRPA=%d tWR=%d tMRD=%d tCWL=%d(CWL=%d)"%(
  MDCFG1,bits(MDCFG1,31,29)+1,bits(MDCFG1,28,26)+1,bits(MDCFG1,25,21)+1,bits(MDCFG1,20,16)+1,bits(MDCFG1,15,15),bits(MDCFG1,12,9)+1,bits(MDCFG1,8,5)+1,bits(MDCFG1,2,0),bits(MDCFG1,2,0)+2))
print(" MDCFG2=0x%08x: tDLLK=%d tRTP=%d tWTR=%d tRRD=%d"%(
  MDCFG2,bits(MDCFG2,15,16-16)+0,bits(MDCFG2,2,0)+1,bits(MDCFG2,5,3)+1,bits(MDCFG2,8,6)+1))
print(" MDOTC=0x%08x  MDRWD=0x%08x  MDOR=0x%08x"%(MDOTC,MDRWD,MDOR))
print(" MDMISC=0x%08x: WALAT=%d RALAT=%d BI_ON=%d MIF3=%d DDR_TYPE=%d ADDR_MIRROR=%d"%(
  MDMISC,bits(MDMISC,17,16),bits(MDMISC,8,6),bits(MDMISC,12,12),bits(MDMISC,10,9),bits(MDMISC,4,3),bits(MDMISC,19,19)))
print(" MDREF=0x%08x: REF_SEL=%d REFR=%d"%(MDREF,bits(MDREF,15,14),bits(MDREF,13,11)))
print(" MDPDC=0x%08x  MDOR=0x%08x: tXPR=%d SDE_TO_RST=%d RST_TO_CKE=%d"%(
  MDPDC,MDOR,bits(MDOR,31,24),bits(MDOR,13,8),bits(MDOR,5,0)))

print("==== CALIBRATION (mx6_mmdc_calibration struct) ====")
for nm,off in [("mpwldectrl0",0x80c),("mpwldectrl1",0x810),("mpdgctrl0",0x83c),
               ("mpdgctrl1",0x840),("mprddlctl",0x848),("mpwrdlctl",0x850),("mpzqhwctrl",0x800)]:
    print("  p0_%-11s=0x%08x   p1_%-11s=0x%08x"%(nm,R(0x021b0000+off),nm,R(0x021b4000+off)))

print("==== CLOCK estimate ====")
# CL from MDCFG0, common DDR3 speed bins: if CL~7-8 at these timings -> ~528MHz (DDR3-1066)
print("  CL=%d CWL=%d tRFC=%d  -> compare to DDR3 speed bins (528MHz/1066 typical for i.MX6Q)"%(
  bits(MDCFG0,3,0)+3, bits(MDCFG1,2,0)+2, bits(MDCFG0,31,24)+1))
