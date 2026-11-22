# Repurposing an AMX Modero MT-702 (G5) — from locked-down trash-find to Home Assistant panel (and a bare-metal Linux port)

An **AMX Modero MT‑702** touch panel, found in the trash, turned into a usable
**Home Assistant wall display** — and then pushed further into a ground-up
**mainline-Linux (Debian) bring-up** on its NXP i.MX6 SoC.

This repo documents the whole journey, the dead ends, and — more usefully — the
**reusable tools and the exact board-specific data** (DDR config, console pinout,
device tree) that anyone reviving one of these panels will need.

> **Status:** Android/HA panel = **done and working**. Mainline Debian port =
> **in progress**, blocked on U‑Boot SPL bring-up (see [§5](#5-bare-metal-linux-debian--in-progress)).

---

## The device

| | |
|---|---|
| Model | AMX Modero **MT‑702** (Modero‑X / G5), 7″ 800×1280 capacitive |
| Board | `MODEROX-G5 SOM` (50‑5968‑20) on `INTERFACE BOARD 7/10 MODERO E` (5092904‑00) |
| SoC | **NXP/Freescale i.MX6 Quad** (`MCIMX6Q…`), 792 MHz, **essentially an i.MX6 SABRE‑SD design** |
| RAM | **2 GB DDR3‑1066** (64‑bit, 528 MHz) |
| Storage | **removable 16 GB microSD** (`mmcblk0`) — *no eMMC, no secure-boot lock* → trivially reflashable |
| Display | LVDS via LDB/IPU‑DI0, **800×1280@60 RGB24, single-channel** (`ldb=sin0`) + PWM backlight |
| Touch | Atmel **maXTouch mXT336T**, I²C3 @ `0x4a` |
| Audio | SGTL5000 codec (speaker works; mic header **empty** on this unit) |
| Net | FEC gigabit (no WiFi) |
| Stock OS | **Android 4.2.2** (kernel 3.0.35), AMX firmware 1.8.14, locked-down AMX launcher |

The single most important hardware fact: **the OS boots entirely from the removable
microSD** (no eMMC), the SD is fully writable, and there's no secure-boot/HAB lock.
That makes everything below possible by just editing the card offline.

---

## 1. Getting in & rooting

The stock panel is locked down (no "unknown sources", no dev-mode 7‑tap, browsers
ignore `intent:` links, app installs want AMX-signed `.apx`). But:

- **AMX SSH** (`amx` / `1988`) is a Java command shell (Apache MINA), *not* a system
  shell — needs legacy crypto:
  `ssh -o KexAlgorithms=+diffie-hellman-group14-sha1 -o HostKeyAlgorithms=+ssh-rsa -o Ciphers=+aes128-cbc amx@<ip>`
- **VNC** on `:5900`, **no password** (minimal RFB client in [`tools/vnc.py`](tools/vnc.py)).

**Root** was achieved by editing the microSD **offline on a PC** — patch the
normal-boot ramdisk: `default.prop` → `ro.secure=0`/`ro.debuggable=1`, and append an
`on property:sys.boot_completed=1` block to `init.rc` that does
`setprop service.adb.tcp.port 5555; start adbd`. This beats AMX's lockdown (which
forces `persist.sys.usb.config=mtp` and re-inserts `adb_enabled=0` each boot). Result:
**persistent root ADB over the network** (`adb connect <ip>:5555` → `uid=0`).

See [`hardware/HARDWARE-PROFILE.md`](hardware/HARDWARE-PROFILE.md) for the full profile.

## 2. The Home Assistant panel (Android)

Rather than load HA's native frontend (breaks on the ancient WebView and only gets
worse with HA updates), the panel runs a **thin, frozen, hand-built ES5 dashboard**
hosted inside HA (`/config/www/panel/`), talking to HA's stable REST API. Served
same-origin so a long-lived token works. Displayed in **Fennec 68** (upgraded from the
stock Firefox 45 — the ceiling for Android 4.x). Auto-start + kiosk via a boot-hooked
`kiosk.sh` watchdog; screen kept awake with auto-brightness. **This part is finished
and in daily use.**

## 3. The serial console — the genuinely hard part

To go past Android we needed the **i.MX6 UART console**. The internal micro-USB is
USB-OTG, *not* UART, so we had to find and wire physical pins. The saga:

- The panel has a 4‑pin `J3 DEBUG` header on the interface board. **Pinout (board silk):
  `pin 1 = VCC (3.3V, do not connect), pin 2 = TX, pin 3 = GND, pin 4 = RX`**, 115200 8N1.
- **The CH340 trap:** this PC's `ch341` driver mangles baud rates (returns ~3 Mbit/s
  when set to 9600 — physically impossible). *Every* CH340-based adapter (an ESP8266,
  an Arduino Nano clone) produced pure garbage, which for a long time made the real
  115200 console look like a "fast bus firehose." **Lesson: on a flaky CH340 host, a
  misread console is indistinguishable from "wrong pin."**
- **The fix:** a **Seeed XIAO ESP32‑S3** flashed with a tiny Arduino USB↔UART bridge
  ([`bridge/bridge.ino`](bridge/bridge.ino)). Native USB (no CH340), `Serial1` locked
  to a real hardware-UART baud, plus a runtime baud-sweep command (`\x01B<baud>\n`).
  Flash it in **USB-OTG/TinyUSB CDC** mode for stability (the hardware USB-JTAG mode +
  Linux ModemManager causes a reset loop — `sudo systemctl stop ModemManager`).
- Capture with [`tools/sercap.py`](tools/sercap.py) (non-blocking, sets `CLOCAL` so it
  never hangs on carrier-detect).

