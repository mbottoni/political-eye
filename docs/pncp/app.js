// Public contracts (PNCP): who buys, who sells, how concentrated, where, and under which mayor's party.
import { $, asset, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L, date } from "../lib/i18n.js";
import { setupPage } from "../lib/page.js";

setupPage();

const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const finding = (text) => el("p", { className: "finding", textContent: text });
const grid = (...kids) => el("div", { className: "grid2" }, ...kids.map((k) => { k.classList.remove("wide"); return k; }));
const select = (label, options, value, onChange) => {
  const s = el("select", {}, ...options.map((o) => el("option", { value: o.value ?? o, textContent: o.label ?? o, selected: String(o.value ?? o) === String(value) })));
  s.addEventListener("change", () => onChange(s.value));
  return el("label", {}, label, s);
};
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const day = (v) => el("span", { className: "nowrap", textContent: v ?? "" });
const dayProse = (iso) => date(`${iso}T12:00:00`) || iso;   // "2026-11-06" -> "6 de novembro de 2026" (local noon: no time-zone shift)
const cnpjFmt = (c) => (/^\d{14}$/.test(c) ? `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}` : c);
const short = (s, k = 34) => { s = String(s || ""); k = /[a-z]/.test(s) ? k : Math.round(k * 0.84); return s.length > k ? `${s.slice(0, k - 1)}…` : s; };
const redraws = [];
const later = (f) => { redraws.push(f); f(); };

const SPH = { F: L("Federal", "Federal"), E: L("Estadual", "State"), M: L("Municipal", "Municipal"), D: L("Distrito Federal", "Federal District"), N: L("Outras", "Other") };
const sphColor = (k) => ({ F: C.slot(1), E: C.slot(2), M: C.slot(3), D: C.slot(4), N: css("--other") })[k] || css("--other");
const CAT = { "Serviços": ["Serviços", "Services"], "Obras": ["Obras", "Public works"], "Compras": ["Compras", "Goods"], "Serviços de Engenharia": ["Serviços de engenharia", "Engineering services"],
  "Mão de Obra": ["Mão de obra", "Outsourced labour"], "Informática (TIC)": ["Informática (TIC)", "IT"], "Serviços de Saúde": ["Serviços de saúde", "Health services"],
  "Locação Imóveis": ["Locação de imóveis", "Property rental"], "Cessão": ["Cessão", "Assignment"], "Alienação de Bens Móveis/Imóveis": ["Alienação de bens", "Sale of assets"] };
const cat = (c) => (CAT[c] ? L(...CAT[c]) : c || L("Não informada", "Not stated"));
const R = () => data("site/pncp/resumo.json");
const sancoesLink = (cnpj) => `../sancoes/?tab=company&cnpj=${cnpj}`;

async function coverage() {
  const r = await R(), c = r.coverage, box = $("#coverage");
  box.replaceChildren(el("div", { className: "card wide" },
    el("h2", { textContent: L(`Histórico lido: ${plural(c.days_read, "dia", "dias")} de ${fmt(c.span_days)}`, `History read: ${plural(c.days_read, "day")} of ${fmt(c.span_days)}`) }),
    el("div", { className: "meter" }, el("i", { style: `width:${Math.max(0.5, 100 * c.share).toFixed(1)}%` })),
    el("p", { className: "note", textContent: c.days_read
      ? L(`De ${dayProse(c.first)} a ${dayProse(c.last)}, do mais recente para o mais antigo, entre todos os dias desde ${dayProse(c.since)}. A rotina diária lê mais a cada noite; os totais abaixo cobrem os dias lidos, e as tabelas de grandes contratos trazem todos os grandes contratos publicados ou aditados nesses dias.`,
        `From ${dayProse(c.first)} to ${dayProse(c.last)}, newest first, out of every day since ${dayProse(c.since)}. The daily job reads more each night; totals below cover the days read, and the large-contract tables hold every large contract published or amended on those days.`)
      : L("Nenhum dia lido ainda.", "No day read yet.") })));
}

// ------------------------------------------------------------ overview

