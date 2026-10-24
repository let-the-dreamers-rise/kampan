// The agent session UI: pick a clip, follow the agent's checks, answer it, see the result.
// mode "demo": built-in samples, nothing saved. mode "site": a technician measuring a registered machine.
import { api } from "./api.js";
import { el, fmt, randomId, problem } from "./dom.js";
import { renderResult } from "./result.js";

function describe(e) {
  if (e.kind === "capture") {
    const r = e.request || {};
    const asks = [r.fps ? `${r.fps} fps` : null, r.distance !== 1 ? `distance x${fmt(r.distance)}` : null, r.tripod ? "support" : null, r.markers ? "markers" : null, r.square_on ? "square-on" : null].filter(Boolean);
    return [`Clip ${e.index + 1} received`, asks.length ? `conditions asked: ${asks.join(", ")}` : "first clip"];
  }
  if (e.kind === "human") {
    const shown = e.field === "running_hz" && typeof e.answer === "number" ? `${Math.round(e.answer * 60)} rpm (${fmt(e.answer, 1)} Hz)`
      : e.field === "approve_ticket" ? (e.answer ? "send the ticket" : "do not send") : e.answer === null ? "unknown" : e.answer;
    return [`Answer: ${shown}`, e.question];
  }
  const d = e.detail || {};
  const b = e.because || {};
  const facts = `fps ${fmt(b.fps, 0)} (${b.timebase}) | markers ${JSON.stringify(b.markers)} | shake ${fmt(b.jitter_px, 3)} px | peak ${fmt(b.top_hz, 1)} Hz | SNR ${fmt(b.snr, 1)}`;
  const title = { Recapture: "Asks for a new clip", AskHuman: "Asks you a question", Report: "Reports", ProposeTicket: "Drafts a maintenance ticket" }[e.action] || e.action;
  return [`${title} (${b.rule})`, d.reason || d.summary || (d.report && d.report.summary) || "", facts];
}

function timeline(events) {
  return events.filter((e) => e.kind !== "tool").map((e) => {
    const [what, why, facts] = describe(e);
    const before = events.filter((x) => x.kind !== "tool" && x.seq < e.seq).pop();
    const tools = events.filter((t) => t.kind === "tool" && t.seq < e.seq && t.seq > (before ? before.seq : -1));
    return el("li", { class: `${e.kind} ${e.action || ""}` }, el("div", { class: "what" }, what), why ? el("div", { class: "why" }, why) : "",
      facts ? el("div", { class: "small muted" }, facts) : "",
      tools.length ? el("details", {}, el("summary", {}, `${tools.length} OpenCV tool calls`), el("pre", {}, tools.map((t) => `${t.name} (${t.ms} ms) -> ${JSON.stringify(t.output)}`).join("\n"))) : "");
  });
}

