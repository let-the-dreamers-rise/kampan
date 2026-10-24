// DOM and formatting helpers shared by every view.
export const $ = (sel, root = document) => root.querySelector(sel);

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v; // CSSOM, allowed by the page's CSP
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === undefined || c === null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

export const fmt = (x, d = 2) => (x === null || x === undefined ? "n/a" : Number(x).toFixed(d));
export const when = (ms) => (ms ? new Date(ms).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "");
export const randomId = () => Array.from(crypto.getRandomValues(new Uint8Array(10)), (b) => b.toString(16).padStart(2, "0")).join("");

export function zone(z) {
  return z ? el("span", { class: `zone zone-${z.toLowerCase()}`, title: `ISO 10816-1 zone ${z}` }, z) : el("span", { class: "muted" }, "-");
}

export function problem(err) {
  const refused = err && (err.status === 403 || err.status === 409 || err.status === 429);
  return el("div", { class: "status error", role: "alert" }, el("h3", {}, refused ? "Refused" : "Something went wrong"), el("p", {}, err ? err.message : "Unknown error"));
}

export function empty(text, action) {
  return el("div", { class: "empty" }, el("p", {}, text), action || "");
}

export function copyField(value, label) {
  const input = el("input", { value, readonly: true, "aria-label": label, class: "copy" });
  const btn = el("button", { type: "button", class: "ghost", onclick: async () => {
    try { await navigator.clipboard.writeText(value); btn.textContent = "Copied"; } catch { input.select(); }
  } }, "Copy");
  return el("div", { class: "row" }, input, btn);
}

export function download(name, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = el("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
