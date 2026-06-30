#!/usr/bin/env bash
set -euo pipefail

variant="${SYSID_SOLUTION_VARIANT:-reference}"
case "$variant" in
    reference)
        src="/solution/fit.py"
        ;;
    naive)
        src="/solution/naive_fit.py"
        ;;
    replay)
        src="/solution/replay_fit.py"
        ;;
    brute)
        src="/solution/brute_fit.py"
        ;;
    *)
        echo "unknown SYSID_SOLUTION_VARIANT: $variant" >&2
        exit 2
        ;;
esac

install -m 0755 "$src" /app/solution/fit.py
