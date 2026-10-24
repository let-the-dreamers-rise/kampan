// Machines at the site: the list, registering one (lead), and one machine's history (both roles).
import { api } from "../api.js";
import { trendChart } from "../charts.js";
import { copyField, download, el, empty, fmt, problem, when, zone } from "../dom.js";

const LIMITS = { I: [0.71, 1.8, 4.5], II: [1.12, 2.8, 7.1], III: [1.8, 4.5, 11.2], IV: [2.8, 7.1, 18] };

function registerForm(onCreated) {
  const out = el("div");
  const field = (id, label, input) => el("label", { for: id }, label, input);
  const name = el("input", { id: "m-name", required: true, maxlength: "60", placeholder: "Roof exhaust fan 2" });
  const location = el("input", { id: "m-loc", maxlength: "80", placeholder: "Block B, roof" });
  const cls = el("select", { id: "m-class" }, el("option", { value: "I" }, "I: small, up to 15 kW"), el("option", { value: "II" }, "II: medium, 15 to 75 kW"),
    el("option", { value: "III" }, "III: large, rigid base"), el("option", { value: "IV" }, "IV: large, soft base"));
  const rpm = el("input", { id: "m-rpm", type: "number", min: "30", max: "60000", step: "any", inputmode: "numeric", placeholder: "optional, e.g. 1440" });
  const marker = el("input", { id: "m-marker", type: "number", min: "5", max: "500", step: "0.5", value: "40" });
  const form = el("form", { class: "grid-form" }, field("m-name", "Name", name), field("m-loc", "Location", location),
    field("m-class", "ISO 10816-1 class", cls), field("m-rpm", "Running speed (rpm)", rpm), field("m-marker", "Printed marker size (mm)", marker),
    el("div", { class: "row" }, el("button", { type: "submit" }, "Register machine")), out);
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const m = await api("/api/machines", { name: name.value, location: location.value, machine_class: cls.value, rpm: rpm.value || null, marker_mm: marker.value });
      form.reset(); marker.value = "40"; out.replaceChildren();
      onCreated(m);
    } catch (err) { out.replaceChildren(problem(err)); }
  });
  return form;
}

function machineRow(m) {
  return el("a", { class: "card machine", href: `#/machines/${m.machine_id}` },
    el("div", { class: "card-head" }, el("b", {}, m.name), zone(m.last_zone)),
    el("div", { class: "small muted" }, [m.location, `class ${m.machine_class}`, m.rpm ? `${m.rpm} rpm` : null].filter(Boolean).join(" | ")),
    el("div", { class: "small" }, m.measurements ? `${m.measurements} reading(s); last ${fmt(m.last_velocity)} mm/s, ${when(m.last_at)}` : "Not measured yet"),
    m.last_change ? el("div", { class: "small muted" }, `Velocity ${m.last_change}`) : "");
}

export async function machineList(ctx) {
  const { machines } = await api("/api/machines");
  const list = el("div", { class: "cards" }, machines.map(machineRow));
  const isLead = ctx.me.role === "lead";
  const body = machines.length ? list : empty(isLead ? "No machines yet. Register the first one below; it takes a minute." : "Your lead has not registered a machine yet.");
  return el("div", { class: "page" }, el("section", { class: "panel" }, el("h2", {}, "Machines"), body),
    isLead ? el("section", { class: "panel" }, el("h2", {}, "Register a machine"), registerForm(() => ctx.go("#/machines"))) : "");
}

function shareBox(ctx, machineId, token) {
  const box = el("div");
  const draw = (t) => {
    const link = t ? `${location.origin}/#/m/${t}` : null;
    box.replaceChildren(el("h3", {}, "Read-only link"), link ? copyField(link, "Read-only link") : el("p", { class: "small muted" }, "Share this machine's history with an owner or auditor. They see readings, not people."),
      el("button", { type: "button", class: "ghost", onclick: async () => {
        try { draw((await api(`/api/machines/${machineId}/${t ? "unshare" : "share"}`, {})).share_token); } catch (err) { box.append(problem(err)); }
      } }, t ? "Turn the link off" : "Create link"));
  };
  draw(token);
  return box;
}

export function historyTable(rows, { machineId = null, withPeople = true } = {}) {
  if (!rows.length) return empty("No readings yet.");
  const traceButton = (r) => el("button", { type: "button", class: "ghost small", onclick: async () => {
    download(`kampan-trace-${r.measurement_id}.json`, await api(`/api/machines/${machineId}/measurements/${r.measurement_id}/trace`));
  } }, "Trace");
  return el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, el("tr", {}, ["When", "Zone", "mm/s", "Hz", "Cause", "Change", withPeople ? "By" : null, machineId ? "" : null].filter((x) => x !== null).map((h) => el("th", {}, h)))),
    el("tbody", {}, rows.map((r) => el("tr", {}, el("td", {}, when(r.created), r.sample ? el("span", { class: "tag" }, "simulated") : ""), el("td", {}, r.verdict === "graded" ? zone(r.zone) : el("span", { class: "muted" }, r.verdict.replace("_", " "))),
      el("td", {}, fmt(r.velocity_mm_s)), el("td", {}, fmt(r.dominant_hz, 1)), el("td", {}, r.signature || ""), el("td", { class: r.change && r.change.alert ? "alert" : "" }, r.change ? r.change.text : ""),
      withPeople ? el("td", {}, r.by_name || "") : null, machineId ? el("td", {}, traceButton(r)) : null)))));
}

export function trend(machine, rows) {
  const points = rows.filter((r) => r.verdict === "graded" && r.velocity_mm_s !== null).map((r) => ({ at: r.created, velocity: r.velocity_mm_s })).reverse();
  return points.length ? trendChart(points, LIMITS[machine.machine_class]) : empty("The trend appears after the first graded reading.");
}

export async function machineDetail(ctx, machineId) {
  let data;
  try { data = await api(`/api/machines/${encodeURIComponent(machineId)}`); } catch (err) { return el("div", { class: "page" }, problem(err)); }
  const m = data.machine;
  const actions = el("div", { class: "row" });
  if (ctx.me.role === "technician") actions.append(el("a", { class: "button", href: `#/measure/${m.machine_id}` }, "Measure this machine"));
  return el("div", { class: "page" }, el("section", { class: "panel" },
    el("div", { class: "card-head" }, el("h1", {}, m.name), zone(m.last_zone)),
    el("p", { class: "muted" }, [m.location, `ISO class ${m.machine_class}`, m.rpm ? `${m.rpm} rpm` : "running speed not set", `marker ${m.marker_mm} mm`].filter(Boolean).join(" | ")), actions,
    el("h3", {}, "Velocity trend"), trend(m, data.measurements)),
  el("section", { class: "panel" }, el("h2", {}, "Readings"), historyTable(data.measurements, { machineId: m.machine_id })),
  ctx.me.role === "lead" ? el("section", { class: "panel" }, shareBox(ctx, m.machine_id, data.share_token)) : "");
}
