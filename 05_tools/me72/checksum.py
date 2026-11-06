"""38 BMW checks: 3 ROMSYS + CRC32 + 34 multipoint sums with inverses.

The independent verification path uses arrays and bitwise CRC, not repair's
struct/zlib implementation. MP sum/inverse pairs can lie inside their own or
other ranges. Canonicalize all pairs before repair: every valid 32-bit pair
contributes the same 0x1FFFE to a little-endian 16-bit word sum.
"""
from array import array
import struct
import sys
import zlib
from .images import PROFILE, BASE, validate, require

MP = tuple(row['offset'] for row in PROFILE['multipoint'])


def crc_bitwise(data):
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
    return value ^ 0xFFFFFFFF


def sum_array(data):
    words = array('H'); words.frombytes(data)
    if sys.byteorder != 'little':words.byteswap()
    return sum(words) & 0xFFFFFFFF


def romsys(data):
    u16 = lambda p: int.from_bytes(data[p:p+2], 'little')
    u32 = lambda p: int.from_bytes(data[p:p+4], 'little')
    pages = [*range(0, 0x10000, 0x2000), *range(0x20000, u32(0x8014)-BASE, 0x2000)]
    return [('ROMSYS startup', 0x8038, u16(0x8000)+u16(0xFFFE)),
            ('ROMSYS parameter endpoints', u32(0x8010)-BASE,
             u16(u32(0x8030)-BASE)+u16(u32(0x8034)-BASE)),
            ('ROMSYS program endpoints', 0x803C,
             sum(u16(p)+u16(p+0x1FFE) for p in pages) & 0xFFFFFFFF)]


def verify(data, independent=True):
    data = validate(data)
    u32 = lambda p: int.from_bytes(data[p:p+4], 'little')
    checks = []
    for name, offset, calculated in romsys(data):
        checks.append(dict(name=name, offset=hex(offset), stored=u32(offset),
                           calculated=calculated, ok=u32(offset)==calculated))
    lo, hi = PROFILE['crc_range']; offset=PROFILE['crc_offset']
    calculated = crc_bitwise(data[lo:hi]) if independent else zlib.crc32(data[lo:hi])
    checks.append(dict(name='CRC32 calibration', offset=hex(offset), stored=u32(offset),
                       calculated=calculated, ok=u32(offset)==calculated))
    for row in PROFILE['multipoint']:
        offset, start, end = row['offset'], row['start'], row['end']
        region = data[start-BASE:end-BASE+1] if start != end else b''
        calculated = sum_array(region)
        stored, inverse = u32(offset+8), u32(offset+12)
        checks.append(dict(name='multipoint', offset=hex(offset), start=hex(start), end=hex(end),
            stored=stored, calculated=calculated, inverse=inverse,
            ok=stored==calculated and inverse==(stored ^ 0xFFFFFFFF)))
    return checks


def repair(data):
    data = bytearray(validate(data))
    for _, offset, value in romsys(data):struct.pack_into('<I', data, offset, value)
    # Verify each range includes either a complete pair or none. Partial pairs
    # would invalidate the canonicalization argument and need a new algorithm.
    for row in PROFILE['multipoint']:
        if row['start'] == row['end']:continue
        lo, hi = row['start']-BASE, row['end']-BASE+1
        for offset in MP:
            overlap = max(0, min(hi, offset+16)-max(lo, offset+8))
            require(overlap in (0, 8), 'Checksum range partially overlaps an MP pair')
    for offset in MP:struct.pack_into('<II', data, offset+8, 0, 0xFFFFFFFF)
    for row in PROFILE['multipoint']:
        start, end, offset = row['start'], row['end'], row['offset']
        region = data[start-BASE:end-BASE+1] if start != end else b''
        value = sum(x[0] for x in struct.iter_unpack('<H', region)) & 0xFFFFFFFF
        struct.pack_into('<II', data, offset+8, value, value ^ 0xFFFFFFFF)
    lo, hi = PROFILE['crc_range']
    struct.pack_into('<I', data, PROFILE['crc_offset'], zlib.crc32(data[lo:hi]))
    result = bytes(data)
    require(all(c['ok'] for c in verify(result)), 'Repaired image failed independent verification')
    return result


def storage_offsets():
    rom_locations=(0x8038,0x803C,PROFILE['romsys_pointers']['0x8010']-BASE)
    return ({p+i for p in rom_locations for i in range(4)} |
            set(range(PROFILE['crc_offset'], PROFILE['crc_offset']+4)) |
            {p+i for p in MP for i in range(8,16)})
