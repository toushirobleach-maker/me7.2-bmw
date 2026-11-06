"""Strict image/layout validation for one software version, never a detector."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
PROFILE = json.loads(Path(__file__).with_name('profile_6901I41D.json').read_text())
BASE, SIZE = 0x800000, 0x80000
CAL_START, CAL_END = 0x10000, 0x20000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(data):
    require(len(data) == SIZE, 'Expected full 524288-byte external-flash image')
    epk = PROFILE['epk_offset']
    require(data[epk:epk+8] == b'6901I41D', 'Unsupported EPK/software layout')
    for offset, value in PROFILE['romsys_pointers'].items():
        require(struct.unpack_from('<I', data, int(offset, 16))[0] == value,
                'ROMSYS layout/pointer changed: ' + offset)
    for row in PROFILE['multipoint']:
        start, end = struct.unpack_from('<II', data, row['offset'])
        require((start, end) == (row['start'], row['end']),
                'Multipoint range changed at ' + hex(row['offset']))
        require(BASE <= start <= end < BASE+SIZE, 'Invalid multipoint boundary')
        require(start == end or (start % 2 == 0 and end % 2 == 1), 'Unaligned word range')
    return bytes(data)


def load(path, base=None):
    data = Path(path).read_bytes()
    if len(data) == 65536:
        require(base is not None, '64 KiB input needs --base with its full 512 KiB image')
        reference = validate(Path(base).read_bytes())
        data = reference[:CAL_START] + data + reference[CAL_END:]
    return validate(data)


def diff(before, after):
    require(len(before) == len(after), 'Cannot diff files of different sizes')
    return [{'offset': hex(i), 'old': f'{a:02X}', 'new': f'{b:02X}'}
            for i, (a, b) in enumerate(zip(before, after)) if a != b]


def calibration_transition(before, after):
    validate(before); validate(after)
    for data in (before,after):
        require(data[0x1FFFC:0x20000]==bytes.fromhex('5aa5c33c'),
                'Missing car-tested calibration end marker; a padded SP-Daten reconstruction is not a flash-qualified image')
    require(before[:CAL_START] == after[:CAL_START] and before[CAL_END:] == after[CAL_END:],
            'Write rejected: executable/non-calibration bytes differ from baseline')
    for offset, raw in PROFILE['erase_bound_vectors'].items():
        start = int(offset, 16); expected = bytes.fromhex(raw)
        require(before[start:start+len(expected)] == expected,
                'Loader erase-boundary evidence does not match baseline')
    return diff(before, after)
