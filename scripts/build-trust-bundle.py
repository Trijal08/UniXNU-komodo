#!/usr/bin/env python3
"""Bundle the unchanged original trust-cache modules of the target IPSW for the payload (--trust-cache).

  python3 scripts/build-trust-bundle.py [--ipsw-dir out/ipsw/23F84] [--output out/komodo/payload/original.bundle]
      [--component StaticTrustCache --component Cryptex1,SystemTrustCache ...]

`unixnu ipsw fetch` writes each extracted member next to a .json sidecar naming the component it came from,
which is how the members are found: the file names are release-specific (044-76040… on 21H461,
094-54256-108.dmg.aea… on 23F84) but the component names are not. The members are IM4P envelopes; their
payloads are version-2 trust-cache modules with 24-byte entries. The bundle is the loader's format
(count, offsets, modules), which DarwinBoot's ValidTrustCaches accepts for up to 128 modules.

By default it bundles the modules that cover the volumes the board's [userdata] windows carry, in that
order. When the board declares [payload] trust_cache_sha256 the digest must be one of them, which proves
the modules came through unchanged; without that list the digest is only reported.
"""
import argparse
import hashlib
import json
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


# The trust cache of a volume is the component named after it, with the OS suffix dropped: the OS
# volume is covered by StaticTrustCache, Cryptex1,SystemOS by Cryptex1,SystemTrustCache and
# Cryptex1,AppOS by Cryptex1,AppTrustCache.
def trust_component(volume):
    if volume == 'OS':
        return 'StaticTrustCache'
    prefix, sep, name = volume.partition(',')
    return f'{prefix}{sep}{name.removesuffix("OS")}TrustCache' if sep else f'{volume}TrustCache'


parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
board = tomllib.loads((ROOT / 'board.toml').read_text())
default = [trust_component(w['component']) for w in board.get('userdata', {}).get('windows', [])]
parser.add_argument('--unixnu', type=Path, default=ROOT.parent / 'UniXNU')
parser.add_argument('--ipsw-dir', type=Path)
parser.add_argument('--output', type=Path)
parser.add_argument('--component', action='append', metavar='NAME',
                    help=f'IPSW component to bundle, in order (default: {" ".join(default) or "none"})')
args = parser.parse_args()
ipsw_dir = args.ipsw_dir or args.unixnu / 'out/ipsw' / board['ipsw']['build']
wanted = args.component or default
if not wanted:
    sys.exit('nothing to bundle: pass --component, or give the board [userdata] windows')

# Index what has been fetched by the component each file came from, not by its release-specific name.
fetched = {}
for sidecar in sorted(ipsw_dir.glob('*.trustcache.json')):
    fetched[json.loads(sidecar.read_text())['component']] = sidecar.with_suffix('')
missing = [name for name in wanted if name not in fetched]
if missing:
    sys.exit(f'{ipsw_dir}: no member for {", ".join(missing)}: run "unixnu ipsw fetch {" ".join(missing)}"')

modules = [module(im4p_payload(fetched[name].read_bytes()), name) for name in wanted]
offsets, cursor = [], 4 + 4 * len(modules)
for payload in modules:
    offsets.append(cursor)
    cursor += len(payload)
bundle = struct.pack(f'<{1 + len(offsets)}I', len(modules), *offsets) + b''.join(modules)
digest = hashlib.sha256(bundle).hexdigest()
allowed = board.get('payload', {}).get('trust_cache_sha256', [])
if allowed and digest not in allowed:
    sys.exit(f'bundle sha256 {digest} is not in board.toml [payload] trust_cache_sha256')
output = args.output or args.unixnu / 'out' / board['board']['name'] / 'payload' / 'original.bundle'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(bundle)
counts = ' + '.join(f'{struct.unpack_from("<I", m, 20)[0]} {n}' for n, m in zip(wanted, modules))
print(f'trust bundle: {output} ({len(bundle)} bytes, {counts}) sha256 {digest}')
