// political-eye: find a deputy or a senator by name, party or state (both legislatures), as a combobox with suggestions.
// Used by the front page (it links to the profile) and by the deputies' and senators' pages (they open the profile in place).
import { data, el } from "./ui.js";
import { L } from "./i18n.js";

// The Câmara's party labels are cut at ten characters and some parties renamed; show today's short name.
const ALIASES = { SOLIDARIED: "SOLIDARIEDADE", SOLIDARI: "SOLIDARIEDADE", SD: "SOLIDARIEDADE", SDD: "SOLIDARIEDADE", REPUBLICAN: "REPUBLICANOS",
  REPUBLIC: "REPUBLICANOS", PODEMOS: "PODE", PATRI: "PATRIOTA", "PP**": "PP", PMDB: "MDB", PR: "PL", PPS: "CIDADANIA", PTN: "PODE",
  PEN: "PATRIOTA", PTDOB: "AVANTE", PSDC: "DC", PRB: "REPUBLICANOS" };
export const partyKey = (label) => { const k = String(label || "").trim().toUpperCase(); return ALIASES[k] || k; };
const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** The Câmara's official photo of a deputy. */
export const photo = (id) => `https://www.camara.leg.br/internet/deputado/bandep/${id}.jpg`;
/** The Senado's official photo of a senator (UrlFotoParlamentar in its open data). */
export const senatorPhoto = (id) => `https://www.senado.leg.br/senadores/img/fotos-oficiais/senador${id}.jpg`;

/** A round portrait (the Câmara's photo unless another src is given), falling back to initials when there is none. */
export function avatar(id, name, size = 32, src = photo(id)) {
  const initials = String(name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  const box = el("span", { className: "avatar", style: `width:${size}px;height:${size}px;font-size:${Math.round(size * 0.38)}px`, "aria-hidden": "true" }, initials);
  const img = el("img", { src, alt: "", loading: "lazy", decoding: "async" });
  img.addEventListener("load", () => box.append(img));
  return box;
}

// The two chambers: where each one's profiles live, its id column and its photos.
const HOUSES = {
  camara: { page: "deputados", file: "deputados", id: "deputado_id", param: "dep", photo, tag: "Câmara" },
  senado: { page: "senadores", file: "senadores", id: "senador_id", param: "sen", photo: senatorPhoto, tag: "Senado" },
};

/** A person's profile, from the site's root ("") or from a page ("../"). */
export const profileHref = (d, base = "") => { const h = HOUSES[d.casa]; return `${base}${h.page}/?tab=profile&leg=${d.leg}&${h.param}=${d.id}`; };

let people = null;
/** Every deputy and every senator of the 57th and 56th legislatures, once each per chamber, newest legislature first. */
export function members() {
  if (!people) {
    const files = Object.entries(HOUSES).flatMap(([casa, h]) => [57, 56].map((leg) => [casa, h, leg]));
    people = Promise.all(files.map(([casa, h, leg]) => data(`site/${h.file}/${h.file}_${leg}.csv`).then((rows) => rows.map((r) => ({ ...r, casa, h, leg })), () => [])))
      .then((sets) => {
        const byId = new Map();
        for (const r of sets.flat()) {
          const id = r[r.h.id], k = `${r.casa}:${id}`, have = byId.get(k);
          if (have) { have.legs.push(r.leg); continue; }
          byId.set(k, { id, casa: r.casa, nome: r.nome, party: partyKey(r.partido), uf: r.uf, leg: r.leg, legs: [r.leg], photo: r.h.photo(id),
            votes: +r.n_votes || 0, key: norm(`${r.nome} ${partyKey(r.partido)} ${r.uf} ${r.h.tag}`), name: norm(r.nome) });
        }
        return [...byId.values()];
      });
  }
  return people;
}
/** Deputies only (the front page's suggestions come from both chambers through members()). */
export const deputies = () => members().then((all) => all.filter((d) => d.casa === "camara"));

function rank(all, q) {
  const words = norm(q).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const score = (d) => (d.name.startsWith(words.join(" ")) ? 0 : d.name.split(" ").some((w) => w.startsWith(words[0])) ? 1 : 2);
  // Within a score: newest legislature, then the 81 senators before the 513 deputies, then the most active
  // (a senator casts far fewer votes than a deputy, so votes only order people of one chamber).
  return all.filter((d) => words.every((w) => d.key.includes(w)))
    .map((d) => [score(d), d]).sort((a, b) => a[0] - b[0] || b[1].leg - a[1].leg || b[1].casa.localeCompare(a[1].casa) || b[1].votes - a[1].votes || a[1].nome.localeCompare(b[1].nome, "pt"))
    .slice(0, 8).map(([, d]) => d);
}

let uid = 0;
/**
 * deputySearch({ onPick(d), href(d), large, placeholder, label }) -> element.
 * With href, picking a suggestion follows the link; with onPick, the page handles it.
 */
export function deputySearch({ onPick, href, large = false, placeholder = L("Nome, partido ou estado…", "Name, party or state…"), label = L("Buscar deputado ou senador", "Find a deputy or senator") } = {}) {
  const id = `ds${uid++}`;
  const input = el("input", { type: "search", placeholder, autocomplete: "off", spellcheck: false, role: "combobox", "aria-label": label,
    "aria-autocomplete": "list", "aria-expanded": "false", "aria-controls": `${id}-list` });
  const list = el("ul", { id: `${id}-list`, className: "options", role: "listbox", hidden: true });
  const box = el("div", { className: `dsearch${large ? " large" : ""}` },
    el("span", { className: "icon", "aria-hidden": "true" }), input, list);
  let hits = [], active = -1;
  const legTag = (d) => d.legs.sort((a, b) => b - a).map((l) => `${l}ª`).join(" · ");
  const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; input.removeAttribute("aria-activedescendant"); };
  const pick = (d) => {
    if (!d) return;
    close(); input.value = "";
    if (onPick) onPick(d); else if (href) location.href = href(d);
  };
  const paint = () => {
    list.replaceChildren(...(hits.length ? hits.map((d, i) => {
      const li = el("li", { id: `${id}-o${i}`, role: "option", className: "option", "aria-selected": String(i === active) },
        avatar(d.id, d.nome, 34, d.photo),
        el("span", { className: "who" }, el("b", { textContent: d.nome }), el("span", { textContent: `${d.party} · ${d.uf} · ${HOUSES[d.casa].tag}` })),
        el("span", { className: "leg", textContent: legTag(d) }));
      li.addEventListener("mousedown", (e) => { e.preventDefault(); pick(d); });
      li.addEventListener("mousemove", () => { if (active !== i) { active = i; paint(); } });
      return li;
    }) : [el("li", { className: "none", textContent: L("Nenhum deputado ou senador encontrado.", "No deputy or senator found.") })]));
    list.hidden = false; input.setAttribute("aria-expanded", "true");
    if (active >= 0) input.setAttribute("aria-activedescendant", `${id}-o${active}`); else input.removeAttribute("aria-activedescendant");
  };
  const update = async () => {
    const q = input.value.trim();
    if (!q) { hits = []; close(); return; }
    const all = await members();
    if (input.value.trim() !== q) return;   // typed on meanwhile
    hits = rank(all, q); active = hits.length ? 0 : -1; paint();
  };
  input.addEventListener("input", update);
  input.addEventListener("focus", () => { members(); if (input.value.trim()) update(); });
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
