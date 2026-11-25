# Repurposing an AMX Modero MT-702 (G5) — from locked-down trash-find to Home Assistant panel (and a bare-metal Linux port)

An **AMX Modero MT‑702** touch panel, found in the trash, turned into a usable
**Home Assistant wall display** — and then pushed further into a ground-up
**mainline-Linux (Debian) bring-up** on its NXP i.MX6 SoC.

This repo documents the whole journey, the dead ends, and — more usefully — the
**reusable tools and the exact board-specific data** (DDR config, console pinout,
device tree) that anyone reviving one of these panels will need.

> **Status:** Android/HA panel = **done and working**. **Bare-metal Debian 12 now
> boots to a root shell on the panel** — a modern **U-Boot 2020.04** (NXP **uboot-imx**
> plugin, *not* the 2009 vendor bootloader) → kernel **6.6** → `modero login:`. The long
> "silent U-Boot" saga had two root causes, both solved: **(1) SD boot is a cold-start
> timing race**, not a card/vendor lock (boot fuses blank, the plugin reads no CID) — the
> i.MX6 ROM's impatient SD init (single un-retried CMD0) races the card's power-on, so you
> need a card *and a power supply* that win the race (a passive PoE injector loses it; the
> PoE switch wins); **(2) our earlier plugin/DDR builds** — the fix was NXP's uboot-imx
> plugin with reference DDR plus three board patches (non-fatal PMIC, FAT+ext4 SD layout,
> `disable-wp` for a phantom write-protect GPIO). Reproduce: [`uboot/uboot-imx-build-notes.md`](uboot/uboot-imx-build-notes.md)
> + [`sdcard/make-debian-sd.sh`](sdcard/make-debian-sd.sh). **Next:** a proper
> `imx6q-modero.dts` (LVDS panel, maXTouch, PFUZE100, 2 GB DDR) then the HA kiosk. See [§5](#5-bare-metal-linux-debian--in-progress).

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

**Diagnosed — and a deliberate pivot.** The ported U-Boot came up **dead silent, even
before DDR init** (we reordered `board_init_f` to bring the console up first, with
diagnostic `puts()`, and it still printed nothing). Disassembling the stock boot image
cracked it: **this board boots via the i.MX6 boot-ROM *plugin* mechanism** (`plugin=1`
in the image header) — a small OCRAM routine inits DDR (reading a 3-bit board-ID to pick
the config) and **returns to the boot ROM**, which then loads the real U-Boot. Our
mainline SPL uses the normal load-and-jump flow (`plugin=0`), and **mainline has no i.MX6
plugin** (that code targets i.MX8/9), so the ROM never runs ours.

**The fix — simpler than any of that: non-SPL / DCD mode.** We'd only ever built U-Boot in
*SPL* mode. Mainline's *other* i.MX6 boot mode — **non-SPL / DCD** (the classic flow) — puts
a **DCD** (a table of register writes) in the image header that the **boot ROM itself
applies** to bring up DDR, then loads U-Boot into DDR and runs it. A DCD *is exactly* our
extracted DDR data: the 83 register writes drop straight into an `imximage.cfg`
([`uboot/modero-dcd.cfg`](uboot/modero-dcd.cfg)), built from `mx6modero_defconfig` with
`CONFIG_SPL` off → **[`uboot/u-boot-modero-dcd.imx`](uboot/)** (verified: valid DCD, our
exact values, loads into DDR). No plugin to hand-write, no ancient vendor bootloader, and a
clean device-tree kernel boot (`extlinux`) — so kernel updates stay a file edit, not a
reflash. On i.MX6 the DCD path is the one [reported to boot where SPL doesn't](https://lists.denx.de/pipermail/u-boot/2016-September/267780.html).
**Next step:** one boot test to confirm (flash with [`sdcard/update-uboot.sh`](sdcard/update-uboot.sh)),
then wire `extlinux` to our `zImage` + DTB.

> **Lesson (see the write-up's "rabbit hole" section).** We spent days hand-rolling an SPL
> bring-up and nearly settled for keeping the 2009 vendor bootloader — when mainline's DCD
> build mode, which takes our DDR data directly, built in two minutes. For a *known* board
> (i.MX6 SABRE-SD-class), survey what already exists before hand-rolling. The board-specific
> work (console pinout, live DDR extraction) was real and necessary; the days-long blocker
> was just a build-mode choice the ecosystem had solved long ago.

### 5b. The real wall: it was the SD card all along

Everything above was true — but the "non-SPL/DCD fix" and a long night of bootloader work
after it were debugging code that **never ran a single instruction**. The DCD, the plugin,
the ROM-API fixes — all **dead silent, every time**. The tell we kept rationalising away:
**zero positive evidence the boot ROM was ever reading our card.**

The breakthrough was a question, not a fix: *could the panel just not read this SD card?*
Test: write the **known-good stock bootloader** to our other microSD cards and boot them.

| microSD | stock bootloader written | result |
|---|---|---|
| Apacer Industrial 16 GB (panel's own) | ✓ | boots Android |
| Kingston 2 GB | ✓ (verified on card) | **dead silent** |
| Kioxia 32 GB ("Debian card") | ✓ — 4 MB region *and* full 16 GB image | **dead silent** |

The **i.MX6 boot ROM reads SD in a slow, picky mode at power-on**; cards fine in a PC reader
often won't initialise in that window. The factory card is an **Apacer *Industrial*** part;
our spares weren't. **Every silent boot of the whole project was the ROM never loading the
image off the card** — our bootloaders were never getting a turn.

**Not a vendor lock** (we checked both ways): the stock OCRAM plugin **never touches the SD
controller** (can't check a CID), and the boot-config **fuses are blank** (`BT_FUSE_SEL=0`,
`BMOD=0` — read live over the serial root shell + `devmem` on OCOTP), so the chip boots from
GPIO straps with no card binding. Nothing to unlock — just hardware pickiness.

With a card the ROM *does* read, we finally ran our own code and learned: **plugin=0 (plain
DCD) does not boot on this board** — a plugin=1 image is *required*, not optional. And our
**mainline-built plugin images don't run either** (the stock NXP plugin runs every time).
We found + fixed one real header bug — mainline sets the plugin's OCRAM load length to 64 KB,
overrunning the ROM's own stack; stock uses 16 KB (patch the `boot_data.length` word at image
offset `0x24`) — still silent. Some deeper `imximage`/ROM plugin-format incompatibility remains.

**Path forward: reuse the stock plugin.** It provably inits this board's DDR and hands off
correctly — so splice a modern mainline U-Boot into the stock image in place of the 2009
vendor U-Boot and let the proven plugin do the hard part. The board-specific unknowns
(console, DDR, card compatibility, the plugin requirement) are all answered; what's left is
assembly.

> **The deeper lesson:** *validate the most upstream assumption before debugging downstream.*
> We spent days on DDR timing, IVT offsets and ROM-API tables — careful work on top of a
> layer that was quietly broken (the ROM couldn't read the card). The cheapest question —
> *does the thing even load?* — would have saved all of it. Ask it first.

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

SD-card imaging commands and which cards boot: [docs/sdcard-imaging.md](docs/sdcard-imaging.md)

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
