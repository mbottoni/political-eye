// Sanctions: who is barred or punished, by whom, for how long, and what public money still reaches them.
import { $, asset, brl, css, data, el, fmt, guard, hideTip, onResize, params, pct, plural, setParam, showTip, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L, month } from "../lib/i18n.js";
import { setupPage } from "../lib/page.js";

setupPage();

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
const years = (v) => (v == null ? "–" : `${fmt(v, v < 10 ? 1 : 0)} ${v === 1 ? L("ano", "year") : L("anos", "years")}`);
const days = (v) => (v == null ? "–" : `${fmt(v)} ${v === 1 ? L("dia", "day") : L("dias", "days")}`);
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
const sanctions = (k) => plural(k, L("sanção", "sanction"), L("sanções", "sanctions"));

// The CGU's own codes and wording -> labels in the page's language (Portuguese: the CGU's terms, cleaned up).
const CAT = {
  "Impedimento/proibição de contratar com prazo determinado": L("Impedimento, com prazo", "Contracting ban, fixed term"),
  "Impedimento/proibição de contratar sem prazo determinado": L("Impedimento, sem prazo", "Contracting ban, no end date"),
  "Suspensão": L("Suspensão de licitar", "Suspended from tenders"),
  "Declaração de Inidoneidade sem prazo determinado": L("Inidoneidade, sem prazo", "Declared unfit, no end date"),
  "Declaração de Inidoneidade com prazo determinado": L("Inidoneidade, com prazo", "Declared unfit, fixed term"),
  "Demissão": L("Demissão (servidor público)", "Dismissed (civil servant)"),
  "Suspensão/Interdição das atividades sem prazo determinado": L("Interdição, sem prazo", "Activity halt, no end date"),
  "Suspensão/Interdição das atividades com prazo determinado": L("Interdição, com prazo", "Activity halt, fixed term"),
  "Multa": L("Multa", "Fine"),
  "Advertência": L("Advertência", "Warning"),
  "Publicação extraordinária da decisão condenatória": L("Publicação da condenação", "Ruling published at its cost"),
  "Proibição de receber incentivos, subsídios, subvenções, doações ou empréstimos": L("Proibição de receber subsídios", "No subsidies or public loans"),
  "Dissolução compulsória da PJ": L("Dissolução compulsória", "Compulsory dissolution"),
  "Perdimento de bens": L("Perdimento de bens", "Assets forfeited"),
};
const cat = (c) => CAT[c] || c;
const NOT_STATED = L("Não informada", "Not stated");
const SPH = { FEDERAL: "Federal", ESTADUAL: L("Estadual", "State"), MUNICIPAL: "Municipal", "": NOT_STATED, outra: NOT_STATED };
const SPH_COLOR = () => ({ FEDERAL: C.slot(1), ESTADUAL: C.slot(2), MUNICIPAL: C.slot(3), "": css("--other"), outra: css("--other") });
const SCOPE = {
  "Todas as Esferas em todos os Poderes": L("Todas as esferas e Poderes", "Every sphere and power"),
  "Em todos os Poderes da Esfera do órgão sancionador": L("Toda a esfera do sancionador", "The sanctioner's whole sphere"),
  "Na Esfera e no Poder do órgão sancionador": L("Esfera e Poder do sancionador", "The sanctioner's sphere and power"),
  "No órgão sancionador": L("Só o órgão sancionador", "Only the sanctioning body"),
  "Sem Informação": NOT_STATED,
  "Em outro órgão": L("Outro órgão", "Another body"),
};
const COBRE = { sim: L("Vale para o comprador", "Reaches the buyer"), possivel: L("Pode valer para o comprador", "May reach the buyer"), nao: L("Não vale para o comprador", "Does not reach the buyer") };
const FED = { sim: L("Vale para órgãos federais", "Binds federal bodies"), possivel: L("Pode valer para o pagador", "May bind the paying body"), nao: L("Só vale em outra esfera", "Binds another sphere only") };
const scopeColor = (k) => ({ sim: css("--critical"), possivel: css("--warning"), nao: css("--other") })[k] || css("--other");
const KIND = { deputado: L("Deputado", "Deputy"), senador: L("Senador", "Senator"), bancada: L("Bancada estadual", "State bench"), comissao: L("Comissão", "Committee"), relator: L("Relator-geral", "Rapporteur-general"), outro: L("Não identificado", "Not matched") };
const EFFECT = [
  ["Adoção, aplicação", L("Programa de integridade", "Integrity programme adopted or improved")], ["Outros", L("Outros", "Other")],
  ["Isenção da publicação", L("Isenção da publicação", "Spared publishing the ruling")], ["Isenção da proibição de receber", L("Isenção da proibição de subsídios", "Spared the ban on subsidies")],
  ["Isenção da declaração de inidoneidade", L("Isenção da inidoneidade", "Spared being declared unfit")], ["Isenção da suspensão", L("Isenção da suspensão", "Spared suspension")],
  ["Atenuação da multa", L("Multa reduzida", "Fine reduced")], ["Remissão da multa", L("Multa perdoada", "Fine waived")], ["Atenuação da suspensão", L("Suspensão reduzida", "Suspension shortened")],
  ["Isenção do impedimento", L("Isenção do impedimento do pregão", "Spared the pregão ban")], ["Isenção da advertência", L("Isenção da advertência", "Spared a warning")], ["Isenção da multa de mora", L("Isenção da multa de mora", "Spared a late-payment fine")],
];
const effect = (e) => (EFFECT.find(([k]) => e.startsWith(k)) || [null, e])[1];
const STATUS = { "Em Execução": L("Em execução", "In progress"), "Cumprido": L("Cumprido", "Fulfilled") };
// Agreements signed by several firms of one group are named "<Group> group" by the summary builder.
const agreement = (s) => (/ group$/.test(s) ? L(`Grupo ${s.slice(0, -6)}`, s) : s);
// Groups and law names the summary builder writes in English (politicaleye/site/sancoes.py), keyed by its values.
const GROUP = {
  "Barred from contracting": [L("Impedimento de contratar", "Barred from contracting"), L("impedimento de contratar", "barred from contracting")],
  "Declared unfit (inidoneidade)": [L("Declaração de inidoneidade", "Declared unfit (inidoneidade)"), L("declaração de inidoneidade", "declared unfit (inidoneidade)")],
  "Suspended": [L("Suspensão", "Suspended"), L("suspensão", "suspended")],
  "Other": [L("Outras", "Other"), L("outros tipos", "other")],
};
const group = (g, i = 0) => GROUP[g]?.[i] ?? (i ? g.toLowerCase() : g);
const LAW = {
  "LEI 8429": "Lei de Improbidade (8.429/92)", "LEI 14133": "Lei de Licitações (14.133/21)",
  "LEI 8666": "Antiga Lei de Licitações (8.666)", "LEI 12846": "Lei Anticorrupção (12.846/13)",
  "LEI 10520": "Lei do Pregão (10.520/02)", "LEI 13303": "Lei das Estatais (13.303/16)",
  "LEI 9433 (BA)": "Licitações da Bahia (9.433/05)", "LEI 8443": "Lei Orgânica do TCU (8.443/92)",
  "LEI 45902 (MG)": "Lei estadual 45.902 (MG)", "LEI 13105": "Código de Processo Civil",
  "LEI 12462": "Lei do RDC (12.462/11)", "LEI 12529": "Lei da Concorrência (12.529/11)",
  "CÓDIGO DE PROCESSO PENAL": "Código de Processo Penal",
};
const law = (x) => L(LAW[x.lei] || x.label, x.label);

const R = () => data("site/sancoes/resumo.json");
const E = () => data("site/sancoes/empresas.csv");

let showTab = () => {}, companyView = null;
function openCompany(cnpj) {
  setParam("cnpj", cnpj);
  showTab("company");
  if (companyView) companyView(cnpj);
  window.scrollTo({ top: $("nav.tabs").offsetTop - 8, behavior: "smooth" });
}
const WITHHELD = L("Empresa individual (nome omitido)", "Individual firm (name withheld)");
const companyLink = (name, cnpj) => el("button", { className: "linkish", type: "button", textContent: name || WITHHELD, title: cnpjFmt(cnpj), on: { click: () => openCompany(cnpj) } });
const companyCol = (key = "nome", label = L("Empresa", "Company")) => ({ key, label, text: true, wrap: true, fmt: (v, r) => companyLink(v, r.cnpj) });

// ------------------------------------------------------------ overview

