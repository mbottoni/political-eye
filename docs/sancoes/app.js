// Sanctions: who is barred or punished, by whom, for how long, and what public money still reaches them.
import { $, asset, brl, css, data, el, fmt, guard, hideTip, onResize, params, pct, plural, setParam, showTip, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";

// ------------------------------------------------------------ helpers

const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const finding = (text) => el("p", { className: "finding", textContent: text });
const grid = (...kids) => el("div", { className: "grid2" }, ...kids.map((k) => { k.classList.remove("wide"); return k; }));
const select = (label, options, value, onChange) => {
  const s = el("select", {}, ...options.map((o) => el("option", { value: o.value ?? o, textContent: o.label ?? o, selected: String(o.value ?? o) === String(value) })));
  s.addEventListener("change", () => onChange(s.value));
  return el("label", {}, label, s);
};
const n = (v) => (v === "" || v == null ? 0 : +v);
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const cnpjFmt = (c) => (/^\d{14}$/.test(c) ? `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}` : c);
const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
const years = (v) => (v == null ? "–" : `${fmt(v, v < 10 ? 1 : 0)} ${v === 1 ? "year" : "years"}`);
const days = (v) => (v == null ? "–" : `${fmt(v)} days`);
const perMillion = (share) => (share == null ? "–" : `R$ ${fmt(share * 1e6)}`);
const SMALL = new Set(["DA", "DE", "DO", "DAS", "DOS", "E"]);
const title = (s) => String(s || "").toLowerCase().split(" ").map((w, i) => (i && SMALL.has(w.toUpperCase()) ? w : w.charAt(0).toUpperCase() + w.slice(1))).join(" ");
const day = (v) => el("span", { className: "nowrap", textContent: v ?? "" });
const short = (s, k = 34) => { s = String(s || ""); k = /[a-z]/.test(s) ? k : Math.round(k * 0.84); return s.length > k ? `${s.slice(0, k - 1)}…` : s; };
// Sanctioning bodies' long names, shortened the way they are usually written.
const abbr = (s) => String(s || "").replace(/^Controladoria[- ]Geral da Uni[ãa]o.*/i, "CGU").replace(/Controladoria[- ]Geral do Estado d[aeo]s? /i, "CGE ")
  .replace(/Controladoria[- ]Geral do Munic[íi]pio d[aeo]s? /i, "CGM ").replace(/Secretaria de Estado d[aeo]s? /i, "Sec. Est. ").replace(/ - Unidades com v[íi]nculo direto/i, "");
const redraws = [];
const later = (f) => { redraws.push(f); f(); };

const CAT = {
  "Impedimento/proibição de contratar com prazo determinado": "Contracting ban, fixed term",
  "Impedimento/proibição de contratar sem prazo determinado": "Contracting ban, no end date",
  "Suspensão": "Suspended from tenders",
  "Declaração de Inidoneidade sem prazo determinado": "Declared unfit, no end date",
  "Declaração de Inidoneidade com prazo determinado": "Declared unfit, fixed term",
  "Demissão": "Dismissed (civil servant)",
  "Suspensão/Interdição das atividades sem prazo determinado": "Activity halt, no end date",
  "Suspensão/Interdição das atividades com prazo determinado": "Activity halt, fixed term",
  "Multa": "Fine",
  "Advertência": "Warning",
  "Publicação extraordinária da decisão condenatória": "Ruling published at its cost",
  "Proibição de receber incentivos, subsídios, subvenções, doações ou empréstimos": "No subsidies or public loans",
  "Dissolução compulsória da PJ": "Compulsory dissolution",
  "Perdimento de bens": "Assets forfeited",
};
const cat = (c) => CAT[c] || c;
const SPH = { FEDERAL: "Federal", ESTADUAL: "State", MUNICIPAL: "Municipal", "": "Not stated", outra: "Not stated" };
const SPH_COLOR = () => ({ FEDERAL: C.slot(1), ESTADUAL: C.slot(2), MUNICIPAL: C.slot(3), "": css("--other"), outra: css("--other") });
const SCOPE = {
  "Todas as Esferas em todos os Poderes": "Every sphere and power",
  "Em todos os Poderes da Esfera do órgão sancionador": "The sanctioner's whole sphere",
  "Na Esfera e no Poder do órgão sancionador": "The sanctioner's sphere and power",
  "No órgão sancionador": "Only the sanctioning body",
  "Sem Informação": "Not stated",
  "Em outro órgão": "Another body",
};
const COBRE = { sim: "Reaches the buyer", possivel: "May reach the buyer", nao: "Does not reach the buyer" };
const FED = { sim: "Binds federal bodies", possivel: "May bind the paying body", nao: "Binds another sphere only" };
const scopeColor = (k) => ({ sim: css("--critical"), possivel: css("--warning"), nao: css("--other") })[k] || css("--other");
const KIND = { deputado: "Deputy", senador: "Senator", bancada: "State bench", comissao: "Committee", relator: "Rapporteur-general", outro: "Not matched" };
const EFFECT = [
  ["Adoção, aplicação", "Integrity programme adopted or improved"], ["Outros", "Other"],
  ["Isenção da publicação", "Spared publishing the ruling"], ["Isenção da proibição de receber", "Spared the ban on subsidies"],
  ["Isenção da declaração de inidoneidade", "Spared being declared unfit"], ["Isenção da suspensão", "Spared suspension"],
  ["Atenuação da multa", "Fine reduced"], ["Remissão da multa", "Fine waived"], ["Atenuação da suspensão", "Suspension shortened"],
  ["Isenção do impedimento", "Spared the pregão ban"], ["Isenção da advertência", "Spared a warning"], ["Isenção da multa de mora", "Spared a late-payment fine"],
];
const effect = (e) => (EFFECT.find(([k]) => e.startsWith(k)) || [null, e])[1];
const STATUS = { "Em Execução": "In progress", "Cumprido": "Fulfilled" };

const R = () => data("site/sancoes/resumo.json");
const E = () => data("site/sancoes/empresas.csv");

let showTab = () => {}, companyView = null;
function openCompany(cnpj) {
  setParam("cnpj", cnpj);
  showTab("company");
  if (companyView) companyView(cnpj);
  window.scrollTo({ top: $("nav.tabs").offsetTop - 8, behavior: "smooth" });
}
const companyLink = (name, cnpj) => el("button", { className: "linkish", type: "button", textContent: name || cnpjFmt(cnpj), title: cnpjFmt(cnpj), on: { click: () => openCompany(cnpj) } });
const companyCol = (key = "nome", label = "Company") => ({ key, label, text: true, wrap: true, fmt: (v, r) => companyLink(v, r.cnpj) });

// ------------------------------------------------------------ overview

async function overview(root) {
  const r = await R(), t = r.tiles;
  const withEnd = t.ceis + t.cnep - t.sem_prazo;
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Sanctions listed", value: fmt(t.ceis + t.cnep), sub: `CEIS ${fmt(t.ceis)} · CNEP ${fmt(t.cnep)}, as of ${r.snapshot}` },
    { label: "Companies and organisations", value: fmt(t.empresas), sub: `plus ${fmt(t.cepim_entidades)} non-profits on CEPIM` },
    { label: "People", value: fmt(t.pessoas_distintas), sub: `${fmt(t.pessoas)} sanctions; counted, never named here` },
    { label: "Past their end date, still listed", value: fmt(t.vencidas), sub: `${pct(t.vencidas / withEnd, 1)} of those with an end date` },
  ]);

  const c1 = chart(), c2 = chart();
  root.append(grid(
    card("What kind of sanction", "Every CEIS and CNEP entry by its category. Blue: categories that bar the company or person from public contracts; grey: fines, warnings and the rest.", c1),
    card("Who imposed them, on whom", "Entries by the sphere of the body that imposed them, split into companies and people. Most sanctions on people are improbidade convictions sent by the courts (CNJ).", c2)));
  const cats = new Map();
  for (const x of r.categories) {
    const k = x.categoria, prev = cats.get(k) || { label: cat(k), value: 0, people: 0, barra: x.barra, pt: k };
    prev.value += n(x.empresa) + n(x.pessoa) + n(x.outro); prev.people += n(x.pessoa); cats.set(k, prev);
  }
  const catRows = [...cats.values()].sort((a, b) => b.value - a.value);
  later(() => C.bars(c1, {
    rows: catRows.map((x) => ({ ...x, color: x.barra ? C.slot(1) : css("--other"), title: `${x.label} (${x.pt})`, note: `${pct(x.people / x.value)} people` })),
    labelWidth: 240, legend: [{ label: "Bars public contracts", color: C.slot(1) }, { label: "Does not", color: css("--other") }],
    table: { rows: catRows, cols: [{ key: "label", label: "Category", text: true }, { key: "pt", label: "Published as", text: true }, { key: "value", label: "Entries" }, { key: "people", label: "On people" }], name: "categories" },
  }));
  const sk = r.sphere_kind.filter((x) => x.esfera in SPH && x.esfera !== "");
  later(() => C.stack(c2, {
    x: sk.map((x) => SPH[x.esfera]), height: 220,
    series: [{ name: "Companies and organisations", color: C.slot(1), values: sk.map((x) => n(x.empresa)) }, { name: "People", color: C.slot(4), values: sk.map((x) => n(x.pessoa)) }],
    table: { rows: sk.map((x) => ({ esfera: SPH[x.esfera], empresa: n(x.empresa), pessoa: n(x.pessoa) })), cols: [{ key: "esfera", label: "Sphere", text: true }, { key: "empresa", label: "Companies" }, { key: "pessoa", label: "People" }], name: "spheres" },
  }));

  const c3 = chart();
  root.append(card("When the listed sanctions began", "Start year of every sanction still on CEIS or CNEP, by the sanctioning body's sphere. The lists keep only what is still in force (and some that are past their date), so the recent surge is partly sanctions that have not expired yet. Before 2012 is grouped.", c3));
  const sy = r.start_year.filter((x) => x.ano);
  const early = sy.filter((x) => +x.ano < 2012), late = sy.filter((x) => +x.ano >= 2012);
  const yrs = ["before 2012", ...late.map((x) => x.ano)];
  const val = (rows, k) => sum(rows.map((x) => n(x[k])));
  later(() => C.stack(c3, {
    x: yrs, height: 240,
    series: ["FEDERAL", "ESTADUAL", "MUNICIPAL", "outra"].map((k) => ({ name: SPH[k], color: SPH_COLOR()[k], values: [val(early, k), ...late.map((x) => n(x[k]))] })),
    table: { rows: sy, cols: [{ key: "ano", label: "Year", text: true }, { key: "FEDERAL", label: "Federal" }, { key: "ESTADUAL", label: "State" }, { key: "MUNICIPAL", label: "Municipal" }, { key: "outra", label: "Not stated" }], name: "start-year" },
  }));
  const last = late[late.length - 1], prev = late[late.length - 2];
  if (last && prev) c3.after(finding(`${fmt(sum(["FEDERAL", "ESTADUAL", "MUNICIPAL", "outra"].map((k) => n(last[k]))))} of the listed sanctions started in ${last.ano} (to ${r.snapshot}), against ${fmt(sum(["FEDERAL", "ESTADUAL", "MUNICIPAL", "outra"].map((k) => n(prev[k]))))} in ${prev.ano}.`));

  const map = chart(), rank = chart();
  root.append(grid(
    card("Where: state and municipal sanctions per million inhabitants", "By the state of the sanctioning body; federal sanctions, which have no state of their own, are left out. A stronger colour: more sanctions for the population.", map),
    card("States ranked", "The same rate; the count of state and municipal sanctions in the tooltip.", rank)));
  const shapes = await asset("maps/ufs.json");
  const byIbge = new Map(r.by_uf.map((x) => [String(x.ibge), x]));
  const max = Math.max(...r.by_uf.map((x) => x.por_milhao || 0));
  later(() => {
    C.choropleth(map, {
      shapes: shapes.shapes, viewBox: shapes.viewBox, stroke: 0.6, maxWidth: 520,
      value: (code) => byIbge.get(code)?.por_milhao ?? null, color: (v) => C.seq(Math.sqrt(v / max)),
      tip: (code, v) => { const x = byIbge.get(code); return x ? [el("strong", { textContent: x.uf }), el("div", { className: "row", textContent: `${fmt(v, 1)} per million · ${fmt(x.total)} sanctions (${fmt(x.estadual)} state, ${fmt(x.municipal)} municipal)` }), el("div", { className: "row", textContent: `${fmt(x.empresas_vigentes)} companies under a sanction in force` })] : [el("strong", { textContent: code })]; },
    });
    C.colorKey(map, { color: (t) => C.seq(Math.sqrt(t)), from: "0", to: `${fmt(max)} per million`, label: "" });
  });
  const ranked = [...r.by_uf].sort((a, b) => b.por_milhao - a.por_milhao);
  later(() => C.bars(rank, {
    rows: ranked.map((x) => ({ label: x.uf, value: x.por_milhao, note: `${fmt(x.total)} sanctions`, color: css("--line") })), barHeight: 12, format: (v) => fmt(v, 0),
    table: { rows: ranked, cols: [{ key: "uf", label: "State", text: true }, { key: "estadual", label: "State bodies" }, { key: "municipal", label: "Municipal bodies" }, { key: "populacao", label: "Population" }, { key: "por_milhao", label: "Per million", fmt: (v) => fmt(v, 1) }], name: "by-state" },
  }));
}

