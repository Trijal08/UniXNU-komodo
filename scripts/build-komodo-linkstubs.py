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