async function overview(root) {
  const r = await R(), t = r.tiles;
  const withEnd = t.ceis + t.cnep - t.sem_prazo;
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Sanções listadas", "Sanctions listed"), value: fmt(t.ceis + t.cnep), sub: L(`CEIS ${fmt(t.ceis)} · CNEP ${fmt(t.cnep)}, em ${r.snapshot}`, `CEIS ${fmt(t.ceis)} · CNEP ${fmt(t.cnep)}, as of ${r.snapshot}`) },
    { label: L("Empresas e organizações", "Companies and organisations"), value: fmt(t.empresas), sub: L(`e mais ${fmt(t.cepim_entidades)} entidades sem fins lucrativos no CEPIM`, `plus ${fmt(t.cepim_entidades)} non-profits on CEPIM`) },
    { label: L("Pessoas", "People"), value: fmt(t.pessoas_distintas), sub: L(`${fmt(t.pessoas)} sanções; aqui são contadas, nunca nomeadas`, `${fmt(t.pessoas)} sanctions; counted, never named here`) },
    { label: L("Vencidas, mas ainda listadas", "Past their end date, still listed"), value: fmt(t.vencidas), sub: L(`${pct(t.vencidas / withEnd, 1)} das que têm data de fim`, `${pct(t.vencidas / withEnd, 1)} of those with an end date`) },
  ]);

  const c1 = chart(), c2 = chart();
  root.append(grid(
    card(L("Que tipo de sanção", "What kind of sanction"), L("Cada registro do CEIS e do CNEP, por categoria. Azul: categorias que impedem a empresa ou a pessoa de contratar com o poder público; cinza: multas, advertências e as demais.", "Every CEIS and CNEP entry by its category. Blue: categories that bar the company or person from public contracts; grey: fines, warnings and the rest."), c1),
    card(L("Quem aplicou, e a quem", "Who imposed them, on whom"), L("Registros pela esfera do órgão que aplicou a sanção, separados entre empresas e pessoas. A maior parte das sanções a pessoas são condenações por improbidade enviadas pelos tribunais (CNJ).", "Entries by the sphere of the body that imposed them, split into companies and people. Most sanctions on people are improbidade convictions sent by the courts (CNJ)."), c2)));
  const cats = new Map();
  for (const x of r.categories) {
    const k = x.categoria, prev = cats.get(k) || { label: cat(k), value: 0, people: 0, barra: x.barra, pt: k };
    prev.value += n(x.empresa) + n(x.pessoa) + n(x.outro); prev.people += n(x.pessoa); cats.set(k, prev);
  }
  const catRows = [...cats.values()].sort((a, b) => b.value - a.value);
  later(() => C.bars(c1, {
    rows: catRows.map((x) => ({ ...x, color: x.barra ? C.slot(1) : css("--other"), title: L(x.pt, `${x.label} (${x.pt})`), note: L(`${pct(x.people / x.value)} a pessoas`, `${pct(x.people / x.value)} people`) })),
    labelWidth: 240, legend: [{ label: L("Impede contratar com o poder público", "Bars public contracts"), color: C.slot(1) }, { label: L("Não impede", "Does not"), color: css("--other") }],
    table: { rows: catRows, cols: [{ key: "label", label: L("Categoria", "Category"), text: true }, { key: "pt", label: L("Como publicada", "Published as"), text: true }, { key: "value", label: L("Registros", "Entries") }, { key: "people", label: L("A pessoas", "On people") }], name: "categories" },
  }));
  const sk = r.sphere_kind.filter((x) => x.esfera in SPH && x.esfera !== "");
  later(() => C.stack(c2, {
    x: sk.map((x) => SPH[x.esfera]), height: 220,
    series: [{ name: L("Empresas e organizações", "Companies and organisations"), color: C.slot(1), values: sk.map((x) => n(x.empresa)) }, { name: L("Pessoas", "People"), color: C.slot(4), values: sk.map((x) => n(x.pessoa)) }],
    table: { rows: sk.map((x) => ({ esfera: SPH[x.esfera], empresa: n(x.empresa), pessoa: n(x.pessoa) })), cols: [{ key: "esfera", label: L("Esfera", "Sphere"), text: true }, { key: "empresa", label: L("Empresas", "Companies") }, { key: "pessoa", label: L("Pessoas", "People") }], name: "spheres" },
  }));

  const c3 = chart();
  root.append(card(L("Quando começaram as sanções listadas", "When the listed sanctions began"), L("Ano de início de cada sanção ainda no CEIS ou no CNEP, pela esfera do órgão sancionador. As listas guardam só o que ainda está vigente (e algumas sanções já vencidas), então a alta recente é em parte de sanções que ainda não expiraram. Os anos antes de 2012 estão agrupados.", "Start year of every sanction still on CEIS or CNEP, by the sanctioning body's sphere. The lists keep only what is still in force (and some that are past their date), so the recent surge is partly sanctions that have not expired yet. Before 2012 is grouped."), c3));
  const sy = r.start_year.filter((x) => x.ano);
  const early = sy.filter((x) => +x.ano < 2012), late = sy.filter((x) => +x.ano >= 2012);
  const yrs = [L("antes de 2012", "before 2012"), ...late.map((x) => x.ano)];
  const val = (rows, k) => sum(rows.map((x) => n(x[k])));
  later(() => C.stack(c3, {
    x: yrs, height: 240,
    series: ["FEDERAL", "ESTADUAL", "MUNICIPAL", "outra"].map((k) => ({ name: SPH[k], color: SPH_COLOR()[k], values: [val(early, k), ...late.map((x) => n(x[k]))] })),
    table: { rows: sy, cols: [{ key: "ano", label: L("Ano", "Year"), text: true }, { key: "FEDERAL", label: SPH.FEDERAL }, { key: "ESTADUAL", label: SPH.ESTADUAL }, { key: "MUNICIPAL", label: SPH.MUNICIPAL }, { key: "outra", label: NOT_STATED }], name: "start-year" },
  }));
  const last = late[late.length - 1], prev = late[late.length - 2];
  if (last && prev) {
    const a = fmt(sum(["FEDERAL", "ESTADUAL", "MUNICIPAL", "outra"].map((k) => n(last[k])))), b = fmt(sum(["FEDERAL", "ESTADUAL", "MUNICIPAL", "outra"].map((k) => n(prev[k]))));
    c3.after(finding(L(`${a} das sanções listadas começaram em ${last.ano} (até ${r.snapshot}), contra ${b} em ${prev.ano}.`, `${a} of the listed sanctions started in ${last.ano} (to ${r.snapshot}), against ${b} in ${prev.ano}.`)));
  }

  const map = chart(), rank = chart();
  root.append(grid(
    card(L("Onde: sanções estaduais e municipais por milhão de habitantes", "Where: state and municipal sanctions per million inhabitants"), L("Pela UF do órgão sancionador; as sanções federais, que não têm UF própria, ficam de fora. A escala está na legenda.", "By the state of the sanctioning body; federal sanctions, which have no state of their own, are left out. See the key for the scale."), map),
    card(L("Os estados em ordem", "States ranked"), L("A mesma taxa; o número de sanções estaduais e municipais aparece no detalhe de cada barra.", "The same rate; the count of state and municipal sanctions in the tooltip."), rank)));
  const shapes = await asset("maps/ufs.json");
  const byIbge = new Map(r.by_uf.map((x) => [String(x.ibge), x]));
  const max = Math.max(...r.by_uf.map((x) => x.por_milhao || 0));
  later(() => {
    C.choropleth(map, {
      shapes: shapes.shapes, viewBox: shapes.viewBox, stroke: 0.6, maxWidth: 520,
      value: (code) => byIbge.get(code)?.por_milhao ?? null, color: (v) => C.seq(Math.sqrt(v / max)),
      tip: (code, v) => { const x = byIbge.get(code); return x ? [el("strong", { textContent: x.uf }), el("div", { className: "row", textContent: L(`${fmt(v, 1)} por milhão · ${fmt(x.total)} sanções (${fmt(x.estadual)} estaduais, ${fmt(x.municipal)} municipais)`, `${fmt(v, 1)} per million · ${fmt(x.total)} sanctions (${fmt(x.estadual)} state, ${fmt(x.municipal)} municipal)`) }), el("div", { className: "row", textContent: L(`${fmt(x.empresas_vigentes)} empresas com sanção vigente`, `${fmt(x.empresas_vigentes)} companies under a sanction in force`) })] : [el("strong", { textContent: code })]; },
    });
    C.colorKey(map, { color: (t) => C.seq(Math.sqrt(t)), from: "0", to: L(`${fmt(max)} por milhão`, `${fmt(max)} per million`), label: "" });
  });
  const ranked = [...r.by_uf].sort((a, b) => b.por_milhao - a.por_milhao);
  later(() => C.bars(rank, {
    rows: ranked.map((x) => ({ label: x.uf, value: x.por_milhao, note: L(`${fmt(x.total)} sanções`, `${fmt(x.total)} sanctions`), color: css("--line") })), barHeight: 12, format: (v) => fmt(v, 0),
    table: { rows: ranked, cols: [{ key: "uf", label: L("UF", "State"), text: true }, { key: "estadual", label: L("Órgãos estaduais", "State bodies") }, { key: "municipal", label: L("Órgãos municipais", "Municipal bodies") }, { key: "populacao", label: L("População", "Population") }, { key: "por_milhao", label: L("Por milhão", "Per million"), fmt: (v) => fmt(v, 1) }], name: "by-state" },
  }));
}

// ------------------------------------------------------------ who

