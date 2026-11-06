"""Complete external-flash reads; diagnostic session restoration in finally."""
import time
from .images import BASE, SIZE, require, digest, validate
from .protocol import session_request, restore
from .files import save_bytes


def read_full(link, output, baud=124800):
    require(baud in (9600,124800), 'Only verified read speeds 9600 and 124800 are supported')
    fast = False
    data = bytearray()
    try:
        if baud == 124800:
            # A lost session ACK leaves the state uncertain; no write follows.
            fast = True
            result=session_request(link,bytes.fromhex('108687'))
            require(result[:2]==bytes.fromhex('5086'),'Fast-read session refused')
            link.port.baudrate=124800
        progress=time.monotonic()
        while len(data)<SIZE:
            address=BASE+len(data)
            amount=min(240,SIZE-len(data),65536-(address&0xFFFF))
            data.extend(link.read_flash(address,amount))
            if time.monotonic()-progress>=10 or len(data)==SIZE:
                print('READ_PROGRESS',len(data),'/',SIZE,flush=True); progress=time.monotonic()
        # Preserve actual complete bytes even if their profile/sample checks fail.
        save_bytes(output,data)
        print('READ_SAVED',output,digest(data),flush=True)
        for offset in range(0x10000,0x20000,240):
            length=min(240,0x20000-offset)
            require(link.read_flash(BASE+offset,length)==data[offset:offset+length],
                    'Repeated entire calibration read differs')
            if (offset-0x10000)%15360==0:print('CAL_REPEAT',offset-0x10000,'/ 65536',flush=True)
        for sector in range(0,SIZE,65536):
            for delta in (0,0xFF10):
                offset=sector+delta
                require(link.read_flash(BASE+offset,240)==data[offset:offset+240],
                        'Distributed full-image sample differs')
        validate(data)
        return bytes(data)
    finally:
        result=restore(link,dev_session=fast)
        print('NORMAL_DIAGNOSTICS_RESTORED',result['restored_9600'],flush=True)
