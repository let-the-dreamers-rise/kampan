// Records the demo video on the live app: a no-account demo page, the lead and the technician, each with a virtual
// passkey. Only the page on screen is recorded. Beats follow docs/VIDEO_SCRIPT.md; each lasts as long as its narration.
// Usage: OUT=<dir> WEB=https://<app> PLAYWRIGHT_FROM=<dir with node_modules/@playwright/test> node video/record.mjs
import { createRequire } from "node:module";
import { writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { cards } from "./cards.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const OUT = process.env.OUT;
const WEB = (process.env.WEB || "http://localhost:8765").replace(/\/$/, "");
if (!OUT || !process.env.PLAYWRIGHT_FROM) throw new Error("Set OUT and PLAYWRIGHT_FROM.");
const { chromium } = createRequire(join(process.env.PLAYWRIGHT_FROM, "package.json"))("@playwright/test");

const SIZE = { width: 1440, height: 810 };
const INTRO_SECONDS = 20;
const narr = (id) => join(here, "narration", `${id}.mp3`);
const seconds = (id) => (existsSync(narr(id)) ? Number(spawnSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", narr(id)], { encoding: "utf8" }).stdout.trim()) : INTRO_SECONDS);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const frameDir = join(OUT, "frames");
mkdirSync(frameDir, { recursive: true });
const frames = [];
let t0 = Date.now(); // reset when recording starts, after the off-camera preparation
let active = null;

const browser = await chromium.launch({ channel: "chrome" });

async function window(label) {
  const context = await browser.newContext({ viewport: SIZE });
  const page = await context.newPage();
  page.label = label;
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", { options: { protocol: "ctap2", transport: "internal", hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });
  cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
    cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
    if (active !== page) return;
    const name = `${String(frames.length).padStart(5, "0")}.jpg`;
    writeFileSync(join(frameDir, name), Buffer.from(data, "base64"));
    frames.push({ name, at: metadata.timestamp - t0 / 1000 });
  });
  page.cast = () => cdp.send("Page.startScreencast", { format: "jpeg", quality: 90, maxWidth: SIZE.width, maxHeight: SIZE.height, everyNthFrame: 1 });
  return page;
}

async function show(page) {
  active = page;
  await page.bringToFront();
  await page.mouse.move(SIZE.width / 2, SIZE.height / 2);
  await page.evaluate(() => window.scrollBy(0, 1));
  await page.evaluate(() => window.scrollBy(0, -1));
}

const beats = [];
async function beat(id, act) {
  const start = (Date.now() - t0) / 1000;
  beats.push({ id, start, audio: existsSync(narr(id)) ? narr(id) : null });
  await act();
  const left = seconds(id) * 1000 + 600 - (Date.now() - t0 - start * 1000);
  if (left > 0) await sleep(left);
}

async function moveTo(page, locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + Math.min(box.height / 2, 30), { steps: 16 });
  await sleep(250);
}
const click = async (page, locator) => { await moveTo(page, locator); await locator.click(); };
async function type(page, selector, text) { await click(page, page.locator(selector)); await page.locator(selector).pressSequentially(text, { delay: 55 }); }

// The app's content policy blocks inline styles, so cards are rendered to images in a blank page first.
const cardImages = {};
async function renderCards() {
  const context = await browser.newContext({ viewport: SIZE });
  const page = await context.newPage();
  for (const [name, html] of Object.entries(cards)) {
    await page.setContent(html);
    await sleep(name === "problems" ? 15500 : 300); // let the list's fade-in finish
    cardImages[name] = `data:image/png;base64,${(await page.screenshot()).toString("base64")}`;
  }
  await context.close();
}

async function card(page, name) {
  await page.evaluate((src) => {
    document.getElementById("k-card")?.remove();
    const img = document.createElement("img");
    img.id = "k-card"; img.src = src; img.alt = "";
    img.style.cssText = "position:fixed;inset:0;width:100vw;height:100vh;object-fit:cover;z-index:2147483647;background:#f7f5f0";
    document.body.appendChild(img);
  }, cardImages[name]);
}
const uncard = (page) => page.evaluate(() => document.getElementById("k-card")?.remove());
const status = (page) => page.locator(".measure .status");
async function answerRpm(page, rpm) {
  const input = status(page).locator("input[type=number]");
  await input.waitFor({ timeout: 180000 });
  await click(page, input);
  await input.pressSequentially(String(rpm), { delay: 70 });
  await click(page, status(page).locator("button[type=submit]"));
}