async function who(root) {
  const r = await R();
  let lista = params.get("lista") || "", esfera = params.get("esfera") || "";
  const controls = el("div", { className: "controls" }), c1 = chart();
  root.append(controls, card(L("Os órgãos que mais sancionam", "The bodies that sanction most"), L("Sanções listadas por órgão sancionador: os 25 com mais sanções nos filtros acima. Cada órgão aparece com o nome que ele mesmo informa, então um mesmo órgão pode surgir com duas grafias.", "Sanctions listed per sanctioning body, the 25 with the most under the filters above. Bodies are named as each one reports itself, so one body can appear under two spellings."), c1));
  const draw = () => {
    controls.replaceChildren(
      select(L("Lista", "List"), [{ value: "", label: L("CEIS e CNEP", "CEIS and CNEP") }, "CEIS", "CNEP"], lista, (v) => { lista = v; setParam("lista", v, ""); draw(); }),
      select(L("Esfera", "Sphere"), [{ value: "", label: L("Todas as esferas", "Every sphere") }, ...["FEDERAL", "ESTADUAL", "MUNICIPAL"].map((v) => ({ value: v, label: SPH[v] }))], esfera, (v) => { esfera = v; setParam("esfera", v, ""); draw(); }));
    const agg = new Map();
    for (const b of r.bodies) {
      if ((lista && b.lista !== lista) || (esfera && b.esfera !== esfera)) continue;
      const k = `${b.orgao}|${b.esfera}|${b.uf}`, x = agg.get(k) || { label: b.orgao, esfera: b.esfera, uf: b.uf, value: 0, empresas: 0, vigentes: 0 };
      x.value += b.n; x.empresas += b.empresas; x.vigentes += b.vigentes; agg.set(k, x);
    }
    const rows = [...agg.values()].sort((a, b) => b.value - a.value).slice(0, 25);
    C.bars(c1, {
      rows: rows.map((x) => ({ ...x, label: short(abbr(x.label), 46), title: x.label, color: SPH_COLOR()[x.esfera] || css("--other"), note: `${SPH[x.esfera] || ""}${x.uf ? `, ${x.uf}` : ""} · ${L(`${pct(x.empresas / x.value)} a empresas`, `${pct(x.empresas / x.value)} companies`)}` })), labelWidth: 300,
      legend: ["FEDERAL", "ESTADUAL", "MUNICIPAL"].map((k) => ({ label: SPH[k], color: SPH_COLOR()[k] })),
      table: { rows, cols: [{ key: "label", label: L("Órgão", "Body"), text: true, wrap: true }, { key: "esfera", label: L("Esfera", "Sphere"), text: true, fmt: (v) => SPH[v] ?? v }, { key: "uf", label: "UF", text: true }, { key: "value", label: L("Sanções", "Sanctions") }, { key: "empresas", label: L("A empresas", "On companies") }, { key: "vigentes", label: L("Vigentes", "In force") }], name: "bodies" },
    });
  };
  later(draw);

  const c2 = chart(), c3 = chart();
  root.append(grid(
    card(L("Com base em que lei", "Under which law"), L("A lei que cada sanção cita. A Lei de Improbidade cobre as condenações judiciais enviadas pelo CNJ; as duas leis de licitações, as empresas que descumpriram um contrato ou uma licitação.", "The law each sanction cites. The improbidade law covers the court convictions sent by CNJ; the two procurement laws cover companies that failed a contract or a tender."), c2),
    card(L("Onde a sanção vale", "Where the sanction applies"), L("A abrangência que cada órgão sancionador registrou. Uma sanção limitada ao próprio órgão ou à própria esfera não impede a empresa de contratar em outro lugar.", "The scope each sanctioning body recorded. A sanction limited to its own body or sphere does not stop the company from contracting elsewhere."), c3)));
  const laws = r.laws.map((x) => ({ ...x, label: law(x) }));
  later(() => C.bars(c2, {
    rows: laws.map((x) => ({ label: x.label, value: x.n, note: L(`${pct(x.empresas / x.n)} a empresas`, `${pct(x.empresas / x.n)} on companies`), color: css("--line") })), labelWidth: 260,
    table: { rows: laws, cols: [{ key: "label", label: L("Lei", "Law"), text: true }, { key: "lei", label: L("Citada como", "Cited as"), text: true }, { key: "n", label: L("Sanções", "Sanctions") }, { key: "empresas", label: L("A empresas", "On companies") }], name: "laws" },
  }));
  const sc = new Map();
  for (const x of r.scope) sc.set(x.abrangencia, (sc.get(x.abrangencia) || 0) + x.n);
  const scRows = [...sc].map(([k, v]) => ({ label: SCOPE[k] || k || NOT_STATED, value: v, pt: k })).sort((a, b) => b.value - a.value);
  later(() => C.bars(c3, {
    rows: scRows.map((x) => ({ ...x, color: css("--line"), title: L(x.pt || x.label, `${x.label} (${x.pt})`) })), labelWidth: 230,
    table: { rows: scRows, cols: [{ key: "label", label: L("Abrangência", "Scope"), text: true }, { key: "pt", label: L("Como publicada", "Published as"), text: true }, { key: "value", label: L("Sanções", "Sanctions") }], name: "scope" },
  }));
  const tb = el("div"), c4 = chart();
  root.append(grid(
    card(L("Os artigos mais citados", "The articles cited most"), L("A lei e o artigo que cada sanção cita, como publicados.", "The law and article each sanction cites, as published."), tb),
    card(L("De onde vêm os registros", "Where the entries come from"), L("O órgão que enviou cada registro à CGU. O CNJ repassa as condenações judiciais por improbidade; o Ministério da Fazenda, as sanções de órgãos federais.", "The body that sent each entry to CGU. CNJ relays court convictions for improbidade; the Ministry of Finance relays the sanctions of federal bodies."), c4)));
  table(tb, r.articles, [{ key: "artigo", label: L("Lei e artigo", "Law and article"), text: true }, { key: "n", label: L("Sanções", "Sanctions") }], { sortBy: "n", pageSize: 10, name: "articles" });
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
    { label: L("Impedimento de contratar típico", "Typical contracting ban"), value: years(barred?.p50), sub: L("mediana, entre os impedimentos com data de fim", "median, among bans with an end date") },
    { label: L("Sanções sem data de fim", "Sanctions with no end date"), value: fmt(t.sem_prazo), sub: L(`${pct(t.sem_prazo / (t.ceis + t.cnep), 1)} das listadas`, `${pct(t.sem_prazo / (t.ceis + t.cnep), 1)} of the listed`) },
    { label: L("Até entrar na lista, federais", "Reaching the list, federal"), value: days(lagFed?.p50), sub: L("mediana de dias entre o início da sanção e o registro", "median days from the sanction's start to its record") },
    { label: L("Terminam em até 90 dias", "Ending within 90 days"), value: fmt(t.expirando), sub: L(`sanções a empresas, após ${r.snapshot}; e mais ${fmt(t.expirando_pessoas)} a pessoas`, `company sanctions, after ${r.snapshot}; plus ${fmt(t.expirando_pessoas)} on people`) },
  ]);
  let g = params.get("g") || "Barred from contracting", sph = params.get("s") || "FEDERAL";
  const ctl1 = el("div", { className: "controls" }), c1 = chart(), f1 = el("div");
  root.append(card(L("Quanto duram as sanções", "How long sanctions last"), L("Do início de cada sanção até a data de fim, para as que têm uma. Tracejado: a mediana e o percentil 90. A última barra reúne tudo o que dura dez anos ou mais.", "From each sanction's start to its end date, for sanctions that have one. Dashed: the median and the 90th percentile. The last bar holds everything of ten years or more."), ctl1, c1, f1));
  const drawDur = () => {
    const groups = r.duration.groups.filter((x) => x.n > 20);
    ctl1.replaceChildren(select(L("Tipo de sanção", "Kind of sanction"), groups.map((x) => ({ value: x.grupo, label: group(x.grupo) })), g, (v) => { g = v; setParam("g", v, "Barred from contracting"); drawDur(); }));
    const x = groups.find((y) => y.grupo === g) || groups[0];
    C.histogram(c1, { values: expand(x.hist, r.duration.edges, 0, 10), domain: [0, 10], bins: 40, format: (v) => fmt(v, Number.isInteger(v) ? 0 : 1), xLabel: L("anos (a última barra: dez ou mais)", "years (the last bar: ten or more)"), unit: L("sanções", "sanctions"), height: 220,
      refs: [{ x: x.p50, label: L(`mediana ${years(x.p50)}`, `median ${years(x.p50)}`) }, ...(x.p90 < 9.5 ? [{ x: x.p90, label: L(`percentil 90 ${years(x.p90)}`, `90th percentile ${years(x.p90)}`) }] : [])] });
    f1.replaceChildren(finding(L(`${fmt(x.n)} sanções de ${group(x.grupo, 1)} têm data de fim: um quarto dura ${years(x.p25)} ou menos; outro quarto, mais de ${years(x.p75)}. Outras ${fmt(x.sem_prazo)} não têm.`,
      `${fmt(x.n)} ${group(x.grupo, 1)} sanctions have an end date: a quarter last ${years(x.p25)} or less, a quarter more than ${years(x.p75)}. Another ${fmt(x.sem_prazo)} have none.`)));
  };
  later(drawDur);
  const ctl2 = el("div", { className: "controls" }), c2 = chart(), f2 = el("div");
  root.append(card(L("Quanto tempo uma sanção leva para entrar na lista", "How long a sanction takes to reach the list"), L("Dias entre o início da sanção e a data em que o registro foi criado na CGU. Abaixo de zero: registrada antes de começar. A última barra reúne todos os atrasos de dois anos ou mais.", "Days from the sanction's start to the date its record was created at CGU. Below zero: recorded before it began. The last bar holds every delay of two years or more."), ctl2, c2, f2));
  const SPH_PL = { FEDERAL: L("federais", "Federal"), ESTADUAL: L("estaduais", "State"), MUNICIPAL: L("municipais", "Municipal") };
  const drawLag = () => {
    ctl2.replaceChildren(select(L("Esfera do órgão sancionador", "Sanctioning sphere"), ["FEDERAL", "ESTADUAL", "MUNICIPAL"].map((v) => ({ value: v, label: SPH[v] })), sph, (v) => { sph = v; setParam("s", v, "FEDERAL"); drawLag(); }));
    const x = r.lag.spheres.find((y) => y.esfera === sph);
    C.histogram(c2, { values: expand(x.hist, r.lag.edges, -60, 750), domain: [-60, 750], bins: 27, format: (v) => fmt(v, 0), xLabel: L("dias", "days"), unit: L("sanções", "sanctions"), height: 220, refs: [{ x: x.p50, label: L(`mediana ${days(x.p50)}`, `median ${days(x.p50)}`) }] });
    f2.replaceChildren(finding(L(`Sanções ${SPH_PL[sph]}: metade entra na lista em até ${days(x.p50)}, três quartos em até ${days(x.p75)}; uma em cada dez leva mais de ${days(x.p90)}. Até lá, um comprador que consulta o CEIS não as vê.`,
      `${SPH_PL[sph]} sanctions: half reach the list within ${days(x.p50)}, three quarters within ${days(x.p75)}; one in ten takes more than ${days(x.p90)}. Until then, a buyer checking CEIS does not see them.`)));
  };
  later(drawLag);
  const tb = el("div");
  root.append(card(L("Sanções a empresas que terminam nos próximos 90 dias", "Company sanctions ending in the next 90 days"), L(`A data de fim cai entre ${r.snapshot} e 90 dias depois; passada essa data, a empresa pode voltar a contratar.`, `Their end date falls between ${r.snapshot} and 90 days later; once it passes, the company may contract again.`), tb));
  const soon = await data("site/sancoes/expirando.csv");
  table(tb, soon, [{ key: "fim", label: L("Termina", "Ends"), text: true, fmt: day }, companyCol(), { key: "lista", label: L("Lista", "List"), text: true },
    { key: "categoria", label: L("Sanção", "Sanction"), text: true, fmt: (v) => cat(v) }, { key: "orgao", label: L("Aplicada por", "Imposed by"), text: true, wrap: true }, { key: "uf", label: "UF", text: true }],
  { sortBy: "fim", desc: false, pageSize: 12, name: "ending-soon" });
}

// ------------------------------------------------------------ repeat offenders

