#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
APP_DIR="${APP_DIR:-/app}"
TESTS_DIR="${TESTS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
FIX_DIR="${TESTS_DIR}/fixtures"
RUNNER="${APP_DIR}/scripts/run_solver.py"
HIDDEN_SRC="${FIX_DIR}/hidden_cases.json"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"
REWARD_FILE="${LOG_DIR}/reward.txt"
WORK=""
trap 'status=$?; [ -n "$WORK" ] && rm -rf "$WORK"; [ -f "$REWARD_FILE" ] || echo "0.0" > "$REWARD_FILE"; exit "$status"' EXIT
for path in "$RUNNER" "$HIDDEN_SRC" "$APP_DIR/data"; do
    [ -e "$path" ] || { echo "FATAL: missing required path: $path" >&2; exit 2; }
done
tree_digest() {
    python3 - "$1" <<'PYDIGEST'
import hashlib, sys
from pathlib import Path
root = Path(sys.argv[1]); h = hashlib.sha256()
for path in sorted(root.rglob("*")):
    if not path.is_file(): continue
    rel = path.relative_to(root).as_posix(); h.update(rel.encode("utf-8") + b"\0"); h.update(path.read_bytes()); h.update(b"\0")
print(h.hexdigest())
PYDIGEST
}
fail_tests_mutation() { local phase="$1"; echo "0.0" > "$REWARD_FILE"; echo ">> /tests mutation guard FAILED ${phase}" >&2; exit 1; }
DATA_DIGEST_BEFORE="$(tree_digest "$APP_DIR/data")"
TESTS_DIGEST_BEFORE="$(tree_digest "$TESTS_DIR")"
WORK="$(mktemp -d)"
HIDDEN_COPY="${WORK}/cases.json"
RESULTS_PATH="${WORK}/results.json"
cp "$HIDDEN_SRC" "$HIDDEN_COPY"
echo ">> running /app solver"
(cd "$WORK" && env -u TESTS_DIR -u FIX_DIR -u HIDDEN_SRC -u HIDDEN_CASES_PATH -u RESULTS_PATH -u LOG_DIR -u REWARD_FILE -u OLDPWD python3 "$RUNNER" --cases "$HIDDEN_COPY" --output "$RESULTS_PATH")
TESTS_DIGEST_AFTER_APP="$(tree_digest "$TESTS_DIR")"
[ "$TESTS_DIGEST_BEFORE" = "$TESTS_DIGEST_AFTER_APP" ] || fail_tests_mutation "before unittest"
echo ">> grading emitted output"
set +e
APP_DIR="$APP_DIR" RESULTS_PATH="$RESULTS_PATH" HIDDEN_CASES_PATH="$HIDDEN_COPY" PYTHONPATH="$TESTS_DIR" python3 -m unittest discover -s "$TESTS_DIR" -p 'test_*.py' -v
UNITTEST_RC=$?
set -e
TESTS_DIGEST_AFTER_UNITTEST="$(tree_digest "$TESTS_DIR")"
[ "$TESTS_DIGEST_BEFORE" = "$TESTS_DIGEST_AFTER_UNITTEST" ] || fail_tests_mutation "after unittest"
DATA_DIGEST_AFTER="$(tree_digest "$APP_DIR/data")"
if [ "$DATA_DIGEST_BEFORE" = "$DATA_DIGEST_AFTER" ]; then echo ">> /app/data mutation guard OK"; DATA_RC=0; else echo ">> /app/data mutation guard FAILED" >&2; DATA_RC=1; fi
TESTS_DIGEST_FINAL="$(tree_digest "$TESTS_DIR")"
if [ "$TESTS_DIGEST_BEFORE" = "$TESTS_DIGEST_FINAL" ]; then TESTS_RC=0; else echo ">> /tests mutation guard FAILED before reward" >&2; TESTS_RC=1; fi
if [ "$UNITTEST_RC" -eq 0 ] && [ "$DATA_RC" -eq 0 ] && [ "$TESTS_RC" -eq 0 ]; then echo "1.0" > "$REWARD_FILE"; echo ">> verifier reward: 1.0"; exit 0; else echo "0.0" > "$REWARD_FILE"; echo ">> verifier reward: 0.0 (unittest=${UNITTEST_RC} data=${DATA_RC} tests=${TESTS_RC})"; exit 1; fi
