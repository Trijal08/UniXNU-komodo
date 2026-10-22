# UniXNU-komodo

Device repository for the Google Pixel 9 Pro XL (komodo, Google Tensor G4 "zumapro"). It follows the
[UniXNU porting guide](https://unixnu.com/porting/). The UEFI port lives in a separate Mu-Silicium
repository and already provides GOP, volume buttons, UART logs and UFS block I/O.

## Layout

| Path | Contents |
| --- | --- |
| `board.toml` | Board, IPSW, userdata, kernel, firmware, payload and ADT description |
| `configs/komodo_defconfig` | Kernel switches: generic platform, CPU, display and root policy; Qualcomm drivers off |
| `scripts/make-komodo-adt.py` | Apple device tree generator with the komodo bus map |
| `scripts/komodo-gpt.py` | Prints a UFS LUN's GPT and the `[userdata]` snippet |
| `scripts/komodo-esp.py` | Adds UniXNU and DarwinBoot to the payload volume for the `esp` partition |
| `package/` | Bring-up glue taken from UniXNU-sheng: boot progress, legacy display, HID, key store and process probes, the original-PMGR shim. Touch, cpufreq and GPU probes are stubbed in `KomodoBoardProbes.cpp` |
| `scripts/build-*.py` | Archive builders taken from UniXNU-sheng, kit paths repointed to `kits/komodo` |

## Build

```sh
cd UniXNU
./unixnu defconfig komodo_defconfig -D ../UniXNU-komodo
./unixnu fetch
./unixnu ipsw fetch
./unixnu build kernel
./unixnu build package
./unixnu build firmware --uefi ../Mu-Silicium --edk2 ../Mu-Silicium/Mu_Basecore
./unixnu build payload --unique-chip-id <hex> --trust-cache <bundle> --data-ramdisk <seed>
bash scripts/build-darwinboot.sh
python3 ../UniXNU-komodo/scripts/komodo-esp.py out/komodo/payload/payload.img \
    out/komodo/package/Build/Out/AARCH64-DEBUG/UniXNU.efi \
    package/Build/DarwinBootPkg/DEBUG_CLANGPDB/AARCH64/DarwinBoot.efi out/komodo/esp.img
fastboot flash esp out/komodo/esp.img
```

The firmware is the Mu-Silicium `caimito` port with `DEVICE_MODEL=0`. UniXNU runs from the ESP as
`EFI/BOOT/BOOTAA64.EFI` and DarwinBoot is loaded from the payload, so the firmware volume stays
unchanged. The boot image comes from `build_uefi.py -d caimito` (lz4, header v4, no ramdisk).

The payload volume is written to the 2 GiB `esp` partition on the UFS rather than packed into the
boot image. The Darwin root image goes into the 64 GiB `darwin` partition (`fastboot flash darwin`), carved
from the end of `linux`, so Android and postmarketOS stay intact; the Exynos UFS driver matches
that GPT name. Build the boot image with the Mu-Silicium script until `unixnu bootimg` understands the
Android boot header v4 the Pixel bootloader expects.

## Hardware map

| Block | Address | Driver |
| --- | --- | --- |
| GIC-600 (GICv3) | GICD 0x10400000, GICR 0x10440000 | ArmCpu (generic) |
| UART0 | 0x10870000 | firmware serial |
| UFS host and PHY | 0x13200000, 0x13204000 | Exynos UFS driver, to write |
| USI2 / SPI2 | 0x108900c0, 0x10890000 | USI SPI driver, to write |
| Touch | Synaptics S3908 TCM on SPI2, TSP_INT gpn0-0 | TCM probe into NativeHidInput, to write |
| DECON0 / DSIM0 | 0x19470000, 0x19440000 | GOP framebuffer through NativeMobileDisplay |
| Mali-G715 | 0x1f000000 | none |
| DRAM | 2 GiB at 0x80000000, 13.5 GiB from 0x880000000 | DarwinBoot window |

## Device inputs still missing

| Input | Where it goes |
| --- | --- |
| Data seed volume UUID | `configs/komodo_defconfig` |
| Platform seed | `--unique-chip-id` |
| Boot core MPIDR | first value of `[payload.adt] cpu_regs` |

## Inherited from sheng, still to adapt

- `package/BootReset.c` and `BootResetCore.h` reboot into fastboot through the SM8550 SPMI PMIC arbiter. Do not pass `sheng-autoreset` on komodo until it is rewritten for the Exynos PMU or PSCI SYSTEM_RESET2.
- `package/BootLog.c` writes its diagnostic log through NativeUfs weak imports; it stays silent until the Exynos UFS driver exports the same functions.
- `scripts/build-sheng-platform-power.py` audits the PMGR vtable against an earlier prelink candidate under `build/native-prelink`; the first kernel build needs that reference bootstrapped.
- Every script under `scripts/` that mentions Adreno, GMU, Turnip, Metal or Novatek is sheng's GPU and touch tooling and can be deleted once the archive list is proven on a Mac.

## Building on Linux

The kernel builds on Linux with the shim toolchain in `~/Builds/unixnu-linux` (xcrun, make, clang,
codesign, plutil, install, xcodebuild with the firehose recipe, sw_vers, ditto, brew; cctools ld64;
a host sysroot; mig, iig-tools, unifdef and lzfse built from source; the iPhoneOS 17.5 and macOS
14.5 SDKs). Source `~/Builds/unixnu-linux/env.sh` first. The original kernelcache is decoded once
with lzfse and passed with `--kernelcache`. `configs/bootstrap_defconfig` builds the prelinked
candidate that `scripts/audit-storage-interface-offline.py` and the PMGR builder audit; copy its
`kernel.macho` and `kernel.json` into `build/native-prelink` as `native-apfs-load-positive` and
`native-owner-ufs-rootauth3-candidate` before the full `komodo_defconfig` build.

## State

| Stage | State |
| --- | --- |
| UEFI firmware, GOP, buttons, UART, UFS | works (Mu-Silicium port) |
| UniXNU menu and payload | works (2026-10-21): BOOTAA64.EFI from the esp partition, menu and test payload on the panel |
| DarwinBoot and kernel entry | works (2026-10-21): firmware is at EL2, the override DarwinBoot drops to EL1; a prebuilt uke kernel shows the green, blue and magenta probe bars (hand-off, entry, pre-MMU) and the stage 3 probe resets the phone after the MMU is on |
| Platform expert | stage 5 kernel built on Linux 2026-10-22 (komodo-stage5_defconfig); first boot pending |
| Storage and root | no driver |
| Userland | not reached |
