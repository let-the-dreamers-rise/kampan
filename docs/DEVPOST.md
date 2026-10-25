# Devpost submission text

Paste these into the Devpost form. The user submits.

## Project name

Kampan

## Elevator pitch

An OpenCV 5 agent that checks whether a phone video can measure machine vibration, asks for a better capture when it can't, and grades severity when it can.

## About the project

### Inspiration

Machines announce failure as vibration long before they break. Most small fans, pumps and motors are never measured,
because sensors and visits cost money. Every phone films at 120 or 240 fps. But a phone clip lies in quiet ways:
slow motion saved as 30 fps, a shaking hand, no scale, motion lost in noise, and vibration that aliases into a fake
frequency. I wanted a tool that knows when it is being lied to.

### What it does

A maintenance lead signs up with a passkey, registers the site's machines and sends a technician a one-time invite
link. The technician films a machine in slow motion with two printed ArUco markers and uploads the clip. Kampan's
agent checks the time base, camera shake, metric scale, noise floor and aliasing with OpenCV 5. If a check fails, it
asks for a recapture with a specific instruction or asks one question. When the clip passes, it reports velocity in
mm/s, the ISO 10816-1 zone and an order-based diagnosis, saves the reading to the machine's history, and compares it
with the previous one. In zone C or D it drafts a maintenance ticket; the technician decides whether to send it, and
the lead approves or declines it. The lead can share a read-only report of a machine. Every reading keeps its full
agent trace.

### How I built it

- **OpenCV 5:** ArUco detection with sub-pixel corners for scale, `findTransformECC` for sub-pixel tracking and camera-motion removal, DIS optical flow to find vibrating regions, and a Laplacian pyramid for the magnified view.
- **Agent:** a deterministic policy in Python with ordered checks, bounded recaptures and questions, and a JSON trace. No LLM and no paid API.
- **AWS:** one CloudFormation stack with a Lambda container image behind a function URL, DynamoDB for accounts and records, a Secrets Manager key for session cookies, presigned uploads to a private S3 bucket, and CloudWatch logs, metrics, dashboard, alarm and X-Ray.
- **Accounts:** passkeys (WebAuthn) with signed HttpOnly session cookies; the server enforces the lead and technician roles on every call, and rate-limits every endpoint.
- **Evaluation:** a closed-loop simulator that renders the recapture the agent asks for, so the agent can be scored against the same pipeline without checks.

### Challenges I ran into

My first tracker, `cv2.phaseCorrelate`, gave sub-pixel shifts that depended on the texture: on coarse texture it
halved horizontal motion, which made the agent misgrade an oblique view. I benchmarked it against ECC and switched.
I also found that `phaseCorrelate` with a window modifies its inputs in place, in both OpenCV 4.12 and 5.0. Making the
agent remember an alias suspicion across recaptures, and deciding when camera-motion removal helps rather than hurts,
each took a failed benchmark to find.

### Accomplishments that I'm proud of

On 30 simulated broken captures, the agent was correct 30 times. The same pipeline without the agent was correct 15
times and confidently wrong 12 times. The technical report lists where Kampan still fails.

### What I learned

The valuable part of a measurement agent is refusing. Knowing which capture to ask for is worth more than a better
filter.

### What's next

Validating on real machines against an accelerometer, a phone app that guides the capture live, and fleet history so a
rising trend triggers an inspection before a zone change does.

## Built with

opencv, python, numpy, aws-lambda, amazon-dynamodb, amazon-s3, aws-secrets-manager, amazon-cloudwatch, aws-x-ray, aws-cloudformation, webauthn, docker, javascript

## Links

- App: https://4qxecavgpe5btmwt7jk4nzqwfi0xdlhl.lambda-url.us-east-1.on.aws/
- Code: https://github.com/let-the-dreamers-rise/kampan
- Report: https://github.com/let-the-dreamers-rise/kampan/blob/main/docs/REPORT.md

## Agentic Vision Award

Opt in. Point judges to `docs/agent-workflow.png` for the workflow diagram. For a trace in which an OpenCV result
changes a later decision, any saved reading has a Trace button on its machine page. The hand-held sample shows it:
the camera-shake measurement triggers the recapture, and the second clip is graded. The no-account demo on the home
page shows the same agent timeline without signing in.

## AI tools disclosure

Code and documentation were written with help from Claude (Anthropic) as a coding assistant. The running system uses no
generative AI model; the agent is a deterministic policy.
