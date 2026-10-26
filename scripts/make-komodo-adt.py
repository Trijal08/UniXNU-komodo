#!/usr/bin/env python3
"""Apple device tree for the Google Pixel 9 Pro XL (komodo, Tensor G4 "zumapro").

Called by `unixnu build payload` with the options listed in the Payload concept page. Board
addresses come from the mainline komodo device tree (arch/arm64/boot/dts/exynos/google):

  GIC-600 (GICv3)   GICD 0x10400000/0x10000, GICR 0x10440000/0x100000 (8 frames)
  UFS host          0x13200000 hci, 0x13201100 vs_hci, 0x13280000 unipro, 0x132a0000 ufsp
  UFS PHY           0x13204000
  USI2 / SPI2       0x108900c0 usi, 0x10890000 spi (Synaptics S3908 touch)
  UART0             0x10870000 (google,gs101-uart)
  DECON0 / DSIM0    0x19470000 / 0x19440000
  Mali-G715         0x1f000000
  DRAM              bank 0: 0x80000000 + 2 GiB; upper banks: 0x880000000 .. 0xbe0f83000

Every bus child sits inside one arm-io window at 0x10000000 of 256 MiB, so child `reg` values
are offsets from 0x10000000.

Identity: the iPad7,1 block follows make-sheng-adt.py (UniXNU-sheng) property for property. The
root model and target-type give hw.product and hw.target; the security tuple in /chosen makes
mobileactivationd take its Hactivation branch (no activation record, SEP or baseband); /buttons
and /product carry the artwork and button facts MobileGestalt reads. The panel geometry and the
button set are komodo's.
"""
from pathlib import Path
import argparse
import os
import struct
import uuid
import zlib

ARM_IO_BASE = 0x10000000
ARM_IO_SIZE = 0x10000000
DRAM_BANK0_BASE = 0x80000000
DRAM_BANK0_SIZE = 0x80000000
# Verified on the phone 2026-10-21: "arch_timer: cp15 timer running at 24.57MHz" and oscclk 24576000 Hz.
# ArmCpu reads CNTFRQ_EL0 itself, but the kernel's mach timebase comes from this property.
TIMEBASE_HZ = 24576000
CPU_COMPATIBLE = ['arm,cortex-a520'] * 4 + ['arm,cortex-a720'] * 3 + ['arm,cortex-x4']

BOARD_COMPATIBLE = ('google,komodo', 'google,zumapro')


def node(name, properties=(), children=()):
    properties = [('name', name.encode() + b'\0'), *properties]
    result = struct.pack('<II', len(properties), len(children))
    for key, data in properties:
        if len(key) > 31:
            raise SystemExit(f'property name too long: {key}')
        result += struct.pack('<32sI', key.encode(), len(data))
        result += data + bytes(-len(data) % 4)
    return result + b''.join(children)


def u32(value):
    return struct.pack('<I', value)


def u64(value):
    return struct.pack('<Q', value)


def string(value):
    return value.encode() + b'\0'


def strings(*values):
    return b''.join(string(v) for v in values)