// ------------------------------------------------------------ who

async function who(root) {
  const r = await R();
  let lista = params.get("lista") || "", esfera = params.get("esfera") || "";
  const controls = el("div", { className: "controls" }), c1 = chart();
  root.append(controls, card("The bodies that sanction most", "Sanctions listed per sanctioning body, the 25 with the most under the filters above. Bodies are named as each one reports itself, so one body can appear under two spellings.", c1));
  const draw = () => {
    controls.replaceChildren(
      select("List", [{ value: "", label: "CEIS and CNEP" }, "CEIS", "CNEP"], lista, (v) => { lista = v; setParam("lista", v, ""); draw(); }),
      select("Sphere", [{ value: "", label: "Every sphere" }, ...["FEDERAL", "ESTADUAL", "MUNICIPAL"].map((v) => ({ value: v, label: SPH[v] }))], esfera, (v) => { esfera = v; setParam("esfera", v, ""); draw(); }));
    const agg = new Map();
    for (const b of r.bodies) {
      if ((lista && b.lista !== lista) || (esfera && b.esfera !== esfera)) continue;
      const k = `${b.orgao}|${b.esfera}|${b.uf}`, x = agg.get(k) || { label: b.orgao, esfera: b.esfera, uf: b.uf, value: 0, empresas: 0, vigentes: 0 };
      x.value += b.n; x.empresas += b.empresas; x.vigentes += b.vigentes; agg.set(k, x);
    }
    const rows = [...agg.values()].sort((a, b) => b.value - a.value).slice(0, 25);
    C.bars(c1, {
      rows: rows.map((x) => ({ ...x, label: short(abbr(x.label), 46), title: x.label, color: SPH_COLOR()[x.esfera] || css("--other"), note: `${SPH[x.esfera] || ""}${x.uf ? `, ${x.uf}` : ""} · ${pct(x.empresas / x.value)} companies` })), labelWidth: 300,
      legend: ["FEDERAL", "ESTADUAL", "MUNICIPAL"].map((k) => ({ label: SPH[k], color: SPH_COLOR()[k] })),
      table: { rows, cols: [{ key: "label", label: "Body", text: true, wrap: true }, { key: "esfera", label: "Sphere", text: true }, { key: "uf", label: "UF", text: true }, { key: "value", label: "Sanctions" }, { key: "empresas", label: "On companies" }, { key: "vigentes", label: "In force" }], name: "bodies" },
    });
  };
  later(draw);

  const c2 = chart(), c3 = chart();
  root.append(grid(
    card("Under which law", "The law each sanction cites. The improbidade law covers the court convictions sent by CNJ; the two procurement laws cover companies that failed a contract or a tender.", c2),
    card("Where the sanction applies", "The scope each sanctioning body recorded. A sanction limited to its own body or sphere does not stop the company from contracting elsewhere.", c3)));
  later(() => C.bars(c2, {
    rows: r.laws.map((x) => ({ label: x.label, value: x.n, note: `${pct(x.empresas / x.n)} on companies`, color: css("--line") })), labelWidth: 260,
    table: { rows: r.laws, cols: [{ key: "label", label: "Law", text: true }, { key: "lei", label: "Cited as", text: true }, { key: "n", label: "Sanctions" }, { key: "empresas", label: "On companies" }], name: "laws" },
  }));
  const sc = new Map();
  for (const x of r.scope) sc.set(x.abrangencia, (sc.get(x.abrangencia) || 0) + x.n);
  const scRows = [...sc].map(([k, v]) => ({ label: SCOPE[k] || k || "Not stated", value: v, pt: k })).sort((a, b) => b.value - a.value);
  later(() => C.bars(c3, {
    rows: scRows.map((x) => ({ ...x, color: css("--line"), title: `${x.label} (${x.pt})` })), labelWidth: 230,
    table: { rows: scRows, cols: [{ key: "label", label: "Scope", text: true }, { key: "pt", label: "Published as", text: true }, { key: "value", label: "Sanctions" }], name: "scope" },
  }));
  const tb = el("div"), c4 = chart();
  root.append(grid(
    card("The articles cited most", "The law and article each sanction cites, as published.", tb),
    card("Where the entries come from", "The body that sent each entry to CGU. CNJ relays court convictions for improbidade; the Ministry of Finance relays the sanctions of federal bodies.", c4)));
  table(tb, r.articles, [{ key: "artigo", label: "Law and article", text: true }, { key: "n", label: "Sanctions" }], { sortBy: "n", pageSize: 10, name: "articles" });
  later(() => C.bars(c4, { rows: r.origin.map((x) => ({ label: short(x.origem, 40), title: x.origem, value: x.n, color: css("--line") })), labelWidth: 260 }));
}

