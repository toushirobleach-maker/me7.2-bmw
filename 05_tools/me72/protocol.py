"""Wire protocol extracted from the car-tested 2026-11-06 implementation.
No port is opened by import; no generic/raw command CLI is provided.
"""
import time
import json
from .images import require
from .transport import readonly_policy, NegativeResponse
BASE, SIZE = 0x810000, 0x10000

def region(address, length):
    require(BASE <= address < address + length <= BASE + SIZE,
            'Operation outside the fixed calibration region')

def erase_request():
    # 10EK726 @ FFcb / 1002C..100BA: start address, memory type 06,
    # three zero bytes. This OEM service erases by address, NOT by byte count.
    return b'\x31\x02' + BASE.to_bytes(3, 'big') + b'\x06\x00\x00\x00'

def download_request(address, length):
    region(address, length)
    # OEM @10607..107CB: address3, memory type06, format00, length3.
    return b'\x34' + address.to_bytes(3, 'big') + b'\x06\x00' + length.to_bytes(3, 'big')

def transfer_request(data):
    require(1 <= len(data) <= 240, 'Invalid transfer block length')
    # OEM @10A4A..10B86: raw data only, NO UDS/VAG block counter.
    return b'\x36' + bytes(data)

def derive_key(seed_payload, nonce):
    require(3 <= nonce <= 41, 'Nonce outside OEM range')
    require(seed_payload[:2] == b'\x67\x01', 'Not an OEM seed response')
    # Indices in BEST/2 refer to the entire ECU frame, WITHOUT its XOR byte.
    full = bytes([0xB8, 0xF1, 0x12, len(seed_payload)]) + seed_payload
    require(len(full) >= 48, 'Seed frame too short for OEM algorithm')
    return bytes((full[0x15 + i] + full[0x2C + i] + full[(nonce + i) % 0x31]) & 255
                 for i in range(4))

def auth_policy(payload):
    if payload == bytes.fromhex('10 85 01') or payload == bytes.fromhex('27 01'):
        return
    if len(payload) == 6 and payload[:5] == bytes.fromhex('27 02 42 4d 57') and 3 <= payload[5] <= 41:
        return
    if len(payload) == 6 and payload[:2] == bytes.fromhex('27 04'):
        return
    readonly_policy(payload)

def authenticate(link, nonce=17):
    # Exactly one key attempt; the OEM retry loop is deliberately not copied.
    r = link.request(bytes.fromhex('27 02 42 4d 57') + bytes([nonce]))
    require(r[:2] == b'\x67\x02', 'OEM challenge setup refused')
    seed = link.request(bytes.fromhex('27 01'))
    require(seed[:2] == b'\x67\x01', 'OEM seed request refused')
    require(len(seed) >= 4, 'Truncated seed response')
    if seed[2:4] == b'\0\0':
        return dict(already_authorized=True)
    key = derive_key(seed, nonce)
    r = link.request(b'\x27\x04' + key)
    require(r[:2] == b'\x67\x04', 'OEM key not acknowledged')
    return dict(already_authorized=False, nonce=nonce, key_accepted=True)

def decode_live(payload):
    require(payload[:3] == bytes.fromhex('62 40 00') and len(payload) >= 29,
            'Unexpected live-data response')
    return dict(rpm=int.from_bytes(payload[10:12], 'big') * 0.25,
                speed_kmh=payload[9] * 1.25, voltage_V=round(payload[25] * 0.095, 3),
                scaling='OEM me72kwp1.prg BetriebswTab UB: frame byte29 * 0.095 V')

def baseline(link, minimum_voltage=12.5):
    ident = link.request(b'\xa2')
    require(ident[:8] == b'\xe27532675', 'Unexpected DME identity')
    require(ident[8:10] == b'0F' and ident[12:14] == b'AC', 'Unexpected hardware/diagnostic index')
    live = decode_live(link.request(bytes.fromhex('22 40 00')))
    require(live['rpm'] == 0 and live['speed_kmh'] == 0, 'Engine or vehicle is moving')
    print('BASELINE', json.dumps(live), flush=True)
    require(minimum_voltage <= live['voltage_V'] <= 14.8,
            f"Supply {live['voltage_V']} V outside development range {minimum_voltage}..14.8 V")
    return dict(ident_payload=ident.hex(), live=live)

def session_request(link, payload, wait_seconds=5):
    """OEM session job repeats only the explicit busy NRC21, not timeouts."""
    require(payload in (bytes.fromhex('10 81'), bytes.fromhex('10 85 01'),
                        bytes.fromhex('10 86 10'), bytes.fromhex('10 86 87')),
            'Not a known session request')
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            return link.request(payload)
        except NegativeResponse as e:
            if e.payload != bytes.fromhex('7f 10 21') or time.monotonic() >= deadline:
                raise
            time.sleep(0.15)

def restore(link, dev_session=False):
    if dev_session:
        r = session_request(link, bytes.fromhex('10 86 10'))
        require(r[:2] == bytes.fromhex('50 86'), 'Read baud restoration refused')
        link.port.baudrate = 9600
    # No reset service; default diagnostic session only.
    r = session_request(link, bytes.fromhex('10 81'))
    require(r[:2] == bytes.fromhex('50 81'), 'Diagnostic session restoration refused')
    ident = link.request(b'\xa2')
    require(ident[:8] == b'\xe27532675', 'DME identity absent after restoration')
    return dict(restored_9600=True, ident_payload=ident.hex())
