"use strict";

const $ = (sel) => document.querySelector(sel);
const state = Object.freeze({ clips: [], answers: {}, sample: null });
let session = state;
let player = null;

function setSession(patch) {
  session = Object.freeze({ ...session, ...patch });
  renderClips();
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v; // CSSOM, allowed by the page's CSP
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) node.setAttribute(k, v);
  }
  for (const c of children.flat()) node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}

const fmt = (x, d = 2) => (x === null || x === undefined ? "n/a" : Number(x).toFixed(d));

function config() {
  const base = { marker_mm: Number($("#marker").value), machine_class: $("#mclass").value };
  return session.sample ? { ...base, ...session.sample.config } : base;
}

async function api(path, body) {
  const res = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function status(kind, ...content) {
  const box = $("#status");
  box.className = `status ${kind}`;
  box.replaceChildren(...content);
}

function busy(text) {
  const started = Date.now();
  const label = el("span", {}, text);
  status("busy", el("span", { class: "spinner", "aria-hidden": "true" }), label);
  const timer = setInterval(() => { label.textContent = `${text} ${Math.round((Date.now() - started) / 1000)} s`; }, 1000);
  return () => clearInterval(timer);
}

function upload(file) {
  return new Promise(async (resolve, reject) => {
    try {
      const target = await api("/api/upload", { filename: file.name, content_type: file.type || "application/octet-stream" });
      const xhr = new XMLHttpRequest();
      xhr.open(target.method, target.url);
      xhr.upload.onprogress = (e) => { if (e.lengthComputable) status("busy", el("span", { class: "spinner" }), `Uploading ${Math.round((100 * e.loaded) / e.total)}%`); };
      xhr.onload = () => (xhr.status < 300 ? resolve(target.key) : reject(new Error(`upload failed (${xhr.status})`)));
      xhr.onerror = () => reject(new Error("upload failed: network error"));
      if (target.method === "POST") {
        const form = new FormData();
        for (const [k, v] of Object.entries(target.fields)) form.append(k, v);
        form.append("file", file);
        xhr.send(form);
      } else {
        xhr.send(file);
      }
    } catch (err) { reject(err); }
  });
}

async function analyze() {
  const stop = busy("Agent is measuring...");
  try {
    const data = await api("/api/analyze", { clips: session.clips, answers: session.answers, config: config() });
    stop();
    render(data);
  } catch (err) {
    stop();
    status("error", el("h3", {}, "Something went wrong"), el("p", {}, err.message));
  }
}

async function addFile(file) {
  if (!file) return;
  if (file.size > 300 * 1024 * 1024) { status("error", "That file is over 300 MB. Trim it to about 10 seconds."); return; }
  try {
    const key = await upload(file);
    setSession({ clips: [...session.clips, key] });
    await analyze();
  } catch (err) {
    status("error", el("h3", {}, "Upload failed"), el("p", {}, err.message));
  }
}

function renderClips() {
  const list = $("#clips");
  if (!session.clips.length) { list.replaceChildren(el("li", { class: "muted" }, "None yet.")); return; }
  list.replaceChildren(...session.clips.map((k) => el("li", {}, k.startsWith("samples/") ? `${k.split("/")[1]} (simulated)` : "your clip")));
}

function describe(e) {
  if (e.kind === "capture") {
    const r = e.request || {};
    const asks = [r.fps ? `${r.fps} fps` : null, r.distance !== 1 ? `distance x${fmt(r.distance)}` : null, r.tripod ? "support" : null, r.markers ? "markers" : null, r.square_on ? "square-on" : null].filter(Boolean);
    return [`Clip ${e.index + 1} received`, asks.length ? `conditions asked: ${asks.join(", ")}` : "first clip"];
  }
  if (e.kind === "human") return [`You answered: ${e.answer}`, e.question];
  const d = e.detail || {};
  const b = e.because || {};
  const facts = `fps ${fmt(b.fps, 0)} (${b.timebase}) | markers ${JSON.stringify(b.markers)} | shake ${fmt(b.jitter_px, 3)} px | peak ${fmt(b.top_hz, 1)} Hz | SNR ${fmt(b.snr, 1)} | noise ${fmt(b.noise_px, 4)} px`;
  const title = { Recapture: "Asks for a new clip", AskHuman: "Asks you a question", Report: "Reports", ProposeTicket: "Drafts a maintenance ticket" }[e.action] || e.action;
  const why = d.reason || d.summary || (d.report && d.report.summary) || "";
  return [`${title} (${b.rule})`, why, facts];
}

function renderTimeline(events) {
  const items = events.filter((e) => e.kind !== "tool").map((e, i) => {
    const [what, why, facts] = describe(e);
    const tools = events.filter((t) => t.kind === "tool" && t.seq < e.seq && t.seq > (events.filter((x) => x.kind !== "tool" && x.seq < e.seq).pop() || { seq: -1 }).seq);
    const li = el("li", { class: `${e.kind} ${e.action || ""}` }, el("div", { class: "what" }, what), why ? el("div", { class: "why" }, why) : "", facts ? el("div", { class: "small muted" }, facts) : "");
    if (tools.length) {
      li.append(el("details", {}, el("summary", {}, `${tools.length} OpenCV tool calls`), el("pre", {}, tools.map((t) => `${t.name} (${t.ms} ms) -> ${JSON.stringify(t.output)}`).join("\n"))));
    }
    li.style.animationDelay = `${Math.min(i * 60, 900)}ms`;
    return li;
  });
  $("#timeline").replaceChildren(...items);
}

function askCapture(data) {
  const next = session.sample && session.sample.clips[session.clips.length];
  const input = el("input", { type: "file", accept: "video/*", "aria-label": "Upload the new clip" });
  input.addEventListener("change", () => addFile(input.files[0]));
  const row = el("div", { class: "row" }, input);
  if (next) row.append(el("button", { type: "button", onclick: () => { setSession({ clips: [...session.clips, next] }); analyze(); } }, "Use the sample's next clip (simulated recapture)"));
  status("ask", el("h3", {}, `The agent needs a new clip: ${data.instruction}`), el("p", { class: "reason" }, `Why: ${data.reason}`), row);
}

function answer(key, value) {
  setSession({ answers: { ...session.answers, [key]: value } });
  analyze();
}

function askQuestion(data) {
  const q = data.question;
  const head = [el("h3", {}, q.text), el("p", { class: "reason" }, `Why: ${q.reason}`)];
  if (q.field === "approve_ticket") {
    status("ask", ...head, el("div", { class: "row" },
      el("button", { type: "button", onclick: () => answer(data.answer_key, true) }, "Approve ticket"),
      el("button", { type: "button", class: "ghost", onclick: () => answer(data.answer_key, false) }, "Decline")));
    return;
  }
  const isRpm = q.field === "running_hz";
  const input = el("input", { type: "number", step: "any", min: "0", required: "", "aria-label": isRpm ? "Running speed in rpm" : "Frame rate" });
  const hint = session.sample && session.sample.answers && isRpm && session.sample.answers.running_hz ? `Sample machine: ${Math.round(session.sample.answers.running_hz * 60)} rpm` : "";
  const form = el("form", {}, input, el("span", { class: "small muted" }, isRpm ? "rpm" : "fps"), el("button", { type: "submit" }, "Answer"));
  if (isRpm) form.append(el("button", { type: "button", class: "ghost", onclick: () => answer(data.answer_key, "unknown") }, "I don't know"));
  form.addEventListener("submit", (ev) => { ev.preventDefault(); const v = Number(input.value); if (v > 0) answer(data.answer_key, isRpm ? v / 60 : v); });
  status("ask", ...head, form, hint ? el("p", { class: "small muted" }, hint) : "");
  input.focus();
}

function zoneBar(velocity, limits) {
  const max = limits[2] * 1.5;
  const bar = el("div", { class: "zones", role: "img", "aria-label": `Velocity ${fmt(velocity)} mm/s against zone limits ${limits.join(", ")} mm/s` },
    el("div", { class: "za" }, "A"), el("div", { class: "zb" }, "B"), el("div", { class: "zc" }, "C"), el("div", { class: "zd" }, "D"));
  const edges = [0, ...limits, max];
  const seg = Math.max(0, Math.min(3, limits.findIndex((l) => velocity < l) === -1 ? 3 : limits.findIndex((l) => velocity < l)));
  const frac = Math.min(1, (velocity - edges[seg]) / (edges[seg + 1] - edges[seg]));
  const pos = `${(100 * (seg + frac)) / 4}%`;
  bar.append(el("span", { class: "pin", style: `left:${pos}` }), el("span", { class: "pinlabel", style: `left:${pos}` }, `${fmt(velocity)} mm/s`));
  return bar;
}

function chart(series, xs, ys, { w = 640, h = 220, xlabel = "", ylabel = "", marks = [] } = {}) {
  const c = el("canvas", { class: "chart", width: w, height: h, role: "img", "aria-label": `${ylabel} against ${xlabel}` });
  const g = c.getContext("2d");
  const pad = { l: 56, r: 10, t: 10, b: 30 };
  const xmax = Math.max(...xs), xmin = Math.min(...xs), ymax = Math.max(...ys.map(Math.abs)) || 1, ymin = Math.min(0, ...ys);
  const X = (x) => pad.l + ((x - xmin) / (xmax - xmin || 1)) * (w - pad.l - pad.r);
  const Y = (y) => h - pad.b - ((y - ymin) / (ymax - ymin || 1)) * (h - pad.t - pad.b);
  g.strokeStyle = "#dedad0"; g.fillStyle = "#5d636a"; g.font = "11px system-ui";
  for (let i = 0; i <= 4; i++) { const y = ymin + ((ymax - ymin) * i) / 4; g.beginPath(); g.moveTo(pad.l, Y(y)); g.lineTo(w - pad.r, Y(y)); g.stroke(); g.fillText(y.toPrecision(2), 4, Y(y) + 4); }
  for (let i = 0; i <= 5; i++) { const x = xmin + ((xmax - xmin) * i) / 5; g.fillText(x.toFixed(x < 10 ? 2 : 0), X(x) - 8, h - 12); }
  g.fillText(xlabel, w - pad.r - g.measureText(xlabel).width, h - 2);
  g.strokeStyle = "#0f6b62"; g.lineWidth = 1.5; g.beginPath();
  xs.forEach((x, i) => (i ? g.lineTo(X(x), Y(ys[i])) : g.moveTo(X(x), Y(ys[i]))));
  g.stroke();
  g.fillStyle = "#b42318";
  for (const [mx, my, label] of marks) { g.beginPath(); g.arc(X(mx), Y(my), 4, 0, 7); g.fill(); g.fillText(label, X(mx) + 6, Y(my) - 4); }
  return c;
}

function filmPlayer(strip) {
  const img = new Image();
  const c = el("canvas", { width: strip.tile_w, height: strip.tile_h, role: "img", "aria-label": "Original on the left, motion magnified on the right" });
  const g = c.getContext("2d");
  let frame = 0, playing = true, speed = 8;
  img.onload = () => { g.drawImage(img, 0, 0, strip.tile_w, strip.tile_h, 0, 0, strip.tile_w, strip.tile_h); };
  img.src = `data:image/jpeg;base64,${strip.jpeg}`;
  if (player) clearInterval(player);
  const tick = () => { if (!playing || !img.complete) return; frame = (frame + 1) % strip.frames; g.drawImage(img, 0, frame * strip.tile_h, strip.tile_w, strip.tile_h, 0, 0, strip.tile_w, strip.tile_h); };
  player = setInterval(tick, 1000 / speed);
  const toggle = el("button", { type: "button", class: "ghost", onclick: () => { playing = !playing; toggle.textContent = playing ? "Pause" : "Play"; } }, "Pause");
  return [c, el("div", { class: "row" }, toggle, `Left: original. Right: motion x${strip.alpha} around ${fmt(strip.freq_hz, 1)} Hz, played ${fmt(strip.capture_fps / speed, 0)}x slower.`)];
}

function renderResult(data) {
  const r = data.report;
  const box = $("#result");
  const out = [el("p", { class: "headline" }, r.summary)];
  if (r.velocity_mm_s !== null && r.velocity_mm_s !== undefined && data.zone_limits) out.push(zoneBar(r.velocity_mm_s, data.zone_limits));
  out.push(el("div", { class: "stats" },
    el("div", { class: "stat" }, el("div", { class: "k" }, "Verdict"), el("div", { class: "v" }, r.verdict)),
    el("div", { class: "stat" }, el("div", { class: "k" }, "Strongest frequency"), el("div", { class: "v" }, `${fmt(r.dominant_hz, 1)} Hz`)),
    el("div", { class: "stat" }, el("div", { class: "k" }, "Velocity (RMS)"), el("div", { class: "v" }, `${fmt(r.velocity_mm_s)} mm/s`)),
    el("div", { class: "stat" }, el("div", { class: "k" }, "Likely cause"), el("div", { class: "v" }, r.signature || "n/a")),
    el("div", { class: "stat" }, el("div", { class: "k" }, "Clips used"), el("div", { class: "v" }, (data.captures || []).length))));
  if (data.ticket) {
    out.push(el("div", { class: "ticket" }, el("h4", {}, data.ticket.title), el("p", { class: "small" }, data.ticket.evidence),
      el("p", { class: "small" }, data.ticket_approved ? "Approved by you. Kampan does not send it anywhere; copy it into your maintenance system." : "Declined by you. Nothing was created.")));
  }
  if (r.caveats && r.caveats.length) out.push(el("ul", { class: "caveats" }, r.caveats.map((c) => el("li", {}, c))));
  const figs = el("div", { class: "figs" });
  const v = data.visuals || {};
  if (v.filmstrip) figs.append(el("div", { class: "fig" }, el("h4", {}, "Motion magnified"), ...filmPlayer(v.filmstrip)));
  if (v.frame) figs.append(el("div", { class: "fig" }, el("h4", {}, "What was measured"), el("img", { src: `data:image/jpeg;base64,${v.frame}`, alt: "First frame with the markers, the measured region and the vibration direction" })));
  if (v.spectrum) {
    const s = v.spectrum;
    const marks = (r.peaks_mm || []).slice(0, 3).map(([f, a]) => [f, a, `${fmt(f, 1)} Hz`]);
    figs.append(el("div", { class: "fig" }, el("h4", {}, `Spectrum (peak displacement, ${s.unit})`), chart("s", s.freqs, s.amp, { xlabel: "Hz", ylabel: s.unit, marks })));
    figs.append(el("div", { class: "fig" }, el("h4", {}, `Displacement over 0.5 s (${s.unit})`), chart("d", s.t, s.disp, { xlabel: "s", ylabel: s.unit })));
  }
  out.push(figs);
  box.replaceChildren(...out);
}

function render(data) {
  renderTimeline(data.events || []);
  if (data.status === "need_capture") return askCapture(data);
  if (data.status === "need_answer") return askQuestion(data);
  status("done", el("h3", {}, "Done"), el("p", { class: "reason" }, `${data.report.verdict} after ${(data.captures || []).length} clip(s), ${fmt(data.seconds, 1)} s of analysis.`));
  renderResult(data);
}

async function loadSamples() {
  try {
    const { samples } = await api("/api/samples");
    $("#samples").replaceChildren(...samples.map((s) => el("button", { type: "button", class: "sample", "data-testid": `sample-${s.id}`, onclick: () => {
      setSession({ clips: [s.clips[0]], answers: {}, sample: s });
      $("#marker").value = s.config.marker_mm;
      analyze();
    } }, el("b", {}, s.title), el("span", {}, s.description))));
  } catch (err) {
    $("#samples").replaceChildren(el("p", { class: "muted small" }, `Samples unavailable: ${err.message}`));
  }
}

function reset() {
  setSession({ clips: [], answers: {}, sample: null });
  if (player) clearInterval(player);
  $("#timeline").replaceChildren();
  $("#result").replaceChildren(el("p", { class: "muted" }, "The result appears when the agent has a measurement it can defend."));
  status("idle", "Waiting for a clip.");
}

$("#file").addEventListener("change", (e) => { reset(); addFile(e.target.files[0]); });
$("#reset").addEventListener("click", reset);
const drop = $("#drop");
["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => { reset(); addFile(e.dataTransfer.files[0]); });
loadSamples();