async function overview(root) {
  const r = await R(), t = r.totals, Lg = r.large;
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Contratos publicados", "Contracts published"), value: fmt(t.contratos), sub: L(`em ${plural(r.coverage.days_read, "dia lido", "dias lidos")}`, `on the ${plural(r.coverage.days_read, "day")} read`) },
    { label: L("Valor total", "Their value"), value: brl(t.valor), sub: L("valor global, como publicado", "global value, as published") },
    { label: L("Parcela dos contratos de R$ 1 mi+", "Share in contracts of R$ 1 M+"), value: pct(Lg.share_of_value), sub: L(`${fmt(Lg.on_days_read.contratos)} grandes contratos nesses dias`, `${fmt(Lg.on_days_read.contratos)} large contracts on those days`) },
    { label: L("Grandes contratos acompanhados", "Large contracts followed"), value: fmt(Lg.contratos), sub: L(`${brl(Lg.valor)}; mediana de ${brl(Lg.median)}`, `${brl(Lg.valor)}; median ${brl(Lg.median)}`) },
  ]);
  const d = await data("site/pncp/diario.csv");
  let metric = params.get("m") || "valor";
  const ctl = el("div", { className: "controls" }), c1 = chart();
  root.append(card(L("Contratos publicados por dia", "Contracts published per day"), L("Todos os contratos que o PNCP publicou a cada dia, pela esfera do órgão comprador.", "Every contract the PNCP published each day, by the buyer's sphere."), ctl, c1));
  const daysAll = [...new Set(d.map((x) => x.dia))].sort();
  const draw = () => {
    ctl.replaceChildren(select(L("Medida", "Measure"), [{ value: "valor", label: L("Valor", "Value") }, { value: "contratos", label: L("Número de contratos", "Number of contracts") }], metric, (v) => { metric = v; setParam("m", v, "valor"); draw(); }));
    const f = metric === "valor" ? (v) => brl(v, 0) : (v) => fmt(v);
    if (daysAll.length < 7) { c1.replaceChildren(el("p", { className: "empty", textContent: L(`A série diária aparece quando houver uma semana de histórico lida (${plural(daysAll.length, "dia", "dias")} até agora). Os totais acima cobrem o que já foi lido.`, `The daily series appears once a week of history is read (${plural(daysAll.length, "day")} so far). The totals beside it cover what is read.`) })); return; }
    C.line(c1, { x: "day", height: 240, y: { format: f, min: 0 }, empty: L("Nenhum dia lido ainda.", "No day read yet."),
      series: ["M", "E", "F", "D", "N"].map((k) => ({ name: SPH[k], color: sphColor(k), points: daysAll.map((dd) => { const x = d.find((y) => y.dia === dd && y.esfera === k); return [dd, x ? +x[metric] : 0]; }) }))
        .filter((s) => s.points.some((p) => p[1] > 0)) });
  };
  later(draw);
  const c2 = chart(), c3 = chart();
  root.append(grid(card(L("Quem compra", "Who buys"), L("Contratos e valor nos dias lidos, pela esfera do órgão comprador.", "Contracts and value on the days read, by the buyer's sphere."), c2),
    card(L("Quem vende", "Who sells"), L("Por tipo de fornecedor: empresas (PJ), pessoas físicas (PF) e fornecedores estrangeiros (PE).", "By kind of supplier: companies (PJ), private individuals (PF) and foreign suppliers (PE)."), c3)));
  const bs = [...t.by_sphere].sort((a, b) => b.valor - a.valor);
  later(() => C.bars(c2, { rows: bs.map((x) => ({ label: SPH[x.esfera] || x.esfera, value: x.valor, note: L(`${fmt(x.contratos)} contratos · média de ${brl(x.valor / x.contratos)}`, `${fmt(x.contratos)} contracts · average ${brl(x.valor / x.contratos)}`), color: sphColor(x.esfera) })), format: (v) => brl(v, 1), labelWidth: 130 }));
  const KIND = { PJ: L("Empresas", "Companies"), PF: L("Pessoas físicas", "Individuals"), PE: L("Estrangeiros", "Foreign") };
  const bt = [...t.by_supplier].sort((a, b) => b.valor - a.valor);
  later(() => C.bars(c3, { rows: bt.map((x) => ({ label: KIND[x.fornecedor_tipo] || x.fornecedor_tipo, value: x.valor, note: L(`${fmt(x.contratos)} contratos`, `${fmt(x.contratos)} contracts`), color: css("--line") })), format: (v) => brl(v, 1), labelWidth: 130 }));
  if (daysAll.length >= 7) {
    const c4 = chart();
    root.append(card(L("Por dia da semana", "By day of the week"), L("Média de contratos publicados em cada dia da semana, nos dias lidos.", "Average contracts published per weekday, over the days read."), c4));
    const W = L(["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"], ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]), acc = W.map(() => ({ n: 0, days: new Set() }));
    for (const x of d) { const w = new Date(`${x.dia}T12:00:00Z`).getUTCDay(); acc[w].n += +x.contratos; acc[w].days.add(x.dia); }
    later(() => C.stack(c4, { x: W, height: 200, series: [{ name: L("Contratos por dia", "Contracts per day"), color: css("--line"), values: acc.map((a) => (a.days.size ? a.n / a.days.size : 0)) }] }));
  }
}

// ------------------------------------------------------------ large contracts

