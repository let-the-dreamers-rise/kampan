# Demo video script (target about 3:30, hard limit 5:00)

Narration style: energetic, story-told, not a neutral readout. Narration is generated with edge-tts
(en-US-AndrewMultilingualNeural, rate +8%, pitch +2Hz) by `tools/make_narration.py`, except the team segment, which
is Ashwin on camera. `video/record.mjs` records the beats on the live app; `video/mux.mjs` joins them.

| Time | On screen | Narration |
|---|---|---|
| 0:00-0:15 | Coin-on-blade sample, the magnified view: the fan visibly shakes. | This fan looks perfectly still. It isn't. Every motor, pump and fan warns you it is about to fail, in a motion too small to see. |
| 0:15-0:35 | Ashwin to camera (selfie clip). Name on screen. | (Ashwin, own words) I'm Ashwin. I built Kampan, which means vibration in Hindi. Your phone can film a machine at 240 frames a second. The question is whether you can trust what it sees. |
| 0:35-1:00 | Card: five ways a phone clip lies. | Because phones lie. Slow motion saved as 30 fps. A shaking hand. Pixels that aren't millimetres. Motion buried in noise. Vibration so fast it folds into a fake frequency. A normal pipeline ignores all five and prints a confident number anyway. |
| 1:00-1:25 | Live app on AWS, phone-sized. The lead creates an account with a passkey, registers the fan with its running speed, and creates an invite link. | Kampan is built for a real site. The maintenance lead signs in with a passkey. No password. Registers the fan with its class and running speed, and sends the technician a one-time invite link. |
| 1:25-2:05 | The technician joins from the link, picks the fan and uploads a hand-held clip. The agent refuses and asks for a braced recapture with the reference marker. The second clip passes and the reading is saved. | The technician opens the link and picks the fan. Here, a simulated hand-held clip with nothing still in view. The agent measures the camera shake with OpenCV, refuses to grade, and says exactly what to fix. Second clip, braced, reference marker showing. Now it measures, and the reading lands in the fan's history. |
| 2:05-2:45 | Coin on the blade: zone C, unbalance. The technician sends the drafted ticket; the lead approves it and opens the machine's trend and a read-only share link. | Tape a coin to a blade. Zone C, unbalance. The agent drafts a maintenance ticket, but nothing moves without people. The technician sends it, the lead approves it, and the fan's trend shows exactly when things got worse. |
| 2:45-3:10 | Card: agent 30 of 30, baseline 15 of 30 with 12 confidently wrong. Failure cases in the report. | I tested it. Ten broken-capture scenarios, three seeds each. The agent got all thirty right. The same pipeline without the agent got fifteen, and twelve of its misses were confidently wrong. Where Kampan still fails is written down in the report, not hidden. |
| 3:10-3:35 | Architecture diagram. | It is one CloudFormation stack: a Lambda container running OpenCV 5, DynamoDB for sites and readings, passkey sign-in, private S3 uploads, and a CloudWatch dashboard on every agent decision. No paid AI API. Just OpenCV, a careful agent, and your phone. Kampan. |

If real clips are filmed in time, use the real fan clip in the hook and add the speaker tone (known 47 Hz) as ground
truth in the results beat.
