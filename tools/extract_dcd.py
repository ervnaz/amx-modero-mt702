import struct,sys
data=open('stock-uboot-region.bin','rb').read()
def find_ivt(d):
    for off in range(0,0x8000):
        if d[off]==0xD1 and d[off+1]==0x00 and d[off+2]==0x20 and d[off+3] in (0x40,0x41,0x42,0x43):
            # sanity: self ptr should look like a DDR/OCRAM addr
            return off
    return None
ivt=find_ivt(data)
if ivt is None: print("no IVT found"); sys.exit(1)
hdr,entry,res1,dcd,boot_data,selfp,csf,res2=struct.unpack('<8I',data[ivt:ivt+32])
print("IVT@0x%x  entry=0x%08x self=0x%08x dcd=0x%08x boot_data=0x%08x"%(ivt,entry,selfp,dcd,boot_data))
if dcd==0: print("DCD ptr is 0 (DDR init may be in code, not DCD)"); sys.exit(2)
dcd_off=dcd-selfp+ivt
tag=data[dcd_off]; dlen=(data[dcd_off+1]<<8)|data[dcd_off+2]; ver=data[dcd_off+3]
print("DCD@0x%x tag=0x%02x len=%d ver=0x%02x"%(dcd_off,tag,dlen,ver))
if tag!=0xD2: print("not a DCD tag!"); sys.exit(3)
p=dcd_off+4; end=dcd_off+dlen; writes=[]; checks=0
while p<end:
    ctag=data[p]; clen=(data[p+1]<<8)|data[p+2]; param=data[p+3]
    if ctag==0xCC:
        n=(clen-4)//8; q=p+4
        for i in range(n):
            a,v=struct.unpack('>II',data[q:q+8]); q+=8; writes.append((a,v))
    elif ctag==0xCF:
        checks+=1
    p+=clen if clen else 4
print("write-commands pairs:%d  check-data cmds:%d"%(len(writes),checks))
out=open('amx-dcd.cfg','w')
out.write("/* AMX Modero i.MX6Q DCD extracted from stock U-Boot 2009.08 */\n")
for a,v in writes:
    out.write("DATA 4 0x%08x 0x%08x\n"%(a,v))
out.close()
print("wrote amx-dcd.cfg (%d DATA lines)"%len(writes))
# show the MMDC/DDR-relevant ones (0x021b_xxxx = MMDC, 0x020e_xxxx = IOMUX)
print("--- first 12 + any MMDC (0x021b):")
for a,v in writes[:12]: print("  0x%08x = 0x%08x"%(a,v))
mmdc=[(a,v) for a,v in writes if 0x021b0000<=a<=0x021bffff]
print("  ...MMDC regs:%d  IOMUX regs:%d"%(len(mmdc),len([1 for a,v in writes if 0x020e0000<=a<=0x020effff])))
