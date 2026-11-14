// political-eye: find a town by name or state, as a combobox with suggestions (the same widget as the deputy search
// in search.js). Used by the front page (it links to the profile) and by the town profile page (it opens in place).
import { data, el, fmt } from "./ui.js";
import { L } from "./i18n.js";

const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/['’`-]/g, " ").toLowerCase().replace(/\s+/g, " ").trim();

/** The town profile's address. */
export const townHref = (cod, base = "municipios/") => `${base}?town=${cod}`;

let all = null;
/** Every municipality: {cod, nome, uf, pop}, with a search key. */
export function towns() {
  if (!all) {
    all = data("site/municipios/index.csv").then((rows) => rows.map((r) => ({ cod: r.cod_ibge, nome: r.ente, uf: r.uf, pop: +r.populacao || 0,
      name: norm(r.ente), key: norm(`${r.ente} ${r.uf}`) })));
  }
  return all;
}

function rank(list, q) {
  const words = norm(q).split(" ").filter(Boolean);
  if (!words.length) return [];
  const whole = words.join(" ");
  // A name that starts with what was typed first, then a word that does, then the rest; bigger towns first.
  const score = (t) => (t.name === whole ? 0 : t.name.startsWith(whole) ? 1 : t.name.split(" ").some((w) => w.startsWith(words[0])) ? 2 : 3);
  return list.filter((t) => words.every((w) => t.key.includes(w)))
    .map((t) => [score(t), t]).sort((a, b) => a[0] - b[0] || b[1].pop - a[1].pop || a[1].nome.localeCompare(b[1].nome, "pt"))
    .slice(0, 8).map(([, t]) => t);
}

let uid = 0;
/**
 * townSearch({ onPick(t), href(t), large, placeholder, label }) -> element.
 * With href, picking a suggestion follows the link; with onPick, the page handles it.
 */
export function townSearch({ onPick, href, large = false, placeholder = L("Nome do município…", "Town name…"), label = L("Buscar município", "Find a town") } = {}) {
  const id = `ts${uid++}`;
  const input = el("input", { type: "search", placeholder, autocomplete: "off", spellcheck: false, role: "combobox", "aria-label": label,
    "aria-autocomplete": "list", "aria-expanded": "false", "aria-controls": `${id}-list` });
  const list = el("ul", { id: `${id}-list`, className: "options", role: "listbox", hidden: true });
  const box = el("div", { className: `dsearch${large ? " large" : ""}` }, el("span", { className: "icon", "aria-hidden": "true" }), input, list);
  let hits = [], active = -1;
  const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; input.removeAttribute("aria-activedescendant"); };
  const pick = (t) => {
    if (!t) return;
    close(); input.value = "";
    if (onPick) onPick(t); else if (href) location.href = href(t);
  };
  const badge = (t) => el("span", { className: "avatar", style: "width:34px;height:34px;font-size:12px", "aria-hidden": "true" }, t.uf);
  const paint = () => {
    list.replaceChildren(...(hits.length ? hits.map((t, i) => {
      const li = el("li", { id: `${id}-o${i}`, role: "option", className: "option", "aria-selected": String(i === active) }, badge(t),
        el("span", { className: "who" }, el("b", { textContent: t.nome }), el("span", { textContent: L(`${fmt(t.pop)} habitantes`, `${fmt(t.pop)} inhabitants`) })),
        el("span", { className: "leg", textContent: t.uf }));
      li.addEventListener("mousedown", (e) => { e.preventDefault(); pick(t); });
      li.addEventListener("mousemove", () => { if (active !== i) { active = i; paint(); } });
      return li;
    }) : [el("li", { className: "none", textContent: L("Nenhum município encontrado.", "No town found.") })]));
    list.hidden = false; input.setAttribute("aria-expanded", "true");
    if (active >= 0) input.setAttribute("aria-activedescendant", `${id}-o${active}`); else input.removeAttribute("aria-activedescendant");
  };
  const update = async () => {
    const q = input.value.trim();
    if (!q) { hits = []; close(); return; }
    const every = await towns();
    if (input.value.trim() !== q) return;   // typed on meanwhile
    hits = rank(every, q); active = hits.length ? 0 : -1; paint();
  };
  input.addEventListener("input", update);
  input.addEventListener("focus", () => { towns(); if (input.value.trim()) update(); });
  input.addEventListener("blur", () => setTimeout(close, 100));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!hits.length) return;
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + hits.length) % hits.length; paint();
    } else if (e.key === "Enter") { e.preventDefault(); pick(hits[Math.max(0, active)]); }
    else if (e.key === "Escape") close();
  });
  return box;
}
