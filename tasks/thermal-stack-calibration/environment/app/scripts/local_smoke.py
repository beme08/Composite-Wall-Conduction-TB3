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
        worst = max(worst, abs(float(result.get("energy_residual_w", 0.0))))
        for value in result.get("temperature_c", []):
            if not math.isfinite(float(value)):
                raise SystemExit("not converged: non-finite temperature")
    if worst < 1000.0:
        print("Converged! local smoke check passed")
        return 0
    print("Solver diverged near an interface; try refining the mesh")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
