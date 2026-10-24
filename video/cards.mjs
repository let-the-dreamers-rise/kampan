// Full-screen cards shown between app beats in the demo video.
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const docs = join(dirname(fileURLToPath(import.meta.url)), "..", "docs");
const png = (name) => `data:image/png;base64,${readFileSync(join(docs, name)).toString("base64")}`;

const page = (body) => `<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;
 background:#f7f5f0;color:#1d2125;font-family:system-ui,Segoe UI,sans-serif}
h1{font-size:52px;margin:0 0 24px}h2{font-size:34px;margin:0 0 28px;color:#0f6b62}
ul{list-style:none;padding:0;margin:0;font-size:30px;line-height:1.9}
li{opacity:0;animation:in .5s forwards}li b{color:#b42318}
@keyframes in{to{opacity:1}}
table{border-collapse:collapse;font-size:30px}td,th{padding:12px 28px;border-bottom:2px solid #dedad0;text-align:left}
th{color:#5d636a;font-weight:600}.good{color:#0f6b62;font-weight:700}.bad{color:#b42318;font-weight:700}
img{max-width:88vw;max-height:78vh}.note{font-size:20px;color:#5d636a;margin-top:22px}
</style></head><body>${body}</body></html>`;

const delays = [0.6, 3.6, 6.6, 9.6, 12.6];

export const cards = {
  intro: page(`<h1>Kampan</h1><h2>Ashwin Goyal</h2><p class="note">Intro clip goes here</p>`),
  problems: page(`<h2>Five ways a phone clip lies</h2><ul>${[
    "<b>Time base:</b> slow motion saved as 30 fps",
    "<b>Shake:</b> the hand moves more than the machine",
    "<b>Scale:</b> pixels are not millimetres",
    "<b>Noise:</b> motion smaller than sensor noise",
    "<b>Aliasing:</b> fast vibration folds into a fake frequency",
  ].map((t, i) => `<li style="animation-delay:${delays[i]}s">${t}</li>`).join("")}</ul>`),
  results: page(`<h2>30 simulated broken captures, 3 seeds each</h2><table>
    <tr><th></th><th>Correct</th><th>Confidently wrong</th><th>Abstained</th></tr>
    <tr><td>Kampan agent</td><td class="good">30 / 30</td><td>0</td><td>0</td></tr>
    <tr><td>Same pipeline, no checks</td><td>15 / 30</td><td class="bad">12</td><td>3</td></tr></table>
    <p class="note">Recaptures are rendered by the simulator. Failure cases and limits: docs/REPORT.md</p>`),
  architecture: page(`<img src="${png("architecture.png")}" alt="Architecture">`),
};