// ------------------------------------------------------------ duration and delays

function expand(hist, edges, lo, hi) {
  const out = [];
  hist.forEach((c, i) => { const a = Math.max(lo, edges[i]), b = Math.min(hi, edges[i + 1]); const mid = a < b ? (a + b) / 2 : hi; for (let k = 0; k < c; k++) out.push(mid); });
  return out;
}

async function time(root) {
  const r = await R(), t = r.tiles;
  const barred = r.duration.groups.find((g) => g.grupo === "Barred from contracting"), lagFed = r.lag.spheres.find((s) => s.esfera === "FEDERAL");
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Typical contracting ban", value: years(barred?.p50), sub: "median, among bans with an end date" },
    { label: "Sanctions with no end date", value: fmt(t.sem_prazo), sub: `${pct(t.sem_prazo / (t.ceis + t.cnep), 1)} of the listed` },
    { label: "Reaching the list, federal", value: days(lagFed?.p50), sub: "median days from the sanction's start to its record" },
    { label: "Ending within 90 days", value: fmt(t.expirando), sub: `company sanctions, after ${r.snapshot}; plus ${fmt(t.expirando_pessoas)} on people` },
  ]);
  let g = params.get("g") || "Barred from contracting", sph = params.get("s") || "FEDERAL";
  const ctl1 = el("div", { className: "controls" }), c1 = chart(), f1 = el("div");
  root.append(card("How long sanctions last", "From each sanction's start to its end date, for sanctions that have one. Dashed: the median and the 90th percentile. The last bar holds everything of ten years or more.", ctl1, c1, f1));
  const drawDur = () => {
    const groups = r.duration.groups.filter((x) => x.n > 20);
    ctl1.replaceChildren(select("Kind of sanction", groups.map((x) => x.grupo), g, (v) => { g = v; setParam("g", v, "Barred from contracting"); drawDur(); }));
    const x = groups.find((y) => y.grupo === g) || groups[0];
    C.histogram(c1, { values: expand(x.hist, r.duration.edges, 0, 10), domain: [0, 10], bins: 40, format: (v) => fmt(v, Number.isInteger(v) ? 0 : 1), xLabel: "years (the last bar: ten or more)", unit: "sanctions", height: 220,
      refs: [{ x: x.p50, label: `median ${years(x.p50)}` }, ...(x.p90 < 9.5 ? [{ x: x.p90, label: `90th percentile ${years(x.p90)}` }] : [])] });
    f1.replaceChildren(finding(`${fmt(x.n)} ${x.grupo.toLowerCase()} sanctions have an end date: a quarter last ${years(x.p25)} or less, a quarter more than ${years(x.p75)}. Another ${fmt(x.sem_prazo)} have none.`));
  };
  later(drawDur);
  const ctl2 = el("div", { className: "controls" }), c2 = chart(), f2 = el("div");
  root.append(card("How long a sanction takes to reach the list", "Days from the sanction's start to the date its record was created at CGU. Below zero: recorded before it began. The last bar holds every delay of two years or more.", ctl2, c2, f2));
  const drawLag = () => {
    ctl2.replaceChildren(select("Sanctioning sphere", ["FEDERAL", "ESTADUAL", "MUNICIPAL"].map((v) => ({ value: v, label: SPH[v] })), sph, (v) => { sph = v; setParam("s", v, "FEDERAL"); drawLag(); }));
    const x = r.lag.spheres.find((y) => y.esfera === sph);
    C.histogram(c2, { values: expand(x.hist, r.lag.edges, -60, 750), domain: [-60, 750], bins: 27, format: (v) => fmt(v, 0), xLabel: "days", unit: "sanctions", height: 220, refs: [{ x: x.p50, label: `median ${days(x.p50)}` }] });
    f2.replaceChildren(finding(`${SPH[sph]} sanctions: half reach the list within ${days(x.p50)}, three quarters within ${days(x.p75)}; one in ten takes more than ${days(x.p90)}. Until then, a buyer checking CEIS does not see them.`));
  };
  later(drawLag);
  const tb = el("div");
  root.append(card("Company sanctions ending in the next 90 days", `Their end date falls between ${r.snapshot} and 90 days later; once it passes, the company may contract again.`, tb));
  const soon = await data("site/sancoes/expirando.csv");
  table(tb, soon, [{ key: "fim", label: "Ends", text: true, fmt: day }, companyCol(), { key: "lista", label: "List", text: true },
    { key: "categoria", label: "Sanction", text: true, fmt: (v) => cat(v) }, { key: "orgao", label: "Imposed by", text: true, wrap: true }, { key: "uf", label: "UF", text: true }],
  { sortBy: "fim", desc: false, pageSize: 12, name: "ending-soon" });
}

// ------------------------------------------------------------ repeat offenders