def empty_nvram_proxy():
    """A fresh volatile CHRP bank for IODTNVRAM. komodo has no NVRAM controller XNU can use."""
    def header(name, size):
        raw = bytearray(struct.pack('<BBH12s', 0x70, 0, size // 16, name))
        checksum = sum(raw)
        while checksum > 255:
            checksum = (checksum & 255) + (checksum >> 8)
        raw[1] = checksum
        return raw

    image = bytearray(8192)
    image[:16] = header(b'nvram', 32)
    image[32:48] = header(b'common', 16 + 2048)
    free_at = 32 + 16 + 2048
    image[free_at:free_at + 16] = header(b'free', len(image) - free_at)
    struct.pack_into('<I', image, 16, zlib.adler32(image[20:]))
    return [('nvram-bank-size', u32(len(image))), ('nvram-bank-count', u32(1)),
            ('nvram-current-bank', u32(0)), ('nvram-proxy-data', bytes(image))]


def parse_int(value):
    return int(value, 0)


parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--dram-size', type=parse_int, default=DRAM_BANK0_SIZE, help='Size reported in /chosen/dram-size')
parser.add_argument('--dram-base', type=parse_int, default=DRAM_BANK0_BASE, help='Base reported in /chosen/dram-base')
parser.add_argument('--owned-memory-size', type=parse_int, help='Contiguous DarwinBoot window: 256 MiB to 8 GiB in 2 MiB steps')
parser.add_argument('--root-match-volume-uuid', type=uuid.UUID, help='Volume UUID of the OS window')
parser.add_argument('--chip-id', type=lambda v: int(v, 16), help='/chosen/chip-id (hex, as sheng), IOPlatformUUID seed with --unique-chip-id')
parser.add_argument('--cpu-regs', default='0,0x100,0x200,0x300,0x400,0x500,0x600,0x700', help='MPIDR affinity of each core, boot core first')
parser.add_argument('--psci-method', choices=['smc', 'hvc'], default='smc')
parser.add_argument('--unique-chip-id', type=lambda v: int(v, 16), help='/chosen/unique-chip-id (hex), 64-bit platform seed')
parser.add_argument('--packed-data-ramdisk', action='store_true', help='Reserve the PackedRAMDisk placeholder')
parser.add_argument('--data-ramdisk', action='store_true', help='Reserve the dense RAMDisk placeholder')
parser.add_argument('--trust-cache', action='store_true', help='Reserve the TrustCache placeholder')
parser.add_argument('--ipad-identity', action='store_true', help='Present the iPad7,1 identity of the bring-up IPSW')
parser.add_argument('--osenvironment', choices=['main', 'recoveryos', 'ramdisk'], default='main')
parser.add_argument('--crypto-hash-method', default='sha2-384')
parser.add_argument('--sleep-enabled', action='store_true', help='Omit /defaults/sleep-disabled; suspend is not implemented')
args = parser.parse_args()

if args.owned_memory_size is not None and (not 0x10000000 <= args.owned_memory_size <= 0x200000000 or args.owned_memory_size % 0x200000):
    parser.error('--owned-memory-size is 256 MiB to 8 GiB, aligned to 2 MiB')
if args.packed_data_ramdisk and args.data_ramdisk:
    parser.error('choose one Data delivery form')
if (args.unique_chip_id is None) != (args.chip_id is None):
    parser.error('--unique-chip-id and --chip-id must be supplied together')
cpu_regs = [int(v, 0) for v in args.cpu_regs.split(',') if v]
if not 1 <= len(cpu_regs) <= 8:
    parser.error('--cpu-regs lists 1 to 8 cores')

identity = args.ipad_identity

# /chosen
chosen = [('random-seed', os.urandom(64)),
          ('osenvironment', string(args.osenvironment)),
          ('dram-base', u64(args.dram_base)),
          ('dram-size', u64(args.dram_size)),
          ('crypto-hash-method', string(args.crypto_hash_method)),
          ('amfi-only-platform-code', u32(1))]
if args.owned_memory_size:
    chosen.append(('darwinboot-memory-size', u64(args.owned_memory_size)))
if args.root_match_volume_uuid:
    xml = ('<dict><key>IOProviderClass</key><string>IOMedia</string>'
           '<key>IOPropertyMatch</key><dict><key>UUID</key><string>' +
           str(args.root_match_volume_uuid).upper() + '</string></dict></dict>')
    chosen.append(('root-matching', string(xml)))
if args.packed_data_ramdisk or args.data_ramdisk:
    chosen.append(('ephemeral-storage', u32(1)))
if args.chip_id is not None:
    chosen.append(('chip-id', u32(args.chip_id)))
if args.unique_chip_id is not None:
    chosen.append(('unique-chip-id', u64(args.unique_chip_id)))
if identity:
    # Dev-fused, undemoted security status (0,0,1,1) as read by MobileGestalt; established on hardware by ios-sweet and sheng.
    chosen += [('certificate-production-status', u32(0)), ('effective-production-status-ap', u32(0)),
               ('certificate-security-mode', u32(1)), ('effective-security-mode-sep', u32(1))]
chosen += empty_nvram_proxy()

memory_map = []
if args.data_ramdisk:
    memory_map.append(('RAMDisk', bytes(16)))
if args.packed_data_ramdisk:
    memory_map.append(('PackedRAMDisk', bytes(16)))
if args.trust_cache:
    memory_map.append(('TrustCache', bytes(16)))

# /cpus: the first entry is the core the firmware hands over on; its reg must be that core's MPIDR.
cpus = []
for index, reg in enumerate(cpu_regs):
    cluster = (reg >> 8) & 0xff
    compatible = CPU_COMPATIBLE[min(cluster, len(CPU_COMPATIBLE) - 1)]
    cpus.append(node(f'cpu{index}', [('state', string('running' if index == 0 else 'waiting')),
                                     ('reg', u32(reg)),
                                     ('device_type', string('cpu')),
                                     ('compatible', string(compatible)),
                                     ('timebase-frequency', u32(TIMEBASE_HZ))]))

# /arm-io: one window, children as offsets. Only the interrupt controller is described for the
# first boots; storage, SPI and display nodes are added when their drivers exist.
def io(name, compatible, windows, extra=()):
    reg = b''.join(u64(base - ARM_IO_BASE) + u64(size) for base, size in windows)
    return node(name, [('compatible', string(compatible)), ('reg', reg), *extra])

arm_io_children = [
    io('intc', 'arm,gic-v3', [(0x10400000, 0x10000), (0x10440000, 0x100000)], [('redistributor-stride', u64(0x20000))]),
    # Described, not yet consumed. Driver matching starts when a personality names them.
    # The kernel's Apple UART driver (pexpert apple_uart, enabled for this kernel by the native-samsung-uart patch)
    # binds the boot console the way iBoot's tree does: node uart0, compatible uart-1,samsung. It reprograms the line
    # to 8N1 at 115200 and takes the divisor from 'ubrdiv'; 0x6b is what the firmware left (200 MHz source, sampling 16,
    # UFRACVAL 0x8 untouched), observed on 2026-10-22 with the passthrough driver.
    # exynos-fifo-status: this UART revision reports its FIFO levels with 8-bit counts (tx full is bit 24); the Apple
    # SoC layout the driver assumes (tx full bit 9) would let it overrun the transmit FIFO and drop characters.
    io('uart0', 'uart-1,samsung', [(0x10870000, 0xc0)], [('ubrdiv', u32(0x6b)), ('exynos-fifo-status', u32(1))]),
    # No 'interrupts' properties: the registry builder maps interrupts through interrupt-parent phandles the ADT
    # does not carry; the drivers take their INTIDs from board constants.
    io('ufshc', 'google,zuma-ufs', [(0x13200000, 0x200), (0x13201100, 0x2000), (0x13280000, 0x8000), (0x132a0000, 0xa014)],
       [('status', string('disabled'))]),
    io('ufsphy', 'google,zuma-ufs-phy', [(0x13204000, 0x4000)], [('status', string('disabled'))]),
    io('usi2', 'google,zuma-usi', [(0x108900c0, 0x20)], [('status', string('disabled'))]),
    io('spi2', 'google,zuma-spi', [(0x10890000, 0x30)], [('status', string('disabled'))]),
    io('decon0', 'google,zuma-decon', [(0x19470000, 0x6000), (0x19480000, 0xe000), (0x19490000, 0x10000), (0x194a0000, 0xe000)],
       [('status', string('disabled'))]),
    io('dsim0', 'google,zuma-dsim', [(0x19440000, 0x300), (0x19460100, 0x700), (0x19460000, 0x100)], [('status', string('disabled'))]),
    io('gpu', 'arm,mali-valhall-csf', [(0x1f000000, 0x480000)], [('status', string('disabled'))]),
]

# hw.product/hw.machine/hw.target come from the root model/target-type; libMobileGestalt prefix-matches hw.product.
root_properties = [('model', string('iPad7,1' if identity else 'komodo-first-boot')),
                   *([('target-type', string('J120'))] if identity else []),
                   ('compatible', strings(*BOARD_COMPATIBLE)),
                   ('#address-cells', u32(2)), ('#size-cells', u32(2))]

product = [('product-name', string('iPad Pro (12.9-inch) (2nd generation)' if identity else 'Pixel 9 Pro XL')),
           ('model', string('google,komodo'))]
if identity:
    product += [('product-description', string('iPad Pro (12.9-inch) (2nd generation)')),
                ('artwork-device-idiom', string('pad')),
                ('artwork-device-subtype', u32(2732)),
                ('artwork-scale-factor', u32(2)),
                ('artwork-display-gamut', string('P3')),
                ('compatible-device-fallback', string('iPad6,7')),
                ('thin-bezel', u32(1))]

buttons = [node('buttons', [('compatible', string('buttons')), ('device_type', string('buttons')),
                            # komodo has power and the volume rocker, no Home button; 2 is the non-mechanical answer BSPlatform passes through.
                            ('button-names', strings('hold', 'voldown', 'volup')),
                            ('home-button-type', u32(2))])] if identity else []

tree = node('device-tree', root_properties, [
    node('chosen', chosen, [node('memory-map', memory_map), node('manifest-properties')]),
    node('cpus', children=cpus),
    *([node('psci', [('compatible', string('arm,psci-1.0')), ('method', string(args.psci_method))])] if len(cpu_regs) > 1 else []),
    node('defaults', [] if args.sleep_enabled else [('sleep-disabled', u32(1))]),
    node('options'),
    node('product', product),
    *buttons,
    node('arm-io', [('device_type', string('arm-io')),
                    ('#address-cells', u32(2)), ('#size-cells', u32(2)),
                    ('ranges', u64(0) + u64(ARM_IO_BASE) + u64(ARM_IO_SIZE))], arm_io_children),
])

args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(tree)
print(f'komodo ADT: {len(tree)} bytes, {len(cpu_regs)} cpus, {len(arm_io_children)} arm-io children, identity {"iPad7,1" if identity else "komodo"}')
