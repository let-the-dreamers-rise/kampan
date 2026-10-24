// Pages without an account: a machine shared by its lead, and the live impact numbers.
import { api } from "../api.js";
import { el, problem, when, zone } from "../dom.js";
import { historyTable, trend } from "./machines.js";

export async function shared(ctx, token) {
  let data;
  try { data = await api(`/api/share/${encodeURIComponent(token)}`); } catch (err) { return el("div", { class: "page" }, problem(err)); }
  const m = data.machine;
  return el("div", { class: "page" }, el("section", { class: "panel" },
    el("p", { class: "small muted" }, `Read-only report shared by ${data.site}`),
    el("div", { class: "card-head" }, el("h1", {}, m.name), zone(m.last_zone)),
    el("p", { class: "muted" }, [m.location, `ISO class ${m.machine_class}`].filter(Boolean).join(" | ")), trend(m, data.measurements)),
  el("section", { class: "panel" }, el("h2", {}, "Readings"), historyTable(data.measurements, { withPeople: false })),
  el("p", { class: "small muted" }, "Camera screening estimates, not certified ISO 10816 measurements."));
}

const LABELS = { sites: "Sites", machines: "Machines registered", measurements: "Readings saved", graded: "Readings graded", refusals: "Clips refused, recapture asked",
  questions: "Questions asked", tickets: "Tickets sent to a lead", tickets_approved: "Tickets approved", demo_runs: "Demo runs" };

export async function impact() {
  let data;
  try { data = await api("/api/impact"); } catch (err) { return el("div", { class: "page" }, problem(err)); }
  return el("div", { class: "page" }, el("section", { class: "panel" }, el("h1", {}, "Live activity"),
    el("p", { class: "muted" }, "Counted from the live database. No names, sites or clips are shown."),
    el("div", { class: "stats" }, Object.entries(LABELS).map(([k, label]) => el("div", { class: "stat" }, el("div", { class: "k" }, label), el("div", { class: "v" }, data.stats[k]))))),
  el("section", { class: "panel" }, el("h2", {}, "Latest"), data.feed.length ? el("ul", { class: "feed" }, data.feed.map((f) => el("li", {}, f.text, el("span", { class: "small muted" }, ` ${when(f.at)}`)))) : el("p", { class: "muted" }, "Nothing yet.")));
}
