#!/usr/bin/env python3
"""Link stubs for the Linux build of the kernel.

Apple's clang links a profile runtime that defines __llvm_profile_get_size_for_buffer_internal and
__llvm_profile_write_buffer_internal, which OSKext.cpp references for kext PGO data dumps. Upstream LLVM
does not, so this archive supplies them: the size query answers 0 and the writer fails cleanly, which
only disables PGO dumps. Listed through CONFIG_XNU_EXTRA_LD_ARCHIVES.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'build/komodo-linkstubs'
OUT.mkdir(parents=True, exist_ok=True)
source = OUT / 'linkstubs.c'
source.write_text('''unsigned long long __llvm_profile_get_size_for_buffer_internal(const char *a, const char *b, const char *c, const char *d, const char *e, const char *f)
{ (void)a; (void)b; (void)c; (void)d; (void)e; (void)f; return 0; }
int __llvm_profile_write_buffer_internal(char *buffer, const char *a, const char *b, const char *c, const char *d, const char *e, const char *f)
{ (void)buffer; (void)a; (void)b; (void)c; (void)d; (void)e; (void)f; return -1; }
''')
sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
obj = OUT / 'linkstubs.o'
subprocess.run(['xcrun', 'clang', '-arch', 'arm64', '-isysroot', sdk, '-miphoneos-version-min=17.0', '-mkernel', '-nostdinc',
                '-ffreestanding', '-fno-builtin', '-O2', '-DKERNEL', '-c', str(source), '-o', str(obj)], check=True)
archive = OUT / 'libkomodo-linkstubs.a'
archive.unlink(missing_ok=True)
subprocess.run(['xcrun', 'ar', 'rcs', str(archive), str(obj)], check=True)
print(f'link stubs: {archive}')