export function measurePanel({ mode, machine = null, samples = [], onSaved = () => {} }) {
  let s = Object.freeze({ clips: [], answers: {}, sample: null, sessionId: randomId() });
  const status = el("div", { class: "status idle", role: "status", "aria-live": "polite" }, mode === "demo" ? "Pick a sample to start." : "Upload a clip or pick a sample to start.");
  const steps = el("ol", { class: "timeline" });
  const result = el("div", { class: "result" });
  const set = (patch) => { s = Object.freeze({ ...s, ...patch }); };
  const show = (kind, ...content) => { status.className = `status ${kind}`; status.replaceChildren(...content); };

  async function run() {
    const started = Date.now();
    const label = el("span", {}, "The agent is checking the clip...");
    show("busy", el("span", { class: "spinner", "aria-hidden": "true" }), label);
    const timer = setInterval(() => { label.textContent = `The agent is checking the clip... ${Math.round((Date.now() - started) / 1000)} s`; }, 1000);
    try {
      const data = mode === "demo" ? await api("/api/demo/analyze", { clips: s.clips, answers: s.answers })
        : await api("/api/measure", { machine_id: machine.machine_id, session_id: s.sessionId, clips: s.clips, answers: s.answers });
      clearInterval(timer);
      render(data);
    } catch (err) {
      clearInterval(timer);
      status.className = "status error";
      status.replaceChildren(...problem(err).childNodes);
    }
  }

  function upload(file) {
    return new Promise(async (resolve, reject) => {
      try {
        const target = await api("/api/uploads", { filename: file.name, content_type: file.type || "application/octet-stream" });
        const xhr = new XMLHttpRequest();
        xhr.open(target.method, target.url);
        xhr.upload.onprogress = (e) => { if (e.lengthComputable) show("busy", el("span", { class: "spinner" }), `Uploading ${Math.round((100 * e.loaded) / e.total)}%`); };
        xhr.onload = () => (xhr.status < 300 ? resolve(target.key) : reject(new Error(`upload failed (${xhr.status})`)));
        xhr.onerror = () => reject(new Error("upload failed: network error"));
        if (target.method === "POST") {
          const form = new FormData();
          for (const [k, v] of Object.entries(target.fields)) form.append(k, v);
          form.append("file", file);
          xhr.send(form);
        } else xhr.send(file);
      } catch (err) { reject(err); }
    });
  }

  async function addFile(file) {
    if (!file) return;
    if (file.size > 300 * 1024 * 1024) { show("error", "That file is over 300 MB. Trim it to about 10 seconds."); return; }
    try {
      const key = await upload(file);
      set({ clips: [...s.clips, key] });
      await run();
    } catch (err) { show("error", el("h3", {}, "Upload failed"), el("p", {}, err.message)); }
  }

  function fileInput(label) {
    const input = el("input", { type: "file", accept: "video/*", "aria-label": label });
    input.addEventListener("change", () => addFile(input.files[0]));
    return input;
  }

  const answer = (key, value) => { set({ answers: { ...s.answers, [key]: value } }); run(); };

  function askCapture(data) {
    const next = s.sample && s.sample.clips[s.clips.length];
    const row = el("div", { class: "row" });
    if (mode === "site" && !s.sample) row.append(el("label", { class: "filebtn" }, "Upload the new clip", fileInput("Upload the new clip")));
    if (next) row.append(el("button", { type: "button", onclick: () => { set({ clips: [...s.clips, next] }); run(); } }, "Use the sample's next clip (simulated recapture)"));
    show("ask", el("h3", {}, `The agent needs a new clip: ${data.instruction}`), el("p", { class: "reason" }, `Why: ${data.reason}`), row);
  }

  function askQuestion(data) {
    const q = data.question;
    const head = [el("h3", {}, q.text), el("p", { class: "reason" }, `Why: ${q.reason}`)];
    if (q.field === "approve_ticket") {
      const yes = mode === "site" ? "Send ticket to my lead" : "Approve ticket";
      show("ask", ...head, el("div", { class: "row" },
        el("button", { type: "button", onclick: () => answer(data.answer_key, true) }, yes),
        el("button", { type: "button", class: "ghost", onclick: () => answer(data.answer_key, false) }, "Do not send")));
      return;
    }
    const isRpm = q.field === "running_hz";
    const input = el("input", { type: "number", step: "any", min: "0", required: true, inputmode: "decimal", "aria-label": isRpm ? "Running speed in rpm" : "Frame rate in fps" });
    const quick = (isRpm ? [1500, 3000] : [30, 60, 120, 240]).map((v) => el("button", { type: "button", class: "ghost", onclick: () => answer(data.answer_key, isRpm ? v / 60 : v) }, `${v}`));
    const form = el("form", {}, input, el("span", { class: "small muted" }, isRpm ? "rpm" : "fps"), el("button", { type: "submit" }, "Answer"), ...quick);
    if (isRpm) form.append(el("button", { type: "button", class: "ghost", onclick: () => answer(data.answer_key, "unknown") }, "I don't know"));
    form.addEventListener("submit", (ev) => { ev.preventDefault(); const v = Number(input.value); if (v > 0) answer(data.answer_key, isRpm ? v / 60 : v); });
    const hint = s.sample && isRpm && s.sample.answers && s.sample.answers.running_hz ? `Sample machine: ${Math.round(s.sample.answers.running_hz * 60)} rpm` : "";
    show("ask", ...head, form, hint ? el("p", { class: "small muted" }, hint) : "");
    input.focus();
  }

  function render(data) {
    steps.replaceChildren(...timeline(data.events || []));
    if (data.status === "need_capture") return askCapture(data);
    if (data.status === "need_answer") return askQuestion(data);
    const saved = data.saved;
    show("done", el("h3", {}, saved ? "Saved to the machine's history" : "Done (demo, not saved)"),
      el("p", { class: "reason" }, `${data.report.verdict.replace("_", " ")} after ${(data.captures || []).length} clip(s)` + (saved && saved.change ? `; velocity ${saved.change.text}` : "") + (saved && saved.ticket_id ? "; ticket sent to your lead" : "")),
      el("button", { type: "button", class: "ghost", onclick: reset }, "Measure again"));
    result.replaceChildren(renderResult(data));
    if (saved) onSaved(data);
  }

  function reset() {
    s = Object.freeze({ clips: [], answers: {}, sample: null, sessionId: randomId() });
    steps.replaceChildren();
    result.replaceChildren();
    show("idle", "Upload a clip or pick a sample to start.");
  }

  const pickSample = (sample) => { reset(); set({ clips: [sample.clips[0]], sample }); run(); };
  const sampleList = el("div", { class: "samples" }, samples.map((x) => el("button", { type: "button", class: "sample", "data-testid": `sample-${x.id}`, onclick: () => pickSample(x) }, el("b", {}, x.title), el("span", {}, x.description))));
  const intake = el("div", { class: "intake" });
  if (mode === "site") {
    intake.append(el("label", { class: "drop" }, fileInput("Choose a slow-motion clip"), el("strong", {}, "Choose a slow-motion clip"),
      el("span", {}, "About 10 s, phone resting on something still, marker 0 on the machine and marker 1 on something still behind it.")));
  }
  intake.append(el("h3", {}, mode === "site" ? "Or use a simulated sample" : "Pick a simulated sample"),
    el("p", { class: "small muted" }, "Samples are simulated clips with known vibration, labelled as such."), sampleList);
  return el("div", { class: "measure" }, el("div", { class: "cols" }, el("section", { class: "panel" }, intake),
    el("section", { class: "panel" }, el("h2", {}, "Agent"), status, steps)), el("section", { class: "panel" }, el("h2", {}, "Result"), result));
}