async function large(root) {
  const r = await R(), Lg = r.large, rows = await data("site/pncp/maiores.csv");
  let uf = params.get("uf") || "", esf = params.get("esf") || "", ct = params.get("cat") || "";
  const c1 = chart(), c2 = chart(), c3 = chart();
  root.append(grid(
    card(L("De que tamanho", "How large"), L("Todos os contratos de R$ 1 milhão ou mais, em escala logarítmica: cada passo é dez vezes o anterior.", "Every contract of R$ 1 million or more on a log scale: each step is ten times the last."), c1),
    card(L("O que se compra", "What is bought"), L("Grandes contratos por categoria, por valor.", "Large contracts by category, by value."), c2)));
  later(() => C.histogram(c1, { values: Lg.log_hist.flatMap((n0, i) => Array(n0).fill((Lg.log_edges[i] + Lg.log_edges[i + 1]) / 2)), domain: [6, 11], bins: 20, format: (v) => brl(10 ** v, 0), tickFormat: (v) => (Math.abs(v - Math.round(v)) < 1e-9 ? brl(10 ** v, 0) : ""), xLabel: L("valor do contrato (escala logarítmica)", "contract value (log scale)"), unit: L("contratos", "contracts"), height: 220, refs: Lg.median ? [{ x: Math.log10(Lg.median), label: L(`mediana ${brl(Lg.median)}`, `median ${brl(Lg.median)}`) }] : [] }));
  later(() => C.bars(c2, { rows: Lg.by_category.map((x) => ({ label: cat(x.categoria), value: x.valor, note: L(`${fmt(x.contratos)} contratos`, `${fmt(x.contratos)} contracts`), color: css("--line") })), format: (v) => brl(v, 1), labelWidth: 170 }));
  root.append(card(L("Grandes contratos por mês de publicação", "Large contracts by month of publication"), L("Valor, pela esfera do órgão comprador. Os meses anteriores ao histórico lido até agora só têm contratos aditados nos dias lidos.", "Value, by the buyer's sphere. Months before the history read so far hold only contracts amended on the days read."), c3));
  const months = [...new Set(Lg.by_month.map((x) => x.mes))].sort();
  later(() => C.stack(c3, { x: months, height: 220, format: (v) => brl(v, 0), series: ["F", "E", "M", "D", "N"].map((k) => ({ name: SPH[k], color: sphColor(k), values: months.map((m) => sum(Lg.by_month.filter((x) => x.mes === m && x.esfera === k).map((x) => x.valor))) })).filter((s) => s.values.some((v) => v > 0)) }));
  const ctl = el("div", { className: "controls" }), tb = el("div");
  const I = Lg.implausible;
  root.append(card(L("Os maiores contratos", "The largest contracts"), L(
    `Os ${fmt(rows.length)} maiores, filtrados abaixo; busque em qualquer coluna. ${I.contratos ? `${fmt(I.contratos)} contratos foram publicados com valor global mais de ${fmt(I.ratio)} vezes o valor inicial (juntos, ${brl(I.publicado)} em vez de ${brl(I.usado)}); eles entram pelo valor inicial e levam a marca "corrigido".` : ""}`,
    `The ${fmt(rows.length)} largest, filtered below; search any column. ${I.contratos ? `${fmt(I.contratos)} contracts were published with a global value more than ${fmt(I.ratio)} times their initial value (together ${brl(I.publicado)} instead of ${brl(I.usado)}); they are counted at their initial value and marked "fixed".` : ""}`), ctl, tb));
  const ufs = [...new Set(rows.map((x) => x.uf))].filter(Boolean).sort(), cats = [...new Set(rows.map((x) => x.categoria))].sort();
  const t = table(tb, [], [{ key: "assinatura", label: L("Assinatura", "Signed"), text: true, fmt: day }, { key: "orgao", label: L("Órgão comprador", "Buyer"), text: true, wrap: true }, { key: "uf", label: "UF", text: true },
    { key: "fornecedor_nome", label: L("Fornecedor", "Supplier"), text: true, wrap: true }, { key: "objeto", label: L("Objeto", "Object"), text: true, wrap: true }, { key: "categoria", label: L("Categoria", "Category"), text: true, fmt: cat },
    { key: "valor", label: L("Valor", "Value"), fmt: (v, x) => (+x.suspeito ? el("span", { title: L(`Publicado como ${brl(x.valor_publicado)}, ${fmt(+x.valor_publicado / +v, 0)} vezes o valor inicial: tratado como erro de digitação`, `Published as ${brl(x.valor_publicado)}, ${fmt(+x.valor_publicado / +v, 0)} times its initial value: taken as a typo`) }, brl(v), " ", el("span", { className: "flag bad", textContent: L("corrigido", "fixed") })) : brl(v)) }],
  { sortBy: "valor", pageSize: 12, name: "large-contracts" });
  const draw = () => {
    ctl.replaceChildren(
      select(L("Estado", "State"), [{ value: "", label: L("Todos os estados", "Every state") }, ...ufs], uf, (v) => { uf = v; setParam("uf", v, ""); draw(); }),
      select(L("Esfera", "Sphere"), [{ value: "", label: L("Todas as esferas", "Every sphere") }, ...Object.entries(SPH).map(([value, label]) => ({ value, label }))], esf, (v) => { esf = v; setParam("esf", v, ""); draw(); }),
      select(L("Categoria", "Category"), [{ value: "", label: L("Todas as categorias", "Every category") }, ...cats.map((x) => ({ value: x, label: cat(x) }))], ct, (v) => { ct = v; setParam("cat", v, ""); draw(); }));
    t.update(rows.filter((x) => (!uf || x.uf === uf) && (!esf || x.esfera === esf) && (!ct || x.categoria === ct)));
  };
  draw();
  const G = Lg.left_out;
  if (G?.contratos) {
    const gone = await data("site/pncp/descartados.csv"), gb = el("div");
    root.append(card(L("Deixados de fora por erro de digitação", "Left out as typos"), L(
      `${plural(G.contratos, "contrato foi publicado", "contratos foram publicados")} com valores que nenhum órgão poderia pagar, somando ${brl(G.publicado)}: acima de ${brl(G.cap, 0)}, ou contratos municipais de valor maior que ${fmt(G.town_years)} anos de toda a receita do município. O valor inicial também não era plausível, então eles ficam fora de todos os totais e rankings desta página.`,
      `${plural(G.contratos, "contract")} were published at values no buyer could pay, together ${brl(G.publicado)}: over ${brl(G.cap, 0)}, or a town's contract worth more than ${fmt(G.town_years)} years of the town's whole revenue. Their initial value was no better, so they are left out of every total and ranking on this page.`), gb));
    table(gb, gone, [{ key: "publicacao", label: L("Publicação", "Published"), text: true, fmt: day }, { key: "orgao", label: L("Órgão comprador", "Buyer"), text: true, wrap: true }, { key: "uf", label: "UF", text: true },
      { key: "fornecedor_nome", label: L("Fornecedor", "Supplier"), text: true, wrap: true, fmt: (v) => v || L("Pessoa física (nome omitido)", "A person (name withheld)") }, { key: "objeto", label: L("Objeto", "Object"), text: true, wrap: true },
      { key: "valor_publicado", label: L("Valor publicado", "Published at"), fmt: (v) => brl(v) }, { key: "receita", label: L("Receita anual do município", "Town's revenue a year"), fmt: (v) => (v === "" || v == null ? "–" : brl(v)) }],
    { sortBy: "valor_publicado", pageSize: 10, name: "left-out-contracts" });
  }
}

