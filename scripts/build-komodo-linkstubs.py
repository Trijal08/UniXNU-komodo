#!/usr/bin/env python3
"""Link stubs for the Linux build of the kernel, one archive member per symbol so that a real
definition linked with -force_load always takes precedence and the member stays out. A member that
bundled several symbols would be pulled in for the one still undefined and then duplicate the others
(the verified root archive defines verified_root_key, the owner-root audit native_owner_root_accepted),
so every declaration below becomes its own member.

  profile     __llvm_profile_get_size_for_buffer_internal / __llvm_profile_write_buffer_internal:
              Apple's clang links a profile runtime that defines them; OSKext.cpp references them
              for kext PGO dumps. The size query answers 0 and the writer fails cleanly.
  atexit      __cxa_atexit: upstream clang registers static destructors through it even for the kext
              ABI; the kernel never runs them, so registration is a no-op.
  display     native_legacy_display_probe: bsd_init calls it behind a boot argument with no
              compile-time guard. The bootstrap configuration has no display archive; the full
              configuration force-loads the real one, which keeps this member out of the link.

Listed through CONFIG_XNU_EXTRA_LD_ARCHIVES.
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/komodo-linkstubs'
OUT.mkdir(parents=True, exist_ok=True)
TYPES = 'typedef unsigned int u32; typedef unsigned long long u64; typedef unsigned long size_t;\n'
# One C declaration or definition per line; the member is named after its symbol.
DECLARATIONS = '''
unsigned long long __llvm_profile_get_size_for_buffer_internal(const char *a, const char *b, const char *c, const char *d, const char *e, const char *f) { (void)a; (void)b; (void)c; (void)d; (void)e; (void)f; return 0; }
int __llvm_profile_write_buffer_internal(char *buffer, const char *a, const char *b, const char *c, const char *d, const char *e, const char *f) { (void)buffer; (void)a; (void)b; (void)c; (void)d; (void)e; (void)f; return -1; }
int __cxa_atexit(void (*function)(void *), void *argument, void *dso) { (void)function; (void)argument; (void)dso; return 0; }
void native_legacy_display_probe(void) {}
volatile u32 native_adreno_audit_attr;
volatile u64 native_adreno_audit_ticks;
int (*native_adreno_cached_read32)(u64, u32 *);
int (*native_adreno_dram_read32)(u64, u32 *);
volatile u64 native_adreno_cache_stats[5];
char native_adreno_client_log[8 * 512];
volatile u32 native_adreno_coherence[8];
volatile u32 native_adreno_coherent_skips[4];
volatile u32 native_adreno_export_stats[4];
volatile u64 native_adreno_fence_phys;
volatile u32 native_adreno_fence_wait[8];
volatile u32 native_adreno_ib_log[4][4 + 28];
volatile u32 native_adreno_ib_log_count;
volatile u64 native_adreno_import_diag[10];
volatile u64 native_adreno_import_fail_offset;
volatile u64 native_adreno_import_fail_pa;
volatile u32 native_adreno_import_stage;
volatile u32 native_adreno_io_coherent;
volatile u32 native_adreno_map_fail[7][2];
char native_adreno_metal_askers[12 * 512];
char native_adreno_metal_rows[48][96];
volatile u32 native_adreno_method_stats[20][4];
volatile u32 native_adreno_pool_stats[8];
volatile u32 native_adreno_pool_status;
volatile u32 native_adreno_pool_wc;
volatile u64 native_adreno_reassert_ticks;
volatile u32 native_adreno_ring_log[4][4 + 112];
volatile u32 native_adreno_ring_log_count;
volatile u32 native_adreno_view_diag[6];
volatile u64 native_adreno_vm_phase_us[2][8];
volatile u64 native_adreno_wait_outer[4];
volatile u32 native_adreno_wc_audit[6];
volatile u32 native_adreno_wc_distrusted;
char native_gpu_coherence_row[120];
volatile u64 native_gpu_idle_sleeps;
volatile u64 native_gpu_idle_spins;
u32 native_gpu_perf_vote[2];
char native_cpufreq_row[120];
volatile unsigned int native_cpufreq_stage;
void sheng_cpufreq_poll(void) {}
volatile unsigned int native_touch_count;
volatile unsigned int native_touch_seq;
volatile unsigned int native_touch_stroke_count;
volatile unsigned int native_touch_stage_req;
volatile int native_touch_extent[4];
volatile unsigned int native_touch_hid_reports[4];
volatile int native_touch_ids[12];
char native_touch_rows[4][120];
volatile int native_touch_strokes[16][7];
volatile int native_touch_xs[12];
volatile int native_touch_ys[12];
void native_touch_set_sink(void (*sink)(void *), void *context) { (void)sink; (void)context; }
volatile u64 native_ufs_block_failures;
volatile u64 native_ufs_block_reads;
volatile u64 native_ufs_verified_blocks;
volatile u64 native_ufs_verify_ticks;
volatile u64 native_ufs_read_ticks;
volatile u32 native_ufs_integrity_failures;
volatile u32 native_ufs_blocks_published;
volatile u32 native_ufs_probe_calls;
volatile u32 native_ufs_matched;
volatile u32 native_ufs_root_step;
const char *volatile native_ufs_root_failure;
u64 native_ufs_export_blocks(void) { return 0; }
int native_ufs_export_write(u64 a, u32 b, const void *c) { (void)a; (void)b; (void)c; return -1; }
int native_ufs_log_open(u64 *a, u64 *b, const char **why) { (void)a; (void)b; if (why) *why = "no storage driver"; return -1; }
int native_ufs_log_sync(void) { return -1; }
int native_ufs_log_write(u64 a, u32 b, const void *c) { (void)a; (void)b; (void)c; return -1; }
void native_ufs_progress_text(char *out, size_t size) { if (out && size) out[0] = 0; }
unsigned native_ufs_store_gpt_check(void) { return 0; }
unsigned native_ufs_store_mode(void) { return 0; }
int native_ufs_store_open(u64 blocks, u64 *first, const char **why) { (void)blocks; (void)first; if (why) *why = "no storage driver"; return -1; }
int native_ufs_store_read(u64 rel, u32 blocks, void *dst) { (void)rel; (void)blocks; (void)dst; return -1; }
int native_ufs_store_sync(void) { return -1; }
int native_ufs_store_write(u64 rel, u32 blocks, const void *src) { (void)rel; (void)blocks; (void)src; return -1; }
volatile int native_owner_root_accepted;
volatile unsigned long long native_virtio_verified_blocks;
unsigned char verified_root_key[1024];
'''


def symbol_of(declaration):
    """The identifier being declared: the one right before '(' for functions and pointers, else before '[' / ';'."""
    pointer = re.match(r'[^(]*\(\s*\*\s*(\w+)\s*\)\s*\(', declaration)
    if pointer:
        return pointer.group(1)
    match = re.match(r'[^(=;\[]*?(\w+)\s*(\(|\[|;)', declaration)
    if not match:
        raise SystemExit('cannot name the symbol of: ' + declaration)
    return match.group(1)


sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
objects, names = [], set()
for line in DECLARATIONS.strip().splitlines():
    name = symbol_of(line)
    if name in names:
        raise SystemExit('duplicate stub ' + name)
    names.add(name)
    source = OUT / f'{name}.c'
    source.write_text(TYPES + line + '\n')
    obj = OUT / f'{name}.o'
    subprocess.run(['xcrun', 'clang', '-arch', 'arm64', '-isysroot', sdk, '-miphoneos-version-min=17.0', '-mkernel', '-nostdinc',
                    '-ffreestanding', '-fno-builtin', '-O2', '-DKERNEL', '-c', str(source), '-o', str(obj)], check=True)
    objects.append(str(obj))
for stale in list(OUT.glob('*.o')) + list(OUT.glob('*.c')):
    if stale.stem not in names:
        stale.unlink()
archive = OUT / 'libkomodo-linkstubs.a'
archive.unlink(missing_ok=True)
subprocess.run(['xcrun', 'ar', 'rcs', str(archive), *objects], check=True)
print(f'link stubs: {archive} ({len(objects)} members, one per symbol)')