async function repeat(root) {
  const r = await R(), rows = (await E()).filter((x) => n(x.ceis) + n(x.cnep) > 0).map((x) => ({ ...x, n: n(x.ceis) + n(x.cnep) }));
  const multi = rows.filter((x) => x.n >= 2), many = rows.filter((x) => x.n >= 5);
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Companies with two or more sanctions", value: fmt(multi.length), sub: `${pct(multi.length / rows.length)} of sanctioned companies` },
    { label: "Their share of all sanctions", value: pct(sum(multi.map((x) => x.n)) / sum(rows.map((x) => x.n))), sub: "of every company sanction listed" },
    { label: "Five or more", value: fmt(many.length), sub: `with ${fmt(sum(many.map((x) => x.n)))} sanctions between them` },
    { label: "Sanctioned in several states", value: fmt(rows.filter((x) => n(x.ufs) >= 2).length), sub: "by bodies of two or more states" },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(
    card("Sanctions per company", "Companies by how many CEIS and CNEP entries name them.", c1),
    card("Sanctioned by many bodies", "The companies sanctioned by the most different bodies. Each body acts alone, so one company can be barred by dozens of buyers it failed.", c2)));
  const dist = r.repeat.map((x) => ({ label: x.n >= 10 ? "10 or more" : `${x.n} sanction${x.n > 1 ? "s" : ""}`, value: x.empresas, color: css("--line") }));
  later(() => C.bars(c1, { rows: dist, labelWidth: 110 }));
  const top = [...rows].sort((a, b) => n(b.orgaos) - n(a.orgaos) || b.n - a.n).slice(0, 15);
  later(() => C.bars(c2, { rows: top.map((x) => ({ label: short(x.nome || cnpjFmt(x.cnpj), 36), title: x.nome, value: n(x.orgaos), note: `${x.n} sanctions in ${x.ufs} states`, color: C.slot(8), cnpj: x.cnpj })), labelWidth: 260, onClick: (x) => openCompany(x.cnpj) }));
  const tb = el("div");
  root.append(card("Every company with two or more sanctions", "Click a name for the company's profile: its sanctions over time, and the contracts, amendments and campaign sales it had.", tb));
  table(tb, multi, [companyCol(), { key: "cnpj", label: "CNPJ", text: true, fmt: (v) => day(cnpjFmt(v)) }, { key: "n", label: "Sanctions" }, { key: "vigentes", label: "In force" },
    { key: "orgaos", label: "Bodies" }, { key: "ufs", label: "States" }, { key: "primeira", label: "First", text: true, fmt: day }, { key: "ultima", label: "Latest", text: true, fmt: day },
    { key: "emendas_sancionada", label: "Amendments while barred", fmt: (v) => (n(v) ? brl(v) : "") }], { sortBy: "n", pageSize: 15, name: "repeat-offenders" });
}

// ------------------------------------------------------------ fines

async function fines(root) {
  const r = await R(), f = r.fines, t = r.tiles;
  const rows = await data("site/sancoes/multas.csv");
  const top = rows[0];
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Fines listed", value: fmt(t.multas_n), sub: "CNEP, under the Anti-Corruption Law" },
    { label: "Their total", value: brl(t.multas_total), sub: "as recorded, not as collected" },
    { label: "Typical fine", value: brl(f.p50), sub: `median; a quarter above ${brl(f.p75)}` },
    { label: "Largest", value: brl(top ? +top.multa : null), sub: top ? top.nome : "" },
  ]);
  const c1 = chart();
  root.append(card("How large the fines are", "Every CNEP fine above zero on a logarithmic scale: each step is ten times the last. Dashed: the median.", c1));
  later(() => C.histogram(c1, { values: expand(f.log_hist, f.log_edges, 2, 10), domain: [2, 10], bins: 16, format: (v) => brl(10 ** v, 0), xLabel: "fine (R$, log scale)", unit: "fines", height: 220, refs: [{ x: Math.log10(f.p50), label: `median ${brl(f.p50)}` }] }));
  const c2 = chart(), c3 = chart();
  root.append(grid(card("Fines by the year the sanction began", "Total value of the fines still listed.", c2), card("Who fines", "The 15 bodies with the largest total, and how many fines each imposed.", c3)));
  const by = f.by_year.filter((x) => x.ano);
  later(() => C.stack(c2, { x: by.map((x) => x.ano), height: 220, format: (v) => brl(v, 0), series: [{ name: "Total fines", color: css("--line"), values: by.map((x) => x.total) }],
    table: { rows: by, cols: [{ key: "ano", label: "Year", text: true }, { key: "n", label: "Fines" }, { key: "total", label: "Total", fmt: (v) => brl(v) }], name: "fines-by-year" } }));
  later(() => C.bars(c3, { rows: f.by_body.map((x) => ({ label: short(abbr(x.orgao), 36), title: x.orgao, value: x.total, note: `${fmt(x.n)} fines`, color: css("--line") })), labelWidth: 260, format: (v) => brl(v, 0) }));
  const tb = el("div");
  root.append(card("Every fine on a company", "Largest first.", tb));
  table(tb, rows, [companyCol(), { key: "multa", label: "Fine", fmt: (v) => brl(v) }, { key: "inicio", label: "From", text: true, fmt: day }, { key: "orgao", label: "Imposed by", text: true, wrap: true }, { key: "uf", label: "UF", text: true }],
    { sortBy: "multa", pageSize: 12, name: "fines" });
}

// ------------------------------------------------------------ public money