// ------------------------------------------------------------ suppliers

async function suppliers(root) {
  const r = await R(), S = r.suppliers, rows = await data("site/pncp/fornecedores.csv");
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Fornecedores de grandes contratos", "Suppliers of large contracts"), value: fmt(S.n), sub: L("CNPJs distintos (e CPFs mascarados)", "distinct CNPJs (and masked CPFs)") },
    { label: L("Concentração (índice de Gini)", "Concentration (Gini)"), value: S.gini == null ? "–" : fmt(S.gini, 2), sub: L("0: todos recebem o mesmo; 1: um só leva tudo", "0: every supplier gets the same; 1: one gets everything") },
    { label: L("1% maiores fornecedores", "Top 1% of suppliers"), value: pct(S.top1_share), sub: L(`do valor; os 10% maiores: ${pct(S.top10_share)}`, `of the value; the top 10%: ${pct(S.top10_share)}`) },
    { label: L("Também nas listas de sanções", "Also on the sanctions lists"), value: fmt(S.linked.sancionadas), sub: L(`entre os ${fmt(S.linked.of)} maiores fornecedores`, `of the ${fmt(S.linked.of)} largest suppliers`) },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(
    card(L("Quão desigual", "How unequal"), L("Curva de Lorenz: a parcela do valor (eixo vertical) que fica com os menores fornecedores (eixo horizontal). Quanto mais abaixo da diagonal, mais o dinheiro vai para poucos.", "Lorenz curve: the share of value (up) held by the smallest suppliers (across). The further below the diagonal, the more the money goes to few."), c1),
    card(L("Os maiores fornecedores", "The largest suppliers"), L("Pelo valor de seus grandes contratos.", "By the value of their large contracts."), c2)));
  later(() => C.line(c1, { x: "num", height: 240, y: { min: 0, max: 1, format: (v) => pct(v) },
    series: [{ name: L("Partes iguais", "Equal shares"), color: css("--axis"), width: 1.5, points: [[0, 0], [1, 1]] }, { name: L("Real", "Actual"), color: css("--line"), points: S.lorenz }] }));
  later(() => C.bars(c2, { rows: rows.slice(0, 20).map((x) => ({ label: short(x.nome, 36), title: x.nome, value: +x.valor, note: L(`${fmt(x.contratos)} contratos · ${fmt(x.orgaos)} órgãos`, `${fmt(x.contratos)} contracts · ${fmt(x.orgaos)} buyers`), color: +x.sancionada ? css("--critical") : css("--line") })), format: (v) => brl(v, 1), labelWidth: 260, legend: [{ label: L("No CEIS ou no CNEP", "On CEIS or CNEP"), color: css("--critical") }, { label: L("Fora das listas", "Not listed"), color: css("--line") }] }));
  const tb = el("div");
  root.append(card(L("Quem são eles", "Who they are"), L("Os maiores fornecedores e o que mais os liga ao Estado: uma sanção no CEIS ou no CNEP (clique para ver o perfil), contratos assinados enquanto estavam impedidos, dinheiro de emendas pago diretamente a eles e o que campanhas eleitorais lhes pagaram (2018–2026).", "The largest suppliers, and what else ties them to the State: a CEIS or CNEP sanction (click through to its profile), contracts signed while barred, amendment money paid to them directly, and what election campaigns paid them (2018–2026)."), tb));
  table(tb, rows, [
    { key: "nome", label: L("Fornecedor", "Supplier"), text: true, wrap: true, fmt: (v, x) => (+x.sancionada ? el("a", { className: "linkish", href: sancoesLink(x.cnpj), textContent: v }) : v) },
    { key: "cnpj", label: "CNPJ", text: true, fmt: (v) => day(cnpjFmt(v)) }, { key: "contratos", label: L("Contratos", "Contracts") }, { key: "valor", label: L("Valor", "Value"), fmt: (v) => brl(v) },
    { key: "orgaos", label: L("Órgãos", "Buyers") }, { key: "ufs", label: L("Estados", "States") },
    { key: "sancionada", label: L("Sanção", "Sanctioned"), text: true, fmt: (v, x) => (+v ? el("span", { className: "flag bad", textContent: +x.contratos_sancionada ? L(`${fmt(+x.contratos_sancionada)} sob impedimento`, `${x.contratos_sancionada} while barred`) : L("na lista", "listed") }) : "") },
    { key: "emendas", label: L("Emendas", "Amendments"), fmt: (v) => (+v ? brl(v) : "") }, { key: "campanhas", label: L("Pago por campanhas", "Campaigns paid it"), fmt: (v, x) => (+v ? `${brl(v)} · ${fmt(x.campanhas_candidatos)} cand.` : "") },
  ], { sortBy: "valor", pageSize: 15, name: "suppliers" });
  const sv = r.sanctioned.by_cobre_sphere;
  if (sv.length) {
    const c3 = chart();
    root.append(card(L("Contratos assinados com fornecedor impedido", "Contracts signed with a barred supplier"), L("Contratos de qualquer valor cujo fornecedor estava, no dia da assinatura, sob sanção do CEIS ou do CNEP que o impedia de contratar, conforme o alcance da sanção chegue ou não ao órgão comprador. A maioria das sanções vale só para o órgão ou a esfera que a aplicou. Cada contrato está listado, com as sanções da empresa, na página de sanções.", "Contracts of any value whose supplier was under a CEIS or CNEP sanction barring contracting on the signing day, by whether the sanction's scope reaches the buyer. Most sanctions bind only the body or sphere that imposed them. Each one is listed, with the company's sanctions, on the sanctions page."), c3,
      el("p", { className: "finding" }, el("a", { href: "../sancoes/?tab=money", textContent: L("Veja os contratos na página de sanções →", "See them on the sanctions page →") }))));
    const COBRE = { sim: L("Alcança o comprador", "Reaches the buyer"), possivel: L("Pode alcançar o comprador", "May reach the buyer"), nao: L("Não alcança o comprador", "Does not reach the buyer") };
    const col = (k) => ({ sim: css("--critical"), possivel: css("--warning"), nao: css("--other") })[k];
    const agg = ["sim", "possivel", "nao"].map((k) => ({ k, n: sum(sv.filter((x) => x.cobre === k).map((x) => x.contratos)), v: sum(sv.filter((x) => x.cobre === k).map((x) => x.valor)) }));
    later(() => C.bars(c3, { rows: agg.map((x) => ({ label: COBRE[x.k], value: x.n, note: brl(x.v), color: col(x.k) })), labelWidth: 190 }));
  }
}

