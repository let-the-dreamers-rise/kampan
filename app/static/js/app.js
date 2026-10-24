// The shell: who is signed in, the role's tabs, and the hash router. Views live in ./views.
import { api } from "./api.js";
import { $, el, problem } from "./dom.js";
import { machineDetail, machineList } from "./views/machines.js";
import { impact, shared } from "./views/public.js";
import { join, welcome } from "./views/welcome.js";
import { activity, measure, team, ticketQueue } from "./views/work.js";

const TABS = {
  lead: [["#/machines", "Machines"], ["#/tickets", "Tickets"], ["#/team", "Team"], ["#/activity", "Activity"]],
  technician: [["#/measure", "Measure"], ["#/machines", "Machines"], ["#/activity", "Activity"]],
};
const HOME = { lead: "#/machines", technician: "#/measure" };
const PUBLIC = [[/^#\/m\/([\w-]+)$/, shared], [/^#\/impact$/, impact], [/^#\/join\/([\w-]+)$/, join]];
const PRIVATE = [[/^#\/machines$/, machineList], [/^#\/machines\/([\w-]+)$/, machineDetail], [/^#\/tickets$/, ticketQueue],
  [/^#\/team$/, team], [/^#\/activity$/, activity], [/^#\/measure(?:\/([\w-]+))?$/, measure]];

const ctx = {
  me: null,
  go(hash) { if (location.hash === hash) render(); else location.hash = hash; },
  async refresh() { ctx.me = await api("/api/me"); header(); },
  signedIn(me) { ctx.me = me; ctx.go(location.hash.startsWith("#/join/") ? HOME[me.role] : HOME[me.role]); header(); },
  async switchRole(role, hash) {
    try { ctx.me = await api("/api/session/switch", { role }); header(); ctx.go(hash || HOME[role]); } catch (err) { $("#view").prepend(problem(err)); }
  },
};

function header() {
  const box = $("#account");
  const tabs = $("#tabs");
  const me = ctx.me;
  if (!me || !me.signed_in) {
    box.replaceChildren(el("a", { href: "#/impact", class: "small" }, "Live activity"));
    tabs.replaceChildren();
    return;
  }
  const other = me.role === "lead" ? "technician" : "lead";
  const canSwitch = me.roles_here.includes(other) || other === "lead";
  box.replaceChildren(el("div", { class: "who" }, el("b", {}, me.user.name), el("span", { class: "small muted" }, ` ${me.site.name}`)),
    el("span", { class: `tag role ${me.role}` }, me.role),
    canSwitch ? el("button", { type: "button", class: "ghost small", onclick: () => ctx.switchRole(other) }, `Switch to ${other}`) : "",
    el("button", { type: "button", class: "ghost small", onclick: async () => { await api("/api/auth/logout", {}); ctx.me = { signed_in: false }; header(); ctx.go("#/"); } }, "Sign out"));
  const current = location.hash.split("/").slice(0, 2).join("/");
  tabs.replaceChildren(...TABS[me.role].map(([href, label]) => el("a", { href, class: current === href ? "active" : "", "aria-current": current === href ? "page" : null }, label)));
}

async function render() {
  const view = $("#view");
  const hash = location.hash || "#/";
  view.replaceChildren(el("p", { class: "muted loading" }, "Loading..."));
  try {
    if (ctx.me === null) ctx.me = await api("/api/me");
    header();
    for (const [pattern, fn] of PUBLIC) {
      const m = hash.match(pattern);
      if (m) { view.replaceChildren(await fn(ctx, ...m.slice(1))); return; }
    }
    if (!ctx.me.signed_in) { view.replaceChildren(await welcome(ctx)); return; }
    for (const [pattern, fn] of PRIVATE) {
      const m = hash.match(pattern);
      if (m) { view.replaceChildren(await fn(ctx, ...m.slice(1))); window.scrollTo(0, 0); return; }
    }
    ctx.go(HOME[ctx.me.role]);
  } catch (err) {
    if (err.status === 401) { ctx.me = { signed_in: false }; header(); view.replaceChildren(await welcome(ctx)); return; }
    view.replaceChildren(problem(err));
  }
}

window.addEventListener("hashchange", render);
render();
