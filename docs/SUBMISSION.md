# Submission checklist

Deadline: October 26, 2026, 11:59 PM Pacific (October 27, 12:29 PM IST). Aim for the morning of October 27 IST.

## What is ready

| Item | Where |
|---|---|
| Live app on AWS | https://4qxecavgpe5btmwt7jk4nzqwfi0xdlhl.lambda-url.us-east-1.on.aws/ |
| Public repository with pinned dependencies, build, deploy and test steps | https://github.com/let-the-dreamers-rise/kampan |
| Technical report with evaluation and failure cases | `docs/REPORT.md` and `docs/REPORT.pdf` |
| Architecture and agent workflow diagrams | `docs/architecture.png`, `docs/agent-workflow.png` |
| Devpost text, ready to paste | `docs/DEVPOST.md` |
| Demo video without the team intro (2:17) | `out/video/kampan-demo.mp4` on the laptop; not in git |

## What only you can do

1. **Join the hackathon on Devpost** at https://opencv26.devpost.com if you have not yet, and accept the rules yourself.
2. **Email competition@opencv.org** to confirm a Devpost entry is eligible; the draft is in the shared notes folder.
3. **Record the 20-second intro** on your phone: who you are and why Kampan. The competition requires the team on camera.
4. **Add the intro to the video:**

   ```bash
   OUT=out/video SELFIE=path/to/intro.mp4 node video/add_intro.mjs
   ```

   This writes `out/video/kampan-demo-final.mp4`.
5. **Upload the video** to YouTube (unlisted is fine) and paste the link into Devpost.
6. **Test sign-up on your own phone** once: create an account, sign out, sign back in.
7. **Fill in the Devpost form** from `docs/DEVPOST.md`, upload `docs/architecture.png` and screenshots, opt in to the
   Agentic Vision Award, and submit.

## Optional, if time allows

- Film the fan clips in `capture_kit/HOW-TO-FILM.md` and run them through the app. A real clip in the video is
  stronger than a simulated one.
