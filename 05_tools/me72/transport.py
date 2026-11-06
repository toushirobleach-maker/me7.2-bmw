"""ME7.2 KWP2000* transport; no port is opened at import time.

Kept separate from the allowlisted original reader. Live callers must provide
an explicit policy; the default permits only bounded reads and known sessions.
There is no automatic retry of an erase, download or transfer request.
"""
from __future__ import annotations
from datetime import datetime, timezone
from functools import reduce
from operator import xor
from pathlib import Path
import json
import os
import time


class ProtocolError(RuntimeError):
    pass


class NegativeResponse(ProtocolError):
    def __init__(self, payload):
        self.payload = bytes(payload)
        super().__init__('ECU negative response: ' + self.payload.hex(' '))


def encode(payload: bytes, destination=0x12, source=0xF1):
    if not 1 <= len(payload) <= 255:
        raise ValueError('Invalid KWP2000* payload length')
    body = bytes([0xB8, destination, source, len(payload)]) + payload
    return body + bytes([reduce(xor, body, 0)])


class FrameDecoder:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while len(self.buffer) >= 5:
            if self.buffer[0] != 0xB8:
                del self.buffer[0]
                continue
            # Only the two known directions are accepted, including cable echo.
            if bytes(self.buffer[1:3]) not in (b'\x12\xf1', b'\xf1\x12'):
                del self.buffer[0]
                continue
            length = self.buffer[3] + 5
            if len(self.buffer) < length:
                break
            candidate = bytes(self.buffer[:length])
            if reduce(xor, candidate, 0):
                del self.buffer[0]
                continue
            frames.append(candidate)
            del self.buffer[:length]
        if len(self.buffer) > 260:
            raise ProtocolError('Receive buffer overflow')
        return frames


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open('x', encoding='utf-8')

    def __call__(self, **event):
        event['utc'] = datetime.now(timezone.utc).isoformat()
        self.handle.write(json.dumps(event, ensure_ascii=False) + '\n')
        self.handle.flush()
        os.fsync(self.handle.fileno())

    def close(self):
        self.handle.close()


def readonly_policy(payload):
    if payload in (b'\xa2', bytes.fromhex('22 40 00'), bytes.fromhex('21 01'),
                   bytes.fromhex('30 eb 01'), bytes.fromhex('10 81'),
                   bytes.fromhex('10 86 87'), bytes.fromhex('10 86 10')):
        return
    if payload[:1] == b'\x23' and len(payload) in (5, 6):
        address = int.from_bytes(payload[1:4], 'big')
        length = payload[-1]
        if len(payload) == 6 and payload[4] != 6:
            raise ValueError('Only memory type 06 is allowed')
        if 0x800000 <= address < address + length <= 0x880000 and 1 <= length <= 240:
            return
    raise ValueError('Request forbidden by read-only policy: ' + payload.hex(' '))


class Transport:
    def __init__(self, device, journal, policy=readonly_policy, port=None):
        self.journal, self.policy = journal, policy
        self.decoder = FrameDecoder()
        if port is None:
            if not device.startswith('/dev/cu.usbserial-'):
                raise ValueError('An explicit USB serial callout port is required')
            import serial
            port = serial.Serial(None, 9600, 8, 'E', 1, timeout=0.01,
                                 write_timeout=2, exclusive=True,
                                 xonxoff=False, rtscts=False, dsrdtr=False)
            port.port, port.dtr, port.rts = device, False, False
            port.open()
            time.sleep(0.15)
            port.reset_input_buffer()
        self.port = port

    def request(self, payload, timeout=3.0):
        payload = bytes(payload)
        self.policy(payload)
        packet = encode(payload)
        # Persist intent before a byte can leave the port.
        self.journal(event='tx', baud=self.port.baudrate, frame=packet.hex())
        count = self.port.write(packet)
        if count != len(packet):
            raise ProtocolError('Short serial write; request outcome is uncertain')
        self.port.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = self.port.read(max(1, min(self.port.in_waiting, 1024)))
            for packet in self.decoder.feed(raw):
                if packet[1:3] == b'\x12\xf1':
                    continue  # Local cable echo is not an ECU acknowledgement.
                response = packet[4:-1]
                self.journal(event='rx', baud=self.port.baudrate, frame=packet.hex())
                if response[:1] == b'\x7f':
                    if len(response) != 3 or response[1] != payload[0]:
                        raise ProtocolError('Unrelated or malformed negative response')
                    if response[2] == 0x78:
                        continue  # Wait; never resend a destructive request here.
                    raise NegativeResponse(response)
                if not response or response[0] != (payload[0] + 0x40) & 255:
                    raise ProtocolError('Unexpected ECU response: ' + response.hex(' '))
                return response
        self.journal(event='timeout', sid=f'{payload[0]:02X}')
        raise TimeoutError('No final ECU acknowledgement; no automatic retry')

    def read_flash(self, address, length, memory_type=False):
        payload = b'\x23' + address.to_bytes(3, 'big')
        payload += (b'\x06' if memory_type else b'') + bytes([length])
        response = self.request(payload)
        if len(response) != length + 1:
            raise ProtocolError('Wrong flash read length')
        return response[1:]

    def close(self):
        self.port.close()