With a decoder we could finally trust, the console appeared instantly: a full
`U-Boot 2009.08` → kernel → Android boot log ([`logs/stock-boot.log`](logs/stock-boot.log)),
and a **bidirectional root shell** (`root@android:/ #`) once we also wired RX.

## 4. Extracting the exact DDR config from the running hardware

The stock U-Boot does its **DDR init in SPL code, not a DCD table** (IVT `dcd=0`, loads
to OCRAM `0x907400`), so there was no register table to copy out of the binary. Instead
we read the **live, working DDR controller registers** from the running stock Android
via `/dev/mem` (`CONFIG_STRICT_DEVMEM` is off):

- Toolbox `dd` can't seek `/dev/mem`, so we cross-compiled a tiny static-ARM
  [`tools/devmem.c`](tools/devmem.c) (`mmap` + a SIGBUS handler to survive reserved
  register holes).
- Dumped MMDC0/MMDC1/IOMUXC → [`hardware/ddr-regs.txt`](hardware/ddr-regs.txt),
  decoded with [`tools/decode_ddr.py`](tools/decode_ddr.py) →
  **[`hardware/ddr-decoded.txt`](hardware/ddr-decoded.txt)**: the complete,
  build-ready DDR recipe (geometry, timing, **per-channel write-leveling / DQS-gating /
  read-write-delay calibration**, IOMUX drive strengths).

This is the crown jewel for anyone porting a bootloader to this board — the exact,
board-specific DDR calibration, read straight off working silicon.

## 5. Bare-metal Linux (Debian) — in progress

Target: lean **Debian bookworm armhf** booting from a *second* microSD (original kept as
instant-revert backup), running a fullscreen kiosk browser at the HA URL.

Built so far (all cross-compiled on the PC):
- **U-Boot** (mainline 2027, based on `mx6sabresd`) with the AMX DDR values patched into
  the SPL's `mx6q_dcd_table` — see [`uboot/mx6sabresd-modero-ddr.patch`](uboot/mx6sabresd-modero-ddr.patch)
  (15 MMDC regs + per-channel calibration + 34 IOMUX DDR pad drive-strengths).
- **Kernel** mainline 6.6 LTS (`imx_v6_v7_defconfig` + DRM/IMX/LDB, maXTouch, SGTL5000,
  PFUZE100, FEC …).
- **Rootfs** via [`rootfs/rootfs-build.sh`](rootfs/rootfs-build.sh) (debootstrap +
  serial-getty on `ttymxc0`, DHCP, `cage`+`cog` kiosk).
- **First-draft device tree** [`dts/imx6q-modero.dts`](dts/imx6q-modero.dts).
- SD assembly / U-Boot update scripts in [`sdcard/`](sdcard/).

**Current blocker:** the ported U-Boot **SPL is completely silent** — no output *even
before DDR init* (we reordered `board_init_f` to bring the console up first, with
diagnostic `puts()`, and it still prints nothing). Verified: the build is really on the
card, the capture chain works, the image is valid (IVT `self=0x907400`, load 44 KB fits
OCRAM), `CONS_INDEX=1` (UART1, same pads as stock). So it's **not DDR and not
console-config** — the SPL simply isn't running or isn't outputting, cause TBD.
**Next step:** disassemble the stock SPL (which boots perfectly on this exact board)
to see what early clock/PLL/UART setup it does that mainline is missing.

---

## Repo contents

```
hardware/   ddr-regs.txt, ddr-decoded.txt   — live DDR registers + decoded build-ready config
            HARDWARE-PROFILE.md             — full hardware map / porting reference
tools/      devmem.c                        — static-ARM /dev/mem reader (SIGBUS-tolerant)
            decode_ddr.py, extract_dcd.py   — DDR register decoders
            sercap.py                       — non-blocking serial capture
            vnc.py                          — minimal RFB/VNC client
bridge/     bridge.ino                      — XIAO ESP32-S3 USB<->UART bridge (the reliable decoder)
sdcard/     make-sd.sh                      — assemble the Debian boot SD
            update-uboot.sh                 — re-write only U-Boot (self-verifying)
            image-stock.sh                  — read-only full image of the stock card
rootfs/     rootfs-build.sh                 — debootstrap Debian armhf rootfs
dts/        imx6q-modero.dts                — first-draft board device tree
uboot/      mx6sabresd-modero-ddr.patch     — AMX DDR values patched into mainline U-Boot
logs/       stock-boot.log                  — stock U-Boot + kernel boot log
BUILD-PLAN.md                               — the staged Debian build plan
```

## Key gotchas (hard-won)

- **No eMMC, no secure boot** → the whole device is reflashable by editing the SD offline.
- **CH340 on a bad host driver = silent sabotage.** Use a native-USB adapter (XIAO
  ESP32-S3) or a CP2102/FTDI; never trust a CH340 if baud rates misbehave.
- **ESP32-S3 native USB** won't auto-reset to the bootloader (RTS "Protocol error") —
  enter download mode by hand (hold BOOT, tap RESET). Flash in **TinyUSB CDC** mode so
  ModemManager doesn't reset-loop it.
- **DDR port = IOMUX drive-strengths + MMDC config + per-channel calibration**, all
  board-specific. Reading them live off working silicon beats guessing.
- The i.MX6 SPL inits DDR **before** the console by default — reorder it so hangs are visible.

## Credits / license

Reverse-engineering and bring-up notes for a salvaged device, shared so the next person
doesn't have to rediscover the CH340 trap or re-read the DDR calibration by hand.
Provided as-is, no warranty. Scripts: MIT. (The device, trademarks, and stock firmware
belong to AMX/HARMAN.)