async function repeat(root) {
  const r = await R(), rows = (await E()).filter((x) => n(x.ceis) + n(x.cnep) > 0).map((x) => ({ ...x, n: n(x.ceis) + n(x.cnep) }));
  const multi = rows.filter((x) => x.n >= 2), many = rows.filter((x) => x.n >= 5);
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Empresas com duas ou mais sanções", "Companies with two or more sanctions"), value: fmt(multi.length), sub: L(`${pct(multi.length / rows.length)} das empresas sancionadas`, `${pct(multi.length / rows.length)} of sanctioned companies`) },
    { label: L("Sua parcela das sanções", "Their share of all sanctions"), value: pct(sum(multi.map((x) => x.n)) / sum(rows.map((x) => x.n))), sub: L("de todas as sanções a empresas listadas", "of every company sanction listed") },
    { label: L("Cinco ou mais", "Five or more"), value: fmt(many.length), sub: L(`com ${fmt(sum(many.map((x) => x.n)))} sanções somadas`, `with ${fmt(sum(many.map((x) => x.n)))} sanctions between them`) },
    { label: L("Sancionadas em vários estados", "Sanctioned in several states"), value: fmt(rows.filter((x) => n(x.ufs) >= 2).length), sub: L("por órgãos de dois ou mais estados", "by bodies of two or more states") },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(
    card(L("Sanções por empresa", "Sanctions per company"), L("Empresas pelo número de registros do CEIS e do CNEP em seu nome.", "Companies by how many CEIS and CNEP entries name them."), c1),
    card(L("Sancionadas por muitos órgãos", "Sanctioned by many bodies"), L("As empresas sancionadas pelo maior número de órgãos diferentes. Cada órgão age sozinho, então uma empresa pode ser impedida por dezenas de compradores cujos contratos descumpriu.", "The companies sanctioned by the most different bodies. Each body acts alone, so one company can be barred by dozens of buyers it failed."), c2)));
  const dist = r.repeat.map((x) => ({ label: x.n >= 10 ? L("10 ou mais", "10 or more") : sanctions(x.n), value: x.empresas, color: css("--line") }));
  later(() => C.bars(c1, { rows: dist, labelWidth: 110 }));
  const top = [...rows].sort((a, b) => n(b.orgaos) - n(a.orgaos) || b.n - a.n).slice(0, 15);
  later(() => C.bars(c2, { rows: top.map((x) => ({ label: short(x.nome || WITHHELD, 36), title: x.nome || WITHHELD, value: n(x.orgaos), note: L(`${sanctions(x.n)} em ${plural(n(x.ufs), "estado", "estados")}`, `${sanctions(x.n)} in ${plural(n(x.ufs), "state", "states")}`), color: css("--line"), cnpj: x.cnpj })), labelWidth: 260, onClick: (x) => openCompany(x.cnpj) }));
  const tb = el("div");
  root.append(card(L("Todas as empresas com duas ou mais sanções", "Every company with two or more sanctions"), L("Clique num nome para ver o perfil da empresa: suas sanções ao longo do tempo e os contratos, as emendas e as vendas a campanhas que teve.", "Click a name for the company's profile: its sanctions over time, and the contracts, amendments and campaign sales it had."), tb));
  table(tb, multi, [companyCol(), { key: "cnpj", label: "CNPJ", text: true, fmt: (v) => day(cnpjFmt(v)) }, { key: "n", label: L("Sanções", "Sanctions") }, { key: "vigentes", label: L("Vigentes", "In force") },
    { key: "orgaos", label: L("Órgãos", "Bodies") }, { key: "ufs", label: L("Estados", "States") }, { key: "primeira", label: L("Primeira", "First"), text: true, fmt: day }, { key: "ultima", label: L("Última", "Latest"), text: true, fmt: day },
    { key: "emendas_sancionada", label: L("Emendas durante o impedimento", "Amendments while barred"), fmt: (v) => (n(v) ? brl(v) : "") }], { sortBy: "n", pageSize: 15, name: "repeat-offenders" });
}

// ------------------------------------------------------------ fines

async function fines(root) {
  const r = await R(), f = r.fines, t = r.tiles;
  const rows = await data("site/sancoes/multas.csv");
  const top = rows[0];
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Multas listadas", "Fines listed"), value: fmt(t.multas_n), sub: L("CNEP, pela Lei Anticorrupção", "CNEP, under the Anti-Corruption Law") },
    { label: L("Valor total", "Their total"), value: brl(t.multas_total), sub: L("o valor registrado, não o arrecadado", "as recorded, not as collected") },
    { label: L("Multa típica", "Typical fine"), value: brl(f.p50), sub: L(`mediana; um quarto acima de ${brl(f.p75)}`, `median; a quarter above ${brl(f.p75)}`) },
    { label: L("A maior", "Largest"), value: brl(top ? +top.multa : null), sub: top ? top.nome : "" },
  ]);
  const c1 = chart();
  root.append(card(L("O tamanho das multas", "How large the fines are"), L("Cada multa do CNEP acima de zero, em escala logarítmica: cada degrau vale dez vezes o anterior. Tracejado: a mediana.", "Every CNEP fine above zero on a logarithmic scale: each step is ten times the last. Dashed: the median."), c1));
  later(() => C.histogram(c1, { values: expand(f.log_hist, f.log_edges, 2, 10), domain: [2, 10], bins: 16, format: (v) => brl(10 ** v, 0), tickFormat: (v) => (Math.abs(v - Math.round(v)) < 1e-9 ? brl(10 ** v, 0) : ""), xLabel: L("multa (R$, escala logarítmica)", "fine (R$, log scale)"), unit: L("multas", "fines"), height: 220, refs: [{ x: Math.log10(f.p50), label: L(`mediana ${brl(f.p50)}`, `median ${brl(f.p50)}`) }] }));
  const c2 = chart(), c3 = chart();
  root.append(grid(card(L("Multas pelo ano de início da sanção", "Fines by the year the sanction began"), L("Valor total das multas ainda listadas.", "Total value of the fines still listed."), c2), card(L("Quem multa", "Who fines"), L("Os 15 órgãos com o maior valor total, e quantas multas cada um aplicou.", "The 15 bodies with the largest total, and how many fines each imposed."), c3)));
  const by = f.by_year.filter((x) => x.ano);
  later(() => C.stack(c2, { x: by.map((x) => x.ano), height: 220, format: (v) => brl(v, 0), series: [{ name: L("Total das multas", "Total fines"), color: css("--line"), values: by.map((x) => x.total) }],
    table: { rows: by, cols: [{ key: "ano", label: L("Ano", "Year"), text: true }, { key: "n", label: L("Multas", "Fines") }, { key: "total", label: "Total", fmt: (v) => brl(v) }], name: "fines-by-year" } }));
  later(() => C.bars(c3, { rows: f.by_body.map((x) => ({ label: short(abbr(x.orgao), 36), title: x.orgao, value: x.total, note: L(`${fmt(x.n)} multas`, `${fmt(x.n)} fines`), color: css("--line") })), labelWidth: 260, format: (v) => brl(v, 0) }));
  const tb = el("div");
  root.append(card(L("Todas as multas a empresas", "Every fine on a company"), L("Das maiores para as menores.", "Largest first."), tb));
  table(tb, rows, [companyCol(), { key: "multa", label: L("Multa", "Fine"), fmt: (v) => brl(v) }, { key: "inicio", label: L("Início", "From"), text: true, fmt: day }, { key: "orgao", label: L("Aplicada por", "Imposed by"), text: true, wrap: true }, { key: "uf", label: "UF", text: true }],
    { sortBy: "multa", pageSize: 12, name: "fines" });
}

// ------------------------------------------------------------ public money