// ------------------------------------------------------------ buyers

async function buyers(root) {
  const r = await R(), B = r.buyers, rows = await data("site/pncp/orgaos.csv");
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Compradores de grandes contratos", "Buyers of large contracts"), value: fmt(B.n), sub: L("órgãos públicos distintos (CNPJ)", "distinct public bodies (CNPJ)") },
    { label: L("Com contratos suficientes para medir", "With enough contracts to measure"), value: fmt(B.with_hhi), sub: L("cinco ou mais grandes contratos", "five or more large contracts") },
    { label: L("Concentração típica de fornecedores", "Typical supplier concentration"), value: B.hhi_median == null ? "–" : fmt(B.hhi_median, 2), sub: L("HHI mediano: 1 quer dizer que um só fornecedor leva tudo", "median HHI: 1 means one supplier takes it all") },
    { label: L("Fornecedor único", "Single supplier"), value: fmt(B.single_supplier), sub: L("órgãos com 5+ grandes contratos, todos de um só fornecedor","buyers whose five or more large contracts all went to one supplier") },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(
    card(L("Quão concentrados são os fornecedores de cada órgão", "How concentrated each buyer's suppliers are"), L(`Índice de Herfindahl (HHI) do valor dos grandes contratos de cada órgão entre seus fornecedores (a soma das parcelas ao quadrado), para órgãos com cinco ou mais. Acima de ${fmt(0.25, 2)} costuma-se dizer que a concentração é alta.`, "Herfindahl index of each buyer's large-contract value across its suppliers (the sum of squared shares), for buyers with five or more. Above 0.25 is usually called highly concentrated."), c1),
    card(L("Os maiores compradores", "The largest buyers"), L("Pelo valor de seus grandes contratos.", "By the value of their large contracts."), c2)));
  later(() => C.histogram(c1, { values: B.hhi_hist.flatMap((n0, i) => Array(n0).fill((i + 0.5) / 20)), domain: [0, 1], bins: 20, format: (v) => fmt(v, 2), xLabel: "HHI", unit: L("órgãos", "buyers"), height: 220, refs: B.hhi_median != null ? [{ x: 0.25, label: fmt(0.25, 2) }] : [] }));
  later(() => C.bars(c2, { rows: rows.slice(0, 20).map((x) => ({ label: short(x.orgao, 38), title: x.orgao, value: +x.valor, note: L(`${SPH[x.esfera] || x.esfera}, ${x.uf} · ${fmt(x.contratos)} contratos`, `${SPH[x.esfera] || x.esfera}, ${x.uf} · ${fmt(x.contratos)} contracts`), color: sphColor(x.esfera) })), format: (v) => brl(v, 1), labelWidth: 280 }));
  const tb = el("div");
  root.append(card(L("Os órgãos e seu principal fornecedor", "Buyers and their main supplier"), L("Ordene pelo HHI ou pela parcela do principal fornecedor para achar os órgãos que compram quase tudo de uma só empresa.", "Sort by HHI or by the main supplier's share to find the bodies that buy almost everything from one company."), tb));
  table(tb, rows, [{ key: "orgao", label: L("Órgão comprador", "Buyer"), text: true, wrap: true }, { key: "esfera", label: L("Esfera", "Sphere"), text: true, fmt: (v) => SPH[v] || v }, { key: "uf", label: "UF", text: true },
    { key: "contratos", label: L("Contratos", "Contracts") }, { key: "valor", label: L("Valor", "Value"), fmt: (v) => brl(v) }, { key: "fornecedores", label: L("Fornecedores", "Suppliers") },
    { key: "hhi", label: "HHI", fmt: (v) => (v === "" ? "" : fmt(+v, 2)) }, { key: "maior_fornecedor_nome", label: L("Principal fornecedor", "Main supplier"), text: true, wrap: true }, { key: "maior_share", label: L("Parcela dele", "Its share"), fmt: (v) => pct(+v) }],
  { sortBy: "valor", pageSize: 15, name: "buyers" });
}