async function money(root) {
  const r = await R(), m = r.money, A = r.authors;
  const pncp = Object.fromEntries(m.pncp.by_cobre.map((x) => [x.cobre, x]));
  const tseN = sum(m.tse.map((x) => x.sancionados)), tseV = sum(m.tse.map((x) => x.sancionados_total));
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Amendments paid to barred companies", value: brl(m.emendas.barrado), sub: `${fmt(m.emendas.empresas_barrado)} companies; ${brl(m.emendas.barrado_sim)} under a sanction binding federal bodies` },
    { label: "Contracts signed while barred", value: fmt(sum(m.pncp.by_cobre.map((x) => x.contratos))), sub: `${fmt(pncp.sim?.contratos || 0)} where the sanction reaches the buyer; ${plural(m.pncp.days_read, "day")} of PNCP read so far` },
    { label: "Campaign suppliers listed on election day", value: fmt(tseN), sub: `${brl(tseV)} of campaign spending, 2018–2026` },
    { label: "Amendments to non-profits now on CEPIM", value: brl(m.cepim.total), sub: `${fmt(m.cepim.entidades)} organisations, paid before or after they were barred` },
  ]);

  const c1 = chart();
  root.append(card("Amendment money paid to companies while they were barred", "Payments of parliamentary amendments, by month, to a company that was then under a CEIS or CNEP sanction barring it from contracting. A company paid directly by an amendment is paid by a federal body. Red: the sanction bound every federal body. Amber: it bound only its own federal body, which may be the payer. Grey: a state or municipal sanction, which does not bind the Union.", c1));
  const ey = m.emendas.by_year;
  later(() => C.stack(c1, { x: ey.map((x) => x.ano), height: 240, format: (v) => brl(v, 0),
    series: ["sim", "possivel", "nao"].map((k) => ({ name: FED[k], color: scopeColor(k), values: ey.map((x) => x[k]) })),
    table: { rows: ey, cols: [{ key: "ano", label: "Year", text: true }, ...["sim", "possivel", "nao"].map((k) => ({ key: k, label: FED[k], fmt: (v) => brl(v) }))], name: "amendments-while-barred" } }));
  c1.after(finding(`Of the ${brl(m.emendas.total)} in amendments paid since ${m.emendas.first} to companies and organisations on these lists, ${brl(m.emendas.barrado)} (${pct(m.emendas.barrado / m.emendas.total, 1)}) was paid while a barring sanction was in force. Across all paid amendments, deputies' and senators' individual amendments paid barred companies ${perMillion(A.individual_per_million / 1e6)} for every R$ 1 million they paid (${perMillion(A.individual_sim_per_million / 1e6)} under a sanction binding federal bodies).`));

  // party level
  const parties = await data("site/sancoes/partidos.csv");
  let measure = params.get("pm") || "share";
  const ctl = el("div", { className: "controls" }), c2 = chart();
  root.append(card("By party: how much of their amendment money reached barred companies", "For each party, the individual amendments of its deputies and senators (party in the amendment's year), paid to anyone. The bars show the part paid to a company while it was barred, per R$ 1 million paid. Parties whose members' amendments paid at least R$ 500 million. These are small sums: one payment can move a party's bar.", ctl, c2));
  const drawParties = () => {
    ctl.replaceChildren(select("Measure", [{ value: "share", label: "Any barring sanction" }, { value: "share_sim", label: "A sanction binding federal bodies" }], measure, (v) => { measure = v; setParam("pm", v, "share"); drawParties(); }));
    const rows = parties.filter((x) => +x.pago_total >= 5e8).map((x) => ({ ...x, v: +x[measure] })).sort((a, b) => b.v - a.v);
    C.bars(c2, {
      rows: rows.map((x) => ({ label: x.partido, value: x.v * 1e6, note: `${brl(measure === "share" ? x.pago_sancionadas : x.pago_sim)} of ${brl(x.pago_total)} · ${x.autores_com_sancionadas} of ${x.autores} members · ${x.empresas_sancionadas} companies`, color: css("--line") })),
      labelWidth: 110, format: (v) => `R$ ${fmt(v)}`,
      table: { rows: parties, cols: [{ key: "partido", label: "Party", text: true }, { key: "autores", label: "Members" }, { key: "pago_total", label: "Paid, all", fmt: (v) => brl(v) },
        { key: "pago_sancionadas", label: "To barred companies", fmt: (v) => brl(v) }, { key: "pago_sim", label: "Binding federal bodies", fmt: (v) => brl(v) },
        { key: "share", label: "Per R$ 1 million", fmt: (v) => perMillion(+v) }, { key: "autores_com_sancionadas", label: "Members involved" }, { key: "empresas_sancionadas", label: "Companies" }], name: "parties" },
    });
  };
  later(drawParties);

  // individual level
  const authors = (await data("site/sancoes/autores.csv")).filter((x) => +x.pago_sancionadas > 0);
  const ind = authors.filter((x) => x.kind === "deputado" || x.kind === "senador").sort((a, b) => +b.pago_sancionadas - +a.pago_sancionadas);
  const c3 = chart(), tb = el("div");
  root.append(grid(
    card("Members whose amendments paid barred companies most", "Deputies and senators, by the amendment money paid to companies while those were barred; their party in their latest amendment year.", c3),
    card("Who else sends it", "Collective amendments: state benches, committees and the budget rapporteur (the 2020–2022 \"secret budget\").", el("div", { id: "coll" }))));
  later(() => C.bars(c3, { rows: ind.slice(0, 15).map((x) => ({ label: `${title(x.autor)} (${x.partido || "?"}-${x.uf || "?"})`, value: +x.pago_sancionadas, note: `${pct(+x.share, 1)} of the ${brl(x.pago_total)} their amendments paid · ${x.empresas_sancionadas} companies`, color: C.slot(8) })), labelWidth: 250, format: (v) => brl(v, 1) }));
  const coll = authors.filter((x) => ["bancada", "comissao", "relator"].includes(x.kind)).sort((a, b) => +b.pago_sancionadas - +a.pago_sancionadas);
  later(() => C.bars($("#coll", root), { rows: coll.slice(0, 15).map((x) => ({ label: short(title(x.autor), 30), title: x.autor, value: +x.pago_sancionadas, note: `${KIND[x.kind]} · ${pct(+x.share, 2)} of ${brl(x.pago_total)}`, color: css("--other") })), labelWidth: 250, format: (v) => brl(v, 1) }));
  root.append(card("Every author whose amendments paid a barred company", "Share: the part of everything their amendments paid that went to companies while barred.", tb));
  table(tb, authors, [{ key: "autor", label: "Author", text: true, fmt: title }, { key: "kind", label: "Kind", text: true, fmt: (v) => KIND[v] || v }, { key: "partido", label: "Party", text: true }, { key: "uf", label: "UF", text: true },
    { key: "pago_total", label: "Paid, all", fmt: (v) => brl(v) }, { key: "pago_sancionadas", label: "To barred companies", fmt: (v) => brl(v) }, { key: "share", label: "Share", fmt: (v) => pct(+v, 2) },
    { key: "pago_sim", label: "Binding federal bodies", fmt: (v) => brl(v) }, { key: "empresas_sancionadas", label: "Companies" }], { sortBy: "pago_sancionadas", pageSize: 12, name: "authors" });

  const comps = (await E()).filter((x) => +x.emendas_sancionada > 0).sort((a, b) => +b.emendas_sancionada - +a.emendas_sancionada);
  const tc = el("div");
  root.append(card("Companies paid by amendments while barred", "Click a name to see which members' amendments paid it, and when its sanctions ran.", tc));
  table(tc, comps, [companyCol(), { key: "emendas_sancionada", label: "While barred", fmt: (v) => brl(v) }, { key: "emendas", label: "All amendments", fmt: (v) => brl(v) },
    { key: "ceis", label: "CEIS" }, { key: "cnep", label: "CNEP" }, { key: "orgaos", label: "Bodies" }], { sortBy: "emendas_sancionada", pageSize: 10, name: "companies-amendments" });

  const c4 = chart(), tp = el("div");
  root.append(card("Public contracts signed while the supplier was barred (PNCP)", `Contracts published on the PNCP whose supplier was under a sanction barring contracting on the day it was signed. The PNCP history is still being read (${fmt(m.pncp.days_read)} days so far, ${m.pncp.first_day} to ${m.pncp.last_day}). Most matches are sanctions limited to another body or sphere, which do not stop the contract.`, c4, tp));
  const pr = ["sim", "possivel", "nao"].map((k) => ({ k, ...(pncp[k] || { contratos: 0, valor: 0, empresas: 0 }) }));
  later(() => C.bars(c4, { rows: pr.map((x) => ({ label: COBRE[x.k], value: x.contratos, note: `${brl(x.valor)} · ${fmt(x.empresas)} suppliers`, color: scopeColor(x.k) })), labelWidth: 190 }));
  table(tp, m.pncp.flagged, [{ key: "assinatura", label: "Signed", text: true, fmt: day }, { key: "fornecedor_nome", label: "Supplier", text: true, wrap: true, fmt: (v, x) => companyLink(v, x.fornecedor) },
    { key: "orgao", label: "Buyer", text: true, wrap: true }, { key: "uf", label: "UF", text: true }, { key: "valor_global", label: "Value", fmt: (v) => brl(v) },
    { key: "cobre", label: "Scope", text: true, fmt: (v) => COBRE[v] }, { key: "categoria_sancao", label: "Sanction", text: true, fmt: (v) => cat(v) }, { key: "orgao_sancionador", label: "Imposed by", text: true, wrap: true }],
  { sortBy: "valor_global", pageSize: 8, name: "contracts-while-barred" });

  const tt = el("div");
  root.append(card("Campaign suppliers that were on the lists on election day", "Companies paid by candidates' campaigns (TSE) while under a sanction barring them from public contracts. Campaigns are not public contracts, so nothing forbids it; it is context. The 2026 count is larger partly because recent sanctions have not expired yet.", tt));
  table(tt, m.tse_list, [{ key: "ano", label: "Election", text: true }, companyCol(), { key: "total", label: "Campaign spending", fmt: (v) => brl(v) }, { key: "n_candidatos", label: "Candidates" }],
    { sortBy: "total", pageSize: 10, name: "campaign-suppliers" });
}

