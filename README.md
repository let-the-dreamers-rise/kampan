# Kampan

Kampan (Hindi for vibration) turns a phone slow-motion clip of a running machine into a vibration measurement it can
defend. When the clip cannot support a number, an agent says exactly what to capture next.

Built for the OpenCV AI Competition 2026, powered by AWS.

![Architecture](docs/architecture.png)

## Why

A phone can see a machine shake. It can also lie about it. Slow-motion files often claim 30 fps. Hands shake the camera.
Pixels are not millimetres. Small motion sinks under sensor noise. Fast vibration aliases into a slow-looking one.
A pipeline that ignores these conditions still prints a confident number, and the number is wrong.

Kampan's agent measures each condition with OpenCV 5 before it grades anything. If a check fails, it asks for a recapture
with a specific instruction, or asks the person one question. When severity reaches ISO 10816-1 zone C or D, it drafts a
maintenance ticket and holds it for human approval.

## Results

Closed-loop simulator, 10 capture scenarios, 3 seeds each. The baseline is the same OpenCV pipeline with no checks.

| | Correct | Confidently wrong | Abstained |
|---|---|---|---|
| Agent | 30/30 | 0 | 0 |
| Baseline | 15/30 | 12 | 3 |

Per-scenario detail, including how many recaptures and questions each case needed:
[docs/results/agent_vs_baseline.md](docs/results/agent_vs_baseline.md).

Other evaluations:

- **Sub-pixel accuracy versus noise and amplitude:** [docs/results/measurement.md](docs/results/measurement.md).
- **Tracker choice:** [docs/results/estimators.md](docs/results/estimators.md) compares `cv2.findTransformECC` with
  `cv2.phaseCorrelate`. Phase correlation's sub-pixel estimate depended strongly on texture, so ECC is the tracker.
- **Failure cases and limits:** see the technical report, [docs/REPORT.md](docs/REPORT.md).

The simulator renders every recapture the agent requests. Those recaptures are simulated and labelled as such.
Real clips go through the same agent; the human does the recapture.

## How it works

![Agent workflow](docs/agent-workflow.png)

| Check | OpenCV 5 tool | Agent response when it fails |
|---|---|---|
| Time base | container rate, Android capture-fps tag | ask the capture rate |
| Metric scale | ArUco `DICT_4X4_50`, sub-pixel corners, homography | recapture with marker 0 on the machine |
| Camera shake | ECC on static marker 1, else masked global ECC | stabilise, or recapture braced |
| Noise floor | spectrum SNR of the ECC track | move closer |
| Aliasing | peak positions across two capture rates | recapture at a separating rate |
| Severity | velocity RMS 10-1000 Hz, ISO 10816-1 class zones | ask running speed, propose ticket in zone C/D |

Region discovery uses DIS optical flow when no marker is present. The magnified view uses a Laplacian pyramid with a
temporal band-pass. The agent policy is deterministic Python. It uses no LLM and no paid API, and every decision is
written to a JSON trace.

## Run it locally

Python 3.12.

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python -m pytest
```

```bash
KAMPAN_LOCAL_DIR=out/storage .venv/bin/python -m app.local_server
```

Then open http://127.0.0.1:8765.

Reproduce the evaluation:

```bash
.venv/bin/python -m eval.bench_agent
```

```bash
.venv/bin/python -m eval.bench_measure
```

```bash
.venv/bin/python -m eval.bench_estimators
```

## Deploy to AWS

Needs the AWS CLI with credentials and Docker. One CloudFormation stack creates everything.

```bash
bash infra/deploy.sh
```

On Windows with Docker inside WSL, use `infra/deploy.ps1` instead.

The stack contains:

- **Lambda container image** (Python 3.12, opencv-python-headless 5.0.0.93) behind a function URL that serves both the UI and the API.
- **Private S3 bucket** for uploads through presigned POST, capped at 300 MB, with uploads expiring after one day and a TLS-only policy.
- **Observability:** CloudWatch logs with 14-day retention, embedded metrics, a dashboard, an error alarm and X-Ray tracing.
- **Cost guard:** reserved concurrency of 4.

## Film your own clip

Print [capture_kit/kampan-markers-A4.pdf](capture_kit/kampan-markers-A4.pdf) at 100% scale and follow
[capture_kit/HOW-TO-FILM.md](capture_kit/HOW-TO-FILM.md). Tape marker 0 to the machine and marker 1 to something still.

## Limits

- Kampan gives a camera screening estimate, not a certified ISO measurement.
- It sees motion in the image plane only. Motion toward the camera is invisible.
- Phone frame rates of 30, 60, 120 and 240 all divide 240, so they cannot separate some aliases. The agent then asks for a
  rate those cannot provide, or for the running speed.
- Long exposures blur fast vibration and hide amplitude. The report states the possible loss.

## Layout

| Path | Contents |
|---|---|
| `kampan/` | measurement tools, spectrum, de-aliasing, severity, diagnosis |
| `kampan/agent/` | evidence, policy, loop, trace |
| `app/` | Lambda handler, local server, storage, web UI |
| `eval/` | benchmarks; outputs in `docs/results/` |
| `infra/` | CloudFormation template and deploy scripts |
| `tests/` | pytest suite |

## License

MIT.
