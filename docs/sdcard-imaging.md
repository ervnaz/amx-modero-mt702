# SD-card imaging and card compatibility

How to image microSD cards for the AMX Modero MT-702 (i.MX6Q), and which cards actually boot. The i.MX6 boot ROM has an impatient SD init that some cards cannot satisfy on a cold boot.

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

## Card compatibility — it's a cold-start timing race

The i.MX6 boot ROM's SD init is impatient: it sends a single `CMD0` with **no retry**, uses a minimal power-on wait, and never power-cycles the card. On a true **cold boot** (power fully removed), a card whose controller is still powering up when the ROM fires that one `CMD0` misses the window, and boot fails with no second attempt. A quick **warm power-cycle** leaves the card already initialized, so it boots.

Tested empirically on this panel (full stock image written to each card, then cold boot vs. quick warm power-cycle):

| microSD card | Controller (mfg ID) | Cold boot | Warm cycle |
|---|---|---|---|
| Apacer Industrial 16 GB | Phison (0x27) | YES | YES |
| Samsung 32 GB | Samsung (0x1b) | NO | YES |
| Kioxia 32 GB EXCERIA | Toshiba (0x02) | NO | YES |
| Kingston 2 GB | Toshiba (0x02) | NO | (not retested warm) |

**The variable is cold-start readiness, not the controller vendor.** An earlier reading of this data — "Toshiba fails, Phison/Samsung work" — was a small-sample artifact: once each consumer card was given a warm power-cycle, both the Samsung *and* the Kioxia booted. The common factor is that both consumer cards lose the ROM's cold-start race and both win it warm; the Apacer industrial card wins even cold because it powers up fast and deterministically.

- It is not about capacity, SDHC vs SDSC, speed class, or controller vendor.
- It is not a vendor lock: the stock OCRAM plugin never reads the SD CID, and the boot-config fuses (OCOTP) are blank (BT_FUSE_SEL=0, boots from GPIO straps).
- Additional ROM stressor: the ROM also performs an **unverified** `CMD6` high-speed switch to 49.5 MHz (it never checks the switch-status result), which can hurt marginal cards — but the dominant observed failure is the cold-start race above.

### Practical rule

For an always-on panel, **cold-boot reliability is the requirement**: a power outage must bring it back unattended, with nobody there to warm-cycle it. Use a card proven to boot reliably from **cold** — the **Apacer-class industrial card** is proven here. Consumer cards (Samsung, Kioxia) booted only after a manual warm power-cycle, which is unacceptable for an unattended appliance.

Always validate a candidate card with a real **cold boot** (power fully removed for several seconds), never just a warm reboot. Reading the card's controller/manufacturer ID (e.g. its CID via an ESP32 with an SD slot) is useful for inventory, but it does **not** predict cold-boot success — only a real cold boot does.
