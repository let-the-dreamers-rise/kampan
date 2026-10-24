# Kampan - spec (HackForge stages run by hand, 2026-10-24)

Kampan (Hindi: vibration) turns a phone slow-motion clip of a running machine into a vibration
measurement it can defend, and says what to capture next when it cannot.

## Contest facts (scout)

- OpenCV AI Competition 2026, powered by AWS. Devpost: https://opencv26.devpost.com (rules at /rules).
- Deadline: Oct 26 2026, 11:59 PM Pacific (opencv.org). Devpost shows Oct 27 12:15 PM IST. Target: submit by Oct 27 09:00 IST.
- Must: OpenCV 5 for substantive video analysis; a meaningful AWS component; technical report; judge-accessible repo;
  pinned deps with build, deploy and test instructions; architecture diagram; working web endpoint; video of at most
  5 minutes showing the team, the app, the architecture and principal results; evaluation evidence with failure cases.
- Overall rubric: technical execution 30, innovation 20, real-world impact 20, UX 10, documentation 10, cloud delivery 10.
- Agentic Vision Award: OpenCV 5 + agent 30, orchestration and autonomy 25, task effectiveness and evaluation 20,
  failure handling, observability, security and human control 15, UX and docs 10. Needs an agent workflow diagram and a
  trace showing OpenCV output changing a later decision.
- Risk: opencv.org says registration closed Aug 17 and that teams which submitted a proposal build the final project.
  Devpost still offers "Join hackathon" and its rules have no proposal clause. The user must join and should confirm by email.

## Winners and saturation (analyst)

- 2021 grand prizes: Cortic Tigers (AI education on OAK-D), NeoCam (neonate telemonitoring), Cerebros (EEG wheelchair).
  Pattern: a concrete physical problem, a working device, a human who benefits.
- Prior art for this idea: motion magnification for machinery is commercial (RDI Motion Amplification, MSI VibVue), in papers
  (Wu 2012 Eulerian magnification; Wadhwa 2013 phase-based; a 2025 SciTePress paper adding a classifier), and in one Devpost
  project ("Motion Amplification Video Techniques for Vibration Analysis"). Magnification alone is not new and is not the claim.

## The claim

A phone clip gives a vibration number only if the clip is trustworthy: right time base, camera not shaking, a real metric scale,
signal above the noise floor, no aliasing. Existing tools assume a lab capture. Kampan's agent measures each of those conditions
with OpenCV, refuses to grade when one fails, and tells the person holding the phone exactly what to change. Evaluated in a
closed-loop simulator against the same pipeline without the agent, and on real clips.

## Demo (video beats, at most 5 min, target 3:30)

1. Hook: a table fan that looks still; Kampan's magnified view shows it shaking. Severity zone on screen.
2. Upload a clip in the web app on AWS. The agent timeline appears step by step: time base, scale, shake, noise floor, spectrum.
3. Agent refuses: "signal below noise floor at this distance; move to about half the distance and frame region R1".
   The recapture passes. This is the agentic beat.
4. Coin taped to a blade: 1x peak grows, zone changes, a maintenance ticket waits for human approval.
5. Evaluation: simulator table, agent vs baseline, and the failure cases. Real ground truth: speaker tone at a known frequency.
6. Architecture: OpenCV 5 tools, agent loop, Lambda container, S3, CloudWatch. Team on camera. Limits.

## Real / simulated / out

| Component | Status |
|---|---|
| Measurement pipeline (OpenCV 5) | real |
| Agent loop, decisions and trace | real, deterministic policy, no LLM, no paid API |
| Recapture | real clips: the human recaptures; evaluation: a simulator renders the recapture, labelled as simulated |
| ISO 10816-1 zones | real thresholds; Kampan's number is a camera screening estimate, not a certified measurement |
| Maintenance ticket | drafted and held for approval; not sent anywhere |
| COOL / Graviton | out (Marketplace subscription and time) |
| LLM planner | out; MCP server is a stretch |

## Architecture

Browser -> Lambda function URL (UI + API) -> presigned S3 PUT -> Lambda (container image, Python 3.12, opencv-python-headless
5.0.0.93) runs the agent on the clip -> results JSON, trace and magnified MP4 to S3 -> presigned GET. CloudWatch logs and
EMF metrics. Uploads deleted after 1 day by lifecycle rule. Reserved concurrency caps cost. SAM template deploys it.

## Milestones (acceptance check)

1. Synthetic renderer + measurement core: pytest passes on known-frequency, known-amplitude clips.
2. Agent + simulator + benchmark: `python -m eval.bench_agent` writes the agent-vs-baseline table.
3. Web app local: upload a sample, see timeline, spectrum, magnified video.
4. AWS: `sam deploy`, curl the function URL, analyze a sample end to end.
5. Real clips processed; report; video; Devpost text.

## Cut list

COOL, LLM planner, live phone capture in the browser (browsers cannot record 240 fps), multi-machine fleet view, accounts.

## Tripwires

- If sub-pixel tracking error on synthetic clips is above 0.05 px at 0.2 px amplitude by Oct 25 06:00 IST, switch to
  marker-corner tracking only.
- If Lambda container deploy fails by Oct 25 20:00 IST, deploy the same container to App Runner.
- If no real clips by Oct 26 10:00 IST, ship with synthetic evaluation plus the speaker test recorded on the laptop webcam.

## Pre-mortem

1. "Just motion magnification, done before." Prevent: lead with the agent refusing a bad clip and the evaluation table.
2. "Numbers are not trustworthy." Prevent: ground-truth speaker tone, simulator with known truth, noise floor on every result.
3. "Endpoint broken during judging." Prevent: sample clips in the UI, a health route, reserved concurrency, smoke test.