// ------------------------------------------------------------ map

async function map(root) {
  const r = await R(), mun = await data("site/pncp/municipios.csv");
  const [ufs, muns] = await Promise.all([asset("maps/ufs.json"), asset("maps/municipios.json")]);
  const c1 = chart(), c2 = chart();
  root.append(grid(
    card(L("Grandes contratos por habitante, por estado", "Large contracts per inhabitant, by state"), L("Todas as esferas, pelo estado do órgão comprador. Os órgãos federais sediados em Brasília pesam no Distrito Federal.", "Every sphere, by the buyer's state. Federal bodies in Brasília weigh on the Federal District."), c1),
    card(L("Ranking dos estados", "States ranked"), "", c2)));
  const by = new Map(r.by_uf.map((x) => [String(x.ibge), x]));
  const mx = Math.max(1e-9, ...r.by_uf.map((x) => x.por_habitante || 0));
  later(() => { C.choropleth(c1, { shapes: ufs.shapes, viewBox: ufs.viewBox, stroke: 0.6, maxWidth: 520, value: (k) => by.get(k)?.por_habitante ?? null, color: (v) => C.seq(Math.sqrt(v / mx)),
    tip: (k, v) => { const x = by.get(k); return x ? [el("strong", { textContent: x.uf }), el("div", { className: "row", textContent: L(`R$ ${fmt(v, 2)} por habitante · ${brl(x.valor)} em ${fmt(x.contratos)} contratos`, `R$ ${fmt(v, 2)} per inhabitant · ${brl(x.valor)} in ${fmt(x.contratos)} contracts`) })] : [el("strong", { textContent: k })]; } });
    C.colorKey(c1, { color: (t) => C.seq(Math.sqrt(t)), from: "R$ 0", to: L(`R$ ${fmt(mx, 0)} por habitante`, `R$ ${fmt(mx, 0)} per inhabitant`) }); });
  const ranked = [...r.by_uf].sort((a, b) => b.por_habitante - a.por_habitante);
  later(() => C.bars(c2, { rows: ranked.map((x) => ({ label: x.uf, value: x.por_habitante, note: brl(x.valor), color: css("--line") })), barHeight: 12, format: (v) => `R$ ${fmt(v, 0)}` }));
  const c3 = chart(), c4 = chart();
  root.append(grid(card(L("Grandes contratos de órgãos municipais por habitante", "Municipal bodies' large contracts per inhabitant"), L("Contratos de R$ 1 milhão ou mais assinados pelos órgãos do próprio município (prefeitura, fundos, empresas municipais), por habitante. Cinza: nenhum nos dias lidos.", "Contracts of R$ 1 million or more signed by each town's own bodies (prefeitura, funds, municipal companies), per inhabitant. Grey: none on the days read."), c3),
    card(L("Os municípios que mais contratam", "Towns with the most"), L("Pelo valor dos grandes contratos de seus órgãos municipais; o valor por habitante aparece ao passar o mouse.", "By value of their municipal bodies' large contracts; per inhabitant in the tooltip."), c4)));
  const topTowns = [...mun].sort((a, b) => +b.valor - +a.valor).slice(0, 25);
  later(() => C.bars(c4, { rows: topTowns.map((x) => ({ label: `${x.municipio} (${x.uf})`, value: +x.valor, note: L(`R$ ${fmt(+x.por_habitante, 0)} por habitante · ${fmt(x.contratos)} contratos`, `R$ ${fmt(+x.por_habitante, 0)} per inhabitant · ${fmt(x.contratos)} contracts`), color: css("--line") })), format: (v) => brl(v, 1), labelWidth: 190, barHeight: 13 }));
  const mm = new Map(mun.map((x) => [x.cod_ibge, x]));
  const vals = mun.map((x) => +x.por_habitante).filter((v) => v > 0).sort((a, b) => a - b);
  const cap = vals[Math.floor(vals.length * 0.95)] || 1;
  later(() => { C.choropleth(c3, { shapes: muns.shapes, viewBox: muns.viewBox, maxWidth: 560, outline: ufs.shapes, outlineWidth: 0.6,
    value: (k) => (mm.get(k) ? +mm.get(k).por_habitante : null), color: (v) => C.seq(Math.sqrt(Math.min(1, v / cap))),
    tip: (k, v) => { const x = mm.get(k); return x ? [el("strong", { textContent: `${x.municipio} (${x.uf})` }), el("div", { className: "row", textContent: L(`R$ ${fmt(v, 2)} por habitante · ${brl(x.valor)} em ${fmt(x.contratos)} contratos, ${fmt(x.fornecedores)} fornecedores`, `R$ ${fmt(v, 2)} per inhabitant · ${brl(x.valor)} in ${fmt(x.contratos)} contracts, ${fmt(x.fornecedores)} suppliers`) })] : [el("strong", { textContent: L("Nenhum grande contrato municipal nos dias lidos", "No large municipal contract on the days read") })]; } });
    C.colorKey(c3, { color: (t) => C.seq(Math.sqrt(t)), from: "R$ 0", to: L(`R$ ${fmt(cap, 0)}+ por habitante`, `R$ ${fmt(cap, 0)}+ per inhabitant`) }); });
}

