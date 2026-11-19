#!/usr/bin/env python3
"""Sample allowlisted script for workflow_dispatch practice."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone


def main() -> int:
    parser = argparse.ArgumentParser(description="Practice script executed by GitHub Actions")
    parser.add_argument(
        "--name",
        default="world",
        help="Name to include in the greeting",
    )
    args = parser.parse_args()

    payload = {
        "ok": True,
        "script": "hello.py",
        "message": f"hello, {args.name}",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