async function money(root) {
  const r = await R(), m = r.money, A = r.authors;
  const pncp = Object.fromEntries(m.pncp.by_cobre.map((x) => [x.cobre, x]));
  const tseN = sum(m.tse.map((x) => x.sancionados)), tseV = sum(m.tse.map((x) => x.sancionados_total));
  const pncpDays = plural(m.pncp.days_read, L("dia", "day"), L("dias", "days"));
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Emendas pagas a empresas impedidas", "Amendments paid to barred companies"), value: brl(m.emendas.barrado), sub: L(`${fmt(m.emendas.empresas_barrado)} empresas; ${brl(m.emendas.barrado_sim)} sob sanção que vale para órgãos federais`, `${fmt(m.emendas.empresas_barrado)} companies; ${brl(m.emendas.barrado_sim)} under a sanction binding federal bodies`) },
    { label: L("Contratos assinados sob impedimento", "Contracts signed while barred"), value: fmt(sum(m.pncp.by_cobre.map((x) => x.contratos))), sub: L(`${fmt(pncp.sim?.contratos || 0)} em que a sanção vale para o comprador; PNCP lido até agora: ${pncpDays}`, `${fmt(pncp.sim?.contratos || 0)} where the sanction reaches the buyer; ${pncpDays} of PNCP read so far`) },
    { label: L("Fornecedores de campanha nas listas", "Campaign suppliers listed on election day"), value: fmt(tseN), sub: L(`no dia da eleição; ${brl(tseV)} em despesas de campanha, 2018–2026`, `${brl(tseV)} of campaign spending, 2018–2026`) },
    { label: L("Emendas a entidades hoje no CEPIM", "Amendments to non-profits now on CEPIM"), value: brl(m.cepim.total), sub: L(`${fmt(m.cepim.entidades)} entidades, pagas antes ou depois do impedimento`, `${fmt(m.cepim.entidades)} organisations, paid before or after they were barred`) },
  ]);

  const c1 = chart();
  root.append(card(L("Dinheiro de emendas pago a empresas enquanto estavam impedidas", "Amendment money paid to companies while they were barred"), L("Pagamentos de emendas parlamentares, por ano, a empresas que estavam sob uma sanção do CEIS ou do CNEP que as impedia de contratar. Uma empresa paga diretamente por emenda é paga por um órgão federal. Vermelho: a sanção valia para todos os órgãos federais. Âmbar: valia só para o próprio órgão federal, que pode ser o pagador. Cinza: sanção estadual ou municipal, que não obriga a União.", "Payments of parliamentary amendments, by year, to a company that was then under a CEIS or CNEP sanction barring it from contracting. A company paid directly by an amendment is paid by a federal body. Red: the sanction bound every federal body. Amber: it bound only its own federal body, which may be the payer. Grey: a state or municipal sanction, which does not bind the Union."), c1));
  const ey = m.emendas.by_year;
  later(() => C.stack(c1, { x: ey.map((x) => x.ano), height: 240, format: (v) => brl(v, 0),
    series: ["sim", "possivel", "nao"].map((k) => ({ name: FED[k], color: scopeColor(k), values: ey.map((x) => x[k]) })),
    table: { rows: ey, cols: [{ key: "ano", label: L("Ano", "Year"), text: true }, ...["sim", "possivel", "nao"].map((k) => ({ key: k, label: FED[k], fmt: (v) => brl(v) }))], name: "amendments-while-barred" } }));
  const since = m.emendas.first ? month(m.emendas.first) : "";
  c1.after(finding(L(`Dos ${brl(m.emendas.total)} em emendas pagos desde ${since} a empresas e organizações destas listas, ${brl(m.emendas.barrado)} (${pct(m.emendas.barrado / m.emendas.total, 1)}) foram pagos com uma sanção impeditiva vigente. Somando todas as emendas pagas, as emendas individuais de deputados e senadores pagaram a empresas impedidas ${perMillion(A.individual_per_million / 1e6)} a cada R$ 1 milhão (${perMillion(A.individual_sim_per_million / 1e6)} sob sanção que vale para órgãos federais).`,
    `Of the ${brl(m.emendas.total)} in amendments paid since ${since} to companies and organisations on these lists, ${brl(m.emendas.barrado)} (${pct(m.emendas.barrado / m.emendas.total, 1)}) was paid while a barring sanction was in force. Across all paid amendments, deputies' and senators' individual amendments paid barred companies ${perMillion(A.individual_per_million / 1e6)} for every R$ 1 million they paid (${perMillion(A.individual_sim_per_million / 1e6)} under a sanction binding federal bodies).`)));

  // party level
  const parties = await data("site/sancoes/partidos.csv");
  let measure = params.get("pm") || "share";
  const ctl = el("div", { className: "controls" }), c2 = chart();
  root.append(card(L("Por partido: quanto do dinheiro de emendas chegou a empresas impedidas", "By party: how much of their amendment money reached barred companies"), L("Para cada partido, as emendas individuais de seus deputados e senadores (partido no ano da emenda), pagas a qualquer favorecido. As barras mostram a parte paga a uma empresa enquanto ela estava impedida, a cada R$ 1 milhão pago. Só entram partidos cujas emendas pagaram pelo menos R$ 500 milhões. São valores pequenos: um único pagamento pode mudar a barra de um partido.", "For each party, the individual amendments of its deputies and senators (party in the amendment's year), paid to anyone. The bars show the part paid to a company while it was barred, per R$ 1 million paid. Parties whose members' amendments paid at least R$ 500 million. These are small sums: one payment can move a party's bar."), ctl, c2));
  const drawParties = () => {
    ctl.replaceChildren(select(L("Medida", "Measure"), [{ value: "share", label: L("Qualquer sanção impeditiva", "Any barring sanction") }, { value: "share_sim", label: L("Sanção que vale para órgãos federais", "A sanction binding federal bodies") }], measure, (v) => { measure = v; setParam("pm", v, "share"); drawParties(); }));
    const rows = parties.filter((x) => +x.pago_total >= 5e8).map((x) => ({ ...x, v: +x[measure] })).sort((a, b) => b.v - a.v);
    C.bars(c2, {
      rows: rows.map((x) => ({ label: x.partido, value: x.v * 1e6, note: L(`${brl(measure === "share" ? x.pago_sancionadas : x.pago_sim)} de ${brl(x.pago_total)} · ${x.autores_com_sancionadas} de ${x.autores} parlamentares · ${x.empresas_sancionadas} empresas`, `${brl(measure === "share" ? x.pago_sancionadas : x.pago_sim)} of ${brl(x.pago_total)} · ${x.autores_com_sancionadas} of ${x.autores} members · ${x.empresas_sancionadas} companies`), color: css("--line") })),
      labelWidth: 110, format: (v) => `R$ ${fmt(v)}`,
      table: { rows: parties, cols: [{ key: "partido", label: L("Partido", "Party"), text: true }, { key: "autores", label: L("Parlamentares", "Members") }, { key: "pago_total", label: L("Pago, total", "Paid, all"), fmt: (v) => brl(v) },
        { key: "pago_sancionadas", label: L("A empresas impedidas", "To barred companies"), fmt: (v) => brl(v) }, { key: "pago_sim", label: L("Sanção válida p/ órgãos federais", "Binding federal bodies"), fmt: (v) => brl(v) },
        { key: "share", label: L("A cada R$ 1 milhão", "Per R$ 1 million"), fmt: (v) => perMillion(+v) }, { key: "autores_com_sancionadas", label: L("Parlamentares envolvidos", "Members involved") }, { key: "empresas_sancionadas", label: L("Empresas", "Companies") }], name: "parties" },
    });
  };
  later(drawParties);

  // individual level
  const authors = (await data("site/sancoes/autores.csv")).filter((x) => +x.pago_sancionadas > 0);
  const ind = authors.filter((x) => x.kind === "deputado" || x.kind === "senador").sort((a, b) => +b.pago_sancionadas - +a.pago_sancionadas);
  const c3 = chart(), tb = el("div");
  root.append(grid(
    card(L("Os parlamentares cujas emendas mais pagaram empresas impedidas", "Members whose amendments paid barred companies most"), L("Deputados e senadores, pelo dinheiro de emendas pago a empresas enquanto elas estavam impedidas; partido no ano da emenda mais recente.", "Deputies and senators, by the amendment money paid to companies while those were barred; their party in their latest amendment year."), c3),
    card(L("Quem mais envia", "Who else sends it"), L("Emendas coletivas: bancadas estaduais, comissões e o relator-geral do Orçamento (o \"orçamento secreto\" de 2020–2022).", "Collective amendments: state benches, committees and the budget rapporteur (the 2020–2022 \"secret budget\")."), el("div", { id: "coll" }))));
  later(() => C.bars(c3, { rows: ind.slice(0, 15).map((x) => ({ label: `${title(x.autor)} (${x.partido || "?"}-${x.uf || "?"})`, value: +x.pago_sancionadas, note: L(`${pct(+x.share, 1)} dos ${brl(x.pago_total)} pagos por suas emendas · ${x.empresas_sancionadas} empresas`, `${pct(+x.share, 1)} of the ${brl(x.pago_total)} their amendments paid · ${x.empresas_sancionadas} companies`), color: css("--line") })), labelWidth: 250, format: (v) => brl(v, 1) }));
  const coll = authors.filter((x) => ["bancada", "comissao", "relator"].includes(x.kind)).sort((a, b) => +b.pago_sancionadas - +a.pago_sancionadas);
  later(() => C.bars($("#coll", root), { rows: coll.slice(0, 15).map((x) => ({ label: short(title(x.autor), 30), title: x.autor, value: +x.pago_sancionadas, note: `${KIND[x.kind]} · ${pct(+x.share, 2)} ${L("de", "of")} ${brl(x.pago_total)}`, color: css("--other") })), labelWidth: 250, format: (v) => brl(v, 1) }));
  root.append(card(L("Todos os autores cujas emendas pagaram uma empresa impedida", "Every author whose amendments paid a barred company"), L("Parcela: a parte de tudo o que suas emendas pagaram que foi para empresas impedidas.", "Share: the part of everything their amendments paid that went to companies while barred."), tb));
  table(tb, authors, [{ key: "autor", label: L("Autor", "Author"), text: true, fmt: title }, { key: "kind", label: L("Tipo", "Kind"), text: true, fmt: (v) => KIND[v] || v }, { key: "partido", label: L("Partido", "Party"), text: true }, { key: "uf", label: "UF", text: true },
    { key: "pago_total", label: L("Pago, total", "Paid, all"), fmt: (v) => brl(v) }, { key: "pago_sancionadas", label: L("A empresas impedidas", "To barred companies"), fmt: (v) => brl(v) }, { key: "share", label: L("Parcela", "Share"), fmt: (v) => pct(+v, 2) },
    { key: "pago_sim", label: L("Sanção válida p/ órgãos federais", "Binding federal bodies"), fmt: (v) => brl(v) }, { key: "empresas_sancionadas", label: L("Empresas", "Companies") }], { sortBy: "pago_sancionadas", pageSize: 12, name: "authors" });

  const comps = (await E()).filter((x) => +x.emendas_sancionada > 0).sort((a, b) => +b.emendas_sancionada - +a.emendas_sancionada);
  const tc = el("div");
  root.append(card(L("Empresas pagas por emendas enquanto impedidas", "Companies paid by amendments while barred"), L("Clique num nome para ver as emendas de quais parlamentares a pagaram e quando suas sanções vigoraram.", "Click a name to see which members' amendments paid it, and when its sanctions ran."), tc));
  table(tc, comps, [companyCol(), { key: "emendas_sancionada", label: L("Durante o impedimento", "While barred"), fmt: (v) => brl(v) }, { key: "emendas", label: L("Todas as emendas", "All amendments"), fmt: (v) => brl(v) },
    { key: "ceis", label: "CEIS" }, { key: "cnep", label: "CNEP" }, { key: "orgaos", label: L("Órgãos", "Bodies") }], { sortBy: "emendas_sancionada", pageSize: 10, name: "companies-amendments" });

  const c4 = chart(), tp = el("div");
  root.append(card(L("Contratos públicos assinados com o fornecedor impedido (PNCP)", "Public contracts signed while the supplier was barred (PNCP)"), L(`Contratos publicados no PNCP cujo fornecedor estava, no dia da assinatura, sob uma sanção que o impedia de contratar. O histórico do PNCP ainda está sendo lido (${pncpDays} até agora, de ${m.pncp.first_day} a ${m.pncp.last_day}). A maior parte dos casos são sanções limitadas a outro órgão ou esfera, que não impedem o contrato.`, `Contracts published on the PNCP whose supplier was under a sanction barring contracting on the day it was signed. The PNCP history is still being read (${pncpDays} so far, ${m.pncp.first_day} to ${m.pncp.last_day}). Most matches are sanctions limited to another body or sphere, which do not stop the contract.`), c4, tp));
  const pr = ["sim", "possivel", "nao"].map((k) => ({ k, ...(pncp[k] || { contratos: 0, valor: 0, empresas: 0 }) }));
  later(() => C.bars(c4, { rows: pr.map((x) => ({ label: COBRE[x.k], value: x.contratos, note: L(`${brl(x.valor)} · ${fmt(x.empresas)} fornecedores`, `${brl(x.valor)} · ${fmt(x.empresas)} suppliers`), color: scopeColor(x.k) })), labelWidth: 190 }));
  table(tp, m.pncp.flagged, [{ key: "assinatura", label: L("Assinatura", "Signed"), text: true, fmt: day }, { key: "fornecedor_nome", label: L("Fornecedor", "Supplier"), text: true, wrap: true, fmt: (v, x) => companyLink(v, x.fornecedor) },
    { key: "orgao", label: L("Órgão comprador", "Buyer"), text: true, wrap: true }, { key: "uf", label: "UF", text: true }, { key: "valor_global", label: L("Valor", "Value"), fmt: (v) => brl(v) },
    { key: "cobre", label: L("Abrangência", "Scope"), text: true, fmt: (v) => COBRE[v] }, { key: "categoria_sancao", label: L("Sanção", "Sanction"), text: true, fmt: (v) => cat(v) }, { key: "orgao_sancionador", label: L("Aplicada por", "Imposed by"), text: true, wrap: true }],
  { sortBy: "valor_global", pageSize: 8, name: "contracts-while-barred" });

  const tt = el("div");
  root.append(card(L("Fornecedores de campanha que estavam nas listas no dia da eleição", "Campaign suppliers that were on the lists on election day"), L("Empresas pagas por campanhas de candidatos (TSE) enquanto estavam sob uma sanção que as impedia de contratar com o poder público. Campanha não é contrato público, então nada proíbe; é contexto. O número de 2026 é maior em parte porque as sanções recentes ainda não expiraram.", "Companies paid by candidates' campaigns (TSE) while under a sanction barring them from public contracts. Campaigns are not public contracts, so nothing forbids it; it is context. The 2026 count is larger partly because recent sanctions have not expired yet."), tt));
  table(tt, m.tse_list, [{ key: "ano", label: L("Eleição", "Election"), text: true }, companyCol(), { key: "total", label: L("Despesas de campanha", "Campaign spending"), fmt: (v) => brl(v) }, { key: "n_candidatos", label: L("Candidatos", "Candidates") }],
    { sortBy: "total", pageSize: 10, name: "campaign-suppliers" });
}

