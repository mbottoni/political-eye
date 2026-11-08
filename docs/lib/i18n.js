// political-eye: language (Portuguese by default, English on request) and number formats per language.
// The choice comes from ?lang=, then what the reader picked last time, then Portuguese.

export const LANGS = { pt: { label: "PT", name: "Português", tag: "pt-BR" }, en: { label: "EN", name: "English", tag: "en" } };
const KEY = "political-eye.lang";

function initial() {
  if (typeof location === "undefined") return "pt";   // Node (tests/*/parity.mjs import page modules)
  const q = new URLSearchParams(location.search).get("lang");
  if (q in LANGS) { try { localStorage.setItem(KEY, q); } catch { /* storage blocked */ } return q; }
  try { const s = localStorage.getItem(KEY); if (s in LANGS) return s; } catch { /* storage blocked */ }
  return "pt";
}

let current = initial();
export const lang = () => current;
const tag = () => LANGS[current].tag;

/** Switch language: remembered, in the URL (so a shared link keeps it), on <html lang>, and announced with "langchange". */
export function setLang(l) {
  if (!(l in LANGS)) return;
  current = l;
  try { localStorage.setItem(KEY, l); } catch { /* storage blocked */ }
  const p = new URLSearchParams(location.search);
  if (l === "pt") p.delete("lang"); else p.set("lang", l);
  const q = p.toString();
  history.replaceState(null, "", (q ? `?${q}` : location.pathname) + location.hash);
  document.documentElement.lang = tag();
  window.dispatchEvent(new CustomEvent("langchange", { detail: l }));
}
if (typeof document !== "undefined") document.documentElement.lang = tag();

/** Inline text in both languages: L("Contratos públicos", "Public contracts"). */
export const L = (pt, en) => (current === "en" ? en : pt);

/** Pick this language's entry: tr({pt: "…", en: "…"}) or tr(dict, key) for dict = {pt: {key: …}, en: {key: …}}. */
export function tr(x, key) {
  const d = key == null ? x : Object.fromEntries(Object.entries(x).map(([k, v]) => [k, v[key]]));
  return d[current] ?? d.pt;
}

// ------------------------------------------------------------ numbers

const blank = (x) => x == null || x === "" || Number.isNaN(+x);
export const num = (x, d = 0) => (blank(x) ? "–" : (+x).toLocaleString(tag(), { maximumFractionDigits: d, minimumFractionDigits: d }));
export const pct = (x, d = 0) => (blank(x) ? "–" : `${num(100 * x, d)}%`);

const SCALE = { pt: [" tri", " bi", " mi", " mil"], en: [" tn", " bn", " M", " k"] };
/** Money with a scale word: R$ 1,2 bi / R$ 1.2 bn. digits = decimals below 10 of the unit. */
export function brl(x, digits = 1) {
  if (blank(x)) return "–";
  const v = +x, a = Math.abs(v), w = SCALE[current] ?? SCALE.pt;
  const [d, unit] = a >= 1e12 ? [1e12, w[0]] : a >= 1e9 ? [1e9, w[1]] : a >= 1e6 ? [1e6, w[2]] : a >= 1e3 ? [1e3, w[3]] : [1, ""];
  const n = a / d, dd = d === 1 || n >= 100 ? 0 : n >= 10 ? Math.min(1, digits) : digits;
  return `${v < 0 ? "−" : ""}R$ ${num(n, dd)}${unit.replace(" ", " ")}`;
}

const MONTHS = {
  pt: ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
};
/** "2026-05" -> "maio de 2026" / "May 2026". */
export function month(ym) {
  const m = MONTHS[current][+ym.slice(5, 7) - 1], y = ym.slice(0, 4);
  return current === "pt" ? `${m} de ${y}` : `${m} ${y}`;
}
/** "2026-11-08T04:33:47Z" -> "8 de novembro de 2026" / "8 November 2026". */
export function date(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);   // a plain day is that day where the reader is, not UTC midnight
  const d = m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(iso);
  return Number.isNaN(+d) ? "" : d.toLocaleDateString(tag(), { day: "numeric", month: "long", year: "numeric" });
}

// ------------------------------------------------------------ switch

/** A PT | EN segmented switch; buttons stay in sync with the current language. */
export function langSwitch() {
  const box = document.createElement("div");
  box.className = "lang";
  box.setAttribute("role", "group");
  box.setAttribute("aria-label", "Idioma / Language");
  const buttons = Object.entries(LANGS).map(([k, v]) => {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = v.label; b.lang = v.tag; b.title = v.name; b.dataset.lang = k;
    b.addEventListener("click", () => setLang(k));
    return b;
  });
  const sync = () => buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === current)));
  sync();
  window.addEventListener("langchange", sync);
  box.append(...buttons);
  return box;
}

// ------------------------------------------------------------ pages

/**
 * Static text: the HTML is written in Portuguese and carries the English beside it:
 *   <h1 data-en="Public contracts">Contratos públicos</h1>          text
 *   <p data-en-html="See <a href=…>…</a>">Veja <a href=…>…</a></p>    markup
 *   <input placeholder="Buscar…" data-en-placeholder="Search…">        also data-en-title, data-en-aria-label
 */
export function applyStatic(root = document) {
  if (current !== "en") return;
  for (const e of root.querySelectorAll("[data-en]")) e.textContent = e.dataset.en;
  for (const e of root.querySelectorAll("[data-en-html]")) e.innerHTML = e.dataset.enHtml;
  for (const a of ["placeholder", "title", "aria-label", "content"]) {
    const k = `en${a.split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join("")}`;
    for (const e of root.querySelectorAll(`[data-en-${a}]`)) e.setAttribute(a, e.dataset[k]);
  }
}
