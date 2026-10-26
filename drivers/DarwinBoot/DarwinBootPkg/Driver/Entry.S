// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <AsmMacroLib.h>

ASM_FUNC(DarwinCurrentEl)
  mrs x0, CurrentEL
  ret

// x0=boot_args PA, x1=entry PA, x2=owned PA, x3=owned size, x4=frame buffer
// PA (0 for none), x5=its size in bytes. Entered at EL1 or EL2; the kernel
// always starts at EL1 (komodo: the Pixel bootloader hands the firmware over
// at EL2, so the drop to EL1 happens here, after the caches are cleaned).
ASM_FUNC(DarwinEnter)
  msr daifset, #15
  // Breadcrumb: a green bar (BGRA 0xFF00FF00) over the top 1/16 of the frame
  // buffer shows that this code ran, whatever the kernel does afterwards.
  cbz x4, 2f
  lsr x9, x5, #4
  bic x9, x9, #7
  mov w10, #0xFF00
  movk w10, #0xFF00, lsl #16
  mov x11, x4
3:
  stp w10, w10, [x11], #8
  subs x9, x9, #8
  b.hi 3b
  dsb sy
2:
  add x5, x2, x3
  mrs x6, ctr_el0
  ubfx x6, x6, #16, #4
  mov x7, #4
  lsl x6, x7, x6
  sub x7, x6, #1
  bic x4, x2, x7
  dsb sy
1:
  dc civac, x4
  add x4, x4, x6
  cmp x4, x5
  b.lo 1b
  dsb sy
  ic iallu
  dsb sy
  isb
  mrs x9, CurrentEL
  cmp x9, #8
  b.eq 4f
  mrs x4, sctlr_el1
  bic x4, x4, #1
  bic x4, x4, #4
  bic x4, x4, #0x1000
  msr sctlr_el1, x4
  isb
  tlbi vmalle1
  dsb sy
  isb
  br x1
4:
  // EL2 -> EL1. HCR_EL2: RW (AArch64 EL1) only, so no stage-2 translation,
  // no traps, and physical interrupts are taken at EL1.
  mov x9, #1
  lsl x9, x9, #31
  msr hcr_el2, x9
  // EL1 owns the physical counter and timer; no virtual offset.
  mov x9, #3
  msr cnthctl_el2, x9
  msr cntvoff_el2, xzr
  // No FP, SVE or debug traps; the identity registers mirror the hardware.
  mov x9, #0x33FF
  msr cptr_el2, x9
  msr hstr_el2, xzr
  msr mdcr_el2, xzr
  mrs x9, midr_el1
  msr vpidr_el2, x9
  mrs x9, mpidr_el1
  msr vmpidr_el2, x9
  msr vttbr_el2, xzr
  // GICv3 system register interface available to EL1 (ICC_SRE_EL2: SRE, DFB, DIB, Enable).
  mov x9, #0xF
  msr S3_4_C12_C9_5, x9
  // SCTLR_EL1 at its reset value: MMU, caches and alignment checks off, RES1 bits set.
  mov x9, #0x0800
  movk x9, #0x30D0, lsl #16
  msr sctlr_el1, x9
  isb
  tlbi vmalle1
  dsb sy
  isb
  // Return into the kernel entry at EL1h with DAIF masked; x0 still carries boot_args.
  add x9, x2, x3
  msr sp_el1, x9
  mov x9, #0x3C5
  msr spsr_el2, x9
  msr elr_el2, x1
  isb
  eret
