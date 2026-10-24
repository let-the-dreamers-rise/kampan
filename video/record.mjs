// Records the demo video in Chrome against a running Kampan app (local server or the deployed function URL).
// Usage: OUT=<dir> WEB=http://127.0.0.1:8765 PLAYWRIGHT_FROM=<dir with node_modules/@playwright/test> node video/record.mjs
// Writes <OUT>/frames/*.jpg, <OUT>/frames.txt (ffmpeg concat list timed from Chrome's screencast) and <OUT>/beats.json.
// Narration clips are read from video/narration/NN.mp3 (tools/make_narration.py); each beat lasts as long as its clip.
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { cards } from "./cards.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const OUT = process.env.OUT;
const WEB = process.env.WEB || "http://127.0.0.1:8765";
const FROM = process.env.PLAYWRIGHT_FROM;
if (!OUT || !FROM) throw new Error("Set OUT and PLAYWRIGHT_FROM.");
const { chromium } = createRequire(join(FROM, "package.json"))("@playwright/test");

const SIZE = { width: 1440, height: 810 };
const INTRO_SECONDS = 20;
const narr = (id) => join(here, "narration", `${id}.mp3`);
function seconds(id) {
  if (!existsSync(narr(id))) return INTRO_SECONDS;
  const r = spawnSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", narr(id)], { encoding: "utf8" });
  return Number(r.stdout.trim());
}

const browser = await chromium.launch({ channel: "chrome" });
const context = await browser.newContext({ viewport: SIZE });
const page = await context.newPage();
const t0 = Date.now();
const frameDir = join(OUT, "frames");
mkdirSync(frameDir, { recursive: true });
const frames = [];
const cdp = await context.newCDPSession(page);
cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
  const name = `${String(frames.length).padStart(5, "0")}.jpg`;
  writeFileSync(join(frameDir, name), Buffer.from(data, "base64"));
  frames.push({ name, at: metadata.timestamp - t0 / 1000 });
  cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
});
await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: SIZE.width, maxHeight: SIZE.height, everyNthFrame: 1 });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const beats = [];
const status = page.getByTestId("status");

async function beat(id, act) {
  const start = (Date.now() - t0) / 1000;
  beats.push({ id, start, audio: existsSync(narr(id)) ? narr(id) : null });
  await act();
  const left = seconds(id) * 1000 + 600 - (Date.now() - t0 - start * 1000);
  if (left > 0) await sleep(left);
}

async function moveTo(locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + Math.min(box.height / 2, 40), { steps: 18 });
  await sleep(200);
}

async function click(locator) { await moveTo(locator); await locator.click(); }

async function showCard(name) {
  await page.evaluate((html) => {
    const f = document.createElement("iframe");
    f.id = "k-card";
    f.srcdoc = html;
    f.style.cssText = "position:fixed;inset:0;width:100vw;height:100vh;border:0;z-index:2147483647;background:#f7f5f0";
    document.body.appendChild(f);
  }, cards[name]);
}
const hideCard = () => page.evaluate(() => document.getElementById("k-card")?.remove());

async function startSample(id) {
  await click(page.getByRole("button", { name: "Start over" }));
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await click(page.getByTestId(`sample-${id}`));
}

async function waitStatus(cls) {
  await page.locator(`[data-testid="status"].${cls}`).waitFor({ timeout: 120_000 });
}

async function answerNumber(value) {
  const input = status.locator("input[type=number]");
  await click(input);
  await input.pressSequentially(String(value), { delay: 60 });
  await sleep(300);
  await click(status.getByRole("button", { name: "Answer" }));
}

async function showResult() {
  await moveTo(page.getByTestId("result"));
  await sleep(1500);
}

await page.goto(WEB);
await page.getByTestId("sample-unbalanced").waitFor({ timeout: 30_000 });

// 00 hook: run the unbalanced sample off camera, then open on the magnified view.
await startSample("unbalanced");
await waitStatus("ask");
await answerNumber(1260);
await waitStatus("ask");
await click(status.getByRole("button", { name: "Approve ticket" }));
await waitStatus("done");
await beat("00", async () => {
  await moveTo(page.getByText("Motion magnified"));
  await sleep(2500);
});

await showCard("intro");
await beat("01", async () => {});
await hideCard();

await showCard("problems");
await beat("02", async () => {});
await hideCard();

await beat("03", async () => {
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await startSample("slowmo-untagged");
  await waitStatus("ask");
  await moveTo(status);
  await sleep(2500);
  await answerNumber(240);
  await waitStatus("done");
  await moveTo(page.getByTestId("timeline"));
});

await beat("04", async () => {
  await startSample("handheld-unreferenced");
  await waitStatus("ask");
  await moveTo(status);
  await sleep(3000);
  await click(status.getByRole("button", { name: /next clip/ }));
  await waitStatus("done");
  await showResult();
});

await beat("05", async () => {
  await startSample("unbalanced");
  await waitStatus("ask");
  await moveTo(status);
  await answerNumber(1260);
  await waitStatus("ask");
  await sleep(1500);
  await click(status.getByRole("button", { name: "Approve ticket" }));
  await waitStatus("done");
  await moveTo(page.locator(".ticket"));
});

await showCard("results");
await beat("06", async () => {});
await hideCard();
await showCard("architecture");
await beat("07", async () => {});
await sleep(800);

const end = (Date.now() - t0) / 1000;
await cdp.send("Page.stopScreencast").catch(() => {});
await context.close();
await browser.close();

const list = frames.map((f, i) => {
  const next = i + 1 < frames.length ? frames[i + 1].at : end;
  return `file 'frames/${f.name}'\nduration ${Math.max(0.001, next - f.at).toFixed(3)}`;
});
list.unshift(`file 'frames/${frames[0].name}'\nduration ${Math.max(0.001, frames[0].at).toFixed(3)}`);
list.push(`file 'frames/${frames[frames.length - 1].name}'`);
writeFileSync(join(OUT, "frames.txt"), list.join("\n") + "\n");
writeFileSync(join(OUT, "beats.json"), JSON.stringify(beats, null, 2));
console.log(`frames ${frames.length}, length ${end.toFixed(1)} s`);