// ------------------------------------------------------------ CEPIM

const MOTIVO = {
  "INSTAURACAO DE TOMADA DE CONTAS ESPECIAL": L("Tomada de contas especial", "Special audit opened (TCE)"), "MOTIVO NÃO ESPECIFICADO": L("Motivo não especificado", "Not specified"),
  "NAO APRESENTACAO DE DOCUMENTACAO COMPLEMENTAR": L("Sem documentação complementar", "Missing supporting documents"), "NAO APRESENTACAO DA PRESTACAO DE CONTAS": L("Não prestou contas", "No accounts rendered"),
  "IRREGULARIDADE NA EXECUCAO FINANCEIRA": L("Má execução financeira", "Irregular financial execution"), "IRREGULARIDADE NA EXECUCAO FIS. E FINANCEIRA": L("Má execução físico-financeira", "Irregular physical and financial execution"),
  "NAO EXECUTOU TOTALMENTE O OBJETO PACTUADO": L("Não executou todo o objeto", "Did not deliver what was agreed"), "INSCRICAO POR DECISAO DO T.C.U.": L("Inscrita por decisão do TCU", "Listed by a TCU ruling"),
  "TEVE A PRESTACAO DE CONTAS IMPUGNADA": L("Prestação de contas impugnada", "Accounts rejected"), "ATRASO NA ENTREGA DA PRESTACAO DE CONTAS": L("Atraso na prestação de contas", "Accounts rendered late"),
  "ATRASO NA DEVOLUCAO DE RECURSOS": L("Atraso ao devolver recursos", "Funds returned late"), "IRREGULARIDADE NA EXECUCAO FISICA DO OBJETO": L("Má execução física do objeto", "Irregular physical execution"),
  "DESCUMPRIMENTO DE CLAUSULA/CONDICAO DO INSTR.": L("Descumprimento de cláusula do convênio", "Breach of a term of the agreement"), "UTILIZOU OS RECURSOS EM DESACORDO C/PROG TRAB": L("Uso dos recursos fora do plano de trabalho", "Funds spent outside the work plan"),
  "DESCUMPRIMENTO DE PRECEITOS DA LEI NR.8666/93": L("Descumprimento da Lei 8.666/93", "Breach of Law 8.666/93"), "NAO CUMPRIU COM OS RECURSOS DA CONTRAPARTIDA": L("Não aportou a contrapartida", "Matching funds not provided"),
  "NAO APRESENTOU O RELATORIO FISICO-FINANCEIRO": L("Não apresentou o relatório físico-financeiro", "No physical-financial report"), "PENDENTE DE CLASSIFICACAO DE MOTIVO": L("Motivo ainda não classificado", "Reason not yet classified"),
};

async function cepim(root) {
  const r = await R(), c = r.cepim, m = r.money.cepim;
  const ents = (await E()).filter((x) => n(x.cepim) > 0);
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Entidades impedidas", "Non-profits barred"), value: fmt(r.tiles.cepim_entidades), sub: L(`de firmar novos convênios federais, em ${r.cepim_snapshot}`, `from new federal agreements, as of ${r.cepim_snapshot}`) },
    { label: L("Convênios envolvidos", "Agreements behind it"), value: fmt(r.tiles.cepim), sub: L("um registro por convênio que deu errado", "one entry per agreement that went wrong") },
    { label: L("Ministério com mais registros", "Most from one ministry"), value: c.orgaos[0] ? fmt(c.orgaos[0].n) : "0", sub: c.orgaos[0] ? c.orgaos[0].orgao_concedente.replace(" - Unidades com vínculo direto", "") : "" },
    { label: L("Dinheiro de emendas recebido", "Amendment money they received"), value: brl(m.total), sub: L(`${fmt(m.entidades)} delas, em qualquer época`, `${fmt(m.entidades)} of them, at any time`) },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(card(L("Convênios de qual ministério", "Which ministry's agreements"), L("Registros pelo ministério que assinou o convênio.", "Entries by the ministry that signed the agreement."), c1), card(L("Por que foram impedidas", "Why they were barred"), L("O motivo registrado, em redação simplificada.", "The reason recorded, translated."), c2)));
  later(() => C.bars(c1, { rows: c.orgaos.map((x) => ({ label: short(abbr(x.orgao_concedente), 40), title: x.orgao_concedente, value: x.n, note: L(`${fmt(x.entidades)} entidades`, `${fmt(x.entidades)} organisations`), color: css("--line") })), labelWidth: 250 }));
  later(() => C.bars(c2, { rows: c.motivos.map((x) => ({ label: MOTIVO[x.motivo_do_impedimento] || x.motivo_do_impedimento, value: x.n, title: x.motivo_do_impedimento, color: css("--line") })), labelWidth: 250 }));
  const c3 = chart();
  root.append(card(L("Emendas pagas a entidades hoje no CEPIM", "Amendments paid to organisations now on CEPIM"), L("Por ano de pagamento. O CEPIM não registra datas, então podem ser pagamentos feitos antes de a entidade ser impedida: a pergunta é se o dinheiro que deu errado veio de emendas.", "By payment year. CEPIM records no dates, so these may be payments made before the organisation was barred: the question is whether the money that went wrong came from amendments."), c3));
  later(() => C.stack(c3, { x: m.by_year.map((x) => x.ano), height: 200, format: (v) => brl(v, 0), series: [{ name: L("Pago", "Paid"), color: css("--line"), values: m.by_year.map((x) => x.valor) }],
    table: { rows: m.by_year, cols: [{ key: "ano", label: L("Ano", "Year"), text: true }, { key: "valor", label: L("Pago", "Paid"), fmt: (v) => brl(v) }, { key: "entidades", label: L("Entidades", "Organisations") }], name: "cepim-amendments" } }));
  const tb = el("div");
  root.append(card(L("Todas as entidades no CEPIM", "Every organisation on CEPIM"), "", tb));
  table(tb, ents, [companyCol("nome", L("Entidade", "Organisation")), { key: "cnpj", label: "CNPJ", text: true, fmt: (v) => day(cnpjFmt(v)) }, { key: "cepim", label: L("Convênios", "Agreements") }, { key: "emendas", label: L("Emendas recebidas", "Amendments received"), fmt: (v) => (n(v) ? brl(v) : "") }, { key: "ceis", label: L("Também no CEIS", "Also on CEIS") }],
    { sortBy: "cepim", pageSize: 12, name: "cepim" });
}

// ------------------------------------------------------------ leniency

