#!/usr/bin/env python3
"""Validation baseline: probes the early horizon but does not identify modes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def call_oracle(oracle: str) -> None:
    with tempfile.TemporaryDirectory(prefix="sysid-replay-") as tmp_s:
        tmp = Path(tmp_s)
        inp = tmp / "input.json"
        out = tmp / "output.json"
        u = [0.0] * 2000
        u[0] = 1.0
        inp.write_text(json.dumps({"dt": 0.001, "u": u}), encoding="utf-8")
        subprocess.run(
            [sys.executable, oracle, "--input", str(inp), "--output", str(out)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    call_oracle(args.oracle)
    model = {
        "type": "state_space_siso",
        "continuous_time": False,
        "sample_time": 0.001,
        "model_order": 1,
        "A": [[0.999]],
        "B": [[0.0]],
        "C": [[0.0]],
        "D": [[0.0]],
    }
    Path(args.output).write_text(json.dumps(model, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
