#!/usr/bin/env python3
"""Run the thermal stack solver for a JSON case file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from thermal_stack.io import load_cases, write_results
from thermal_stack.solver import solve_case


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, help="Path to an input JSON file with a top-level cases array.")
    parser.add_argument("--output", required=True, help="Path where result JSON should be written.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_cases(args.cases)
    results = [solve_case(case) for case in cases]
    write_results(args.output, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
