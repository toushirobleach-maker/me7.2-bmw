"""Calibration-only state machine: protocol tested on one ECU, refactor offline-tested.
No automatic reset, retry after timeout, recovery write, or arbitrary command.
"""
import time
from .images import require, digest as sha, calibration_transition
from .checksum import verify
from .transport import ProtocolError, NegativeResponse
from .protocol import BASE, SIZE, erase_request, download_request, transfer_request
UIF_RANGES = ((0xFD26, 0xFD44), (0xFD54, 0xFD82))
UIF_SAMPLE_OFFSET, UIF_SAMPLE_LENGTH = 0xFD20, 112


class CalibrationWriter:
    def __init__(self, source, target, *, programming_uif_reference=None, block_size=128):
        calibration_transition(source, target)
        require(all(c['ok'] for c in verify(source)), 'Invalid source checksums')
        require(all(c['ok'] for c in verify(target)), 'Invalid target checksums')
        require(block_size == 128, 'Only the car-tested 128-byte block size is supported')
        source = source[0x10000:0x20000]
        self.target = bytes(target[0x10000:0x20000])
        self.programming_target = self.target
        self.operation = 'calibration_64KiB'
        self.block_size = block_size
        self.state = 'preflight_required'
        self.offset = 0
        self.blocks_acknowledged = 0
        self.erase_may_have_started = False
        self.last_readback = None
        self.readback_exact = False
        if programming_uif_reference is not None:
            reference = bytes(programming_uif_reference)
            require(len(reference) == UIF_SAMPLE_LENGTH, 'Incomplete pre-erase UIF reference')
            permitted = {i for lo, hi in UIF_RANGES for i in range(lo, hi)}
            for i, value in enumerate(reference, UIF_SAMPLE_OFFSET):
                if i not in permitted:
                    require(value == source[i], 'Unexpected pre-erase data outside UIF fields')
            view = bytearray(self.target)
            for lo, hi in UIF_RANGES:
                require(self.target[lo:hi] == source[lo:hi],
                        'UIF exception would hide intentional changes to identification/UIF fields')
                view[lo:hi] = reference[lo-UIF_SAMPLE_OFFSET:hi-UIF_SAMPLE_OFFSET]
            self.programming_target = bytes(view)

    def arm(self, *, authentication_ok, session_ok, max_block_length, supply_ok,
            erase_boundary_reviewed):
        require(self.state == 'preflight_required', 'Writer already armed or used')
        require(all((authentication_ok, session_ok, supply_ok, erase_boundary_reviewed)),
                'Incomplete live preconditions; erase forbidden')
        require(self.block_size + 1 <= max_block_length <= 255,
                'Chosen transfer length exceeds OEM metadata limit')
        self.state = 'ready_to_erase'

    def policy(self, payload):
        allowed = False
        if self.state == 'erasing':
            allowed = payload == erase_request()
        elif self.state == 'download':
            allowed = payload == download_request(BASE, SIZE)
        elif self.state == 'transfer':
            part = self.target[self.offset:self.offset+self.block_size]
            allowed = bool(part) and payload == transfer_request(part)
        elif self.state == 'exit_transfer':
            allowed = payload == b'\x37'
        elif self.state == 'verify':
            # Independent readback limited to calibration and factory checksum.
            if payload == b'\x31\x01':
                allowed = True
            elif len(payload) == 6 and payload[0] == 0x23 and payload[4] == 6:
                address, length = int.from_bytes(payload[1:4], 'big'), payload[-1]
                allowed = BASE <= address < address+length <= BASE+SIZE and 1 <= length <= 240
        if not allowed:
            raise ProtocolError(f'Request forbidden in writer state {self.state}: {payload.hex()}')

    def run(self, link, journal):
        require(self.state == 'ready_to_erase', 'Writer has not passed its preconditions')
        # The final transport gate checks both state AND exact candidate bytes.
        link.policy = self.policy
        try:
            self.state = 'erasing'
            journal(event='erase_intent', address=hex(BASE), calibration_sha256=sha(self.target))
            print('ERASE_BEGIN', hex(BASE), SIZE, self.operation, flush=True)
            self.erase_may_have_started = True
            # OEM repeats only an explicit NRC 21. A timeout is never retried.
            deadline = time.monotonic() + 60
            while True:
                try:
                    result = link.request(erase_request(), timeout=60)
                    break
                except NegativeResponse as e:
                    if e.payload != bytes.fromhex('7f 31 21') or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)
            require(len(result) == 4 and result[:2] == b'\x71\x02', 'Malformed erase acknowledgement')
            require(result[3] == 1 or result[3] >= 0x80, 'OEM erase reported a failure')
            journal(event='erase_acknowledged', payload=result.hex())
            print('ERASE_ACK', result.hex(), flush=True)
            self.state = 'download'
            # OEM @10835 checks NRC23 (routine not complete) for requestDownload.
            deadline = time.monotonic() + 10
            while True:
                try:
                    result = link.request(download_request(BASE, SIZE))
                    break
                except NegativeResponse as e:
                    if e.payload != bytes.fromhex('7f 34 23') or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)
            require(result[:1] == b'\x74', 'Download request not acknowledged')
            print('DOWNLOAD_ACK', result.hex(), flush=True)
            self.state = 'transfer'
            while self.offset < SIZE:
                part = self.target[self.offset:self.offset+self.block_size]
                result = link.request(transfer_request(part), timeout=5)
                require(len(result) == 4 and result[0] == 0x76, 'Malformed transfer acknowledgement')
                # Current binary @80B45C increments 0x9B18 and @80B46A..492
                # returns it BE. It is a block count, NOT the number of bytes.
                count = int.from_bytes(result[1:3], 'big')
                require(count == self.blocks_acknowledged + 1,
                        'Unexpected/duplicate transfer acknowledgement counter')
                require(result[3] == 1 or result[3] >= 0x80, 'OEM transfer reported a failure')
                journal(event='transfer_acknowledged', offset=self.offset, length=len(part),
                        oem_count=int.from_bytes(result[1:3], 'big'), status=result[3])
                self.offset += len(part)
                self.blocks_acknowledged += 1
                if self.blocks_acknowledged % 32 == 0 or self.offset == SIZE:
                    print('WRITE_PROGRESS', self.offset, '/', SIZE, flush=True)
            self.state = 'exit_transfer'
            require(link.request(b'\x37') == b'\x77', 'Transfer exit not acknowledged')
            print('TRANSFER_COMPLETE', flush=True)
            self.state = 'verify'
            data = bytearray()
            while len(data) < SIZE:
                data.extend(link.read_flash(BASE+len(data), min(240, SIZE-len(data)), memory_type=True))
                if len(data) % 15360 == 0 or len(data) == SIZE:
                    print('VERIFY_PROGRESS', len(data), '/', SIZE, flush=True)
            self.last_readback = bytes(data)
            self.readback_exact = self.last_readback == self.target
            require(self.readback_exact or self.last_readback == self.programming_target,
                    'Full calibration readback differs from target and captured pre-erase UIF view')
            journal(event='calibration_readback_checked', exact=self.readback_exact,
                    matched_pre_erase_uif_view=not self.readback_exact,
                    sha256=sha(data), postcycle_verification_required=not self.readback_exact)
            deadline = time.monotonic() + 60
            while True:
                try:
                    result = link.request(b'\x31\x01', timeout=60)
                    break
                except NegativeResponse as e:
                    if e.payload != bytes.fromhex('7f 31 21') or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)
            require(len(result) >= 3 and result[:2] == b'\x71\x01' and result[2] == 0,
                    'OEM calibration checksum verification failed')
            self.state = 'verified' if self.readback_exact else 'programming_view_verified'
            journal(event='write_verified', bytes=self.offset, sha256=sha(data),
                    exact=self.readback_exact, postcycle_verification_required=True)
            print('SESSION_WRITE_VERIFIED_IGNITION_CYCLE_REQUIRED', sha(data), flush=True)
            return bytes(data)
        except BaseException as e:
            self.state = 'uncertain_after_erase'
            journal(event='write_stopped', offset=self.offset, error=f'{type(e).__name__}: {e}',
                    automatic_reset=False, automatic_retry=False)
            # Never reset, start the engine, switch to normal operation, or
            # restore the original automatically after an uncertain transfer.
            raise
