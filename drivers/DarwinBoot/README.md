# DarwinBoot

UEFI bootloader for UniXNU. Loads the payload, kernel, device tree and trust cache, then starts XNU.

Current state: boots from the firmware volume and supports the packed RAM disk handoff.

Built as part of the firmware volume.

## komodo override

This copy of DarwinBoot `85332b3` adds an EL2 to EL1 drop in `DarwinEnter`: the Pixel bootloader
hands the firmware over at EL2, and the kernel starts at EL1. HCR_EL2 gets RW only (no stage 2,
no traps, physical interrupts at EL1), the counter, timer, FP and the GICv3 system registers are
opened to EL1, SCTLR_EL1 is set to its reset value, and the loader returns into the kernel entry
with ERET. The loader accepts a request at EL1 or EL2. Secondary cores started through PSCI still
land at EL2 and need the same drop in the kernel's CPU driver.
