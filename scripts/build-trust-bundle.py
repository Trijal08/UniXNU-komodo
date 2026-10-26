#!/usr/bin/env python3
"""Bundle the two unchanged original trust-cache modules of the target IPSW for the payload (--trust-cache).

  python3 scripts/build-trust-bundle.py [--ipsw-dir out/ipsw/21H461] [--output out/komodo/payload/original-static-system.bundle]

The members (StaticTrustCache and Cryptex1,SystemTrustCache, `unixnu ipsw fetch` extracts them) are IM4P
envelopes; their payloads are version-2 trust-cache modules with 24-byte entries. The bundle is the loader's
format (count, offsets, modules) and must hash to one of the board's [payload] trust_cache_sha256 values; the
sheng port recorded 7416ca4f… for this pair, which proves the modules came through unchanged.
"""
import argparse
import hashlib
import struct
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def der(data, at):
    tag, size = data[at], data[at + 1]
    at += 2
    if size & 128:
        count = size & 127
        size = int.from_bytes(data[at:at + count], 'big')
        at += count
    return tag, data[at:at + size], at + size


def im4p_payload(blob):
    tag, sequence, end = der(blob, 0)
    fields, cursor = [], 0
    while cursor < len(sequence):
        kind, data, cursor = der(sequence, cursor)
        fields.append((kind, data))
    if tag != 0x30 or end != len(blob) or [k for k, _ in fields][:4] != [0x16, 0x16, 0x16, 4] or fields[0][1] != b'IM4P':
        sys.exit('not an IM4P envelope')
    return fields[3][1]


def module(data, name):
    if struct.unpack_from('<I', data)[0] != 2 or len(data) != 24 + struct.unpack_from('<I', data, 20)[0] * 24:
        sys.exit(f'{name}: not a complete version-2 trust module')
    return data


parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
board = tomllib.loads((ROOT / 'board.toml').read_text())
parser.add_argument('--unixnu', type=Path, default=ROOT.parent / 'UniXNU')
parser.add_argument('--ipsw-dir', type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
ipsw_dir = args.ipsw_dir or args.unixnu / 'out/ipsw' / board['ipsw']['build']
# The members are named after the volume they cover: the OS member's trust cache and the SystemOS cryptex's.
os_member = next(n for n in board['ipsw']['sha256'] if n.startswith('044-76040'))
systemos_member = next(n for n in board['ipsw']['sha256'] if n.startswith('044-76034'))
for member in (os_member, systemos_member):
    if not (ipsw_dir / (member + '.trustcache')).is_file():
        sys.exit(f'{ipsw_dir / (member + ".trustcache")} missing: run "unixnu ipsw fetch StaticTrustCache Cryptex1,SystemTrustCache"')
static = module(im4p_payload((ipsw_dir / (os_member + '.trustcache')).read_bytes()), 'StaticTrustCache')
system = module(im4p_payload((ipsw_dir / (systemos_member + '.trustcache')).read_bytes()), 'Cryptex1,SystemTrustCache')
bundle = struct.pack('<3I', 2, 12, 12 + len(static)) + static + system
digest = hashlib.sha256(bundle).hexdigest()
allowed = board.get('payload', {}).get('trust_cache_sha256', [])
if allowed and digest not in allowed:
    sys.exit(f'bundle sha256 {digest} is not in board.toml [payload] trust_cache_sha256')
output = args.output or args.unixnu / 'out' / board['board']['name'] / 'payload' / 'original-static-system.bundle'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(bundle)
print(f'trust bundle: {output} ({len(bundle)} bytes, {struct.unpack_from("<I", static, 20)[0]} + {struct.unpack_from("<I", system, 20)[0]} entries) sha256 {digest}')
