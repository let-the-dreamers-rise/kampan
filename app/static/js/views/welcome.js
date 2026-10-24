// Signed-out home, sign-up and sign-in, the no-account demo, and joining a site from an invite link.
import { api } from "../api.js";
import { el, problem } from "../dom.js";
import { measurePanel } from "../measure.js";
import { signIn, signUp, supported } from "../passkey.js";

function accountForm({ invite = null, onDone }) {
  const out = el("div", { class: "msg", role: "status", "aria-live": "polite" });
  const name = el("input", { id: "your-name", autocomplete: "name", maxlength: "40", required: true, placeholder: "Your name" });
  const busy = (b) => form.querySelectorAll("button").forEach((x) => { x.disabled = b; });
  const attempt = async (fn) => {
    busy(true); out.replaceChildren("Waiting for your passkey...");
    try { onDone(await fn()); } catch (err) { out.replaceChildren(problem(err)); } finally { busy(false); }
  };
  const form = el("form", { class: "account" },
    el("label", { for: "your-name" }, invite ? "Your name, as your lead will see it" : "Your name"), name,
    el("div", { class: "row" }, el("button", { type: "submit" }, invite ? "Join with a passkey" : "Create account with a passkey"),
      invite ? "" : el("button", { type: "button", class: "ghost", onclick: () => attempt(signIn) }, "I have an account: sign in")),
    el("p", { class: "small muted" }, "A passkey uses your phone's fingerprint, face or screen lock. No password, nothing to remember."), out);
  form.addEventListener("submit", (ev) => { ev.preventDefault(); if (name.value.trim()) attempt(() => signUp(name.value.trim(), invite || undefined)); });
  if (!supported()) form.replaceChildren(el("p", {}, "This browser does not support passkeys. Use a recent Chrome, Safari, Edge or Firefox."));
  return form;
}

export async function welcome(ctx) {
  const samples = (await api("/api/samples")).samples;
  return el("div", { class: "page" },
    el("section", { class: "hero panel" },
      el("h1", {}, "Know when a machine starts shaking itself apart, from a phone video."),
      el("p", {}, "Fans, pumps and motors shake more as bearings wear and parts come loose. Most small machines are never measured, because vibration sensors and specialist visits cost money. Kampan measures vibration from a slow-motion phone clip, and its agent refuses to give a number until the clip can support one."),
      el("ol", { class: "how" },
        el("li", {}, el("b", {}, "A lead"), " registers machines and invites technicians with a link."),
        el("li", {}, el("b", {}, "A technician"), " films a machine with two printed markers. The agent checks the frame rate, camera shake, scale, noise and aliasing, and asks for a better clip when one fails."),
        el("li", {}, el("b", {}, "Every reading"), " goes into the machine's history. In ISO 10816-1 zone C or D, the technician can send a drafted ticket, and the lead approves or declines it.")),
      accountForm({ onDone: ctx.signedIn })),
    el("section", { class: "panel" }, el("h2", {}, "Try it without an account"), el("p", { class: "small muted" }, "Runs the real agent on simulated clips. Nothing is saved.")),
    measurePanel({ mode: "demo", samples }));
}

export async function join(ctx, token) {
  let invite;
  try { invite = await api(`/api/invites/${encodeURIComponent(token)}`); } catch (err) { return el("div", { class: "page" }, problem(err)); }
  const intro = el("p", {}, `${invite.by_name} invited you to measure machines at ${invite.site_name} as a technician.`);
  if (ctx.me && ctx.me.signed_in) {
    const out = el("div");
    const accept = el("button", { type: "button", onclick: async () => {
      accept.disabled = true;
      try { ctx.signedIn(await api(`/api/invites/${encodeURIComponent(token)}/accept`, {})); } catch (err) { out.replaceChildren(problem(err)); accept.disabled = false; }
    } }, `Join ${invite.site_name}`);
    return el("div", { class: "page" }, el("section", { class: "panel narrow" }, el("h1", {}, "You're invited"), intro, accept, out));
  }
  return el("div", { class: "page" }, el("section", { class: "panel narrow" }, el("h1", {}, "You're invited"), intro, accountForm({ invite: token, onDone: ctx.signedIn })));
}
