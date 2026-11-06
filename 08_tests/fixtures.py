"""Artificial images constructed in RAM; no vehicle dump or runnable firmware.

The checksum/layout envelope is realistic, but the program is predominantly FF.
The marker here is test input, never a recipe for repairing a SP-Daten image.
"""
from pathlib import Path
import sys
import struct
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'05_tools'))
from me72.images import PROFILE
from me72.checksum import repair


def synthetic_image():
    data=bytearray(b'\xff'*0x80000)
    for offset,value in PROFILE['romsys_pointers'].items():
        struct.pack_into('<I',data,int(offset,16),value)
    for row in PROFILE['multipoint']:
        struct.pack_into('<4I',data,row['offset'],row['start'],row['end'],0,0xFFFFFFFF)
    for offset,raw in PROFILE['erase_bound_vectors'].items():
        start=int(offset,16);value=bytes.fromhex(raw);data[start:start+len(value)]=value
    epk=PROFILE['epk_offset'];data[epk:epk+8]=b'6901I41D'
    data[0x10000:0x10002]=bytes.fromhex('5a5a')
    data[0x1FFFC:0x20000]=bytes.fromhex('5aa5c33c')
    data[0x19CC4]=0x56
    data[0x1FCE5]=240
    return repair(data)


def synthetic_target():
    data=bytearray(synthetic_image());data[0x19CC4]=0x57
    return repair(data)
