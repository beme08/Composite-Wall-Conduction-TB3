#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1
TESTS_DIR="${TESTS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
REPORT_PATH="${SYSID_REPORT_PATH:-/tmp/hidden_resonance_sysid_report.json}"
export SYSID_REPORT_PATH="$REPORT_PATH"

if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    LOG_DIR="/tmp/hidden_resonance_sysid_logs"
    mkdir -p "$LOG_DIR"
fi
REWARD_FILE="${LOG_DIR}/reward.txt"
trap 'status=$?; [ -f "$REWARD_FILE" ] || echo "0.0" > "$REWARD_FILE"; exit "$status"' EXIT

set +e
python3 -m unittest "$TESTS_DIR/test_sysid.py" -v 2>&1 | tee "$LOG_DIR/unittest.log"
UNITTEST_RC=${PIPESTATUS[0]}
set -e

if [ -f "$REPORT_PATH" ]; then
    cp "$REPORT_PATH" "$LOG_DIR/sysid_report.json"
fi

if [ "$UNITTEST_RC" -eq 0 ]; then
    echo "1.0" > "$REWARD_FILE"
    echo ">> verifier reward: 1.0"
    exit 0
fi

echo "0.0" > "$REWARD_FILE"
echo ">> verifier reward: 0.0 (unittest=${UNITTEST_RC})"
exit 1
