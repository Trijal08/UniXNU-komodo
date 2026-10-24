#!/usr/bin/env python3
"""Build the Data seed on Linux: a fresh APFS volume carrying the Data template of the target OS volume.

The IPSW has no Data volume; a restore creates an empty one and fills it from the template the OS volume
keeps at /private/var (ownerships 501 "mobile" and friends included). This script does the same into a
sparse raw image, marks Setup as done the way scripts/seed-data-skip-setup.py does on macOS, and packs the
result into the DBRDISK1 form the payload takes (`unixnu build payload --data-ramdisk <seed>.dbr`).

  python3 scripts/build-data-seed.py --os-mount /run/media/$USER/<os-container-uuid> \\
      --volume-uuid EFC488D9-64E3-49A8-BD93-74BB04D5C0F4 [--gib N] [--no-skip-setup]

Requirements: apfsprogs (mkapfs, apfsck), the linux-apfs-rw kernel module (loaded), sudo for the mount and
the copy (the template is readable by root only and keeps its owners). The OS volume is mounted read-only
beforehand, for example with
  udisksctl loop-setup -r -f out/komodo/userdata/userdata-root.img -o 1048576 -s 6077580800
  udisksctl mount -b /dev/loopN p1 -t apfs -o ro
The seed size follows scripts/seed-data-grow.py --auto: the darwin partition minus the root image, a 4 MiB
guard, the 1024 MiB log reserve and the store's header and bitmap, rounded down to whole GiB, one GiB spare.
The volume UUID goes into CONFIG_XNU_OWNER_DATA_VOLUME_UUID of the kernel configuration.
"""
import argparse
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tomllib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIB, MIB = 1024**3, 1024**2
GUARD_BLOCKS = 1024
BUILD = '21H461'
MOBILE = 501
PREFERENCES = {
    'com.apple.migration': {'LastSystemVersion': BUILD, 'DMUserDataDisposition': {'SyntheticDidUpgrade': False, 'buildVersion': BUILD}},
    'com.apple.springboard': {'BKNoWatchdogs': True, 'FBLaunchWatchdogExceptions': {'com.apple.purplebuddy': 100.0},
                              'MCForceShowCloudConfigurationUI': False},
    'com.apple.purplebuddy': {'SetupDone': True, 'SetupFinishedAllSteps': True, 'SetupVersion': 11, 'daemonizeNeedsToRun': False},
    'com.apple.purplebuddy.notbackedup': {k: False for k in ('ShouldRunDiagnosticsMiniBuddy', 'ShouldRunHSA2MiniBuddy',
                                                             'ShouldRunKeychainSyncMiniBuddy', 'ShouldRunMesaMiniBuddy',
                                                             'ShouldRunPaymentMiniBuddy', 'ShouldRunStandardMiniBuddy', 'SilentICDPUpgrade')},
    'com.apple.managedconfiguration.notbackedup': {'LockdownActivationIndicatesCloudConfigurationAvailable': False},
}
CONTAINERS = ('Bundle', 'Data/System', 'Shared/SystemGroup', 'Temp')
# Template directories emptied in the seed: the staged built-in apps are 456 MiB once their compressed files are
# expanded, and the packed seed format carries at most 256 MiB. The directory itself stays, so installd finds an
# empty staging area. The apps can come back once the seed is delivered another way.
PRUNE = ('staged_system_apps',)


def store_blocks(pages):
    bitmap = (pages + 8 * 4096 - 1) // (8 * 4096)
    return 1 + bitmap + pages


