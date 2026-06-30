# Hidden Resonance SysID

You inherit a small system-identification package in `/app`. The public records
describe only low-frequency behavior, and `/app/scripts/simulate.py` is an
agent-editable placeholder during development. During verification the verifier
replaces that placeholder with a trusted simulator for a private deterministic
LTI instance.

Write:

```bash
/app/solution/fit.py
```

so it can be run as:

```bash
python3 /app/solution/fit.py \
  --oracle /app/scripts/simulate.py \
  --output /app/solution/model.json
```

Your program should actively probe the oracle at verification time, identify a
stable SISO LTI model, and write `model.json`.

## Oracle API

Call:

```bash
python3 /app/scripts/simulate.py --input input.json --output output.json
```

`input.json`:

```json
{
  "dt": 0.001,
  "u": [0.0, 1.0, 0.0]
}
```

`output.json`:

```json
{
  "t": [0.0, 0.001, 0.002],
  "y": [0.0, 0.0001, 0.0002]
}
```

The oracle simulates forced response from zero state only. It rejects requests
where `N * dt > 2.0`, `dt < 0.001`, `dt` is not an integer multiple of `0.001`,
`max(abs(u)) > 1.0`, or the input energy exceeds the cap. It does not return
tail samples after the probing horizon.

## Output Schema

Write JSON with exactly these fields:

```json
{
  "type": "state_space_siso",
  "continuous_time": false,
  "sample_time": 0.001,
  "model_order": 5,
  "A": [[0.9]],
  "B": [[1.0]],
  "C": [[1.0]],
  "D": [[0.0]]
}
```

`continuous_time` may be `false` for a discrete-time model at
`sample_time = 0.001`. Model order must be between 1 and 12. Matrices must be
finite numeric lists with shapes `A=(n,n)`, `B=(n,1)`, `C=(1,n)`, and `D=(1,1)`.
Unstable models, extra fields, executable blobs, NaN/Inf, and malformed shapes
are rejected.

The verifier evaluates only forced responses from zero state, so equivalent
state-space realizations are valid. Do not rely on a shared hidden initial
state.

## Public Data

Public calibration records live at:

```text
/app/data/public_calibration.json
```

They are low-rate development records and do not determine the private resonant
mode. Use them to understand scales and I/O conventions, then probe the
verification oracle to identify the full dynamics.
