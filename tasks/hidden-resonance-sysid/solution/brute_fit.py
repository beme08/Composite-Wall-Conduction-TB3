#!/usr/bin/env python3
"""Validation baseline: exceeds the verifier fit wall-clock."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    Path("/tmp/sysid_brute_child_pid.txt").write_text(str(child.pid), encoding="utf-8")
    time.sleep(120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
