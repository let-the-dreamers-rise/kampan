// Puts the team's on-camera intro (beat 01) over the placeholder card in the recorded demo.
// Usage: OUT=<recording dir> SELFIE=<your clip.mp4> node video/add_intro.mjs  ->  <OUT>/kampan-demo-final.mp4
// The intro plays with its own sound; if it runs longer than the slot it is cut at the next beat.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const { OUT, SELFIE } = process.env;
if (!OUT || !SELFIE) throw new Error("Set OUT and SELFIE.");
const beats = JSON.parse(readFileSync(join(OUT, "beats.json"), "utf8"));
const i = beats.findIndex((b) => b.id === "01");
const start = beats[i].start.toFixed(2);
const end = beats[i + 1].start.toFixed(2);
const len = (beats[i + 1].start - beats[i].start).toFixed(2);
const filter = [
  `[1:v]trim=0:${len},setpts=PTS-STARTPTS+${start}/TB,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x1b1d1f[s]`,
  `[0:v][s]overlay=enable='between(t,${start},${end})':eof_action=pass[v]`,
  `[1:a]atrim=0:${len},asetpts=PTS-STARTPTS,adelay=${Math.round(beats[i].start * 1000)}:all=1[ia]`,
  `[0:a][ia]amix=inputs=2:normalize=0:duration=first[a]`,
].join(";");
const run = spawnSync("ffmpeg", ["-v", "error", "-y", "-i", "kampan-demo.mp4", "-i", SELFIE, "-filter_complex", filter,
  "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
  "kampan-demo-final.mp4"], { cwd: OUT, stdio: "inherit" });
if (run.status !== 0) throw new Error(`ffmpeg exited with ${run.status}`);
console.log(join(OUT, "kampan-demo-final.mp4"));
