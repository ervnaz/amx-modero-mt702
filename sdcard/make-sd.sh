#!/bin/bash
# Assemble the Debian boot SD for the AMX Modero (i.MX6Q).
# Layout: U-Boot(SPL) at raw 1KiB; one ext4 partition (root) holding the rootfs
# plus /boot (zImage + sabresd dtb + extlinux.conf). Run as root:
#   sudo bash make-sd.sh
set -e
DEV=/dev/sdb
SRC=/home/ervin/modero-debian
MNT=/mnt/modero_sd

[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }

# ---- SAFETY: refuse anything that isn't the 29GB removable USB card ----
tran=$(lsblk -dn -o TRAN  "$DEV" 2>/dev/null)
hp=$(  lsblk -dn -o HOTPLUG "$DEV" 2>/dev/null)
szb=$( lsblk -dn -b -o SIZE "$DEV" 2>/dev/null)
echo ">> target $DEV : tran=$tran hotplug=$hp size=$szb bytes"
[ "$tran" = usb ] || { echo "ABORT: $DEV is not USB"; exit 1; }
[ "$hp" = "1" ]   || { echo "ABORT: $DEV is not hot-pluggable"; exit 1; }
[ "$szb" -gt 8000000000 ] && [ "$szb" -lt 70000000000 ] || { echo "ABORT: $DEV size out of expected range"; exit 1; }
case "$(lsblk -dn -o NAME $DEV)" in nvme*|mmcblk*) echo "ABORT: refusing $DEV"; exit 1;; esac

echo ">> unmounting any mounted partitions on $DEV"
umount ${DEV}*  2>/dev/null || true
umount $MNT     2>/dev/null || true

echo ">> partitioning $DEV (msdos, 1x ext4 from 4MiB)"
wipefs -a "$DEV"
parted -s "$DEV" mklabel msdos
parted -s "$DEV" mkpart primary ext4 4MiB 100%
partprobe "$DEV"; sleep 1
echo ">> mkfs.ext4 on ${DEV}1"
mkfs.ext4 -F -q -L rootfs "${DEV}1"

echo ">> mounting + copying rootfs (823MB, ~1-2 min)"
mkdir -p $MNT
mount "${DEV}1" $MNT
cp -a "$SRC/rootfs/." "$MNT/"

echo ">> installing /boot (kernel + dtb + extlinux)"
mkdir -p "$MNT/boot/extlinux"
cp "$SRC/linux/arch/arm/boot/zImage"                              "$MNT/boot/zImage"
cp "$SRC/linux/arch/arm/boot/dts/nxp/imx/imx6q-sabresd.dtb"       "$MNT/boot/imx6q-sabresd.dtb"
cp "$SRC/boot.scr"                                                "$MNT/boot/boot.scr"   # DCD U-Boot boots this
cat > "$MNT/boot/extlinux/extlinux.conf" <<EOF
default debian
timeout 30
menu title Modero Debian
label debian
    kernel /boot/zImage
    fdt /boot/imx6q-sabresd.dtb
    append console=ttymxc0,115200 earlycon=ec_imx6q,0x02020000,115200 root=/dev/mmcblk0p1 rootwait rw
EOF
sync
umount $MNT
rmdir $MNT 2>/dev/null || true

echo ">> writing U-Boot (non-SPL/DCD, DDR via boot-ROM DCD) to $DEV at 1KiB offset"
dd if="$SRC/u-boot-modero-dcd.imx" of="$DEV" bs=1K seek=1 conv=fsync status=none
sync
echo ""
echo "=== SD READY ==="
echo "  $DEV : U-Boot@1KiB + ext4 root (rootfs + /boot/zImage + sabresd dtb + extlinux)"
echo "  Serial login over the console: root / modero"
echo "  Eject, put it in the panel, power on, watch the XIAO console at 115200."
