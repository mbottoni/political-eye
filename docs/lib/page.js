// political-eye: the frame every explorer page shares with the hub: a top bar with every page and the
// language switch, the section's colour and breadcrumb, and the page's static text in the reader's language.
// Call setupPage() first thing in a page's script, before anything is drawn.
import { L, applyStatic, langSwitch } from "./i18n.js";

export const SECTIONS = [
  { key: "congresso", pt: "Congresso", en: "Congress", accent: "--s1", pages: [
    { key: "camara", pt: "Câmara dos Deputados", en: "Câmara dos Deputados" },
    { key: "senado", pt: "Senado Federal", en: "Senado Federal" },
    { key: "orientacoes", pt: "Orientação partidária", en: "Party orientations" },
    { key: "deputados", pt: "Deputados em todas as fontes", en: "Deputies across sources" },
    { key: "ranking", pt: "Ranking dos deputados", en: "Deputies ranked" }] },
  { key: "dinheiro", pt: "Dinheiro público", en: "Public money", accent: "--s3", pages: [
    { key: "tse", pt: "Financiamento de campanha", en: "Campaign finance" },
    { key: "emendas", pt: "Emendas parlamentares", en: "Parliamentary amendments" },
    { key: "pncp", pt: "Contratos públicos", en: "Public contracts" },
    { key: "siconfi", pt: "Finanças municipais", en: "Municipal finances" }] },
  { key: "controle", pt: "Controle e justiça", en: "Accountability and justice", accent: "--s8", pages: [
    { key: "sancoes", pt: "Sanções", en: "Sanctions" },
    { key: "alertas", pt: "Sinais de alerta", en: "Red flags" },
    { key: "empresas", pt: "Empresas em todas as fontes", en: "Companies across sources" }] },
];
const REPO = "https://github.com/mbottoni/political-eye";

const h = (tag, props = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) if (k in e) e[k] = v; else e.setAttribute(k, v);
  e.append(...kids.flat().filter((k) => k != null));
  return e;
};
const NS = "http://www.w3.org/2000/svg";
function logo() {
  const s = document.createElementNS(NS, "svg");
  s.setAttribute("viewBox", "0 0 32 32"); s.setAttribute("aria-hidden", "true");
  s.innerHTML = '<rect width="32" height="32" rx="8" fill="currentColor"/><path d="M5 16s4-7 11-7 11 7 11 7-4 7-11 7S5 16 5 16Z" fill="none" stroke="var(--page)" stroke-width="2"/><circle cx="16" cy="16" r="4" fill="var(--line)"/>';
  return s;
}

/** The page's key from its URL (…/docs/pncp/ -> "pncp"). */
export function currentPage() {
  const parts = location.pathname.split("/").filter(Boolean);
  const keys = SECTIONS.flatMap((s) => s.pages.map((p) => p.key));
  return [...parts].reverse().find((p) => keys.includes(p)) || null;
}

function topBar(here) {
  const menu = h("details", { className: "pages" },
    h("summary", {}, L("Painéis", "Pages")),
    h("div", { className: "menu" }, SECTIONS.map((s) => h("div", { className: "group", style: `--accent: var(${s.accent})` },
      h("a", { className: "sec", href: `../#${s.key}`, textContent: L(s.pt, s.en) }),
      s.pages.map((p) => h("a", { href: `../${p.key}/`, textContent: L(p.pt, p.en), ...(p.key === here ? { "aria-current": "page" } : {}) }))))));
  document.addEventListener("click", (e) => { if (!menu.contains(e.target)) menu.open = false; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") menu.open = false; });
  const brand = h("a", { className: "brand", href: "../", "aria-label": "political-eye" }, logo(), h("span", { className: "brand-name", textContent: "political-eye" }));
  return h("header", { className: "top" }, h("div", { className: "wrap" }, brand,
    h("nav", { className: "nav", "aria-label": L("Navegação", "Navigation") },
      h("a", { className: "nav-feature", href: "../ranking/", textContent: "Ranking", ...(here === "ranking" ? { "aria-current": "page" } : {}) }), menu,
      h("a", { className: "hide-sm", href: `${REPO}/blob/main/METHODOLOGY.md`, textContent: L("Metodologia", "Methodology") }),
      h("a", { className: "hide-sm", href: REPO, textContent: "GitHub" })),
    langSwitch()));
}

/** Frame the page: translate static text, add the top bar and breadcrumb, colour by section, reload on a language switch. */
export function setupPage() {
  applyStatic();
  const here = currentPage(), sec = SECTIONS.find((s) => s.pages.some((p) => p.key === here));
  document.body.classList.add("page");
  if (sec) document.body.style.setProperty("--accent", `var(${sec.accent})`);
  document.body.prepend(topBar(here));
  const crumb = document.querySelector("main header .crumb");
  if (crumb) crumb.replaceChildren(h("a", { href: "../", textContent: L("Início", "Home") }), h("span", { textContent: " / " }),
    sec ? h("a", { href: `../#${sec.key}`, textContent: L(sec.pt, sec.en) }) : null);
  window.addEventListener("langchange", () => location.reload());
}
