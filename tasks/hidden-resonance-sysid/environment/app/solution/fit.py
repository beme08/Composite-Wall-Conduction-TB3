#!/usr/bin/env python3
"""Naive inherited predictor: valid shape, wrong dynamics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    model = {
        "type": "state_space_siso",
        "continuous_time": False,
        "sample_time": 0.001,
        "model_order": 1,
        "A": [[0.95]],
        "B": [[0.0]],
        "C": [[0.0]],
        "D": [[0.0]],
    }
    Path(args.output).write_text(json.dumps(model, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
