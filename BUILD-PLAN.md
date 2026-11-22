# Debian on the AMX Modero MT-702 (i.MX6 Quad "Modero-X") — Build Plan

Target: lean Debian (bookworm, armhf) booting from a **new microSD**, running a
fullscreen kiosk browser at the HA dashboard. Board is **i.MX6 SABRE-SD class**, so we
base everything on the SABRE reference and change only the board-specific nodes.

Keep the ORIGINAL microSD untouched as the instant-revert backup. Build on a 2nd card.

## Hard prerequisite
- **USB-TTL serial adapter** on UART1 (`ttymxc0`, 115200 8N1) — the only way to see boot
  output and debug. The internal micro-USB is USB-OTG, not UART. Without this, bring-up is
  blind. (Cheap CP2102/FTDI 3.3 V adapter.)

## Toolchain (install once on the PC)
```
sudo apt install -y git bc bison flex libssl-dev make gcc-arm-linux-gnueabihf \
  u-boot-tools device-tree-compiler debootstrap qemu-user-static binfmt-support \
  libncurses-dev libgmp-dev libmpc-dev parted dosfstools zip
export ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf-
```

## Hardware map (pulled live from the running panel — authoritative)
| Node | Controller / bus | Addr | Compatible / driver |
|---|---|---|---|
| PMIC PFUZE100 | I2C1 (`&i2c1`) | 0x08 | `fsl,pfuze100` |
| board EEPROM 24c02 | I2C1 | 0x50 | `atmel,24c02` |
| USB3503 hub | I2C2 (`&i2c2`) | 0x08 | `smsc,usb3503` |
| SGTL5000 codec | I2C2 | 0x0a | `fsl,sgtl5000` |
| pots AD5245/AD5243 | I2C2 | 0x2c / 0x2f | `adi,ad5245` / `ad5243` (likely VCOM/gain) |
| **Atmel maXTouch mXT336T** | **I2C3 (`&i2c3`)** | **0x4a** | **`atmel,maxtouch`** |
| Display | LDB ch0 → IPU DI0 | — | `fsl,imx6q-ldb`, single-channel, `spwg`/24-bit |
| Panel | LVDS 800x1280@60 RGB24 | — | `display-timings` (refine porches during bring-up) |
| Backlight | PWM | — | `pwm-backlight`, 0–255 (confirm PWM channel vs SABRE `pwm1`) |
| Ethernet | FEC | — | `fsl,imx6q-fec` |
| RTC | SNVS (on-SoC) | — | `fsl,sec-v4.0-mon-rtc-lp` |
| Buttons | gpio-keys | — | — |

Cmdline reference (stock): `video=mxcfb0:dev=ldb,800x1280@60,if=RGB24,bpp=32 ldb=sin0 rotate=0`

## Stages
1. **U-Boot** — mainline, `mx6sabresd_defconfig` → build `u-boot-dtb.imx`. Brings up DDR,
   SD, UART, FEC. First smoke test: serial banner. (`dd` to SD at 1 KiB offset.)
2. **Kernel** — mainline LTS (6.6.y), `imx_v6_v7_defconfig` → `zImage` + dtbs.
   Confirm CONFIGs: `DRM_IMX`, `DRM_IMX_LDB`, `DRM_PANEL_SIMPLE`, `TOUCHSCREEN_ATMEL_MXT`,
   `SND_SOC_IMX_SGTL5000`, `MFD_PFUZE100`, `USB_HSIC_USB3503`, `RTC_DRV_SNVS`,
   `BACKLIGHT_PWM`, `FEC`, `SI1145` (ambient/prox, optional).
3. **Device tree** — base `imx6q-sabresd.dts`; our deltas:
   - `&ldb`: enable, single `lvds-channel@0` on DI0, 24-bit `spwg`, with the 800x1280@60
     `display-timings` + `backlight` phandle. (This is the #1 thing to get right.)
   - `&i2c3`: add `atmel_mxt_ts@4a { compatible="atmel,maxtouch"; reg=<0x4a>; interrupt-parent/gpio; reset-gpio; }`. Remove SABRE's own touch node.
   - Keep PFUZE100/EEPROM on `&i2c1`, SGTL5000/USB3503/pots on `&i2c2` (SABRE puts some
     elsewhere — move them to match the map above).
   - `pwm-backlight` → correct PWM; `gpio-keys`; `fec`; `sgtl5000` audio-routing.
4. **Rootfs** — `debootstrap --arch=armhf bookworm` + `qemu-user-static`; inside chroot:
   kernel modules, `systemd-networkd` (DHCP on eth0), a kiosk unit launching **`cog`**
   (WPE WebKit, lightweight) or Chromium fullscreen at `http://192.168.1.110:8123/` (HA
   native UI works on a current engine), `weston`/`cage` compositor, autologin.
5. **Assemble SD** — single ext4 root with `/boot` (zImage + dtb + `extlinux/extlinux.conf`
   or `boot.scr`); write `u-boot-dtb.imx` to raw 1 KiB offset. (Image whole new card.)
6. **Boot + iterate over serial** — fix display timings/backlight GPIO, then touch, then
   audio/eth (eth+audio are reference-standard, expected to "just work").

## Notes
- Mic: won't come across (conferencing DSP). Light/prox (Si1142) optional — find its bus
  during bring-up. Smartcard/NFC: skip.
- Everything stays reversible: original card is the backup; nothing here touches the panel.
