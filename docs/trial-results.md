# Trial Results

No official `/run` trials were run.

## Local Validation

- `git diff --check`: pass
- `bash -n tasks/thermal-stack-calibration/tests/test.sh`: pass
- `bash -n tasks/thermal-stack-calibration/solution/solve.sh`: pass
- In-memory Python compilation: pass (`13` Python files)
- Visible calibration runner/schema smoke: pass (`6` calibration cases)
- Patch application smoke: pass (`8` patches apply sequentially)
- `python3 tools/partial_fix_audit.py --check-report`: pass (`256` states, only `0xff` passes, all 8 defect classes differentiated with 10x tolerance margin gate and field-level signatures)
- Local nop verifier: reward `0.0`
- Local oracle verifier: reward `1.0`
- Malicious `/tests` mutation smoke: reward `0.0`

## Docker Validation

Built local Docker images from `python:3.11-slim` with pinned `numpy==2.0.2`.
The v2 environment and tests images were built as `tscal-env:local` and
`tscal-tests:local`. Docker reused cached numpy install layers.

- Docker nop verifier: reward `0.0`
- Docker oracle verifier: reward `1.0`

## Reproduction Steps

Run from the repo root.

Static checks:

```bash
git diff --check
bash -n tasks/thermal-stack-calibration/tests/test.sh
bash -n tasks/thermal-stack-calibration/solution/solve.sh
python3 tools/partial_fix_audit.py --check-report
```

Visible calibration smoke:

```bash
tmp=$(mktemp -d)
python3 tasks/thermal-stack-calibration/environment/app/scripts/run_solver.py \
  --cases tasks/thermal-stack-calibration/environment/app/data/calibration_cases.json \
  --output "$tmp/visible-results.json"
python3 - <<'PY' "$tmp/visible-results.json"
import json, sys
payload = json.load(open(sys.argv[1]))
print(len(payload["results"]))
print([item["case_id"] for item in payload["results"]])
PY
rm -rf "$tmp"
```

Local nop:

```bash
tmp=$(mktemp -d)
cp -R tasks/thermal-stack-calibration/environment/app/. "$tmp/app"
APP_DIR="$tmp/app" LOG_DIR="$tmp/logs-nop" bash tasks/thermal-stack-calibration/tests/test.sh
cat "$tmp/logs-nop/reward.txt"
rm -rf "$tmp"
```

Local oracle:

```bash
tmp=$(mktemp -d)
cp -R tasks/thermal-stack-calibration/environment/app/. "$tmp/app"
APP_DIR="$tmp/app" bash tasks/thermal-stack-calibration/solution/solve.sh
APP_DIR="$tmp/app" LOG_DIR="$tmp/logs-oracle" bash tasks/thermal-stack-calibration/tests/test.sh
cat "$tmp/logs-oracle/reward.txt"
rm -rf "$tmp"
```

Docker build:

```bash
docker build -t tscal-env:local tasks/thermal-stack-calibration/environment
docker build -t tscal-tests:local tasks/thermal-stack-calibration/tests
```

Docker nop:

```bash
tmp=$(mktemp -d)
cid=$(docker create tscal-env:local)
docker cp "$cid:/app" "$tmp/app"
docker rm "$cid"
mkdir -p "$tmp/logs"
docker run --rm -v "$tmp/app:/app" -v "$tmp/logs:/logs/verifier" tscal-tests:local
cat "$tmp/logs/reward.txt"
rm -rf "$tmp"
```

Docker oracle:

```bash
tmp=$(mktemp -d)
cid=$(docker create tscal-env:local)
docker cp "$cid:/app" "$tmp/app"
docker rm "$cid"
docker run --rm \
  -v "$tmp/app:/app" \
  -v "$PWD/tasks/thermal-stack-calibration/solution:/solution:ro" \
  -e APP_DIR=/app \
  -w /solution \
  tscal-env:local \
  bash /solution/solve.sh
mkdir -p "$tmp/logs"
docker run --rm -v "$tmp/app:/app" -v "$tmp/logs:/logs/verifier" tscal-tests:local
cat "$tmp/logs/reward.txt"
rm -rf "$tmp"
```
