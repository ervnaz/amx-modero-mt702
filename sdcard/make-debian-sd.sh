#!/bin/bash
# Build a Debian SD for the AMX Modero MT-702, matching the uboot-imx (NXP
# plugin) boot environment: mmc1 p1 = FAT (zImage/dtb/boot.scr), p2 = ext4 root.
# U-Boot (plugin image) goes at the 1 KiB offset. Auto-detects the ~16GB Apacer.
# Run:  sudo bash make-debian-sd.sh --yes
set -euo pipefail

# capture --yes BEFORE we reuse the positional params for device detection
WANT_YES=no
for a in "$@"; do [ "$a" = "--yes" ] && WANT_YES=yes; done

BASE=/home/ervin/modero-debian
UBOOT="$BASE/u-boot-modero-nxp-ref2.imx"
ZIMAGE="$BASE/linux/arch/arm/boot/zImage"
DTB="$BASE/linux/arch/arm/boot/dts/nxp/imx/imx6q-sabresd.dtb"
BOOTSCR="$BASE/boot.scr"
ROOTFS="$BASE/rootfs"

for f in "$UBOOT" "$ZIMAGE" "$DTB" "$BOOTSCR"; do
  [ -f "$f" ] || { echo "MISSING: $f"; exit 1; }
done
[ -d "$ROOTFS" ] || { echo "MISSING rootfs dir: $ROOTFS"; exit 1; }

# --- auto-detect the ~16GB removable USB card (the Apacer) ---
cands=""
for d in /sys/block/sd*; do
  dev=/dev/$(basename "$d")
  tran=$(lsblk -dn -o TRAN "$dev"); rm=$(lsblk -dn -o RM "$dev"); sz=$(lsblk -dn -b -o SIZE "$dev")
  if [ "$tran" = usb ] && [ "$rm" = 1 ] && [ "$sz" -gt 14000000000 ] && [ "$sz" -lt 17000000000 ]; then
    cands="$cands $dev"
  fi
done
set -- $cands
[ $# -eq 1 ] || { echo "ABORT: expected exactly one ~16GB removable USB card, found: [$cands]"; lsblk -dn -o NAME,SIZE,TRAN,RM,MODEL; exit 1; }
DEV=$1
echo ">> target: $DEV ($(lsblk -dn -o SIZE,MODEL "$DEV"))"

if [ "$WANT_YES" != "yes" ]; then
  echo ">> This ERASES $DEV (the Apacer's stock Android) and installs Debian."
  echo ">> Stock is backed up at ~/amx-panel-backup/stock-sd-full.img — restorable."
  echo ">> Re-run with --yes to proceed:  sudo bash $0 --yes"
  exit 1
fi

umount ${DEV}?* 2>/dev/null || true
wipefs -a "$DEV" >/dev/null 2>&1 || true

echo ">> partitioning (p1 FAT 128MiB boot, p2 ext4 root)..."
parted -s "$DEV" mklabel msdos
parted -s "$DEV" mkpart primary fat32 4MiB 132MiB
parted -s "$DEV" mkpart primary ext4 132MiB 100%
parted -s "$DEV" set 1 boot on
partprobe "$DEV"; sleep 1.5

P1=${DEV}1; P2=${DEV}2
echo ">> formatting..."
mkfs.vfat -F 32 -n BOOT "$P1" >/dev/null
mkfs.ext4 -F -q -L rootfs "$P2"

MNT=$(mktemp -d)
mkdir -p "$MNT/p1" "$MNT/p2"
mount "$P1" "$MNT/p1"
mount "$P2" "$MNT/p2"

echo ">> copying boot files to FAT p1..."
cp "$ZIMAGE" "$MNT/p1/zImage"
cp "$DTB"    "$MNT/p1/imx6q-sabresd.dtb"
cp "$BOOTSCR" "$MNT/p1/boot.scr"

echo ">> copying rootfs to ext4 p2 (823MB, a few minutes)..."
cp -a "$ROOTFS"/. "$MNT/p2"/
sync

umount "$MNT/p1" "$MNT/p2"
rmdir "$MNT/p1" "$MNT/p2" "$MNT"

echo ">> writing U-Boot plugin image at 1 KiB offset..."
dd if="$UBOOT" of="$DEV" bs=1K seek=1 conv=fsync,notrunc status=none
sync
echo ">> IVT: $(dd if="$DEV" bs=1K skip=1 count=1 2>/dev/null | od -An -tx1 | head -1)"
echo ">> DONE. Cold-boot the Apacer in the panel."
