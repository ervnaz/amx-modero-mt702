# SD-card imaging and card compatibility

How to image microSD cards for the AMX Modero MT-702 (i.MX6Q), and which cards actually boot. The i.MX6 boot ROM is picky about card controllers.

> **Safety:** every command below is run with `sudo`, and `/dev/sdX` is the card in a USB reader. **Always run `lsblk` first** and confirm `/dev/sdX` is the intended removable USB card and has the expected size. A wrong device name overwrites the wrong disk.

```
lsblk -o NAME,SIZE,MODEL,TRAN,RM
```

## Boot offset

The i.MX6 boot ROM reads the boot image starting at the 1 KiB offset (sector 2). `dd seek=1 bs=1K` (or `seek=2 bs=512`) places it correctly.

## Imaging commands

### 1. Write a U-Boot image to the boot sector

Writes only the ~660 KB bootloader region at the 1 KiB offset. Existing partitions are left intact.

```
sudo dd if=<uboot-image.imx> of=/dev/sdX bs=1K seek=1 conv=fsync
sync
```

### 2. Write the stock bootloader region (first 4 MB)

Use this to restore stock Android's bootloader, or to test whether a different card can boot the known-good stock bootloader.

```
sudo dd if=stock-uboot-region.bin of=/dev/sdX bs=1M conv=fsync
sync
```

### 3. Clone the full stock image (16 GB)

Gives a complete working Android.

```
sudo dd if=stock-sd-full.img of=/dev/sdX bs=4M conv=fsync status=progress
sync
```

### 4. Verify the IVT header at the 1 KiB offset

```
sudo dd if=/dev/sdX bs=1K skip=1 count=1 2>/dev/null | od -An -tx1 | head -1
```

`d1 00 20 40` is the i.MX6 IVT header tag (little-endian 0x402000d1). Expected first bytes by image type:

| Image type | First bytes | Meaning |
|---|---|---|
| Stock plugin image | `d1 00 20 40 58 74 90 00` | IVT header 0x402000d1, entry 0x00907458 in OCRAM (plugin image) |
| Custom plugin image | `d1 00 20 40 2c 74 90 00` | entry 0x0090742c in OCRAM |
| Non-plugin DCD image | `d1 00 20 40 00 00 80 17` | entry 0x17800000 in DDR |

### 5. Full custom Debian card (`sdcard/make-sd.sh`)

1. Partition the card: msdos label, one ext4 partition starting at 4 MiB.
2. `mkfs.ext4 -L rootfs` on that partition.
3. Copy the Debian rootfs.
4. Install `/boot`: zImage, device tree, `boot.scr`, `extlinux.conf`.
5. `dd` the U-Boot image to the 1 KiB offset, as in command 1.

## Card compatibility

The i.MX6 boot ROM reads SD in a conservative mode at power-on and only boots cards whose controller it tolerates. Tested empirically on this panel by writing the known-good stock bootloader to each card and booting:

| microSD card | Controller (SD manufacturer ID) | Boots the panel? |
|---|---|---|
| Apacer Industrial 16 GB | Phison (mfg 0x27) | YES |
| Samsung 32 GB | Samsung (mfg 0x1b) | YES |
| Kioxia 32 GB EXCERIA | Toshiba/Kioxia (mfg 0x02) | NO |
| Kingston 2 GB | Toshiba/Kioxia (mfg 0x02) | NO (rebranded Toshiba silicon) |

**Both Toshiba-controller cards fail; two different non-Toshiba controllers (Phison, Samsung) work.**

- It is not about capacity, SDHC vs SDSC, speed class, or any advertised spec: the failing cards differ from each other in all of those.
- It tracks only with the card's controller silicon and how it responds to the ROM's boot-time SD init.
- It is not a vendor lock: the stock OCRAM plugin never reads the SD CID, and the boot-config fuses (OCOTP) are blank (BT_FUSE_SEL=0, boots from GPIO straps).

### Practical rule

**Avoid Toshiba/Kioxia-controller cards (mfg 0x02).** Non-Toshiba cards (Phison, Samsung, likely SanDisk) work.

You can read any card's controller/manufacturer ID in about 10 seconds by reading its CID with an SD-capable microcontroller (for example an ESP32 board with an SD slot) before trusting it in the panel.
