// Canvas charts: spectrum and displacement lines, and a machine's velocity trend over zone bands.
import { el } from "./dom.js";

const ZONE_COLORS = ["#e3f0e2", "#eef3dc", "#f8ecd6", "#f7dcd9"];

function frame(w, h, label) {
  const c = el("canvas", { class: "chart", width: w, height: h, role: "img", "aria-label": label });
  return [c, c.getContext("2d")];
}

export function lineChart(xs, ys, { w = 640, h = 220, xlabel = "", ylabel = "", marks = [] } = {}) {
  const [c, g] = frame(w, h, `${ylabel} against ${xlabel}`);
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

/** points: [{ at, velocity }] oldest first; limits: the class's zone limits in mm/s. */
export function trendChart(points, limits, { w = 720, h = 240 } = {}) {
  const [c, g] = frame(w, h, "Velocity over time against the ISO 10816-1 zones");
  const pad = { l: 46, r: 12, t: 10, b: 28 };
  const top = Math.max(limits[2] * 1.3, ...points.map((p) => p.velocity * 1.15));
  const t0 = points[0].at, t1 = points[points.length - 1].at;
  const X = (t) => pad.l + (points.length === 1 ? 0.5 : (t - t0) / (t1 - t0 || 1)) * (w - pad.l - pad.r);
  const Y = (v) => h - pad.b - (v / top) * (h - pad.t - pad.b);
  const edges = [0, ...limits, top];
  edges.slice(0, -1).forEach((lo, i) => {
    g.fillStyle = ZONE_COLORS[i];
    g.fillRect(pad.l, Y(edges[i + 1]), w - pad.l - pad.r, Y(lo) - Y(edges[i + 1]));
    g.fillStyle = "#5d636a"; g.font = "11px system-ui";
    g.fillText("ABCD"[i], w - pad.r - 12, Y(edges[i + 1]) + 13);
  });
  g.fillStyle = "#5d636a";
  for (const v of [0, ...limits]) g.fillText(v.toFixed(1), 4, Y(v) + 4);
  g.fillText("mm/s", 4, pad.t + 8);
  g.strokeStyle = "#1b1d1f"; g.lineWidth = 2; g.beginPath();
  points.forEach((p, i) => (i ? g.lineTo(X(p.at), Y(p.velocity)) : g.moveTo(X(p.at), Y(p.velocity))));
  g.stroke();
  g.fillStyle = "#1b1d1f";
  for (const p of points) { g.beginPath(); g.arc(X(p.at), Y(p.velocity), 4, 0, 7); g.fill(); }
  const fmtDay = (t) => new Date(t).toLocaleDateString([], { month: "short", day: "numeric" });
  g.fillText(fmtDay(t0), pad.l, h - 8);
  if (points.length > 1) g.fillText(fmtDay(t1), w - pad.r - 44, h - 8);
  return c;
}
