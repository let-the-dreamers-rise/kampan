# Demo video script (target 3:30, hard limit 5:00)

Narration style: energetic, story-told, not a neutral readout. Narration is generated with edge-tts
(en-US-AndrewMultilingualNeural, rate +8%, pitch +2Hz) except the team segment, which is Ashwin on camera.

| Time | On screen | Narration |
|---|---|---|
| 0:00-0:15 | Fan clip, normal speed. Cut to the magnified view: the fan visibly shakes. | This fan looks perfectly still. It isn't. Every motor, pump and fan tells you it is about to fail, in a motion too small to see. |
| 0:15-0:35 | Ashwin to camera (selfie clip). Name on screen. | (Ashwin, own words) I'm Ashwin. I built Kampan, which means vibration in Hindi. Your phone can film a machine at 240 frames a second. The question is whether you can trust what it sees. |
| 0:35-1:00 | Five icons appear one by one: clock, shaking hand, ruler, noise, folded wave. | Because phones lie. Slow motion saved as 30 fps. A shaking hand. Pixels that aren't millimetres. Motion buried in noise. Vibration so fast it folds into a fake frequency. A normal pipeline ignores all five and prints a confident number anyway. |
| 1:00-1:35 | Web app on AWS. Pick the slow-motion sample. The agent timeline fills step by step. The agent asks for the capture rate. | So Kampan has an agent. Before it grades anything, it checks each condition with OpenCV 5. Here the file claims 30 fps, but there's no capture tag. So the agent stops and asks one question: what rate did you film at? |
| 1:35-2:10 | Hand-held sample: the agent requests a recapture with a specific instruction. Second clip passes; spectrum and zone appear. | Hand-held, no reference in view? It won't stabilise against nothing. It asks for a braced recapture with the reference marker showing. Second clip: ECC tracking, the camera motion subtracted, a clean peak, a severity zone. |
| 2:10-2:40 | Unbalanced sample: zone C, running-speed question, order diagnosis "1x: unbalance", ticket card with Approve and Discard. | Tape a coin to a blade and the one-times peak jumps. Zone C. Kampan asks the running speed, calls it unbalance, and drafts a maintenance ticket. It waits for a human to approve. Nothing gets sent on its own. |
| 2:40-3:10 | Results table: agent 30 of 30, baseline 15 of 30 with 12 confidently wrong. Then the failure-case list from the report. | I tested it. Ten broken-capture scenarios, three seeds each. The agent got all thirty right. The same pipeline without the agent got fifteen, and twelve of its misses were confidently wrong. And here's where Kampan still fails, written down, not hidden. |
| 3:10-3:30 | Architecture diagram: browser, Lambda container with OpenCV 5, S3, CloudWatch dashboard. | It runs as one CloudFormation stack: a Lambda container with OpenCV 5, private S3 uploads, and a CloudWatch dashboard watching every run. No paid AI API. Just OpenCV, a careful agent, and your phone. Kampan. |

If real clips are filmed in time, replace the slow-motion and hand-held samples with the real fan clips and add the
speaker tone clip (known 47 Hz) as ground truth in the results beat.
