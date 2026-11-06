#!/usr/bin/env python3
"""ME7.2 verify entry point. See 03_docs/TOOLS_RU.md."""
from me72.cli import verify_main, entry

if __name__ == "__main__":
    raise SystemExit(entry(verify_main))
