"""Fake devices only. None of these classes opens a serial port."""
from me72.protocol import BASE, SIZE, erase_request
from me72.transport import readonly_policy

class FakePort:
    baudrate = 9600
    in_waiting = 0

    def __init__(self, response):
        self.response, self.writes, self.parts = response, [], []

    def write(self, packet):
        self.writes.append(packet)
        # Deliberately fragmented cable echo + fragmented ECU response.
        raw = packet + self.response
        self.parts.extend(raw[i:i+3] for i in range(0, len(raw), 3))
        return len(packet)

    def read(self, _):
        return self.parts.pop(0) if self.parts else b''

    def flush(self):
        pass

    def close(self):
        pass

class FakeECU:
    """Stateful flash memory model; transport policy is applied on every call."""
    def __init__(self, source, fault=None):
        self.memory = bytearray(source)
        self.policy = readonly_policy
        self.calls = []
        self.address = 0
        self.blocks = 0
        self.fault = fault

    def request(self, p, timeout=3):
        self.policy(p)
        self.calls.append(p)
        if p == erase_request():
            self.memory[:] = b'\xff' * SIZE
            if self.fault == 'erase_timeout':
                raise TimeoutError('Erase occurred but its acknowledgement was lost')
            return bytes.fromhex('71 02 00 01')
        if p[0] == 0x34:
            self.address = 0
            return b'\x74'
        if p[0] == 0x36:
            if self.fault == 'transfer_timeout' and self.address >= 128:
                raise TimeoutError('Block may have been written; acknowledgement lost')
            self.memory[self.address:self.address+len(p)-1] = p[1:]
            self.address += len(p)-1
            self.blocks += 1
            if self.fault == 'bad_transfer_status':
                return bytes.fromhex('76 00 80 02')
            count = self.blocks - 1 if self.fault == 'duplicate_counter' else self.blocks
            return b'\x76' + count.to_bytes(2, 'big') + b'\x01'
        if p == b'\x37':
            return b'\x77'
        if p[0] == 0x23:
            address = int.from_bytes(p[1:4], 'big') - BASE
            data = bytes(self.memory[address:address+p[-1]])
            if self.fault == 'readback_corruption' and address == 0:
                data = bytes([data[0] ^ 1]) + data[1:]
            return b'\x63' + data
        if p == b'\x31\x01':
            return b'\x71\x01' + (b'\x01' if self.fault == 'bad_checksum' else b'\0')
        raise AssertionError(p.hex())

    def read_flash(self, address, length, memory_type=False):
        return self.request(b'\x23' + address.to_bytes(3, 'big') + b'\x06' + bytes([length]))[1:]
