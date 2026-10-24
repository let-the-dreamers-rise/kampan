// Renders a finished agent session: verdict, zone bar, numbers, ticket, magnified view and charts.
import { lineChart } from "./charts.js";
import { el, fmt } from "./dom.js";

let player = null;

function zoneBar(velocity, limits) {
  const max = limits[2] * 1.5;
  const bar = el("div", { class: "zones", role: "img", "aria-label": `Velocity ${fmt(velocity)} mm/s against zone limits ${limits.join(", ")} mm/s` },
    el("div", { class: "za" }, "A"), el("div", { class: "zb" }, "B"), el("div", { class: "zc" }, "C"), el("div", { class: "zd" }, "D"));
  const edges = [0, ...limits, max];
  const idx = limits.findIndex((l) => velocity < l);
  const seg = idx === -1 ? 3 : idx;
  const frac = Math.min(1, (velocity - edges[seg]) / (edges[seg + 1] - edges[seg]));
  const pos = `${(100 * (seg + frac)) / 4}%`;
  bar.append(el("span", { class: "pin", style: `left:${pos}` }), el("span", { class: "pinlabel", style: `left:${pos}` }, `${fmt(velocity)} mm/s`));
  return bar;
}

function filmPlayer(strip) {
  const img = new Image();
  const c = el("canvas", { width: strip.tile_w, height: strip.tile_h, role: "img", "aria-label": "Original on the left, motion magnified on the right" });
  const g = c.getContext("2d");
  let frame = 0, playing = true;
  img.onload = () => g.drawImage(img, 0, 0, strip.tile_w, strip.tile_h, 0, 0, strip.tile_w, strip.tile_h);
  img.src = `data:image/jpeg;base64,${strip.jpeg}`;
  if (player) clearInterval(player);
  player = setInterval(() => {
    if (!playing || !img.complete || !c.isConnected) return;
    frame = (frame + 1) % strip.frames;
    g.drawImage(img, 0, frame * strip.tile_h, strip.tile_w, strip.tile_h, 0, 0, strip.tile_w, strip.tile_h);
  }, 125);
  const toggle = el("button", { type: "button", class: "ghost", onclick: () => { playing = !playing; toggle.textContent = playing ? "Pause" : "Play"; } }, "Pause");
  return [c, el("div", { class: "row" }, toggle, `Left: original. Right: motion x${strip.alpha} around ${fmt(strip.freq_hz, 1)} Hz, slowed down.`)];
}

export function renderResult(data) {
  const r = data.report;
  const out = [el("p", { class: "headline" }, r.summary)];
  if (r.velocity_mm_s !== null && r.velocity_mm_s !== undefined && data.zone_limits) out.push(zoneBar(r.velocity_mm_s, data.zone_limits));
  const stat = (k, v) => el("div", { class: "stat" }, el("div", { class: "k" }, k), el("div", { class: "v" }, v));
  out.push(el("div", { class: "stats" }, stat("Verdict", r.verdict.replace("_", " ")), stat("Strongest frequency", `${fmt(r.dominant_hz, 1)} Hz`),
    stat("Velocity (RMS)", `${fmt(r.velocity_mm_s)} mm/s`), stat("Likely cause", r.signature || "n/a"), stat("Clips used", (data.captures || []).length)));
  if (data.ticket) {
    const note = data.ticket_approved ? (data.saved ? "Sent to your lead for a decision." : "Approved (demo: nothing is sent).") : "Not sent.";
    out.push(el("div", { class: "ticket" }, el("h4", {}, data.ticket.title), el("p", { class: "small" }, data.ticket.evidence), el("p", { class: "small" }, note)));
  }
  if (r.caveats && r.caveats.length) out.push(el("ul", { class: "caveats" }, r.caveats.map((c) => el("li", {}, c))));
  const figs = el("div", { class: "figs" });
  const v = data.visuals || {};
  if (v.filmstrip) figs.append(el("div", { class: "fig" }, el("h4", {}, "Motion magnified"), ...filmPlayer(v.filmstrip)));
  if (v.frame) figs.append(el("div", { class: "fig" }, el("h4", {}, "What was measured"), el("img", { src: `data:image/jpeg;base64,${v.frame}`, alt: "First frame with the markers, the measured region and the vibration direction" })));
  if (v.spectrum) {
    const s = v.spectrum;
    const marks = (r.peaks_mm || []).slice(0, 3).map(([f, a]) => [f, a, `${fmt(f, 1)} Hz`]);
    figs.append(el("div", { class: "fig" }, el("h4", {}, `Spectrum (peak displacement, ${s.unit})`), lineChart(s.freqs, s.amp, { xlabel: "Hz", ylabel: s.unit, marks })));
    figs.append(el("div", { class: "fig" }, el("h4", {}, `Displacement over 0.5 s (${s.unit})`), lineChart(s.t, s.disp, { xlabel: "s", ylabel: s.unit })));
  }
  out.push(figs);
  return el("div", {}, ...out);
}
