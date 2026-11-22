#!/bin/bash
# Read-only full image of the STOCK AMX microSD, for offline analysis + backup.
# It ONLY reads the card — never writes. Run:  sudo bash image-stock.sh
set -e
DEV=/dev/sdb
OUT=/home/ervin/amx-panel-backup/stock-sd-full.img
[ "$(id -u)" = 0 ] || { echo "run as root: sudo bash image-stock.sh"; exit 1; }
[ -b "$DEV" ] || { echo "No $DEV — plug the STOCK card into the reader first."; exit 1; }
szb=$(lsblk -dn -b -o SIZE "$DEV"); tran=$(lsblk -dn -o TRAN "$DEV")
echo ">> $DEV: $szb bytes (tran=$tran)"
[ "$tran" = usb ] || { echo "ABORT: $DEV is not USB."; exit 1; }
# stock card is ~16GB; refuse the ~29GB Debian card by mistake
[ "$szb" -lt 20000000000 ] || { echo "ABORT: $DEV >20GB — that's the Debian card, not stock. Aborting."; exit 1; }
echo ">> READ-ONLY imaging (this cannot modify the card) -> $OUT"
dd if="$DEV" of="$OUT" bs=4M conv=noerror,sync status=progress
sync
echo "=== DONE: $OUT ($(du -h "$OUT" | cut -f1)). Stock card untouched. ==="
