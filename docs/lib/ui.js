// political-eye: shared helpers for every explorer page (no dependencies).
import { parseCSV } from "../camara/core.js";

export { parseCSV };

const LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname);
const ROOT = LOCAL ? new URL("../../data/", import.meta.url).href : "https://raw.githubusercontent.com/mbottoni/political-eye/main/data/";
const cache = new Map();

/** Fetch a file under data/ (local checkout on localhost, GitHub otherwise); CSV and JSON are parsed. */
export function data(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(ROOT + path).then(async (r) => {
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      if (path.endsWith(".json")) return r.json();
      const t = await r.text();
      return path.endsWith(".csv") ? parseCSV(t) : t;
    }));
  }
  return cache.get(path);
}

/** A file shipped with the site itself (maps), relative to docs/lib/. */
export function asset(path) {
  const url = new URL(path, import.meta.url).href;
  if (!cache.has(url)) cache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`); return r.json(); }));
  return cache.get(url);
}

// ------------------------------------------------------------ format

export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];
export const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
export const isDark = () => css("--is-dark") === "1";

export const fmt = (x, d = 0) => (x == null || Number.isNaN(+x) ? "–" : (+x).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d }));
export const pct = (x, d = 0) => (x == null || x === "" || Number.isNaN(+x) ? "–" : `${(100 * x).toFixed(d)}%`);
export const plural = (n, word, many = `${word}s`) => `${fmt(n)} ${n === 1 ? word : many}`;

/** R$ with a scale word: brl(1.23e9) -> "R$ 1.23 bn". */
export function brl(x, digits = 2) {
  if (x == null || x === "" || Number.isNaN(+x)) return "–";
  const v = +x, a = Math.abs(v), s = v < 0 ? "−" : "";
  const [d, w] = a >= 1e12 ? [1e12, " tn"] : a >= 1e9 ? [1e9, " bn"] : a >= 1e6 ? [1e6, " M"] : a >= 1e3 ? [1e3, " k"] : [1, ""];
  const n = a / d, whole = Math.abs(n - Math.round(n)) < 1e-6;
  // digits=0 (axis ticks, rough labels): whole numbers stay whole, R$ 1.5 bn keeps its decimal so ticks never repeat.
  const dd = d === 1 ? 0 : n >= 100 ? 0 : n >= 10 ? (digits === 0 && whole ? 0 : 1) : digits === 0 ? (whole ? 0 : 1) : digits;
  return `${s}R$\u00a0${n.toFixed(dd)}${w.replace(" ", "\u00a0")}`;   // non-breaking: "R$ 151 M" never wraps
}

export function el(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null) continue;
    if (k === "on") for (const [ev, f] of Object.entries(v)) e.addEventListener(ev, f);
    else if (k in e && k !== "list") e[k] = v;
    else e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k);
  return e;
}

// ------------------------------------------------------------ url state

export const params = { get: (k) => new URLSearchParams(location.search).get(k) };
export function setParam(k, v, dflt) {
  const p = new URLSearchParams(location.search);
  if (v == null || v === "" || v === dflt) p.delete(k); else p.set(k, v);
  const q = p.toString();
  history.replaceState(null, "", q ? `?${q}` : location.pathname);
}

/** Tabs: buttons in `nav.tabs` with data-tab, panels with id `tab-<name>`. Calls onShow(name) the first time a tab opens. */
export function tabs(onShow) {
  const nav = $("nav.tabs"), buttons = $$("button[data-tab]", nav), shown = new Set();
  const show = (name) => {
    if (!buttons.some((b) => b.dataset.tab === name)) name = buttons[0].dataset.tab;
    for (const b of buttons) {
      const on = b.dataset.tab === name;
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
      $(`#tab-${b.dataset.tab}`).hidden = !on;
    }
    setParam("tab", name, buttons[0].dataset.tab);
    if (!shown.has(name)) { shown.add(name); onShow(name); }
    window.dispatchEvent(new Event("tabshow"));
  };
  nav.setAttribute("role", "tablist");
  for (const b of buttons) {
    b.setAttribute("role", "tab");
    b.addEventListener("click", () => show(b.dataset.tab));
    b.addEventListener("keydown", (e) => {
      const i = buttons.indexOf(b), j = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
      if (j != null) { const n = buttons[(j + buttons.length) % buttons.length]; n.focus(); show(n.dataset.tab); }
    });
  }
  show(params.get("tab") || buttons[0].dataset.tab);
  return show;
}

// ------------------------------------------------------------ tooltip

function tipBox() {
  let t = $("#tip");
  if (!t) { t = el("div", { id: "tip", role: "tooltip" }); document.body.append(t); }
  return t;
}
export function tipRow(color, value, label, box = false) {
  return el("div", { className: "row" }, el("span", { className: `key${box ? " box" : ""}`, style: `background:${color}` }), el("b", { textContent: value }), label);
}
export function showTip(ev, kids) {
  const t = tipBox();
  t.replaceChildren(...kids); t.style.display = "block";
  const pad = 14, r = t.getBoundingClientRect();
  let x = ev.clientX + pad, y = ev.clientY + pad;
  if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - pad;
  if (y + r.height > innerHeight - 8) y = ev.clientY - r.height - pad;
  t.style.left = `${Math.max(4, x)}px`; t.style.top = `${Math.max(4, y)}px`;
}
export function hideTip() { tipBox().style.display = "none"; }