async function leniency(root) {
  const r = await R(), Le = r.leniency, rows = await data("site/sancoes/leniencia.csv");
  const brlRows = rows.filter((x) => x.moeda === "BRL" && x.valor_total !== "");
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Acordos de leniência", "Leniency agreements"), value: fmt(r.tiles.acordos), sub: L(`envolvendo ${fmt(r.tiles.acordos_empresas)} empresas`, `covering ${fmt(r.tiles.acordos_empresas)} companies`) },
    { label: L("Valores acordados", "Amounts agreed"), value: brl(Le.brl_total), sub: L(`em reais, nos ${brlRows.length} acordos cujos termos trazem um total`, `in reais, the ${brlRows.length} agreements whose terms state a total`) },
    { label: L("Dos quais, multas", "Of which fines"), value: brl(Le.brl_multa), sub: L("a parte que os termos chamam de multa", "the part the terms call a fine") },
    { label: L("Ainda em execução", "Still being carried out"), value: fmt(Le.status.find((x) => x.situacao === "Em Execução")?.n || 0), sub: L(`acordos ainda não cumpridos, de ${fmt(r.tiles.acordos)}`, `agreements not yet fulfilled, of ${fmt(r.tiles.acordos)}`) },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(card(L("Acordos pelo ano de assinatura", "Agreements by the year they were signed"), "", c1), card(L("O que as empresas ganharam, e deram", "What the companies got, and gave"), L("Quantos acordos incluem cada efeito.", "How many agreements include each effect."), c2)));
  later(() => C.stack(c1, { x: Le.by_year.map((x) => x.ano), height: 200, series: [{ name: L("Acordos", "Agreements"), color: css("--line"), values: Le.by_year.map((x) => x.n) }] }));
  later(() => C.bars(c2, { rows: Le.effects.map((x) => ({ label: effect(x.efeito), value: x.n, title: x.efeito, color: css("--line") })), labelWidth: 280 }));
  const c3 = chart();
  root.append(card(L("Os maiores acordos", "The largest agreements"), L("Valores totais em reais como os termos os trazem, incluindo ressarcimento e multas; os acordos em euros ou dólares estão na tabela.", "Total amounts in reais as their terms state them, which include restitution and fines; agreements in euros or dollars are in the table."), c3));
  const big = [...brlRows].sort((a, b) => +b.valor_total - +a.valor_total).slice(0, 15);
  later(() => C.bars(c3, { rows: big.map((x) => ({ label: short(agreement(x.nome), 36), title: x.empresas, value: +x.valor_total, note: L(`${x.inicio.slice(0, 4)} · multa ${brl(x.multa)}`, `${x.inicio.slice(0, 4)} · fine ${brl(x.multa)}`), color: css("--line") })), labelWidth: 280, format: (v) => brl(v, 1) }));
  const tb = el("div");
  root.append(card(L("Todos os acordos", "Every agreement"), "", tb));
  table(tb, rows, [{ key: "inicio", label: L("Assinatura", "Signed"), text: true, fmt: day }, { key: "nome", label: L("Acordo", "Agreement"), text: true, fmt: agreement }, { key: "empresas", label: L("Empresas", "Companies"), text: true, wrap: true }, { key: "situacao", label: L("Situação", "Status"), text: true, fmt: (v) => day(STATUS[v] || v) },
    { key: "valor_total", label: "Total", fmt: (v, x) => (v === "" ? "" : x.moeda === "BRL" ? brl(v) : L(`${x.moeda} ${fmt(+v / 1e6, 1)} mi`, `${x.moeda} ${fmt(+v / 1e6, 1)} M`)) }, { key: "multa", label: L("Multa", "Fine"), fmt: (v) => (v === "" ? "" : brl(v)) },
    { key: "efeitos", label: L("Efeitos", "Effects"), text: true, wrap: true, fmt: (v) => v.split("; ").map(effect).join("; ") }], { sortBy: "inicio", pageSize: 10, name: "leniency" });
}

// ------------------------------------------------------------ changes

async function changes(root) {
  const r = await R(), ch = await data("site/sancoes/mudancas.csv"), recent = await data("site/sancoes/recentes.csv");
  const ins = sum(ch.filter((x) => x.mudanca === "entrou").map((x) => +x.n)), outs = sum(ch.filter((x) => x.mudanca === "saiu").map((x) => +x.n));
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Histórico desde", "Recorded since"), value: "2026-11-06", sub: L("CEPIM desde 2026-10-28", "CEPIM since 2026-10-28") },
    { label: L("Registros incluídos", "Entries added"), value: fmt(ins), sub: L("sanções que entraram em uma lista", "sanctions that appeared in a list") },
    { label: L("Registros retirados", "Entries removed"), value: fmt(outs), sub: L("vencidas, revogadas ou corrigidas", "expired, lifted or corrected") },
    { label: L("Última mudança", "Latest change"), value: r.changes.last || L("nenhuma ainda", "none yet"), sub: L(`última captura em ${r.snapshot}`, `latest snapshot ${r.snapshot}`) },
  ]);
  const c1 = chart();
  root.append(card(L("Entradas e saídas por dia", "Entries and exits per day"), L("A CGU substitui cada lista todos os dias e não guarda histórico; o political-eye compara a captura de cada dia com a última registrada. Cada dia é datado pela captura, não pelo dia em que a rotina rodou.", "CGU replaces each list every day and keeps no history; political-eye compares each day's snapshot with the last one recorded. A day is dated by the snapshot, not by the day the job ran."), c1));
  if (!ch.length) c1.append(el("p", { className: "empty", textContent: L("Nenhuma mudança registrada ainda: a primeira captura é a base, e cada dia seguinte acrescenta um ponto aqui.", "No change recorded yet: the first snapshot is the baseline, and each later day adds a point here.") }));
  else {
    const daysAll = [...new Set(ch.map((x) => x.data))].sort();
    const s = (what, name, color) => ({ name, color, points: daysAll.map((d) => [d, sum(ch.filter((x) => x.data === d && x.mudanca === what).map((x) => +x.n))]) });
    later(() => C.line(c1, { x: "day", height: 220, series: [s("entrou", L("Incluídas", "Added"), C.slot(1)), s("saiu", L("Retiradas", "Removed"), C.slot(2))] }));
  }
  const tb = el("div");
  root.append(card(L("As últimas mudanças envolvendo empresas", "The latest changes about companies"), L("Os registros de pessoas entram na contagem acima, mas não são listados.", "People's entries are counted above but not listed."), tb));
  table(tb, recent, [{ key: "data", label: L("Dia", "Day"), text: true, fmt: day }, { key: "lista", label: L("Lista", "List"), text: true }, { key: "mudanca", label: L("Mudança", "Change"), text: true, fmt: (v) => (v === "entrou" ? L("Incluída", "Added") : L("Retirada", "Removed")) }, companyCol()],
    { sortBy: "data", pageSize: 15, name: "changes" });
}

// ------------------------------------------------------------ one company

