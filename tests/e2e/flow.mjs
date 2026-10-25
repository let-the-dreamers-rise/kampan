// End-to-end test in real Chrome with virtual passkeys: lead -> invite -> technician -> agent -> ticket -> lead -> share.
// Usage: BASE=https://<app> PLAYWRIGHT_FROM=<dir with node_modules/@playwright/test> node tests/e2e/flow.mjs
import { createRequire } from "node:module";
import { join } from "node:path";

const BASE = (process.env.BASE || "http://localhost:8765").replace(/\/$/, "");
const { chromium } = createRequire(join(process.env.PLAYWRIGHT_FROM, "package.json"))("@playwright/test");
const errors = [];
const step = (msg) => console.log(`ok  ${msg}`);

async function person(browser, label) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } }); // phone-sized
  const page = await context.newPage();
  page.on("console", (m) => { if (m.type() === "error" && !page.expectRefusal) errors.push(`${label}: ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`${label}: ${e.message}`));
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", { options: { protocol: "ctap2", transport: "internal", hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });
  return { context, page };
}

const browser = await chromium.launch({ channel: "chrome" });
try {
  const lead = await person(browser, "lead");
  let p = lead.page;
  await p.goto(`${BASE}/`);
  await p.fill("#your-name", "Asha (test)");
  await p.waitForTimeout(1200); // lets the page fetch the challenge before the tap, as on a real phone
  await p.click("text=Create account with a passkey");
  await p.locator(".tabs a", { hasText: "Machines" }).waitFor();
  step("lead signed up with a passkey and landed on Machines");
  await p.getByText("No machines yet").waitFor();
  await p.fill("#m-name", "Workshop fan");
  await p.fill("#m-loc", "Bench 3");
  await p.fill("#m-rpm", "1260");
  await p.fill("#m-marker", "20");
  await p.click("text=Register machine");
  await p.locator("a.card.machine", { hasText: "Workshop fan" }).waitFor();
  step("lead registered a machine");
  await p.click(".tabs >> text=Team");
  await p.click("text=Create an invite link");
  const invite = await p.locator("input.copy").inputValue();
  step("lead created an invite link");

  const tech = await person(browser, "technician");
  let t = tech.page;
  await t.goto(invite);
  await t.getByText("invited you to measure machines").waitFor();
  await t.fill("#your-name", "Ravi (test)");
  await t.click("text=Join with a passkey");
  await t.locator(".tabs a", { hasText: "Measure" }).waitFor();
  step("technician joined through the invite");
  await t.selectOption("#pick-machine", { label: "Workshop fan" });
  await t.click("[data-testid=sample-unbalanced]");
  const status = t.locator(".measure .status");
  await status.locator("input[type=number]").waitFor({ timeout: 180000 });
  await status.locator("input[type=number]").fill("1260");
  await status.locator("button[type=submit]").click();
  await status.getByText("Send ticket to my lead").waitFor({ timeout: 180000 });
  await status.getByText("Send ticket to my lead").click();
  await t.getByText("Saved to the machine's history").waitFor({ timeout: 180000 });
  step("technician measured, answered the agent and sent the ticket");

  p = lead.page;
  await p.click(".tabs >> text=Tickets");
  await p.locator(".ticket-card.open").waitFor();
  await p.click(".ticket-card.open >> text=Approve");
  await p.locator(".ticket-card.approved").waitFor();
  step("lead approved the ticket");
  await p.click(".tabs >> text=Machines");
  await p.click("a.card.machine >> text=Workshop fan");
  await p.getByText("Velocity trend").waitFor();
  await p.click("text=Create link");
  const share = await p.locator("input.copy").inputValue();
  step("lead created a read-only link");

  const viewer = await browser.newContext();
  const v = await viewer.newPage();
  v.on("pageerror", (e) => errors.push(`viewer: ${e.message}`));
  await v.goto(share);
  await v.getByText("Read-only report shared by").waitFor();
  if (await v.getByText("Ravi (test)").count()) throw new Error("share page shows a person's name");
  step("anonymous viewer opened the shared report without names");
  await v.goto(`${BASE}/#/impact`);
  await v.getByText("Tickets approved").waitFor();
  step("impact page loads");

  await t.reload();
  await t.goto(`${BASE}/#/machines`);
  await t.locator("a.card.machine", { hasText: "Workshop fan" }).waitFor();
  t.expectRefusal = true;
  const forbidden = await t.evaluate(async () => (await fetch("/api/machines", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "x" }) })).status);
  if (forbidden !== 403) throw new Error(`technician could create a machine (HTTP ${forbidden})`);
  await t.waitForTimeout(300);
  t.expectRefusal = false;
  step("server refuses a technician creating a machine");

  await p.click("text=Sign out");
  await p.click("text=I have an account: sign in");
  await p.locator(".tabs a", { hasText: "Machines" }).waitFor();
  step("lead signed back in with the same passkey");
} finally {
  await browser.close();
}
if (errors.length) { console.log("console errors:\n" + errors.join("\n")); process.exit(1); }
console.log("all steps passed, no console errors");