// ------------------------------------------------------------ tiles

/** tiles(box, [{label, value, sub}]) */
export function tiles(box, items) {
  box.replaceChildren(...items.map((t) => el("div", { className: "card tile" },
    el("div", { className: "label", textContent: t.label }),
    el("div", { className: "value", textContent: t.value }),
    el("div", { className: "sub", textContent: t.sub ?? "" }))));
}

// ------------------------------------------------------------ table

/**
 * A sortable, searchable, paged table with a CSV download.
 * cols: [{key, label, text?: bool, fmt?: (v, row) => string|Node, sort?: (row) => any}]
 */
export function table(box, rows, cols, { pageSize = 25, search = true, sortBy = null, desc = true, name = "table" } = {}) {
  let q = "", key = sortBy, down = desc, page = 0;
  const wrap = el("div", { className: "tablewrap" }), bar = el("div", { className: "tablebar" });
  const input = search ? el("input", { type: "search", placeholder: "Filter…", "aria-label": "Filter rows" }) : null;
  const info = el("span"), prev = el("button", { type: "button", textContent: "Previous" }), next = el("button", { type: "button", textContent: "Next" });
  const dl = el("button", { type: "button", textContent: "Download CSV" });
  const value = (r, c) => (c.sort ? c.sort(r) : r[c.key]);
  const filtered = () => {
    let out = rows;
    if (q) out = out.filter((r) => cols.some((c) => String(r[c.key] ?? "").toLowerCase().includes(q)));
    if (key) {
      const c = cols.find((x) => x.key === key);
      const blank = (v) => v === "" || v == null || (typeof v === "number" && Number.isNaN(v));
      out = [...out].sort((a, b) => {
        const x = value(a, c), y = value(b, c);
        if (blank(x) || blank(y)) return blank(x) === blank(y) ? 0 : blank(x) ? 1 : -1;   // blanks last, both ways
        const nx = +x, ny = +y;
        const cmp = x === y ? 0 : !Number.isNaN(nx) && !Number.isNaN(ny) ? nx - ny : String(x).localeCompare(String(y), "pt");
        return down ? -cmp : cmp;
      });
    }
    return out;
  };
  const render = () => {
    const all = filtered(), pages = Math.max(1, Math.ceil(all.length / pageSize));
    page = Math.min(page, pages - 1);
    const t = el("table", { className: "view" });
    t.append(el("thead", {}, el("tr", {}, ...cols.map((c) => el("th", { className: c.text ? "text" : "", scope: "col" },
      el("button", { type: "button", textContent: c.label + (key === c.key ? (down ? " ↓" : " ↑") : ""), on: { click: () => { down = key === c.key ? !down : !c.text; key = c.key; render(); } } }))))));
    const body = el("tbody");
    for (const r of all.slice(page * pageSize, (page + 1) * pageSize)) {
      body.append(el("tr", {}, ...cols.map((c) => {
        const v = c.fmt ? c.fmt(r[c.key], r) : r[c.key];
        return el("td", { className: (c.text ? "text" : "") + (c.wrap ? " wrap" : "") }, v instanceof Node ? v : String(v ?? ""));
      })));
    }
    t.append(body);
    wrap.replaceChildren(t);
    info.textContent = all.length ? `${fmt(page * pageSize + 1)}–${fmt(Math.min(all.length, (page + 1) * pageSize))} of ${fmt(all.length)}` : "No rows";
    prev.disabled = page === 0; next.disabled = page >= pages - 1;
  };
  prev.addEventListener("click", () => { page--; render(); });
  next.addEventListener("click", () => { page++; render(); });
  input?.addEventListener("input", () => { q = input.value.trim().toLowerCase(); page = 0; render(); });
  dl.addEventListener("click", () => {
    const esc = (v) => { const s = String(v ?? ""); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const text = [cols.map((c) => esc(c.label)).join(","), ...filtered().map((r) => cols.map((c) => esc(r[c.key])).join(","))].join("\n");
    const a = el("a", { href: URL.createObjectURL(new Blob([text], { type: "text/csv" })), download: `${name}.csv` });
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  bar.append(...[input, info, prev, next, dl].filter(Boolean));
  box.replaceChildren(bar, wrap);
  render();
  return { update(newRows) { rows = newRows; page = 0; render(); } };
}

/** Run an async page section, showing its error in place instead of failing silently. */
export async function guard(box, f) {
  try { return await f(); } catch (e) {
    console.error(e);
    box.append(el("p", { className: "error", textContent: `Could not load this section: ${e.message}` }));
  }
}

/** Re-run f when the page width changes (charts size themselves to their box). */
export function onResize(f) {
  let last = 0, timer;
  new ResizeObserver(([e]) => {
    const w = Math.round(e.contentRect.width);
    if (w === last) return;
    last = w; clearTimeout(timer); timer = setTimeout(f, 120);
  }).observe(document.querySelector("main"));
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", f);
  window.addEventListener("tabshow", () => setTimeout(f, 0));
}