// ------------------------------------------------------------ CEPIM

const MOTIVO = {
  "INSTAURACAO DE TOMADA DE CONTAS ESPECIAL": "Special audit opened (TCE)", "MOTIVO NÃO ESPECIFICADO": "Not specified",
  "NAO APRESENTACAO DE DOCUMENTACAO COMPLEMENTAR": "Missing supporting documents", "NAO APRESENTACAO DA PRESTACAO DE CONTAS": "No accounts rendered",
  "IRREGULARIDADE NA EXECUCAO FINANCEIRA": "Irregular financial execution", "IRREGULARIDADE NA EXECUCAO FIS. E FINANCEIRA": "Irregular physical and financial execution",
  "NAO EXECUTOU TOTALMENTE O OBJETO PACTUADO": "Did not deliver what was agreed", "INSCRICAO POR DECISAO DO T.C.U.": "Listed by a TCU ruling",
};

async function cepim(root) {
  const r = await R(), c = r.cepim, m = r.money.cepim;
  const ents = (await E()).filter((x) => n(x.cepim) > 0);
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Non-profits barred", value: fmt(r.tiles.cepim_entidades), sub: `from new federal agreements, as of ${r.cepim_snapshot}` },
    { label: "Agreements behind it", value: fmt(r.tiles.cepim), sub: "one entry per agreement that went wrong" },
    { label: "Most from one ministry", value: c.orgaos[0] ? fmt(c.orgaos[0].n) : "0", sub: c.orgaos[0] ? c.orgaos[0].orgao_concedente.replace(" - Unidades com vínculo direto", "") : "" },
    { label: "Amendment money they received", value: brl(m.total), sub: `${fmt(m.entidades)} of them, at any time` },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(card("Which ministry's agreements", "Entries by the ministry that signed the agreement.", c1), card("Why they were barred", "The reason recorded, translated.", c2)));
  later(() => C.bars(c1, { rows: c.orgaos.map((x) => ({ label: short(abbr(x.orgao_concedente), 40), title: x.orgao_concedente, value: x.n, note: `${fmt(x.entidades)} organisations`, color: css("--line") })), labelWidth: 250 }));
  later(() => C.bars(c2, { rows: c.motivos.map((x) => ({ label: MOTIVO[x.motivo_do_impedimento] || x.motivo_do_impedimento, value: x.n, title: x.motivo_do_impedimento, color: css("--line") })), labelWidth: 250 }));
  const c3 = chart();
  root.append(card("Amendments paid to organisations now on CEPIM", "By payment year. CEPIM records no dates, so these may be payments made before the organisation was barred: the question is whether the money that went wrong came from amendments.", c3));
  later(() => C.stack(c3, { x: m.by_year.map((x) => x.ano), height: 200, format: (v) => brl(v, 0), series: [{ name: "Paid", color: css("--line"), values: m.by_year.map((x) => x.valor) }],
    table: { rows: m.by_year, cols: [{ key: "ano", label: "Year", text: true }, { key: "valor", label: "Paid", fmt: (v) => brl(v) }, { key: "entidades", label: "Organisations" }], name: "cepim-amendments" } }));
  const tb = el("div");
  root.append(card("Every organisation on CEPIM", "", tb));
  table(tb, ents, [companyCol("nome", "Organisation"), { key: "cnpj", label: "CNPJ", text: true, fmt: (v) => day(cnpjFmt(v)) }, { key: "cepim", label: "Agreements" }, { key: "emendas", label: "Amendments received", fmt: (v) => (n(v) ? brl(v) : "") }, { key: "ceis", label: "Also on CEIS" }],
    { sortBy: "cepim", pageSize: 12, name: "cepim" });
}

// ------------------------------------------------------------ leniency

async function leniency(root) {
  const r = await R(), L = r.leniency, rows = await data("site/sancoes/leniencia.csv");
  const brlRows = rows.filter((x) => x.moeda === "BRL" && x.valor_total !== "");
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Leniency agreements", value: fmt(r.tiles.acordos), sub: `covering ${fmt(r.tiles.acordos_empresas)} companies` },
    { label: "Amounts agreed", value: brl(L.brl_total), sub: `in reais, the ${brlRows.length} agreements whose terms state a total` },
    { label: "Of which fines", value: brl(L.brl_multa), sub: "the part the terms call a fine" },
    { label: "Still being carried out", value: fmt(L.status.find((x) => x.situacao === "Em Execução")?.n || 0), sub: `agreements not yet fulfilled, of ${fmt(r.tiles.acordos)}` },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(card("Agreements by the year they were signed", "", c1), card("What the companies got, and gave", "How many agreements include each effect.", c2)));
  later(() => C.stack(c1, { x: L.by_year.map((x) => x.ano), height: 200, series: [{ name: "Agreements", color: css("--line"), values: L.by_year.map((x) => x.n) }] }));
  later(() => C.bars(c2, { rows: L.effects.map((x) => ({ label: effect(x.efeito), value: x.n, title: x.efeito, color: css("--line") })), labelWidth: 280 }));
  const c3 = chart();
  root.append(card("The largest agreements", "Total amounts in reais as their terms state them, which include restitution and fines; agreements in euros or dollars are in the table.", c3));
  const big = [...brlRows].sort((a, b) => +b.valor_total - +a.valor_total).slice(0, 15);
  later(() => C.bars(c3, { rows: big.map((x) => ({ label: short(x.nome, 36), title: x.empresas, value: +x.valor_total, note: `${x.inicio.slice(0, 4)} · fine ${brl(x.multa)}`, color: css("--line") })), labelWidth: 280, format: (v) => brl(v, 1) }));
  const tb = el("div");
  root.append(card("Every agreement", "", tb));
  table(tb, rows, [{ key: "inicio", label: "Signed", text: true, fmt: day }, { key: "nome", label: "Agreement", text: true }, { key: "empresas", label: "Companies", text: true, wrap: true }, { key: "situacao", label: "Status", text: true, fmt: (v) => day(STATUS[v] || v) },
    { key: "valor_total", label: "Total", fmt: (v, x) => (v === "" ? "" : x.moeda === "BRL" ? brl(v) : `${x.moeda} ${fmt(+v / 1e6, 1)} M`) }, { key: "multa", label: "Fine", fmt: (v) => (v === "" ? "" : brl(v)) },
    { key: "efeitos", label: "Effects", text: true, wrap: true, fmt: (v) => v.split("; ").map(effect).join("; ") }], { sortBy: "inicio", pageSize: 10, name: "leniency" });
}

// ------------------------------------------------------------ changes

async function changes(root) {
  const r = await R(), ch = await data("site/sancoes/mudancas.csv"), recent = await data("site/sancoes/recentes.csv");
  const ins = sum(ch.filter((x) => x.mudanca === "entrou").map((x) => +x.n)), outs = sum(ch.filter((x) => x.mudanca === "saiu").map((x) => +x.n));
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Recorded since", value: "2026-11-06", sub: "CEPIM since 2026-10-28" },
    { label: "Entries added", value: fmt(ins), sub: "sanctions that appeared in a list" },
    { label: "Entries removed", value: fmt(outs), sub: "expired, lifted or corrected" },
    { label: "Latest change", value: r.changes.last || "none yet", sub: `latest snapshot ${r.snapshot}` },
  ]);
  const c1 = chart();
  root.append(card("Entries and exits per day", "CGU replaces each list every day and keeps no history; political-eye compares each day's snapshot with the last one recorded. A day is dated by the snapshot, not by the day the job ran.", c1));
  if (!ch.length) c1.append(el("p", { className: "empty", textContent: "No change recorded yet: the first snapshot is the baseline, and each later day adds a point here." }));
  else {
    const daysAll = [...new Set(ch.map((x) => x.data))].sort();
    const s = (what, name, color) => ({ name, color, points: daysAll.map((d) => [d, sum(ch.filter((x) => x.data === d && x.mudanca === what).map((x) => +x.n))]) });
    later(() => C.line(c1, { x: "day", height: 220, series: [s("entrou", "Added", C.slot(1)), s("saiu", "Removed", C.slot(2))] }));
  }
  const tb = el("div");
  root.append(card("The latest changes about companies", "People's entries are counted above but not listed.", tb));
  table(tb, recent, [{ key: "data", label: "Day", text: true, fmt: day }, { key: "lista", label: "List", text: true }, { key: "mudanca", label: "Change", text: true, fmt: (v) => (v === "entrou" ? "Added" : "Removed") }, companyCol()],
    { sortBy: "data", pageSize: 15, name: "changes" });
}

