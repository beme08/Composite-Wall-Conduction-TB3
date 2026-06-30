#!/usr/bin/env python3
"""Agent-editable placeholder. The verifier replaces this file."""

from __future__ import annotations

import sys


def main() -> int:
    print("simulate.py is a verifier-owned oracle and is unavailable before verification", file=sys.stderr)
    return 99


if __name__ == "__main__":
    raise SystemExit(main())