function timeline(box, o) {
  box.replaceChildren();
  const rows = o.rows;
  if (!rows.length) { box.append(el("p", { className: "empty", textContent: L("Nenhuma sanção com data.", "No dated sanction.") })); return; }
  const w = Math.max(300, box.clientWidth || 600), lw = Math.round(Math.min(210, w * 0.3)), mr = 12, rh = 18, mt = 4, mb = 24, H = mt + rh * (rows.length + o.lanes.length) + mb;
  const s = C.svg("svg", { width: w, height: H, role: "img" });
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
    const lab = C.svg("text", { x: lw - 6, y: y + rh / 2 + 4, "text-anchor": "end", "font-size": 11, fill: ink2 }); const fit = Math.floor((lw - 8) / 6.2); lab.textContent = x.label.length > fit ? `${x.label.slice(0, fit - 1)}…` : x.label; s.append(lab);
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
  const input = el("input", { type: "search", placeholder: L("Nome da empresa ou CNPJ…", "Company name or CNPJ…"), autocomplete: "off", style: "min-width:320px" });
  const results = el("ul", { className: "search-results" }), out = el("div");
  root.append(el("div", { className: "controls" }, el("label", {}, L("Busque uma empresa ou entidade sancionada", "Find a sanctioned company or organisation"), input)), results, out);
  const index = all.map((x) => [norm(x.nome), x]);
  input.addEventListener("input", () => {
    const q = norm(input.value.trim()), digits = input.value.replace(/\D/g, "");
    if (q.length < 3 && digits.length < 4) { results.replaceChildren(); return; }
    const hits = (digits.length >= 4 && digits.length === input.value.replace(/[\s./-]/g, "").length ? all.filter((x) => x.cnpj.startsWith(digits)) : index.filter(([k]) => k.includes(q)).map(([, x]) => x)).slice(0, 12);
    results.replaceChildren(...(hits.length ? hits.map((x) => el("li", {}, el("button", { type: "button", on: { click: () => { results.replaceChildren(); input.value = ""; openCompany(x.cnpj); } } },
      el("span", { textContent: x.nome || WITHHELD }), el("span", { className: "n", textContent: `${cnpjFmt(x.cnpj)} · ${sanctions(n(x.ceis) + n(x.cnep))}${n(x.cepim) ? ` · CEPIM ${x.cepim}` : ""}` })))) : [el("li", { className: "hint", textContent: L("Nenhuma empresa sancionada com esse nome ou CNPJ.", "No sanctioned company matches.") })]));
  });

  const leni = await data("site/sancoes/leniencia.csv");
  const show = async (cnpj) => {
    const x = byCnpj.get(cnpj);
    if (!x) { out.replaceChildren(el("p", { className: "empty", textContent: L("Este CNPJ não está em nenhuma das listas.", "This CNPJ is on none of the lists.") })); return; }
    const shard = await data(`site/sancoes/empresas/${cnpj.slice(0, 2)}.json`), d = shard[cnpj] || {};
    const S = (d.s || []).map(([lista, codigo, categoria, inicio, fim, orgao, esfera, uf, abrangencia, multa, processo, artigo]) => ({ lista, codigo, categoria, inicio, fim, orgao, esfera, uf, abrangencia, multa, processo, artigo }));
    const Cn = (d.c || []).map(([assinatura, orgao, esfera, uf, objeto, valor, cobre, controle]) => ({ assinatura, orgao, esfera, uf, objeto, valor, cobre, controle }));
    const Em0 = new Map((d.e || []).map(([ano, total, sancionada, sim]) => [+ano, { ano: String(ano), total, sancionada, sim }]));
    const ys = [...Em0.keys()], Em = ys.length ? Array.from({ length: Math.max(...ys) - Math.min(...ys) + 1 }, (_, i) => Em0.get(Math.min(...ys) + i) || { ano: String(Math.min(...ys) + i), total: 0, sancionada: 0, sim: 0 }) : [];
    const Au = (d.a || []).map(([autor, partido, uf, valor, sanc]) => ({ autor, partido, uf, valor, sanc }));
    const T = (d.t || []).map(([ano, total, n_candidatos, barrado]) => ({ ano, total, n_candidatos, barrado }));
    const P = (d.p || []).map(([convenio, orgao, motivo]) => ({ convenio, orgao, motivo }));
    const Ls = leni.filter((l) => (d.l || []).includes(l.id));
    const lists = [n(x.ceis) && "CEIS", n(x.cnep) && "CNEP", n(x.cepim) && "CEPIM", n(x.leniencia) && L("Leniência", "Leniency")].filter(Boolean);
    const box = el("div");
    box.append(el("div", { className: "profile-head" }, el("h2", { textContent: x.nome || WITHHELD }),
      el("span", { className: "doc" }, cnpjFmt(cnpj), " ", ...lists.map((l) => el("span", { className: "pill", textContent: l })))));
    if (/^\d{14}$/.test(cnpj)) box.append(el("p", { className: "about" }, el("a", { href: `../empresas/?cnpj=${cnpj}`, textContent: L("Todos os contratos, emendas, campanhas e sinais de alerta desta empresa, numa só ficha →", "All of this company's contracts, amendments, campaigns and red flags, in one profile →") })));
    if (!x.nome) box.append(el("p", { className: "about", textContent: L("Uma empresa individual (empresário individual ou MEI) leva o nome do dono; por isso esta página mostra o CNPJ e as sanções, mas não o nome.", "An individual firm (empresário individual or MEI) carries its owner's name, so this page shows its CNPJ and sanctions but not the name.") }));
    const tl = el("section", { className: "tiles" });
    box.append(tl);
    tiles(tl, [
      { label: L("Sanções listadas", "Sanctions listed"), value: fmt(S.length), sub: L(`${fmt(x.vigentes)} ${n(x.vigentes) === 1 ? "vigente" : "vigentes"} em ${r.snapshot}${n(x.barra) ? ", impedindo contratos" : ""}`, `${fmt(x.vigentes)} in force on ${r.snapshot}${n(x.barra) ? ", barring contracts" : ""}`) },
      { label: L("Órgãos que a sancionaram", "Bodies that sanctioned it"), value: fmt(x.orgaos), sub: n(x.ufs) ? L(`em ${plural(+x.ufs, "estado", "estados")}`, `in ${plural(+x.ufs, "state")}`) : L("federais, ou sem UF registrada", "federal, or no state recorded") },
      { label: L("Dinheiro de emendas recebido", "Amendment money received"), value: brl(n(x.emendas)), sub: n(x.emendas_sancionada) ? L(`${brl(x.emendas_sancionada)} durante o impedimento`, `${brl(x.emendas_sancionada)} while barred`) : L("nada durante o impedimento", "none while barred") },
      { label: L("Grandes contratos públicos", "Large public contracts"), value: fmt(x.contratos), sub: n(x.contratos_sancionada) ? L(`${fmt(x.contratos_sancionada)} assinados durante o impedimento`, `${fmt(x.contratos_sancionada)} signed while barred`) : L("PNCP, R$ 1 mi ou mais, histórico em leitura", "PNCP, R$ 1 M or more, history being read") },
    ]);
    const tlc = chart();
    box.append(card(L("Suas sanções ao longo do tempo", "Its sanctions over time"), L("Cada barra é uma sanção, do início ao fim; as barras claras não têm data de fim e vão até hoje (linha tracejada). Abaixo: os pagamentos de emendas que recebeu, por ano, e seus grandes contratos públicos.", "Each bar is a sanction, from its start to its end; faded bars have no end date and run to today (dashed line). Below: the amendment payments it received, by year, and its large public contracts."), tlc));
    const pays = Em.filter((e) => e.total > 0);
    const maxPay = Math.max(1, ...pays.map((e) => e.total));
    const drawTl = () => timeline(tlc, {
      today: r.snapshot,
      rows: S.filter((s0) => s0.inicio).map((s0) => ({ label: cat(s0.categoria), from: s0.inicio, to: s0.fim, color: /^(Impedimento|Declaração de Inidoneidade|Suspensão$)/.test(s0.categoria) ? css("--critical") : css("--other"),
        title: `${s0.lista}: ${cat(s0.categoria)}`, tip: [L(`${s0.inicio} a ${s0.fim || "sem data de fim"}`, `${s0.inicio} to ${s0.fim || "no end date"}`), s0.orgao, SCOPE[s0.abrangencia] || s0.abrangencia, s0.multa ? L(`multa ${brl(s0.multa)}`, `fine ${brl(s0.multa)}`) : ""].filter(Boolean) })),
      lanes: [
        { label: L("Emendas pagas", "Amendments paid"), points: pays.map((e) => ({ date: `${e.ano}-07-01`, r: 3 + 6 * Math.sqrt(e.total / maxPay), color: e.sancionada > 0 ? css("--critical") : css("--line"), title: `${e.ano}: ${brl(e.total)}`, tip: e.sancionada ? [L(`${brl(e.sancionada)} durante o impedimento`, `${brl(e.sancionada)} while barred`)] : [] })) },
        { label: L("Contratos assinados", "Contracts signed"), points: Cn.filter((c0) => c0.assinatura).map((c0) => ({ date: c0.assinatura, color: c0.cobre ? scopeColor(c0.cobre) : css("--line"), title: `${c0.assinatura}: ${brl(c0.valor)}`, tip: [c0.orgao, c0.objeto, c0.cobre ? L(`durante o impedimento: ${COBRE[c0.cobre]}`, `while barred: ${COBRE[c0.cobre]}`) : ""].filter(Boolean) })) },
      ],
      legend: [{ label: L("Impedida de contratar", "Barred from contracting"), color: css("--critical") }, { label: L("Outra sanção", "Other sanction"), color: css("--other") }, { label: L("Pagamento ou contrato", "Payment or contract"), color: css("--line") }],
    });
    out.replaceChildren(box);
    drawTl();
    redraws.push(drawTl);
    const ts = el("div");
    box.append(card(L("Todas as sanções", "Every sanction"), "", ts));
    table(ts, S, [{ key: "lista", label: L("Lista", "List"), text: true }, { key: "categoria", label: L("Sanção", "Sanction"), text: true, fmt: (v) => cat(v) }, { key: "inicio", label: L("Início", "From"), text: true, fmt: day }, { key: "fim", label: L("Fim", "To"), text: true, fmt: day },
      { key: "orgao", label: L("Aplicada por", "Imposed by"), text: true, wrap: true }, { key: "uf", label: "UF", text: true }, { key: "abrangencia", label: L("Abrangência", "Scope"), text: true, fmt: (v) => SCOPE[v] || v }, { key: "artigo", label: L("Fundamento legal", "Legal ground"), text: true, wrap: true },
      { key: "multa", label: L("Multa", "Fine"), fmt: (v) => (v ? brl(v) : "") }], { sortBy: "inicio", pageSize: 10, name: `sanctions-${cnpj}` });
    if (Em.length || Au.length) {
      const ce = chart(), ta = el("div");
      box.append(grid(card(L("Dinheiro de emendas recebido, por ano", "Amendment money it received, by year"), L("Vermelho: pago com uma sanção impeditiva vigente.", "Red: paid while a barring sanction was in force."), ce), card(L("Emendas de quem a pagaram", "Whose amendments paid it"), L("Autores das emendas por trás dos pagamentos; partido no ano da emenda.", "Authors of the amendments behind its payments; their party in the amendment's year."), ta)));
      const draw = () => C.stack(ce, { x: Em.map((e) => e.ano), height: 200, format: (v) => brl(v, 0), series: [{ name: L("Durante o impedimento", "While barred"), color: css("--critical"), values: Em.map((e) => e.sancionada) }, { name: L("Fora do impedimento", "Otherwise"), color: css("--line"), values: Em.map((e) => e.total - e.sancionada) }] });
      draw(); redraws.push(draw);
      table(ta, Au, [{ key: "autor", label: L("Autor", "Author"), text: true, fmt: title }, { key: "partido", label: L("Partido", "Party"), text: true }, { key: "uf", label: "UF", text: true }, { key: "valor", label: L("Pago", "Paid"), fmt: (v) => brl(v) }, { key: "sanc", label: L("Durante o impedimento", "While barred"), fmt: (v) => (v ? brl(v) : "") }],
        { sortBy: "valor", pageSize: 8, search: false, name: `authors-${cnpj}` });
    }
    if (Cn.length) {
      const tc = el("div");
      box.append(card(L("Seus contratos públicos no PNCP", "Its public contracts on the PNCP"), L("Contratos de R$ 1 milhão ou mais, e qualquer contrato assinado enquanto estava impedida.", "Contracts of R$ 1 million or more, and any contract signed while it was barred."), tc));
      table(tc, Cn, [{ key: "assinatura", label: L("Assinatura", "Signed"), text: true, fmt: day }, { key: "orgao", label: L("Órgão comprador", "Buyer"), text: true, wrap: true }, { key: "uf", label: "UF", text: true }, { key: "objeto", label: L("Objeto", "Object"), text: true, wrap: true },
        { key: "valor", label: L("Valor", "Value"), fmt: (v) => brl(v) }, { key: "cobre", label: L("Durante o impedimento", "While barred"), text: true, fmt: (v) => (v ? COBRE[v] : "") }], { sortBy: "assinatura", pageSize: 8, name: `contracts-${cnpj}` });
    }
    if (T.length) {
      const tt = el("div");
      box.append(card(L("Suas vendas a campanhas eleitorais", "Its sales to election campaigns"), L("Quanto os candidatos lhe pagaram, por eleição (TSE).", "What candidates paid it, by election (TSE)."), tt));
      table(tt, T, [{ key: "ano", label: L("Eleição", "Election"), text: true }, { key: "total", label: L("Pago pelas campanhas", "Paid by campaigns"), fmt: (v) => brl(v) }, { key: "n_candidatos", label: L("Candidatos", "Candidates") }, { key: "barrado", label: L("Listada no dia da eleição", "Listed on election day"), text: true, fmt: (v) => (v ? L("sim", "yes") : L("não", "no")) }],
        { search: false, name: `campaigns-${cnpj}` });
    }
    if (P.length) {
      const tp = el("div");
      box.append(card(L("Seus registros no CEPIM", "Its CEPIM entries"), L("Os convênios federais por trás do impedimento.", "The federal agreements behind its bar."), tp));
      table(tp, P, [{ key: "convenio", label: L("Convênio", "Agreement"), text: true }, { key: "orgao", label: L("Ministério", "Ministry"), text: true, wrap: true }, { key: "motivo", label: L("Motivo", "Reason"), text: true, fmt: (v) => MOTIVO[v] || v }], { search: false, name: `cepim-${cnpj}` });
    }
    if (Ls.length) box.append(card(L("Seus acordos de leniência", "Its leniency agreements"), "", ...Ls.map((l) => el("p", { className: "about", textContent: `${l.inicio}, ${STATUS[l.situacao] || l.situacao}: ${l.termos}…` }))));
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
