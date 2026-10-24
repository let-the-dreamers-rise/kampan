| Scenario | What is wrong with the capture | Agent correct | Baseline correct | Agent captures (mean) | Agent questions (mean) | Agent actions (seed 0) |
|---|---|---|---|---|---|---|
| clean | good capture of a healthy machine | 3/3 | 3/3 | 1.0 | 0.0 | Report |
| slowmo-untagged | slow-motion file whose container says 30 fps and carries no capture tag | 3/3 | 0/3 | 1.0 | 1.0 | AskHuman > Report |
| far | camera too far: motion below the noise floor | 3/3 | 0/3 | 2.7 | 0.0 | Recapture > Report |
| handheld-referenced | hand shake, static reference marker visible | 3/3 | 0/3 | 2.0 | 0.0 | Recapture > Report |
| handheld-unreferenced | hand shake, no static reference | 3/3 | 0/3 | 2.0 | 0.0 | Recapture > Report |
| aliased | vibration above the Nyquist limit of 240 fps | 3/3 | 0/3 | 3.0 | 2.0 | Recapture > Recapture > AskHuman > ProposeTicket |
| no-markers | no marker in view | 3/3 | 0/3 | 2.0 | 0.0 | Recapture > Report |
| oblique | camera at 60 degrees to the machine face, horizontal vibration | 0/3 | 2/3 | 2.0 | 0.0 | Recapture > Report |
| unbalanced | coin on a blade: strong 1x | 3/3 | 3/3 | 1.0 | 2.0 | AskHuman > ProposeTicket |
| machine-off | nothing vibrates | 3/3 | 3/3 | 3.0 | 0.0 | Recapture > Recapture > Report |

| | Correct | Confidently wrong | Abstained | Missed |
|---|---|---|---|---|
| agent | 27/30 | 3 | 0 | 0 |
| baseline | 11/30 | 13 | 1 | 5 |