// ------------------------------------------------------------ mayors' parties

async function parties(root) {
  const r = await R(), rows = (await data("site/pncp/partidos.csv")).map((x) => ({ ...x, municipios: +x.municipios, contratos: +x.contratos, valor: +x.valor, pop_anos: +x.pop_anos, sancionadas: +x.sancionadas, ph: +x.por_habitante_ano, pm: +x.contratos_por_milhao_hab }));
  const big = rows.filter((x) => x.municipios >= 50).sort((a, b) => b.ph - a.ph);
  const allPop = sum(rows.map((x) => x.pop_anos)), allV = sum(rows.map((x) => x.valor)), nContracts = sum(rows.map((x) => x.contratos));
  const early = nContracts < 2000;
  if (early) root.append(el("div", { className: "card wide" }, el("h2", { textContent: L("Cedo demais para comparar partidos", "Too early to compare parties") }),
    el("p", { className: "note", textContent: L(`Só ${fmt(nContracts)} grandes contratos municipais foram lidos até agora (${plural(r.coverage.days_read, "dia", "dias")} de histórico). Nesse tamanho, um único grande contrato leva um partido ao topo, e o ranking abaixo é ruído até que mais do histórico seja lido; ele se firma à medida que a carga do histórico avança.`, `Only ${fmt(nContracts)} large municipal contracts have been read so far (${plural(r.coverage.days_read, "day")} of history). At this size one large contract moves a party to the top, so the ranking below is noise until more of the history is read; it firms up as the backfill fills in.`) })));
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Partidos que governam 50+ municípios", "Parties governing 50+ towns"), value: fmt(big.length), sub: L(`nos anos ${r.parties.years.join(", ").replace(/, (\d+)$/, " e $1") || "–"}`,`in the years ${r.parties.years.join(", ") || "–"}`) },
    { label: L("Valor municipal atribuído", "Municipal value attributed"), value: pct(r.parties.attributed), sub: L("dos grandes contratos municipais, ao prefeito então no cargo", "of municipal large contracts, to the mayor then in office") },
    { label: L("Média, todos os municípios", "Average, every town"), value: `R$ ${fmt(allPop ? allV / allPop : null, 2)}`, sub: L("em grandes contratos por habitante-ano", "large contracts per inhabitant-year") },
    early ? { label: L("Contratos municipais lidos", "Municipal contracts read"), value: fmt(nContracts), sub: L("ainda poucos para ordenar os partidos", "too few to rank parties yet") }
      : { label: L("Partido no topo", "Highest party"), value: big[0] ? big[0].partido : "–", sub: big[0] ? L(`R$ ${fmt(big[0].ph, 2)} por habitante-ano`, `R$ ${fmt(big[0].ph, 2)} per inhabitant-year`) : "" },
  ]);
  let metric = params.get("pm") || "ph";
  const ctl = el("div", { className: "controls" }), c1 = chart();
  root.append(card(L("Grandes contratos municipais pelo partido do prefeito", "Large municipal contracts by the mayor's party"), L("Municípios agrupados pelo partido do prefeito no cargo no ano em que cada contrato foi assinado (partidos fundidos ou renomeados aparecem com o nome atual). Por habitante-ano: o valor dividido pela população que esses prefeitos governaram, ano a ano, para que partidos grandes e pequenos se comparem. Partidos que governam pelo menos 50 municípios. O histórico do PNCP lido até agora é parcial, mas por igual entre os partidos: os municípios de todos eles estão nos mesmos dias.", "Towns grouped by the party of the mayor in office in the year each contract was signed (merged or renamed parties under today's name). Per inhabitant-year: the value over the population those mayors governed, year by year, so big and small parties compare. Parties governing at least 50 towns. The PNCP history read so far is partial, but evenly across parties: every party's towns are on the same days."), ctl, c1));
  const M = { ph: [L("R$ por habitante-ano", "R$ per inhabitant-year"), (v) => `R$ ${fmt(v, 2)}`], pm: [L("Contratos por milhão de habitantes-ano", "Contracts per million inhabitant-years"), (v) => fmt(v, 1)] };
  const draw = () => {
    ctl.replaceChildren(select(L("Medida", "Measure"), Object.entries(M).map(([value, [label]]) => ({ value, label })), metric, (v) => { metric = v; setParam("pm", v, "ph"); draw(); }));
    const avg = metric === "ph" ? (allPop ? allV / allPop : 0) : (allPop ? (sum(rows.map((x) => x.contratos)) / allPop) * 1e6 : 0);
    const sorted = [...big].sort((a, b) => b[metric] - a[metric]);
    C.bars(c1, { rows: sorted.map((x) => ({ label: x.partido, value: x[metric], note: L(`${fmt(x.municipios)} municípios · ${fmt(x.contratos)} contratos, ${brl(x.valor)}`, `${fmt(x.municipios)} towns · ${fmt(x.contratos)} contracts, ${brl(x.valor)}`), color: x[metric] > avg ? C.slot(2) : css("--line") })),
      format: M[metric][1], labelWidth: 120, legend: [{ label: L("Acima da média de todos os municípios", "Above the average of every town"), color: C.slot(2) }, { label: L("Abaixo", "Below"), color: css("--line") }],
      table: { rows: big, cols: [{ key: "partido", label: L("Partido", "Party"), text: true }, { key: "municipios", label: L("Municípios", "Towns") }, { key: "pop_anos", label: L("Habitantes-ano", "Inhabitant-years") }, { key: "contratos", label: L("Contratos", "Contracts") }, { key: "valor", label: L("Valor", "Value"), fmt: (v) => brl(v) }, { key: "ph", label: L("R$ por habitante-ano", "R$ per inhabitant-year"), fmt: (v) => fmt(v, 2) }, { key: "sancionadas", label: L("Com fornecedor impedido", "With barred suppliers") }], name: "mayor-parties" } });
  };
  later(draw);
  const c2 = chart();
  root.append(card(L("Contratos com fornecedor impedido, pelo partido do prefeito", "Contracts with barred suppliers, by the mayor's party"), L("Contratos municipais de qualquer valor assinados com um fornecedor sob sanção cujo alcance chega ou pode chegar ao município, por milhão de habitantes-ano governados.", "Municipal contracts of any value signed with a supplier under a sanction whose scope reaches or may reach the town, per million inhabitant-years governed."), c2));
  const sb = big.map((x) => ({ ...x, rate: x.pop_anos ? (x.sancionadas / x.pop_anos) * 1e6 : 0 })).sort((a, b) => b.rate - a.rate);
  later(() => C.bars(c2, { rows: sb.map((x) => ({ label: x.partido, value: x.rate, note: L(`${fmt(x.sancionadas)} contratos`, `${fmt(x.sancionadas)} contracts`), color: css("--line") })), format: (v) => fmt(v, 2), labelWidth: 120 }));
  root.append(el("p", { className: "about", textContent: L("São associações, não causas: os partidos governam municípios diferentes (grandes e pequenos, ricos e pobres, em estados diferentes), e o gasto de um município reflete mais seu tamanho e suas necessidades do que o partido do prefeito.", "These are associations, not causes: parties govern different kinds of towns (big and small, rich and poor, in different states), and a town's spending reflects its size and needs more than its mayor's party.") }));
}

const SECTIONS = { overview, large, suppliers, buyers, map, parties };
guard($("#coverage"), coverage);
tabs((name) => { const box = $(`#tab-${name}`); guard(box, () => SECTIONS[name](box)); });
onResize(() => redraws.forEach((f) => f()));
