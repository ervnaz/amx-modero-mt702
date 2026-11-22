# AMX Modero MT-702 (G5) — Hardware Profile for OS Porting

Captured live from the running device (root adb) on 2026-11-22. Purpose: a ready-to-use
reference for porting a newer Android (NXP i.MX6 Android 9 BSP) or mainline Linux + kiosk
browser onto this board. Raw captures sit beside this file (dmesg.txt, proc_basics.txt,
input_devices.txt, sys_map.txt, cmdline.txt, config.gz = full kernel .config).

## TL;DR
Kernel board string: **"AMX i.MX6 Quad Modero-X Board"** (boardId `0x15`, somRev `0x2`).
This is essentially a **Freescale i.MX6 SABRE-SD class design** — PFUZE100 PMIC + SGTL5000
codec + USB3503 hub are the reference-board parts. **Every peripheral is standard and has
mainline / NXP-BSP driver support.** A port is an *adaptation of the SABRE board config*,
not a from-scratch bring-up. The only board-specific work is the LVDS panel node and
pointing the (already-supported) touch driver at the right I²C address.

## SoC / core
| | |
|---|---|
| SoC | **NXP i.MX6 Quad** (Cortex-A9 ×4, ARMv7l rev 10, NEON/VFPv3), ~996 MHz |
| RAM | **1.76 GB** (`MemTotal: 1762336 kB`) — enough for Android 9 (tight) or any Linux |
| Storage | single **16 GB microSD** (removable), `mmcblk0` via `sdhci-esdhc-imx.1` (no eMMC) |
| Stock OS | Android 4.2.2, kernel **Freescale 3.0.35** (2018) |
| Power | PoE (no battery, no `power_supply`) |

