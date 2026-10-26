#!/usr/bin/env python3
"""Turn the payload volume into the image flashed to the "esp" partition.

The caimito firmware volume has no room for UniXNU or DarwinBoot, so both come from the ESP:
BdsDxe starts EFI/BOOT/BOOTAA64.EFI (UniXNU) from the FAT partition, and UniXNU loads
Payloads/DarwinBoot.efi as a driver because the board file sets [payload] loader = "payload".

The payload step writes a 512-byte-sector FAT image, but the UFS reports 4096-byte logical blocks
and the EDK II FAT driver requires the BPB sector size to match, so the files are extracted and
re-packed into a FAT32 image with 4 KiB sectors and one-sector clusters.

  python3 scripts/komodo-esp.py out/komodo/payload/payload.img \\
      out/komodo/package/Build/Out/AARCH64-DEBUG/UniXNU.efi \\
      out/komodo/tree/build/DarwinBoot/DEBUG_CLANGPDB/AARCH64/DarwinBoot.efi \\
      out/komodo/esp.img [--size-mib 512]
  fastboot flash esp out/komodo/esp.img

mtools (mcopy, mdir) and dosfstools (mkfs.fat) are required. The payload image is never modified.
"""
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('payload', type=Path, help='FAT image written by "unixnu build payload"')
parser.add_argument('unixnu_efi', type=Path, help='UniXNU.efi from the package build')
parser.add_argument('darwinboot_efi', type=Path, help='DarwinBoot.efi from the DarwinBootPkg build')
parser.add_argument('output', type=Path, help='image to flash to the esp partition')
parser.add_argument('--size-mib', type=int, default=512, help='image size; must leave FAT32 above its minimum cluster count')
parser.add_argument('--label', default='KOMODOESP')
args = parser.parse_args()

for path in (args.payload, args.unixnu_efi, args.darwinboot_efi):
    if not path.is_file():
        raise SystemExit(f'missing: {path}')
for tool in ('mcopy', 'mdir', 'mkfs.fat'):
    if shutil.which(tool) is None:
        raise SystemExit(f'{tool} is required (mtools, dosfstools)')
env = dict(os.environ, MTOOLS_SKIP_CHECK='1', TZ='UTC')

with tempfile.TemporaryDirectory() as scratch:
    stage = Path(scratch) / 'stage'
    stage.mkdir()
    subprocess.run(['mcopy', '-i', str(args.payload), '-s', '-n', '::/EFI', str(stage)], env=env, check=True)
    (stage / 'EFI/BOOT').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.unixnu_efi, stage / 'EFI/BOOT/BOOTAA64.EFI')
    shutil.copyfile(args.darwinboot_efi, stage / 'EFI/UniXNU/Payloads/DarwinBoot.efi')
    content = sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())
    if content > args.size_mib * 1024 * 1024 * 0.9:
        raise SystemExit(f'files take {content >> 20} MiB; raise --size-mib (now {args.size_mib})')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)
    with open(args.output, 'wb') as handle:
        handle.truncate(args.size_mib * 1024 * 1024)
    subprocess.run(['mkfs.fat', '-F', '32', '-S', '4096', '-s', '1', '-n', args.label, str(args.output)],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['mcopy', '-i', str(args.output), '-s', str(stage / 'EFI'), '::/'], env=env, check=True)
subprocess.run(['mdir', '-i', str(args.output), '-/', '::/EFI'], env=env, check=False)
print(f'esp image: {args.output} ({args.output.stat().st_size >> 20} MiB, 4096-byte sectors); flash with: fastboot flash esp {args.output}')
