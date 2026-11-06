#!/usr/bin/env python3
"""ME7.2 checksums entry point. See 03_docs/TOOLS_RU.md."""
from me72.cli import checksum_main, entry

if __name__ == "__main__":
    raise SystemExit(entry(checksum_main))