// ------------------------------------------------------------ one company

function timeline(box, o) {
  box.replaceChildren();
  const rows = o.rows;
  if (!rows.length) { box.append(el("p", { className: "empty", textContent: "No dated sanction." })); return; }
  const lw = 150, mr = 12, rh = 18, mt = 4, mb = 24, H = mt + rh * (rows.length + o.lanes.length) + mb;
  const w = Math.max(320, box.clientWidth || 600), s = C.svg("svg", { width: w, height: H, role: "img" });
  const t = (d) => Date.parse(`${d}T00:00:00Z`);
  const all = [...rows.flatMap((x) => [x.from, x.to]), ...o.lanes.flatMap((l) => l.points.map((p) => p.date))].filter(Boolean).map(t);
  const lo0 = Math.min(...all), hi0 = Math.max(...all, t(o.today)), pad = Math.max(30 * 864e5, (hi0 - lo0) * 0.04);
  const lo = lo0 - pad, hi = hi0 + pad;
  const sx = (d) => lw + ((t(d) - lo) / Math.max(1, hi - lo)) * (w - lw - mr);
  const muted = css("--muted"), ink2 = css("--ink2"), grid = css("--grid");
  const y0 = new Date(lo).getUTCFullYear(), y1 = new Date(hi).getUTCFullYear(), step = Math.max(1, Math.ceil((y1 - y0 + 1) / Math.floor((w - lw) / 60)));
  for (let y = y0; y <= y1 + 1; y += step) {
    const x = sx(`${y}-01-01`); if (x < lw || x > w - mr) continue;
    s.append(C.svg("line", { x1: x, x2: x, y1: mt, y2: H - mb, stroke: grid }));
    const tx = C.svg("text", { x, y: H - 8, "text-anchor": "middle", "font-size": 10, fill: muted }); tx.textContent = y; s.append(tx);
  }
  const today = sx(o.today);
  s.append(C.svg("line", { x1: today, x2: today, y1: mt, y2: H - mb, stroke: css("--axis"), "stroke-dasharray": "3 3" }));
  const hit = (node, kids) => { node.addEventListener("pointermove", (ev) => showTip(ev, kids)); node.addEventListener("pointerleave", hideTip); };
  rows.forEach((x, i) => {
    const y = mt + i * rh;
    const lab = C.svg("text", { x: lw - 6, y: y + rh / 2 + 4, "text-anchor": "end", "font-size": 11, fill: ink2 }); lab.textContent = x.label.length > 24 ? `${x.label.slice(0, 23)}…` : x.label; s.append(lab);
    const a = sx(x.from), b = x.to ? sx(x.to) : today;
    const r = C.svg("rect", { x: a, y: y + 3, width: Math.max(3, b - a), height: rh - 6, rx: 3, fill: x.color, opacity: x.to ? 1 : 0.75 });
    hit(r, [el("strong", { textContent: x.title }), ...x.tip.map((t2) => el("div", { className: "row", textContent: t2 }))]);
    s.append(r);
  });
  o.lanes.forEach((l, k) => {
    const y = mt + (rows.length + k) * rh;
    const lab = C.svg("text", { x: lw - 6, y: y + rh / 2 + 4, "text-anchor": "end", "font-size": 11, fill: ink2 }); lab.textContent = l.label; s.append(lab);
    for (const p of l.points) {
      const c = C.svg("circle", { cx: sx(p.date), cy: y + rh / 2, r: p.r || 4, fill: p.color, stroke: css("--surface"), "stroke-width": 1 });
      hit(c, [el("strong", { textContent: p.title }), ...(p.tip || []).map((t2) => el("div", { className: "row", textContent: t2 }))]);
      s.append(c);
    }
  });
  box.append(s);
  C.legend(box, o.legend || []);
}