## Peripherals (bus / address / driver — all supported upstream)
| Function | Part | Bus @ addr | Driver / node | Kernel CONFIG |
|---|---|---|---|---|
| Display | LVDS panel via **LDB → IPU DI0** | — | `mxc_ldb` / `mxc_sdc_fb` | `FB_MXC_LDB`, `MXC_IPU` |
| Backlight | PWM backlight, 255 levels | — | `pwm-backlight` | `BACKLIGHT_PWM` |
| **Touch** | **Atmel maXTouch mXT336T** (7", 3 finger, matrix 24×14) | **i²c-2 @ 0x4a** | `atmel_mxt_ts` (node `qt602240_ts`) | `TOUCHSCREEN_ATMEL_MXT` |
| Audio | **SGTL5000** codec (card `sgtl5000audio`) | i²c-1 @ 0x0a | `snd-soc-sgtl5000` | `SND_SOC_SGTL5000` |
| PMIC | **PFUZE100** | i²c-0 @ 0x08 | `mc_pfuze` | `MFD_PFUZE` |
| USB hub | SMSC **USB3503** (2-port) | i²c-1 @ 0x08 | `usb3503` | `USB_USB3503` |
| Digital pots | **AD5245** / **AD5243** (likely VCOM/contrast or gain) | i²c-1 @ 0x2c / 0x2f | `ad5245`/`ad524x` | — |
| EEPROM | 24C02 (board ID/config, read by U-Boot) | i²c-0 @ 0x50 | `at24` | — |
| RTC | **i.MX6 internal SNVS RTC** | on-SoC | `snvs_rtc` | `RTC_DRV_SNVS` |
| Ethernet | **Freescale FEC**, PHY@1, 100/Full, MAC `00:60:9f:a5:b3:ed` | on-SoC | `fec` | `FEC` |
| Buttons | gpio-keys | GPIO | `gpio-keys` | — |
| Thermal | i.MX6 anatop/processor | on-SoC | `imx_thermal` | — |
| Ambient/prox | **Si1142** (light+proximity) — seen via Android sensorservice | *not in standard i²c map; secondary/bitbang bus — confirm during bring-up; optional for a kiosk* | | |

Notes:
- **No Wi-Fi** — ethernet only (PoE). A VLAN-tagged iface `eth0.269` is configured by the AMX stack.
- The "dead clock" is the **SNVS RTC backup cell** (coin cell / supercap on `VSNVS`, ~1.8 V). Replaceable on the PCB.
- PFUZE100 rails observed: SW1A/B/C, SW2, SW3A/B, SW4, SWBST, VSNVS, VREFDDR, VGEN1–6 (SABRE-standard voltages — see dmesg.txt).

## Display details (the one thing you must get right)
```
Kernel cmdline: video=mxcfb0:dev=ldb,800x1280@60,if=RGB24,bpp=32 ldb=sin0   rotate=0
fb0 name: "DISP3 BG"   fb0 modes: "U:800x1280p-60"   bpp: 32   virtual_size: 800,3840
```
- Native panel is **portrait 800×1280 @ 60 Hz**, RGB24 (24-bit), **single-channel LVDS** (`ldb=sin0`), on **IPU DI0**, used landscape (1280×800) by the UI. Triple-buffered (3840 = 1280×3).
- For a port: configure LDB single-channel on DI0 with an **800×1280@60 RGB24** panel node + `pwm-backlight`. Start from the 800×1280@60 modedb entry; pull exact porch/clock values and the **panel-enable GPIO + backlight PWM channel** from the 3.0.35 board file if you need pixel-perfect timing (extractable from the stock kernel — not yet done here).

## Serial console (bring-up lifeline — PHYSICAL access needed)
- **Console: `ttymxc0` (UART1) @ MMIO `0x2020000`, IRQ 58, 115200 8N1.** (UART2 `ttymxc1` @ `0x21e8000` also wired.)
- The internal micro-USB is USB-OTG (device), **not** the UART. You'll need UART1 TX/RX/GND from PCB test points/header (likely a 3.3 V TTL header — a USB-TTL adapter).

## Storage / boot layout (`mmcblk0`, ~16 GB)
```
raw (first ~8 MB, before p1) : U-Boot (i.MX6 u-boot.imx @ 1 KB offset) + env   [standard i.MX6 SD boot]
mmcblk0p1   8 MB    boot (Android bootimg: kernel+ramdisk)      <- our root patch lives here
mmcblk0p2   8 MB    recovery (Android recovery)                 <- left stock (safety net)
mmcblk0p3   1 KB    extended-partition marker
mmcblk0p4  ~13 GB   userdata (ext4)
mmcblk0p5  768 MB   system (ext4)
mmcblk0p6  512 MB   cache (ext4)
mmcblk0p7   8 MB    vendor
mmcblk0p8   8 MB    misc / env
mmcblk0p9  512 MB   factoryfw
```
- **Boot chain:** i.MX6 BootROM → U-Boot (raw SD) → Android bootimg (p1). No secure-boot lock observed (HAB appears open/dev) — the SD is fully writable, which is why re-imaging is easy.
- **To flash a new OS:** image the whole card first, then `dd` a new `u-boot.imx` to the 1 KB offset and write kernel/rootfs to partitions (or repartition). Nothing here is fused shut.

## Porting routes
**Option A — Android 9 (Pie):** NXP `imx-p9.0.0` BSP (SABRE-SD target, kernel 4.14.x) → add a board/DT variant. Board-specific delta vs. SABRE:
1. LVDS panel node (800×1280@60 RGB24, single-channel LDB on DI0) + backlight PWM + panel-enable GPIO.
2. `atmel_mxt_ts` on `i2c-2 @ 0x4a` (chip carries its own config).
3. PFUZE100 regulators (match the rails above), SGTL5000 audio routing, gpio-keys — mostly SABRE defaults.

**Option B — mainline Linux + kiosk browser (recommended for a pure modern kiosk):** mainline U-Boot + kernel (`imx6q`), Buildroot/Yocto/Debian, `cage`/`weston` + Chromium or Cog/WPE WebKit fullscreen. Mainline already has `imx-ldb`, `panel-simple`/`panel-lvds`, `atmel_mxt_ts`, `sgtl5000`, `pfuze100`, `fec`, `snvs_rtc`, `usb3503` — so the delta is the same panel DT node + maXTouch address.

**Won't/needn't port (AMX-only):** smartcard reader, NFC, the conferencing mic/DSP (the mic is on that DSP, not a normal input), AMX ICSP/NetLinx stack.

## First concrete steps if you proceed
1. Get UART1 console access (TTL adapter on the PCB header/test points).
2. Full `dd` backup of `mmcblk0` to a file.
3. Build mainline (or NXP) U-Boot for `imx6q` → boot to serial (no display yet).
4. Bring up: **display node → touch → audio/eth** (eth/audio are reference-standard).
5. Pick userspace (Android BSP vs. Linux + kiosk browser) and build the rootfs.
