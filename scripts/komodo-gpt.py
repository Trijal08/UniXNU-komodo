#!/usr/bin/env python3
"""Print the GPT of a UFS LUN (or an image of its first megabytes) and the board.toml [userdata]
snippet for the partition named userdata.

  sudo python3 scripts/komodo-gpt.py /dev/sda
  python3 scripts/komodo-gpt.py lun0-head.bin --sector-size 4096

The sector size is detected from the "EFI PART" signature at LBA 1 unless given.
"""
import argparse
import struct
import sys
import uuid

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('device')
parser.add_argument('--sector-size', type=int, choices=[512, 4096])
parser.add_argument('--partition', default='userdata', help='Partition name to emit the snippet for')
args = parser.parse_args()

with open(args.device, 'rb') as handle:
    def read(offset, length):
        handle.seek(offset)
        data = handle.read(length)
        if len(data) != length:
            sys.exit(f'short read at {offset:#x}')
        return data

    sizes = [args.sector_size] if args.sector_size else [4096, 512]
    for sector in sizes:
        header = read(sector, 92)
        if header[:8] == b'EFI PART':
            break
    else:
        sys.exit('no GPT header at LBA 1 for 4096 or 512 byte sectors')

    (_, revision, header_size, _, _, current, backup, first_usable, last_usable,
     disk_guid, entries_lba, count, entry_size, _) = struct.unpack_from('<8sIIII QQQQ 16s QIII', header)
    entries = read(entries_lba * sector, count * entry_size)

print(f'sector size {sector}, disk {uuid.UUID(bytes_le=disk_guid)}, usable LBAs {first_usable:#x}..{last_usable:#x}')
print(f'{"name":<24} {"first":>12} {"last":>12} {"MiB":>10}')
snippet = None
for index in range(count):
    entry = entries[index * entry_size:(index + 1) * entry_size]
    type_guid, part_guid, first, last, flags = struct.unpack_from('<16s16sQQQ', entry)
    if type_guid == bytes(16):
        continue
    name = entry[56:56 + 72].decode('utf-16-le').rstrip('\0')
    mib = (last - first + 1) * sector / (1 << 20)
    print(f'{name:<24} {first:>#12x} {last:>#12x} {mib:>10.1f}')
    if name == args.partition:
        snippet = (first, last)

if snippet is None:
    sys.exit(f'no partition named {args.partition}')
first, last = snippet
print(f'\n[userdata]\nfirst_lba = {first:#x}\nlast_lba = {last:#x}\nlba_bytes = {sector}\n'
      f'# capacity {(last - first + 1) * sector / (1 << 30):.2f} GiB')
