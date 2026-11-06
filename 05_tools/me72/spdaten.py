"""Offline sparse SP-Daten importer for the observed ME7.2 record dialect.

Record types 00 and BMW 10 carry bytes; type 04 sets the upper address.
The observed zero type-02 records coexist with the upper address. Nonzero
segments/other extensions are deliberately unsupported. Input record checksums
are checked before any use. Gaps are coverage gaps, not evidence of erased FF.
"""
from pathlib import Path
from .images import (BASE,SIZE,CAL_START,CAL_END,validate,calibration_transition,
                     require,digest,diff)
from .checksum import verify,repair,storage_offsets

# Fields identified in this layout. This is not a universal VIN/ISN map.
PRESERVE_FIELDS=((0x1FD26,0x1FD44),(0x1FD54,0x1FFFC))


def read_records(path):
    memory={};upper=0;ended=False;records=0
    for line_no,line in enumerate(Path(path).read_text(encoding='latin-1').splitlines(),1):
        if not line.startswith(':'):continue
        require(not ended,f'Record after EOF at line {line_no}')
        try:record=bytes.fromhex(line[1:])
        except ValueError as exc:raise ValueError(f'Invalid hex at line {line_no}') from exc
        require(len(record)>=5 and len(record)==record[0]+5,f'Wrong record length at {line_no}')
        require(sum(record)&255==0,f'Record checksum failed at {line_no}')
        records+=1;address=int.from_bytes(record[1:3],'big');kind=record[3];data=record[4:-1]
        if kind==4:
            require(len(data)==2 and address==0,'Invalid extended linear address')
            upper=int.from_bytes(data,'big')<<16
        elif kind==2:
            require(data==b'\0\0' and address==0,'Unsupported nonzero segment address')
        elif kind==1:
            require(not data and address==0,'Invalid EOF record');ended=True
        elif kind in (0,0x10):
            for i,value in enumerate(data):
                absolute=upper+address+i
                require(BASE<=absolute<BASE+SIZE,'Data outside supported external flash')
                require(absolute not in memory or memory[absolute]==value,'Conflicting overlapping records')
                memory[absolute]=value
        else:raise ValueError(f'Unsupported record type {kind:#x}')
    require(ended and memory,'Missing EOF or no data bytes')
    return memory,dict(file=Path(path).name,records=records,covered_bytes=len(memory),
                       sha256=digest(Path(path).read_bytes()))


def coverage_ranges(addresses):
    result=[]
    for address in sorted(addresses):
        if result and result[-1][1]==address:result[-1][1]+=1
        else:result.append([address,address+1])
    return [[hex(a),hex(b)] for a,b in result]


def reconstruct(program_path,data_path):
    program,pm=read_records(program_path);data,dm=read_records(data_path)
    require(all(not BASE+CAL_START<=a<BASE+CAL_END for a in program),'.0PA overlaps calibration; unsupported pairing')
    require(all(BASE+CAL_START<=a<BASE+CAL_END for a in data),'.0DA is not calibration-only')
    result=bytearray(b'\xff'*SIZE)
    for source in (program,data):
        for address,value in source.items():result[address-BASE]=value
    validate(result)
    return bytes(result),program,data,dict(program=pm,data=dm,
        total_covered_bytes=len(set(program)|set(data)),
        calibration_uncovered_ranges=coverage_ranges(set(range(CAL_START,CAL_END))-{a-BASE for a in data}),
        fill_policy='FF for analysis reconstruction only, not assumed physical flash content')


def prepare_calibration(baseline,program_path,data_path):
    baseline=validate(baseline)
    require(all(c['ok'] for c in verify(baseline)),'Baseline checksum failure; use a verified full ECU read')
    stock,program,data,report=reconstruct(program_path,data_path)
    mismatches=[address for address,value in program.items() if baseline[address-BASE]!=value]
    require(not mismatches,'Known .0PA bytes differ from baseline program; calibration-only update cannot restore the program: '+
            ', '.join(hex(a) for a in mismatches[:8]))
    target=bytearray(baseline);overlaid=[];preserved=[]
    for address,value in data.items():
        offset=address-BASE
        if any(lo<=offset<hi for lo,hi in PRESERVE_FIELDS):
            preserved.append(offset);continue
        target[offset]=value;overlaid.append(offset)
    target=repair(target)
    changes=calibration_transition(baseline,target)
    require(all(target[lo:hi]==baseline[lo:hi] for lo,hi in PRESERVE_FIELDS),
            'Identified service fields were unexpectedly changed')
    checksum_fields=storage_offsets()
    require(all(target[i]==baseline[i] for i in range(CAL_START,CAL_END)
                if BASE+i not in data and i not in checksum_fields),
            'Unexpected uncovered-byte change')
    report.update(operation='prepare_stock_calibration_overlay_offline',
        baseline_sha256=digest(baseline),analysis_reconstruction_sha256=digest(stock),
        output_sha256=digest(target),program_covered_bytes_match=True,
        overlaid_data_bytes=len(overlaid),protected_covered_bytes=len(preserved),
        protected_fields=[[hex(a),hex(b)] for a,b in PRESERVE_FIELDS],changes=changes,
        checksums=verify(target),
        limitations=['Not a complete factory restore; uncovered program/EEPROM/IROM not supplied by SP-Daten.',
                    'Correct ZUSB/hardware/vehicle variant selection and separate coding/EWS checks remain required.',
                    'Protected fields are layout-specific identification/UIF areas, not a general VIN/ISN transplant.',
                    'Preparation has offline tests; no hardware stock-restore trial is claimed.'])
    return bytes(target),report