await renderCards();
// Off camera: run the coin-on-blade sample in the no-account demo, so the video opens on the magnified view.
const demo = await window("demo");
const lead = await window("lead");
const tech = await window("tech");
await demo.goto(`${WEB}/`);
await demo.click("[data-testid=sample-unbalanced]");
await answerRpm(demo, 1260);
await status(demo).getByText("Approve ticket").click({ timeout: 180000 });
await demo.getByText("Done (demo, not saved)").waitFor({ timeout: 180000 });
await lead.goto(`${WEB}/`);
await lead.locator("#your-name").waitFor();
t0 = Date.now();
for (const p of [demo, lead, tech]) await p.cast();

await show(demo);
await beat("00", async () => { await moveTo(demo, demo.getByText("Motion magnified")); await sleep(2500); });
await card(demo, "intro");
await beat("01", async () => {});
await card(demo, "problems");
await beat("02", async () => {});

await show(lead);
await beat("03", async () => {
  await type(lead, "#your-name", "Asha");
  await sleep(1200);
  await click(lead, lead.getByText("Create account with a passkey"));
  await lead.locator("#m-name").waitFor();
  await type(lead, "#m-name", "Workshop fan");
  await type(lead, "#m-loc", "Bench 3");
  await type(lead, "#m-rpm", "1260");
  await lead.fill("#m-marker", "20");
  await click(lead, lead.getByText("Register machine"));
  await lead.locator("a.card.machine", { hasText: "Workshop fan" }).waitFor();
  await click(lead, lead.locator(".tabs a", { hasText: "Team" }));
  await click(lead, lead.getByText("Create an invite link"));
  await moveTo(lead, lead.locator("input.copy"));
});
const invite = await lead.locator("input.copy").inputValue();

await tech.goto(invite);
await tech.locator("#your-name").waitFor();
await show(tech);
await beat("04", async () => {
  await type(tech, "#your-name", "Ravi");
  await sleep(1200);
  await click(tech, tech.getByText("Join with a passkey"));
  await tech.locator("#pick-machine").waitFor();
  await tech.selectOption("#pick-machine", { label: "Workshop fan" });
  await click(tech, tech.locator("[data-testid=sample-handheld-unreferenced]"));
  await status(tech).getByText("needs a new clip").waitFor({ timeout: 180000 });
  await moveTo(tech, status(tech));
  await sleep(3500);
  await click(tech, status(tech).getByText("Use the sample's next clip"));
  await tech.getByText("Saved to the machine's history").waitFor({ timeout: 180000 });
  await moveTo(tech, tech.locator(".zones"));
});

await beat("05", async () => {
  await click(tech, tech.locator("[data-testid=sample-unbalanced]"));
  await answerRpm(tech, 1260);
  await status(tech).getByText("Send ticket to my lead").waitFor({ timeout: 180000 });
  await click(tech, status(tech).getByText("Send ticket to my lead"));
  await tech.getByText("Saved to the machine's history").waitFor({ timeout: 180000 });
  await moveTo(tech, tech.locator(".ticket"));
  await sleep(1200);
  await show(lead);
  await click(lead, lead.locator(".tabs a", { hasText: "Tickets" }));
  await click(lead, lead.locator(".ticket-card.open").getByText("Approve"));
  await lead.locator(".ticket-card.approved").waitFor();
  await click(lead, lead.locator(".tabs a", { hasText: "Machines" }));
  await click(lead, lead.locator("a.card.machine", { hasText: "Workshop fan" }));
  await moveTo(lead, lead.getByText("Velocity trend"));
  await click(lead, lead.getByText("Create link"));
});

await card(lead, "results");
await beat("06", async () => {});
await card(lead, "architecture");
await beat("07", async () => {});
await sleep(800);

const end = (Date.now() - t0) / 1000;
await browser.close();
const list = frames.map((f, i) => `file 'frames/${f.name}'\nduration ${Math.max(0.001, (i + 1 < frames.length ? frames[i + 1].at : end) - f.at).toFixed(3)}`);
list.unshift(`file 'frames/${frames[0].name}'\nduration ${Math.max(0.001, frames[0].at).toFixed(3)}`);
list.push(`file 'frames/${frames[frames.length - 1].name}'`);
writeFileSync(join(OUT, "frames.txt"), list.join("\n") + "\n");
writeFileSync(join(OUT, "beats.json"), JSON.stringify(beats, null, 2));
console.log(`frames ${frames.length}, length ${end.toFixed(1)} s`);
