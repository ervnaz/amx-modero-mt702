#!/bin/bash
# Re-write ONLY U-Boot on the Debian SD (rootfs/kernel untouched).
# Safety: refuses unless /dev/sdb is the 29GB USB hot-plug card AND carries an
# ext4 partition labelled 'rootfs' (i.e. our Debian card, NOT the stock Android card).
set -e
DEV=/dev/sdb
IMG=/home/ervin/modero-debian/u-boot-modero-dcd.imx
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }

tran=$(lsblk -dn -o TRAN "$DEV" 2>/dev/null); hp=$(lsblk -dn -o HOTPLUG "$DEV" 2>/dev/null)
szb=$(lsblk -dn -b -o SIZE "$DEV" 2>/dev/null)
[ "$tran" = usb ] && [ "$hp" = 1 ] || { echo "ABORT: $DEV not USB hot-plug"; exit 1; }
[ "$szb" -gt 8000000000 ] && [ "$szb" -lt 70000000000 ] || { echo "ABORT: $DEV size wrong"; exit 1; }
# MUST be our Debian card: has an ext4 partition labelled rootfs
if ! lsblk -no FSTYPE,LABEL "$DEV" | grep -q 'ext4 *rootfs'; then
  echo "ABORT: $DEV has no ext4 'rootfs' partition — this is NOT the Debian card."
  echo "       (refusing, so we don't overwrite the stock backup). Partitions seen:"
  lsblk -no NAME,FSTYPE,LABEL "$DEV"
  exit 1
fi
echo ">> target confirmed Debian card ($DEV, $szb bytes)"
umount ${DEV}* 2>/dev/null || true
echo ">> writing new U-Boot (DDR-fixed) to 1KiB offset"
dd if="$IMG" of="$DEV" bs=1K seek=1 conv=fsync status=none
sync
echo ">> verifying what's actually on the card now..."
if dd if="$DEV" bs=1024 skip=1 count=760 2>/dev/null | strings | grep -qi 'U-Boot 20'; then
  echo "    ✓ VERIFIED: the DCD U-Boot IS on the card"
else
  echo "    ⚠ WARNING: 'U-Boot 20..' string NOT found on the card after write!"
fi
echo "=== U-BOOT UPDATED (DDR config patched). Rootfs/kernel untouched. ==="
echo "    Move the card to the panel, power on, watch the console."