def auto_gib(userdata, root_bytes, reserve_mib=1024):
    avail = userdata - ((root_bytes + 4095) // 4096 + GUARD_BLOCKS) * 4096 - reserve_mib * MIB
    if avail <= 0:
        sys.exit('the partition is too small for the root image and the reserve')
    gib = avail // GIB
    while gib > 0 and store_blocks(gib * GIB // 4096) * 4096 > avail:
        gib -= 1
    return gib - 1


def populate(template, mount, skip_setup):
    """Root half: copy the template with owners and modes, then the Setup preferences. Runs under sudo."""
    if os.geteuid() != 0:
        sys.exit('the populate step must run as root')
    template, mount = Path(template), Path(mount)
    if not (template / 'mobile').is_dir():
        sys.exit(f'{template} has no mobile directory; is the OS volume mounted?')
    # cp -a keeps owners, modes, times, symlinks and hard links. Extended attributes are copied separately: the
    # template's compressed files expose com.apple.decmpfs (and a resource fork) while the copy holds plain data,
    # and apfsck rejects an uncompressed inode that still carries the decmpfs attribute.
    # The pruned directories are skipped here rather than deleted afterwards: freed blocks keep their data, and the
    # packer carries every nonzero page.
    for child in sorted(template.iterdir()):
        if child.name in PRUNE:
            continue
        result = subprocess.run(['cp', '-a', '--no-preserve=xattr', str(child), str(mount) + '/'], capture_output=True, text=True)
        if result.returncode:
            sys.stderr.write(result.stderr[-4000:])
            sys.exit('cp -a failed')
        if result.stderr:
            sys.stderr.write(result.stderr[-2000:])
    for name in PRUNE:
        source, target = template / name, mount / name
        if source.is_dir():
            target.mkdir()
            info = source.stat()
            os.chmod(target, info.st_mode & 0o7777)
            os.chown(target, info.st_uid, info.st_gid)
            print(f'{name}/ left empty')
    shutil.copystat(template, mount)
    copied, skipped = 0, 0
    for root, dirs, files in os.walk(template):
        if Path(root) == template:
            dirs[:] = [d for d in dirs if d not in PRUNE]
        for name in dirs + files:
            source = Path(root) / name
            target = mount / source.relative_to(template)
            try:
                names = os.listxattr(source, follow_symlinks=False)
            except OSError:
                continue
            for attribute in names:
                if attribute.split('osx.', 1)[-1] in ('com.apple.decmpfs', 'com.apple.ResourceFork'):   # the module prefixes Apple names with osx.
                    skipped += 1
                    continue
                try:
                    os.setxattr(target, attribute, os.getxattr(source, attribute, follow_symlinks=False), follow_symlinks=False)
                    copied += 1
                except OSError as error:
                    print(f'xattr {attribute} on {target.relative_to(mount)}: {error.strerror}')
    print(f'xattrs: {copied} copied, {skipped} compression attributes left behind')
    if skip_setup:
        preferences = mount / 'mobile/Library/Preferences'
        preferences.mkdir(parents=True, exist_ok=True)
        for name, values in PREFERENCES.items():
            path = preferences / (name + '.plist')
            data = plistlib.loads(path.read_bytes()) if path.exists() else {}
            data.update(values)
            path.write_bytes(plistlib.dumps(data, fmt=plistlib.FMT_BINARY))
            os.chmod(path, 0o600)
            os.chown(path, MOBILE, MOBILE)
            print('pref', name, sorted(values))
        for parent in (mount / 'mobile/Library', preferences):
            os.chown(parent, MOBILE, MOBILE)
        for sub in CONTAINERS:
            d = mount / 'containers' / sub
            if not d.is_dir():
                d.mkdir(parents=True)
                os.chmod(d, 0o755)
                print('mkdir containers/' + sub)
    os.sync()
    entries = sum(len(files) + len(dirs) for _, dirs, files in os.walk(mount))
    print(f'populated {entries} entries')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--os-mount', type=Path, help='mounted (read-only) target OS volume')
    parser.add_argument('--volume-uuid', type=uuid.UUID, help='the Data volume UUID (CONFIG_XNU_OWNER_DATA_VOLUME_UUID)')
    parser.add_argument('--gib', type=int, help='container size; default from the darwin partition and the root image')
    parser.add_argument('--unixnu', type=Path, default=ROOT.parent / 'UniXNU', help='the UniXNU checkout (packer, outputs)')
    parser.add_argument('--output', type=Path, help='packed seed; default out/komodo/userdata/data-seed.dbr')
    parser.add_argument('--no-skip-setup', action='store_true', help='leave Setup to run on first boot')
    parser.add_argument('--populate', nargs=3, metavar=('TEMPLATE', 'MOUNT', 'SKIP'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.populate:
        populate(args.populate[0], args.populate[1], args.populate[2] == '1')
        return
    if not args.os_mount or not args.volume_uuid:
        parser.error('--os-mount and --volume-uuid are required')
    template = args.os_mount / 'private/var'
    if not template.is_dir():
        sys.exit(f'{template} is not a directory; mount the OS volume first')
    for tool in ('mkapfs', 'apfsck', 'sudo', 'losetup'):
        if not shutil.which(tool):
            sys.exit(f'{tool} not found')
    if 'apfs' not in Path('/proc/filesystems').read_text():
        sys.exit('the apfs kernel module is not loaded (sudo modprobe apfs)')
    sys.path.insert(0, str(args.unixnu / 'drivers/DarwinBoot/Test'))
    import packed_ramdisk
    board = tomllib.loads((ROOT / 'board.toml').read_text())
    spec = board['userdata']
    userdata = (spec['last_lba'] - spec['first_lba'] + 1) * spec.get('lba_bytes', 4096)
    out = args.unixnu / 'out' / board['board']['name'] / 'userdata'
    if args.gib:
        gib = args.gib
    else:
        report = out / 'userdata-root.json'
        if not report.is_file():
            sys.exit(f'{report} missing: build the root image first or give --gib')
        gib = auto_gib(userdata, json.loads(report.read_text())['image_bytes'])
    if not 3 <= gib <= 1024:
        sys.exit(f'{gib} GiB is outside 3..1024')
    output = args.output or out / 'data-seed.dbr'
    raw = output.with_suffix('.raw')
    output.parent.mkdir(parents=True, exist_ok=True)
    for stale in (raw, output):
        if stale.exists():
            stale.unlink()
    volume_uuid = str(args.volume_uuid).upper()
    print(f'seed: {gib} GiB container, volume {volume_uuid}, label Data')
    with raw.open('wb') as handle:
        handle.truncate(gib * GIB)
    subprocess.run(['mkapfs', '-L', 'Data', '-u', volume_uuid, str(raw)], check=True)
    mount = Path('/mnt/komodo-data-seed')
    loop = None
    try:
        loop = subprocess.run(['sudo', 'losetup', '-f', '--show', str(raw)], check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run(['sudo', 'mkdir', '-p', str(mount)], check=True)
        subprocess.run(['sudo', 'mount', '-t', 'apfs', '-o', 'rw,readwrite', loop, str(mount)], check=True)   # readwrite: the module's experimental write support
        subprocess.run(['sudo', sys.executable, str(Path(__file__).resolve()), '--populate', str(template), str(mount),
                        '0' if args.no_skip_setup else '1'], check=True)
    finally:
        subprocess.run(['sudo', 'umount', str(mount)], capture_output=True)
        if loop:
            subprocess.run(['sudo', 'losetup', '-d', loop], capture_output=True)
    check = subprocess.run(['apfsck', str(raw)], capture_output=True, text=True)
    if check.returncode:
        sys.stderr.write(check.stdout[-2000:] + check.stderr[-2000:])
        sys.exit('apfsck rejected the seed')
    packed_ramdisk.pack(raw, output)
    blob = output.read_bytes()
    logical, extents = packed_ramdisk.regions(blob)
    used = sum(len(data) for _, data in extents)
    record = {'output': str(output), 'sha256': hashlib.sha256(blob).hexdigest(), 'packed_bytes': len(blob), 'logical_bytes': logical,
              'nonzero_bytes': used, 'extents': len(extents), 'volume_uuid': volume_uuid, 'gib': gib, 'skip_setup': not args.no_skip_setup,
              'template': str(template), 'build': BUILD, 'userdata_bytes': userdata, 'pruned': list(PRUNE)}
    output.with_suffix('.json').write_text(json.dumps(record, indent=2) + '\n')
    raw.unlink()
    print(f'seed: {output} ({len(blob) >> 20} MiB packed, {used >> 20} MiB nonzero of {logical >> 30} GiB) sha256 {record["sha256"]}')
    print(f'seed: CONFIG_XNU_OWNER_DATA_VOLUME_UUID="{volume_uuid}", then unixnu build payload --data-ramdisk {output}')


if __name__ == '__main__':
    main()
