# Trial Results

No official `/run` trials were run.

## Local Validation (v1.1)

- Originality grep against `/tmp/terminal-bench-3-upstream/tasks`: completed; no close thermal-contact/composite-wall finite-volume overlap found.
- Upstream `task.toml` schema convention check: completed; task uses `schema_version = "1.0"` with standard metadata/verifier/agent/environment sections.
- `git diff --check`: pass
- `bash -n tasks/thermal-contact-stack/tests/test.sh`: pass
- `bash -n tasks/thermal-contact-stack/solution/solve.sh`: pass
- In-memory Python compilation: pass (`13` Python files)
- Visible-case runner smoke: pass (`4` visible cases)
- Patch application smoke: pass (`8` patches apply sequentially)
- `python3 tools/partial_fix_audit.py --check-report`: pass (`256` states, only `0xff` passes, all 8 defect classes differentiated with 10x tolerance margin gate and field-level signatures)
- Local nop verifier: reward `0.0`
- Local oracle verifier: reward `1.0`
- Malicious `/tests` mutation smoke: reward `0.0`

## v1.1 Improvements (June 2026)

The v1.1 hardening pass improved hidden-case differentiation and added contact-resistance × interface-conductance entanglement:

- **h001 collapse eliminated**: Previously 224/255 failing states hit `h001.temperature_c[0]`. Now failures distribute across h002 (192), h006 (48), h005 (11), and h011 (4) with diverse output-field signatures.
- **All 8 defect classes differentiated**: The case-differentiation audit now checks all eight classes (not a 6-of-8 subset) and reports per-class detecting case IDs, responsible output fields, and field-level signal margins.
- **Entanglement case added**: `h005_entangled_high_contrast_contact` (133× k-contrast, 0.02 m²K/W contact resistance) proves that CONTACT_RESISTANCE_OMITTED and INTERFACE_CONDUCTANCE interact — fixing either alone fails, fixing both substantially improves the interface diagnostic signature.
- **All-but-one failure signatures are unique**: Each defect class produces a distinctive failure signature when removed (e.g., LEFT_BOUNDARY → entangled case temperature, RIGHT_CONVECTION → strong-convection temperatures, CONTACT_RESISTANCE → contact delta-t).

## Docker Validation

Built local Docker images from `python:3.11-slim` with pinned `numpy==2.0.2`. The v1.1 tests image was rebuilt after hidden-case and audit updates.

- Docker nop verifier: reward `0.0`
- Docker oracle verifier: reward `1.0`

## Reproduction Steps

Run from the repo root.

Static checks:

```bash
git diff --check
bash -n tasks/thermal-contact-stack/tests/test.sh
bash -n tasks/thermal-contact-stack/solution/solve.sh
python3 tools/partial_fix_audit.py --check-report
```

Local nop:

```bash
tmp=$(mktemp -d)
cp -R tasks/thermal-contact-stack/environment/app/. "$tmp/app"
APP_DIR="$tmp/app" LOG_DIR="$tmp/logs-nop" bash tasks/thermal-contact-stack/tests/test.sh
cat "$tmp/logs-nop/reward.txt"
rm -rf "$tmp"
```

Local oracle:

```bash
tmp=$(mktemp -d)
cp -R tasks/thermal-contact-stack/environment/app/. "$tmp/app"
APP_DIR="$tmp/app" bash tasks/thermal-contact-stack/solution/solve.sh
APP_DIR="$tmp/app" LOG_DIR="$tmp/logs-oracle" bash tasks/thermal-contact-stack/tests/test.sh
cat "$tmp/logs-oracle/reward.txt"
rm -rf "$tmp"
```

Docker build:

```bash
docker build -t tcs-tb3-env:local tasks/thermal-contact-stack/environment
docker build -t tcs-tb3-tests:local tasks/thermal-contact-stack/tests
```

Docker nop:

```bash
tmp=$(mktemp -d)
cid=$(docker create tcs-tb3-env:local)
docker cp "$cid:/app" "$tmp/app"
docker rm "$cid"
mkdir -p "$tmp/logs"
docker run --rm -v "$tmp/app:/app" -v "$tmp/logs:/logs/verifier" tcs-tb3-tests:local
cat "$tmp/logs/reward.txt"
rm -rf "$tmp"
```

Docker oracle:

```bash
tmp=$(mktemp -d)
cid=$(docker create tcs-tb3-env:local)
docker cp "$cid:/app" "$tmp/app"
docker rm "$cid"
docker run --rm -v "$tmp/app:/app" -v "$PWD/tasks/thermal-contact-stack/solution:/solution:ro" -e APP_DIR=/app -w /solution tcs-tb3-env:local bash /solution/solve.sh
mkdir -p "$tmp/logs"
docker run --rm -v "$tmp/app:/app" -v "$tmp/logs:/logs/verifier" tcs-tb3-tests:local
cat "$tmp/logs/reward.txt"
rm -rf "$tmp"
```
