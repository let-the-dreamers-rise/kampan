// Technician measuring, the lead's ticket queue, the team and invites, and site activity.
import { api } from "../api.js";
import { copyField, el, empty, fmt, problem, when, zone } from "../dom.js";
import { measurePanel } from "../measure.js";

export async function measure(ctx, machineId) {
  const [{ machines }, { samples }] = await Promise.all([api("/api/machines"), api("/api/samples")]);
  if (!machines.length) {
    return el("div", { class: "page" }, el("section", { class: "panel" }, el("h2", {}, "Measure"), empty(ctx.me.roles_here.includes("lead")
      ? "No machines yet. Switch to the lead role to register one, then come back." : "Your lead has not registered a machine yet. Ask them to add one.",
    ctx.me.roles_here.includes("lead") ? el("button", { type: "button", onclick: () => ctx.switchRole("lead", "#/machines") }, "Switch to lead") : "")));
  }
  const chosen = machines.find((m) => m.machine_id === machineId) || null;
  const select = el("select", { id: "pick-machine", onchange: () => ctx.go(`#/measure/${select.value}`) },
    el("option", { value: "" }, "Choose a machine"), machines.map((m) => el("option", { value: m.machine_id, selected: chosen && m.machine_id === chosen.machine_id }, m.name)));
  const head = el("section", { class: "panel" }, el("h2", {}, "Measure"), el("label", { for: "pick-machine" }, "Machine "), select,
    chosen ? el("p", { class: "small muted" }, `Class ${chosen.machine_class}, marker ${chosen.marker_mm} mm` + (chosen.rpm ? `, ${chosen.rpm} rpm (the agent will not need to ask)` : "")) : "",
    el("p", { class: "small" }, el("a", { href: "https://github.com/let-the-dreamers-rise/kampan/blob/main/capture_kit/kampan-markers-A4.pdf", target: "_blank", rel: "noopener" }, "Print the marker sheet"), " | ",
      el("a", { href: "https://github.com/let-the-dreamers-rise/kampan/blob/main/capture_kit/HOW-TO-FILM.md", target: "_blank", rel: "noopener" }, "How to film")));
  return el("div", { class: "page" }, head, chosen ? measurePanel({ mode: "site", machine: chosen, samples, onSaved: () => ctx.refresh() }) : "");
}

function ticketCard(ctx, t) {
  const out = el("div");
  const note = el("input", { maxlength: "300", placeholder: "Note (optional)", "aria-label": "Note" });
  const decide = (approve) => async () => {
    try { await api(`/api/tickets/${t.ticket_id}/decision`, { approve, note: note.value }); ctx.go("#/tickets"); } catch (err) { out.replaceChildren(problem(err)); }
  };
  const open = t.status === "open";
  return el("div", { class: `card ticket-card ${t.status}` },
    el("div", { class: "card-head" }, el("b", {}, t.title), el("span", { class: `tag ${t.status}` }, t.status)),
    el("div", { class: "small" }, el("a", { href: `#/machines/${t.machine_id}` }, t.machine_name), ` | zone `, zone(t.zone), ` | ${fmt(t.velocity_mm_s)} mm/s | sent by ${t.sent_by}, ${when(t.created)}`),
    el("p", { class: "small muted" }, t.evidence),
    open && ctx.me.role === "lead" ? el("div", { class: "row" }, note, el("button", { type: "button", onclick: decide(true) }, "Approve"), el("button", { type: "button", class: "ghost", onclick: decide(false) }, "Decline")) : "",
    !open ? el("p", { class: "small" }, `${t.status} by ${t.decided_by}, ${when(t.decided_at)}${t.note ? `: ${t.note}` : ""}`) : "", out);
}

export async function ticketQueue(ctx) {
  const { tickets } = await api("/api/tickets");
  return el("div", { class: "page" }, el("section", { class: "panel" }, el("h2", {}, "Maintenance tickets"),
    el("p", { class: "small muted" }, "The agent drafts a ticket in zone C or D; the technician decides whether to send it; you decide what happens. Kampan does not email or file tickets anywhere yet (planned)."),
    tickets.length ? el("div", { class: "cards" }, tickets.map((t) => ticketCard(ctx, t))) : empty("No tickets. They appear when a technician sends one from a zone C or D reading.")));
}

export async function team(ctx) {
  const data = await api("/api/team");
  const isLead = ctx.me.role === "lead";
  const linkBox = el("div");
  const invite = el("button", { type: "button", onclick: async () => {
    try { const inv = await api("/api/team/invites", {}); linkBox.replaceChildren(el("p", { class: "small" }, "Send this link to one technician. It works once and expires in 7 days."), copyField(`${location.origin}/#/join/${inv.token}`, "Invite link")); } catch (err) { linkBox.replaceChildren(problem(err)); }
  } }, "Create an invite link");
  return el("div", { class: "page" }, el("section", { class: "panel" }, el("h2", {}, `People at ${ctx.me.site.name}`),
    el("ul", { class: "people" }, data.members.map((m) => el("li", {}, el("b", {}, m.name), ` ${m.roles.join(" and ")}`, el("span", { class: "small muted" }, ` since ${when(m.joined)}`))))),
  isLead ? el("section", { class: "panel" }, el("h2", {}, "Invite a technician"), invite, linkBox,
    data.invites.length ? el("ul", { class: "small muted" }, data.invites.map((i) => el("li", {}, `Link from ${when(i.created)}: ${i.used ? `used by ${i.used_by}` : `unused, expires ${when(i.expires)}`}`))) : "") : "");
}

export async function activity(ctx) {
  const { measurements } = await api("/api/activity");
  const rows = measurements.map((r) => el("li", {}, el("a", { href: `#/machines/${r.machine_id}` }, r.machine_name), " ", r.verdict === "graded" ? zone(r.zone) : el("span", { class: "muted" }, r.verdict.replace("_", " ")),
    ` ${fmt(r.velocity_mm_s)} mm/s by ${r.by_name}, ${when(r.created)}`, r.sample ? el("span", { class: "tag" }, "simulated") : "", r.change ? el("span", { class: r.change.alert ? "alert small" : "small muted" }, ` (${r.change.text})`) : ""));
  return el("div", { class: "page" }, el("section", { class: "panel" }, el("h2", {}, "Activity at this site"),
    rows.length ? el("ul", { class: "feed" }, rows) : empty("No readings yet.")));
}
