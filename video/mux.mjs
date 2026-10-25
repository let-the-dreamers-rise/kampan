// Joins the recorded frames with the narration, each clip placed at its beat's start time.
// Usage: OUT=<dir> node video/mux.mjs  ->  <OUT>/kampan-demo.mp4 (needs ffmpeg on PATH)
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const OUT = process.env.OUT;
if (!OUT) throw new Error("Set OUT to the recording directory.");

// ffmpeg rounds every concat entry up to a whole output frame, so frames shorter than one are merged into the
// previous kept frame first; otherwise fast typing stretches the picture and it drifts from the narration.
const MIN = 1 / 30;
const entries = [];
for (const block of readFileSync(join(OUT, "frames.txt"), "utf8").trim().split(/\n(?=file )/)) {
  const [fileLine, durLine] = block.split("\n");
  entries.push({ file: fileLine, dur: durLine ? parseFloat(durLine.split(" ")[1]) : null });
}
const kept = [];
for (const e of entries) {
  if (e.dur === null) { kept.push(e); continue; }
  const last = kept[kept.length - 1];
  if (last && last.dur !== null && last.dur < MIN) { last.dur += e.dur; last.file = e.file; } else kept.push({ ...e });
}
writeFileSync(join(OUT, "frames.merged.txt"), kept.map((e) => (e.dur === null ? e.file : `${e.file}\nduration ${e.dur.toFixed(3)}`)).join("\n") + "\n");

const beats = JSON.parse(readFileSync(join(OUT, "beats.json"), "utf8")).filter((b) => b.audio);
const inputs = ["-f", "concat", "-safe", "0", "-i", "frames.merged.txt"];
const delays = beats.map((b, i) => {
  inputs.push("-i", b.audio);
  const ms = Math.round(b.start * 1000);
  return `[${i + 1}:a]adelay=${ms}|${ms}[a${i}]`;
});
const mix = `${beats.map((_, i) => `[a${i}]`).join("")}amix=inputs=${beats.length}:normalize=0,loudnorm=I=-16:TP=-1.5[aout]`;
const video = "[0:v]fps=30,scale=1920:1080:flags=lanczos,format=yuv420p[vout]";
const run = spawnSync("ffmpeg", [
  "-v", "error", "-y", ...inputs,
  "-filter_complex", [video, ...delays, mix].join(";"),
  "-map", "[vout]", "-map", "[aout]",
  "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
  // the concat demuxer holds the final still image longer than listed, so cap the output at the recorded length
  "-t", (kept.reduce((s, e) => s + (e.dur || 0), 0) + 0.2).toFixed(2),
  "-movflags", "+faststart", "kampan-demo.mp4",
], { cwd: OUT, stdio: "inherit" });
if (run.status !== 0) throw new Error(`ffmpeg exited with ${run.status}`);
console.log(join(OUT, "kampan-demo.mp4"));
