"""Review corrections over the preserved GPL-3.0 C166 decoder.
Selected opcode forms verified; linear listing, not full control-flow analysis.
Original wrapper source is preserved in evidence reviews; explicit image input
and range validation are repository packaging changes.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'decoder'))
from c166_disasm import C166Disassembler

class ReviewDecoder(C166Disassembler):
    def bitword(self, value):
        if value < 0x80:
            return f'0x{0xFD00 + 2 * value:04X}'
        if value < 0xF0:
            return f'0x{0xFF00 + 2 * (value & 0x7F):04X}'
        return f'R{value & 15}'

    def cbitaddr(self, word, bit):
        return f'{self.bitword(int(word, 2))}.{int(bit, 2)}'

    def cbitoff(self, word):
        return self.bitword(int(word, 2))

    def cmask8(self, mask):
        return f'#0x{int(mask, 2):02X}'

    def decode_one(self, buf, off, ea):
        length, raw, text = super().decode_one(buf, off, ea)
        instruction = buf[off:off + length]
        opcode = instruction[0]
        if opcode == 0xD7 and length == 4 and instruction[1] & 0xC0 == 0x40:
            page = int.from_bytes(instruction[2:4], 'little')
            count = ((instruction[1] >> 4) & 3) + 1
            text = f'EXTP     #0x{page:03X},#{count}'
        if opcode == 0xDC and length == 2 and instruction[1] & 0xC0 == 0x40:
            count = ((instruction[1] >> 4) & 3) + 1
            text = f'EXTP     R{instruction[1] & 15},#{count}'
        if opcode == 0xC0 and length == 2:
            source = self.cRb(format(instruction[1] >> 4, '04b'))
            text = f'MOVBZ    R{instruction[1] & 15},{source}'
        if opcode == 0xC2 and length == 4:
            dest = (f'R{instruction[1] & 15}' if instruction[1] >= 0xF0
                    else f'short_reg(0x{instruction[1]:02X})')
            text = f'MOVBZ    {dest},0x{int.from_bytes(instruction[2:4], "little"):04X}'
        return length, raw, text

D=ReviewDecoder()

def decode(start, end, image):
    if not (0x800000 <= start < end <= 0x800000+len(image)):
        raise ValueError("Decode range outside image")
    rows = []
    cursor = start - 0x800000
    page = None
    count = 0
    while cursor < end - 0x800000:
        length, raw, text = D.decode_one(image, cursor, cursor + 0x800000)
        instruction = image[cursor:cursor + length]
        note = ''
        if count:
            # Annotate explicit mem16 forms only. Do not infer runtime pointers,
            # register-EXTP page values, branches, or arbitrary DPP state.
            memory_forms = (0xF2, 0xF3, 0xF6, 0xF7, 0xC2, 0x42, 0x43, 0x02,
                            0x03, 0x22, 0x23, 0x62, 0x63, 0x72, 0x73)
            if length == 4 and instruction[0] in memory_forms:
                mem = int.from_bytes(instruction[2:4], 'little')
                physical = page * 0x4000 + (mem & 0x3FFF)
                note = f' ; EXTP physical=0x{physical:06X}'
            count -= 1
        if length == 4 and instruction[0] == 0xD7 and instruction[1] & 0xC0 == 0x40:
            page = int.from_bytes(instruction[2:4], 'little')
            count = ((instruction[1] >> 4) & 3) + 1
        rows.append(f'{cursor + 0x800000:06X} {raw:<10} {text}{note}')
        cursor += length
    return '\n'.join(rows) + '\n'