async function company(root) {
  const r = await R(), all = await E();
  const byCnpj = new Map(all.map((x) => [x.cnpj, x]));
  const input = el("input", { type: "search", placeholder: "Company name or CNPJ…", autocomplete: "off", style: "min-width:320px" });
  const results = el("ul", { className: "search-results" }), out = el("div");
  root.append(el("div", { className: "controls" }, el("label", {}, "Find a sanctioned company or organisation", input)), results, out);
  const index = all.map((x) => [norm(x.nome), x]);
  input.addEventListener("input", () => {
    const q = norm(input.value.trim()), digits = input.value.replace(/\D/g, "");
    if (q.length < 3 && digits.length < 4) { results.replaceChildren(); return; }
    const hits = (digits.length >= 4 && digits.length === input.value.replace(/[\s./-]/g, "").length ? all.filter((x) => x.cnpj.startsWith(digits)) : index.filter(([k]) => k.includes(q)).map(([, x]) => x)).slice(0, 12);
    results.replaceChildren(...(hits.length ? hits.map((x) => el("li", {}, el("button", { type: "button", on: { click: () => { results.replaceChildren(); input.value = ""; openCompany(x.cnpj); } } },
      el("span", { textContent: x.nome || cnpjFmt(x.cnpj) }), el("span", { className: "n", textContent: `${cnpjFmt(x.cnpj)} · ${n(x.ceis) + n(x.cnep)} sanctions${n(x.cepim) ? ` · CEPIM ${x.cepim}` : ""}` })))) : [el("li", { className: "hint", textContent: "No sanctioned company matches." })]));
  });

  const leni = await data("site/sancoes/leniencia.csv");
  const show = async (cnpj) => {
    const x = byCnpj.get(cnpj);
    if (!x) { out.replaceChildren(el("p", { className: "empty", textContent: "This CNPJ is on none of the lists." })); return; }
    const shard = await data(`site/sancoes/empresas/${cnpj.slice(0, 2)}.json`), d = shard[cnpj] || {};
    const S = (d.s || []).map(([lista, codigo, categoria, inicio, fim, orgao, esfera, uf, abrangencia, multa, processo, artigo]) => ({ lista, codigo, categoria, inicio, fim, orgao, esfera, uf, abrangencia, multa, processo, artigo }));
    const Cn = (d.c || []).map(([assinatura, orgao, esfera, uf, objeto, valor, cobre, controle]) => ({ assinatura, orgao, esfera, uf, objeto, valor, cobre, controle }));
    const Em = (d.e || []).map(([ano, total, sancionada, sim]) => ({ ano, total, sancionada, sim }));
    const Au = (d.a || []).map(([autor, partido, uf, valor, sanc]) => ({ autor, partido, uf, valor, sanc }));
    const T = (d.t || []).map(([ano, total, n_candidatos, barrado]) => ({ ano, total, n_candidatos, barrado }));
    const P = (d.p || []).map(([convenio, orgao, motivo]) => ({ convenio, orgao, motivo }));
    const Ls = leni.filter((l) => (d.l || []).includes(l.id));
    const lists = [n(x.ceis) && "CEIS", n(x.cnep) && "CNEP", n(x.cepim) && "CEPIM", n(x.leniencia) && "Leniency"].filter(Boolean);
    const box = el("div");
    box.append(el("div", { className: "profile-head" }, el("h2", { textContent: x.nome || cnpjFmt(cnpj) }),
      el("span", { className: "doc" }, cnpjFmt(cnpj), " ", ...lists.map((l) => el("span", { className: "pill", textContent: l })))));
    const tl = el("section", { className: "tiles" });
    box.append(tl);
    tiles(tl, [
      { label: "Sanctions listed", value: fmt(S.length), sub: `${fmt(x.vigentes)} in force on ${r.snapshot}${n(x.barra) ? ", barring contracts" : ""}` },
      { label: "Bodies that sanctioned it", value: fmt(x.orgaos), sub: `in ${fmt(x.ufs)} states` },
      { label: "Amendment money received", value: brl(n(x.emendas)), sub: n(x.emendas_sancionada) ? `${brl(x.emendas_sancionada)} while barred` : "none while barred" },
      { label: "Large public contracts", value: fmt(x.contratos), sub: n(x.contratos_sancionada) ? `${fmt(x.contratos_sancionada)} signed while barred` : "PNCP, R$ 1 M or more, history being read" },
    ]);
    const tlc = chart();
    box.append(card("Its sanctions over time", "Each bar is a sanction, from its start to its end; faded bars have no end date and run to today (dashed line). Below: the amendment payments it received, by year, and its large public contracts.", tlc));
    const pays = Em.filter((e) => e.total > 0);
    const maxPay = Math.max(1, ...pays.map((e) => e.total));
    const drawTl = () => timeline(tlc, {
      today: r.snapshot,
      rows: S.filter((s0) => s0.inicio).map((s0) => ({ label: `${s0.lista} ${cat(s0.categoria)}`, from: s0.inicio, to: s0.fim, color: /^(Impedimento|Declaração de Inidoneidade|Suspensão$)/.test(s0.categoria) ? css("--critical") : css("--other"),
        title: cat(s0.categoria), tip: [`${s0.inicio} to ${s0.fim || "no end date"}`, s0.orgao, SCOPE[s0.abrangencia] || s0.abrangencia, s0.multa ? `fine ${brl(s0.multa)}` : ""].filter(Boolean) })),
      lanes: [
        { label: "Amendments paid", points: pays.map((e) => ({ date: `${e.ano}-07-01`, r: 3 + 6 * Math.sqrt(e.total / maxPay), color: e.sancionada > 0 ? css("--critical") : css("--line"), title: `${e.ano}: ${brl(e.total)}`, tip: e.sancionada ? [`${brl(e.sancionada)} while barred`] : [] })) },
        { label: "Contracts signed", points: Cn.filter((c0) => c0.assinatura).map((c0) => ({ date: c0.assinatura, color: c0.cobre ? scopeColor(c0.cobre) : css("--line"), title: `${c0.assinatura}: ${brl(c0.valor)}`, tip: [c0.orgao, c0.objeto, c0.cobre ? `while barred: ${COBRE[c0.cobre]}` : ""].filter(Boolean) })) },
      ],
      legend: [{ label: "Bars contracts", color: css("--critical") }, { label: "Other sanction", color: css("--other") }, { label: "Payment or contract", color: css("--line") }],
    });
    out.replaceChildren(box);
    drawTl();
    redraws.push(drawTl);
    const ts = el("div");
    box.append(card("Every sanction", "", ts));
    table(ts, S, [{ key: "lista", label: "List", text: true }, { key: "categoria", label: "Sanction", text: true, fmt: (v) => cat(v) }, { key: "inicio", label: "From", text: true, fmt: day }, { key: "fim", label: "To", text: true, fmt: day },
      { key: "orgao", label: "Imposed by", text: true, wrap: true }, { key: "uf", label: "UF", text: true }, { key: "abrangencia", label: "Scope", text: true, fmt: (v) => SCOPE[v] || v }, { key: "artigo", label: "Legal ground", text: true, wrap: true },
      { key: "multa", label: "Fine", fmt: (v) => (v ? brl(v) : "") }], { sortBy: "inicio", pageSize: 10, name: `sanctions-${cnpj}` });
    if (Em.length || Au.length) {
      const ce = chart(), ta = el("div");
      box.append(grid(card("Amendment money it received, by year", "Red: paid while a barring sanction was in force.", ce), card("Whose amendments paid it", "Authors of the amendments behind its payments; their party in the amendment's year.", ta)));
      const draw = () => C.stack(ce, { x: Em.map((e) => e.ano), height: 200, format: (v) => brl(v, 0), series: [{ name: "While barred", color: css("--critical"), values: Em.map((e) => e.sancionada) }, { name: "Otherwise", color: css("--line"), values: Em.map((e) => e.total - e.sancionada) }] });
      draw(); redraws.push(draw);
      table(ta, Au, [{ key: "autor", label: "Author", text: true, fmt: title }, { key: "partido", label: "Party", text: true }, { key: "uf", label: "UF", text: true }, { key: "valor", label: "Paid", fmt: (v) => brl(v) }, { key: "sanc", label: "While barred", fmt: (v) => (v ? brl(v) : "") }],
        { sortBy: "valor", pageSize: 8, search: false, name: `authors-${cnpj}` });
    }
    if (Cn.length) {
      const tc = el("div");
      box.append(card("Its public contracts on the PNCP", "Contracts of R$ 1 million or more, and any contract signed while it was barred.", tc));
      table(tc, Cn, [{ key: "assinatura", label: "Signed", text: true, fmt: day }, { key: "orgao", label: "Buyer", text: true, wrap: true }, { key: "uf", label: "UF", text: true }, { key: "objeto", label: "Object", text: true, wrap: true },
        { key: "valor", label: "Value", fmt: (v) => brl(v) }, { key: "cobre", label: "While barred", text: true, fmt: (v) => (v ? COBRE[v] : "") }], { sortBy: "assinatura", pageSize: 8, name: `contracts-${cnpj}` });
    }
    if (T.length) {
      const tt = el("div");
      box.append(card("Its sales to election campaigns", "What candidates paid it, by election (TSE).", tt));
      table(tt, T, [{ key: "ano", label: "Election", text: true }, { key: "total", label: "Paid by campaigns", fmt: (v) => brl(v) }, { key: "n_candidatos", label: "Candidates" }, { key: "barrado", label: "Listed on election day", text: true, fmt: (v) => (v ? "yes" : "no") }],
        { search: false, name: `campaigns-${cnpj}` });
    }
    if (P.length) {
      const tp = el("div");
      box.append(card("Its CEPIM entries", "The federal agreements behind its bar.", tp));
      table(tp, P, [{ key: "convenio", label: "Agreement", text: true }, { key: "orgao", label: "Ministry", text: true, wrap: true }, { key: "motivo", label: "Reason", text: true, fmt: (v) => MOTIVO[v] || v }], { search: false, name: `cepim-${cnpj}` });
    }
    if (Ls.length) box.append(card("Its leniency agreements", "", ...Ls.map((l) => el("p", { className: "about", textContent: `${l.inicio}, ${STATUS[l.situacao] || l.situacao}: ${l.termos}…` }))));
  };
  companyView = show;
  const start = params.get("cnpj") && byCnpj.has(params.get("cnpj")) ? params.get("cnpj")
    : [...all].sort((a, b) => n(b.emendas_sancionada) - n(a.emendas_sancionada))[0]?.cnpj;
  if (start) await show(start);
}

// ------------------------------------------------------------ boot

const SECTIONS = { overview, who, time, repeat, fines, money, cepim, leniency, changes, company };
showTab = tabs((name) => { const box = $(`#tab-${name}`); guard(box, () => SECTIONS[name](box)); });
onResize(() => redraws.forEach((f) => f()));
