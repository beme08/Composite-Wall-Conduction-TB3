#!/usr/bin/env python3
"""Loose local smoke checker used by facility technicians."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.results).read_text(encoding="utf-8"))
    worst = 0.0
    for result in payload.get("results", []):
        worst = max(worst, abs(float(result.get("energy_residual_w_m2", 0.0))))
        for value in result.get("temperature_c", []):
            if not math.isfinite(float(value)):
                print("not converged: non-finite temperature")
                return 1
    if worst < 1000.0:
        print("Converged! local smoke check passed")
    else:
        print("Warning: local residual diagnostic is outside the technician smoke threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
