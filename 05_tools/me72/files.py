"""Exclusive artifact creation. Existing inputs/outputs are never replaced."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path


def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def save_bytes(path, data):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())


def save_json(path, value):
    save_bytes(path, (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())


def update_report(path, value):
    # The uniquely reserved report is the only mutable output of a run.
    path=Path(path); temporary=path.with_suffix('.pending')
    with temporary.open('w') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2); handle.write('\n')
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)
