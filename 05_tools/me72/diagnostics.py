"""Previously used read-only measured-value, DTC and three RAM-word requests."""
import json
from pathlib import Path
import time
from .images import require
from .protocol import decode_live

RAM = (0xFD2E,0xFDD8,0xFD50)
TABLE_PATH=Path(__file__).with_name('fault_tables.json')


def policy(p):
    allowed={b'\xa2',*[bytes.fromhex('2240')+bytes([d]) for d in (0,3,4,5,7)],
             *[b'\x23'+a.to_bytes(3,'big')+b'\x02' for a in RAM]}
    require(p in allowed or (len(p)==2 and p[0]==0xA0),'Read-only diagnostics gate rejected request')


def read_ram(link):
    words={}
    for address in RAM:
        raw=link.read_flash(address,2)
        words[hex(address)]=dict(raw=raw.hex(),word_le=int.from_bytes(raw,'little'))
    lr=words['0xfd2e']['word_le']; inhibit=words['0xfdd8']['word_le']
    return dict(words=words,B_lr=bool(lr&0x200),B_lr2=bool(lr&0x400),
                inhibit_bank1=bool(inhibit&0x200),inhibit_bank2=bool(inhibit&0x400),
                note='FD50 denotes configured sensor presence, not sensor readiness')


def read_dtcs(link):
    tables=json.loads(TABLE_PATH.read_text())['ort']
    first=link.request(b'\xa0\0')
    require(len(first)>=2 and first[0]==0xE0,'Malformed DTC count')
    faults=[]
    for index in range(1,first[1]+1):
        response=link.request(bytes([0xA0,index]))
        require(len(response)>=6 and response[0]==0xE0,'Malformed DTC record')
        code=response[3]
        faults.append(dict(index=index,code=hex(code),description=tables.get(str(code),{}).get('text'),
            status_raw=response[4:6].hex(),payload=response.hex()))
    return dict(count=first[1],count_payload=first.hex(),faults=faults,
                note='Raw statuses retained. No heuristic ART/current-fault interpretation and no clearing.')


def read_lambda(link, samples=16):
    require(1<=samples<=60,'Sample count must be 1..60')
    result=[]
    start=time.monotonic()
    for index in range(samples):
        raw={}
        for did in (0,3,4,5,7):
            response=link.request(bytes.fromhex('2240')+bytes([did]))
            require(response[:3]==bytes.fromhex('6240')+bytes([did]),'Wrong measured-value group')
            raw[f'400{did}']=response.hex()
        p=bytes.fromhex(raw['4000'])
        sample=dict(t_s=round(time.monotonic()-start,3),raw=raw,live=decode_live(p),
            coolant_C=p[18]*0.75-48,
            fr1_raw=int.from_bytes(p[5:7],'big'),fr2_raw=int.from_bytes(p[7:9],'big'),
            fr1_ratio_approx=int.from_bytes(p[5:7],'big')/32768,
            fr2_ratio_approx=int.from_bytes(p[7:9],'big')/32768)
        result.append(sample)
        print('LAMBDA_SAMPLE',index+1,sample['fr1_ratio_approx'],sample['fr2_ratio_approx'],flush=True)
        if index+1<samples:time.sleep(1.25)
    return dict(samples=result,ram=read_ram(link),
                note='FR raw/32768 is approximate; original SGBD scales differ by about 0.0006. RAM flags are direct.')
