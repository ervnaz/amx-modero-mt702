# Building the modern U-Boot that actually boots the Modero MT-702

This is the U-Boot that boots the panel (`u-boot-modero-nxp-ref2.imx`). Debian 12 +
kernel 6.6 boot from it to a root shell over the serial console.

## Why the NXP uboot-imx fork (not mainline)
This board's i.MX6 boot ROM runs only **plugin=1** images, and in practice only the
NXP **uboot-imx** fork's i.MX6 plugin format is accepted — mainline's imximage
plugin and our hand-built DCD/plugin images are all silent (the ROM never executes
them). Confirmed by booting the reference build on a ROM-bootable card: it banners.

## Source + config
```
git clone https://github.com/nxp-imx/uboot-imx -b imx_v2020.04_5.4.70_2.3.0
cd uboot-imx
export ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf-
make mx6qsabresd_plugin_defconfig     # CONFIG_USE_IMXIMG_PLUGIN=y; plugin @ 0x00907000
make -j4 u-boot-dtb.imx               # -> u-boot-dtb.imx (== u-boot-modero-nxp-ref2.imx)
```

## The one required source patch
`board/freescale/common/pfuze.c`, in `pfuze_mode_init()`: the SABRE PFUZE100 PMIC is
unreachable over I2C on the Modero (reads come back as garbage), so the unknown
device-id branch returns `-EINVAL`, which is **fatal** to U-Boot's init sequence
(`### ERROR ### Please RESET the board ###`). Make it non-fatal — the board runs on
the PMIC's power-on-default rails (stock proves the rails are fine):

```diff
-		printf("Not supported, id=%d\n", id);
-		return -EINVAL;
+		printf("Not supported, id=%d (PMIC unreachable); skipping PMIC mode init\n", id);
+		return 0; /* MODERO: non-fatal - board runs on PMIC power-on defaults */
```

## DDR note
Uses the **reference** mx6qsabresd DDR, which brings up **1 GB** of the board's 2 GB
— enough to boot. The board's live-extracted DDR register values do **not** work as a
cold-start init (silent); a proper 2 GB cold-start DDR init is future work.

## Boot environment (sabresd default) and the SD card
- SD enumerates as **mmc1**. Env wants **p1 = FAT** (zImage + dtb + boot.scr) and
  **p2 = ext4** root → `root=/dev/mmcblk1p2`, console `ttymxc0,115200`,
  kernel → `0x12000000`, dtb → `0x18000000`, `bootz`.
- **Phantom write-protect:** the sabresd dtb has `wp-gpios` on
  `/soc/bus@2100000/mmc@2194000`; the Modero has no WP line so it reads "protected",
  the card is forced read-only, and root mount fails with `-EROFS`. `boot.scr` fixes
  it by patching the live DTB: `fdt set /soc/bus@2100000/mmc@2194000 disable-wp`.

Flash `u-boot-modero-nxp-ref2.imx` at the 1 KiB offset and build the card with
`../sdcard/make-debian-sd.sh --yes` (auto-detects the ~16 GB Apacer).

## Cold-boot / power caveat
Cold-boot reliability depends on the power source: a weak **passive PoE injector**
(e.g. 48 V 0.5 A / 24 W) sags on cold inrush and the i.MX6 ROM loses its cold-start
SD race (needs a warm power-cycle). A proper **PoE switch** or an active 802.3at
injector cold-boots reliably. This is a power-delivery issue, independent of U-Boot.
