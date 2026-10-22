#!/usr/bin/env python3
"""Link stubs for the Linux build of the kernel, one archive member per symbol so that a real
definition linked with -force_load always takes precedence and the member stays out.

  profile.o   __llvm_profile_get_size_for_buffer_internal / __llvm_profile_write_buffer_internal:
              Apple's clang links a profile runtime that defines them; OSKext.cpp references them
              for kext PGO dumps. The size query answers 0 and the writer fails cleanly.
  atexit.o    __cxa_atexit: upstream clang registers static destructors through it even for the kext
              ABI; the kernel never runs them, so registration is a no-op.
  display.o   native_legacy_display_probe: bsd_init calls it behind a boot argument with no
              compile-time guard. The bootstrap configuration has no display archive; the full
              configuration force-loads the real one, which keeps this member out of the link.

Listed through CONFIG_XNU_EXTRA_LD_ARCHIVES.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/komodo-linkstubs'
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = {
    'profile': '''unsigned long long __llvm_profile_get_size_for_buffer_internal(const char *a, const char *b, const char *c, const char *d, const char *e, const char *f)
{ (void)a; (void)b; (void)c; (void)d; (void)e; (void)f; return 0; }
int __llvm_profile_write_buffer_internal(char *buffer, const char *a, const char *b, const char *c, const char *d, const char *e, const char *f)
{ (void)buffer; (void)a; (void)b; (void)c; (void)d; (void)e; (void)f; return -1; }
''',
    'atexit': '''int __cxa_atexit(void (*function)(void *), void *argument, void *dso)
{ (void)function; (void)argument; (void)dso; return 0; }
''',
    'display': '''void native_legacy_display_probe(void) {}
''',
    # Diagnostics the sheng boot-progress layer and display bundle read from drivers komodo does not link
    # (declared weak_import there, which a static kernel link still cannot leave undefined). Zeroed data and
    # no-op functions; sizes cover the declarations in package/*.h. One member per subsystem.
    'adreno-diag': '''typedef unsigned int u32; typedef unsigned long long u64;
volatile u32 native_adreno_audit_attr; volatile u64 native_adreno_audit_ticks;
int (*native_adreno_cached_read32)(u64, u32 *); int (*native_adreno_dram_read32)(u64, u32 *);
volatile u64 native_adreno_cache_stats[5]; char native_adreno_client_log[8 * 512];
volatile u32 native_adreno_coherence[8]; volatile u32 native_adreno_coherent_skips[4];
volatile u32 native_adreno_export_stats[4]; volatile u64 native_adreno_fence_phys; volatile u32 native_adreno_fence_wait[8];
volatile u32 native_adreno_ib_log[4][4 + 28]; volatile u32 native_adreno_ib_log_count;
volatile u64 native_adreno_import_diag[10]; volatile u64 native_adreno_import_fail_offset; volatile u64 native_adreno_import_fail_pa;
volatile u32 native_adreno_import_stage; volatile u32 native_adreno_io_coherent; volatile u32 native_adreno_map_fail[7][2];
char native_adreno_metal_askers[12 * 512]; char native_adreno_metal_rows[48][96];
volatile u32 native_adreno_method_stats[20][4]; volatile u32 native_adreno_pool_stats[8]; volatile u32 native_adreno_pool_status;
volatile u32 native_adreno_pool_wc; volatile u64 native_adreno_reassert_ticks;
volatile u32 native_adreno_ring_log[4][4 + 112]; volatile u32 native_adreno_ring_log_count; volatile u32 native_adreno_view_diag[6];
volatile u64 native_adreno_vm_phase_us[2][8]; volatile u64 native_adreno_wait_outer[4]; volatile u32 native_adreno_wc_audit[6];
volatile u32 native_adreno_wc_distrusted;
''',
    'gpu-diag': '''typedef unsigned int u32; typedef unsigned long long u64;
char native_gpu_coherence_row[120]; volatile u64 native_gpu_idle_sleeps; volatile u64 native_gpu_idle_spins; u32 native_gpu_perf_vote[2];
''',
    'cpufreq-diag': '''char native_cpufreq_row[120]; volatile unsigned int native_cpufreq_stage; void sheng_cpufreq_poll(void) {}
''',
    'touch-diag': '''volatile unsigned int native_touch_count, native_touch_seq, native_touch_stroke_count, native_touch_stage_req;
volatile int native_touch_extent[4]; volatile unsigned int native_touch_hid_reports[4]; volatile int native_touch_ids[12];
char native_touch_rows[4][120]; volatile int native_touch_strokes[16][7]; volatile int native_touch_xs[12], native_touch_ys[12];
void native_touch_set_sink(void (*sink)(void *), void *context) { (void)sink; (void)context; }
''',
    'ufs-diag': '''typedef unsigned int u32; typedef unsigned long long u64; typedef unsigned long size_t;
volatile u64 native_ufs_block_failures, native_ufs_block_reads, native_ufs_verified_blocks, native_ufs_verify_ticks, native_ufs_read_ticks;
volatile u32 native_ufs_integrity_failures, native_ufs_blocks_published, native_ufs_probe_calls, native_ufs_matched, native_ufs_root_step;
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
''',
    'root-diag': '''volatile int native_owner_root_accepted; volatile unsigned long long native_virtio_verified_blocks;
unsigned char verified_root_key[1024];
''',
}
sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
objects = []
for name, text in SOURCES.items():
    source = OUT / f'{name}.c'
    source.write_text(text)
    obj = OUT / f'{name}.o'
    subprocess.run(['xcrun', 'clang', '-arch', 'arm64', '-isysroot', sdk, '-miphoneos-version-min=17.0', '-mkernel', '-nostdinc',
                    '-ffreestanding', '-fno-builtin', '-O2', '-DKERNEL', '-c', str(source), '-o', str(obj)], check=True)
    objects.append(str(obj))
archive = OUT / 'libkomodo-linkstubs.a'
archive.unlink(missing_ok=True)
subprocess.run(['xcrun', 'ar', 'rcs', str(archive), *objects], check=True)
print(f'link stubs: {archive} ({len(objects)} members)')
