// Parliamentary amendments: what was committed and paid, where it went, who sent it and who received it.
import { $, asset, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L } from "../lib/i18n.js";
import { setupPage } from "../lib/page.js";

setupPage();

const TYPES = [
  ["individual", L("Individual", "Individual")], ["especial", L("Pix (transferência especial)", "Individual “Pix”")], ["bancada", L("De bancada", "State bench")],
  ["comissao", L("De comissão", "Committee")], ["relator", L("De relator", "Rapporteur")],
];
const typeName = Object.fromEntries(TYPES);
const typeColor = (t) => C.slot(TYPES.findIndex(([k]) => k === t) + 1);
const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const select = (label, options, value, onChange) => {
  const s = el("select", {}, ...options.map((o) => el("option", { value: o.value ?? o, textContent: o.label ?? o, selected: String(o.value ?? o) === String(value) })));
  s.addEventListener("change", () => onChange(s.value));
  return el("label", {}, label, s);
};
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const day = (v) => el("span", { style: "white-space:nowrap", textContent: v ?? "" });   // 2026-11 never breaks at the hyphen
const redraws = [];
const later = (f) => { redraws.push(f); f(); };
const PERIODS = [
  { value: "57", label: L("Orçamentos 2024–2027 (57ª legislatura)", "Budgets 2024–2027 (57th legislature)"), years: [2024, 2025, 2026, 2027] },
  { value: "56", label: L("Orçamentos 2020–2023 (56ª legislatura)", "Budgets 2020–2023 (56th legislature)"), years: [2020, 2021, 2022, 2023] },
  { value: "55", label: L("Orçamentos 2016–2019 (55ª legislatura)", "Budgets 2016–2019 (55th legislature)"), years: [2016, 2017, 2018, 2019] },
  { value: "all", label: L("Todos os anos desde 2014", "Every year since 2014"), years: null },
];
const inPeriod = (p, y) => { const P = PERIODS.find((x) => x.value === p); return !P.years || P.years.includes(+y); };

// Labels used by several tables, charts and selects.
const T = {
  year: L("Ano", "Year"), type: L("Tipo", "Type"), amendments: L("Emendas", "Amendments"), committed: L("Empenhado", "Committed"), paid: L("Pago", "Paid"),
  party: L("Partido", "Party"), period: L("Período", "Period"), everyType: L("Todos os tipos", "Every type"), otherParties: L("Outros partidos", "Other parties"),
  legalNature: L("Natureza jurídica", "Legal nature"), median: (v) => L(`mediana ${pct(v)}`, `median ${pct(v)}`),
  inhabitants: (n) => L(`${fmt(n)} habitantes`, `${fmt(n)} inhabitants`),
};

let ANOS;
async function anos() {
  if (!ANOS) {
    const rows = await data("site/emendas/anos.csv");
    const years = [...new Set(rows.map((r) => +r.ano))].sort((a, b) => a - b);
    const get = (y, t, k) => sum(rows.filter((r) => +r.ano === y && (!t || r.tipo === t)).map((r) => +r[k]));
    ANOS = { rows, years, get, current: years[years.length - 1], complete: years[years.length - 2] };
  }
  return ANOS;
}

// ------------------------------------------------------------ overview

async function overview(root) {
  const A = await anos(), y = A.complete;
  const paid = A.get(y, null, "pago"), committed = A.get(y, null, "empenhado"), pix = A.get(y, "especial", "pago");
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L(`Pago do orçamento de ${y}`, `Paid for the ${y} budget`), value: brl(paid), sub: L(`de ${brl(committed)} empenhados (${pct(paid / committed)})`, `of ${brl(committed)} committed (${pct(paid / committed)})`) },
    { label: L("Enviado como “emendas Pix”", "Sent as “Pix” transfers"), value: pct(pix / paid), sub: L(`${brl(pix)}: direto para as contas de estados e municípios, sem finalidade definida`, `${brl(pix)}: straight to state and town accounts, with no defined purpose`) },
    { label: L(`O orçamento de ${A.current} até agora`, `The ${A.current} budget so far`), value: brl(A.get(A.current, null, "pago")), sub: L(`pagos de ${brl(A.get(A.current, null, "empenhado"))} empenhados`, `paid of ${brl(A.get(A.current, null, "empenhado"))} committed`) },
    { label: L("Pago desde 2014", "Paid since 2014"), value: brl(sum(A.years.map((x) => A.get(x, null, "pago")))), sub: plural(A.years.length, L("orçamento", "budget"), L("orçamentos", "budgets")) },
  ]);
  const g = el("div", { className: "grid2" }), c1 = chart(), c2 = chart();
  g.append(card(L("Empenhado, por tipo", "Committed, by type"),
    L("Valores que o governo se comprometeu a pagar (empenho), por ano do orçamento. As emendas de relator antes de 2020 são ajustes do relator-geral ao orçamento (em 2016 e 2017, sobretudo repasses de saúde aos estados), não as RP 9 de 2020–2022.",
      "Amounts the government committed to pay (empenhado), by budget year. Rapporteur amendments before 2020 are the general rapporteur's adjustments to the budget (in 2016 and 2017 mostly health transfers to states), not the RP 9 of 2020–2022."), c1),
    card(L("Pago, por tipo", "Paid, by type"), L(`O que já foi de fato pago, incluindo restos a pagar. O orçamento de ${A.current} ainda está em execução.`, `What has actually been paid so far, including carried-over payments. ${A.current} is still running.`), c2));
  root.append(g);
  const tbl = { rows: A.rows, cols: [{ key: "ano", label: T.year, text: true }, { key: "tipo", label: T.type, text: true, fmt: (v) => typeName[v] || v }, { key: "emendas", label: T.amendments, fmt: (v) => fmt(v) }, { key: "empenhado", label: T.committed, fmt: (v) => brl(v) }, { key: "pago", label: T.paid, fmt: (v) => brl(v) }], name: "amendments-by-year" };
  const stackOf = (k) => TYPES.map(([t, name]) => ({ name, color: typeColor(t), values: A.years.map((x) => A.get(x, t, k)) }));
  later(() => { C.stack(c1, { x: A.years, series: stackOf("empenhado"), format: (v) => brl(v, 0), table: tbl }); C.stack(c2, { x: A.years, series: stackOf("pago"), format: (v) => brl(v, 0), table: { ...tbl, name: "amendments-paid-by-year" } }); });
  const c3 = chart();
  root.append(card(L("Quanto do empenhado chega a ser pago", "How much of what is committed gets paid"),
    L("Pago como parcela do empenhado, por ano do orçamento e tipo. As emendas individuais são impositivas (de pagamento obrigatório) desde uma emenda constitucional de 2015, e as de bancada desde o orçamento de 2020; as emendas de relator de 2020–2022 (RP 9, o “orçamento secreto”) não eram, e o STF acabou com elas em dezembro de 2022.",
      "Paid as a share of committed, by budget year and type. Individual amendments are mandatory (impositivas) since a 2015 constitutional amendment, bench amendments since the 2020 budget; the rapporteur amendments of 2020–2022 (RP 9, the 'secret budget') were not, and were ended by the Supreme Court in December 2022."), c3));
  later(() => C.line(c3, {
    x: "num", y: { min: 0, max: 1, format: (v) => pct(v) }, height: 240,
    series: TYPES.map(([t, name]) => ({ name, color: typeColor(t), points: A.years.map((x) => { const e = A.get(x, t, "empenhado"); return [x, e > 1e6 ? A.get(x, t, "pago") / e : null]; }) })),
  }));
  const rel = sum([2020, 2021, 2022].map((x) => A.get(x, "relator", "pago")));
  const pix0 = A.years.find((x) => A.get(x, "especial", "pago") > 0);
  root.append(el("p", { className: "finding", textContent: L(
    `As transferências especiais (“emendas Pix”) começam no orçamento de ${pix0} e chegam a ${pct(pix / paid)} do que foi pago do orçamento de ${y}. As emendas de relator pagaram ${brl(rel)} em 2020–2022, dinheiro cujos verdadeiros padrinhos o arquivo não nomeia.`,
    `“Pix” transfers start with the ${pix0} budget and reach ${pct(pix / paid)} of what was paid for ${y}. Rapporteur amendments paid ${brl(rel)} in 2020–2022, money whose real sponsors the file does not name.`) }));
}

// ------------------------------------------------------------ map

async function map(root) {
  const [rows, entes, mun, ufs] = await Promise.all([data("site/emendas/municipios.csv"), data("siconfi/entes.csv"), asset("maps/municipios.json"), asset("maps/ufs.json")]);
  const ente = new Map(entes.map((r) => [r.cod_ibge, r]));
  const years = [...new Set(rows.map((r) => +r.ano))].sort((a, b) => a - b);
  let year = +(params.get("y") || years[years.length - 2]), pix = params.get("t") === "pix", measure = params.get("v") || "pc", picked = params.get("m") || "";
  const controls = el("div", { className: "controls" }), mbox = chart(), side = el("div"), town = el("div"), states = chart();
  const grid = el("div", { className: "grid2" });
  grid.append(card(L("Onde o dinheiro caiu", "Where the money landed"),
    L("Dinheiro de emendas pago no ano a favorecidos de cada município: a prefeitura e seus fundos, e as organizações e empresas de lá. Cor: a posição do município entre todos (veja a legenda). Clique num município para ver o histórico.",
      "Amendment money paid in the year to recipients located in each town: the town hall and its funds, and the organisations and companies there. Colour: the town's rank among all towns (see the key). Click a town for its history."), mbox), side);
  root.append(controls, grid, card(L("Por estado", "By state"), L("Pago a favorecidos de cada estado, por habitante.", "Paid to recipients in each state, per inhabitant."), states), town);
  const draw = () => {
    controls.replaceChildren(
      select(L("Ano do pagamento", "Year paid"), [...years].reverse(), year, (v) => { year = +v; setParam("y", v); draw(); }),
      select(T.amendments, [{ value: "", label: T.everyType }, { value: "pix", label: L("Só “emendas Pix”", "“Pix” transfers only") }], pix ? "pix" : "", (v) => { pix = v === "pix"; setParam("t", v, ""); draw(); }),
      select(L("Medida", "Measure"), [{ value: "pc", label: L("Por habitante", "Per inhabitant") }, { value: "total", label: "Total" }], measure, (v) => { measure = v; setParam("v", v, "pc"); draw(); }));
    const val = new Map(rows.filter((r) => +r.ano === year).map((r) => [r.municipio_ibge, +(pix ? r.pix : r.valor)]));
    const value = (code) => {
      const v = val.get(code);
      if (!v || v <= 0) return null;
      if (measure !== "pc") return v;
      const pop = +(ente.get(code)?.populacao || 0);
      return pop > 0 ? v / pop : null;
    };
    const sorted = [...val.keys()].map(value).filter((v) => v != null).sort((a, b) => a - b);
    const rank = (v) => { let lo = 0, hi = sorted.length; while (lo < hi) { const m = (lo + hi) >> 1; if (sorted[m] < v) lo = m + 1; else hi = m; } return lo / Math.max(1, sorted.length - 1); };
    const f = measure === "pc" ? (v) => L(`R$ ${fmt(v, 2)} por habitante`, `R$ ${fmt(v, 2)} per inhabitant`) : (v) => brl(v);
    C.choropleth(mbox, {
      shapes: mun.shapes, viewBox: mun.viewBox, outline: ufs.shapes, outlineWidth: 1.2,
      value, color: (v) => C.seq(0.08 + 0.92 * rank(v)),
      tip: (c, v) => { const e = ente.get(c); return [el("strong", { textContent: e ? `${e.ente} (${e.uf})` : c }), el("div", { className: "row", textContent: v == null ? L("nada pago aqui neste ano", "nothing paid here this year") : f(v) }), e ? el("div", { className: "row", textContent: T.inhabitants(+e.populacao) }) : null].filter(Boolean); },
      onClick: (c) => { picked = c; setParam("m", c); showTown(); },
      title: L(`Dinheiro de emendas pago por município, ${year}`, `Amendment money paid by municipality, ${year}`),
    });
    C.colorKey(mbox, { color: (t) => C.seq(0.08 + 0.92 * t), from: L("menos", "less"), to: L("mais", "more"), label: L("municípios em ordem", "towns ranked") });
    const towns = [...val.keys()].map((c) => ({ c, v: value(c), e: ente.get(c) })).filter((x) => x.v != null && x.e && (measure !== "pc" || +x.e.populacao >= 10000));
    towns.sort((a, b) => b.v - a.v);
    const bx = chart();
    side.replaceChildren(card(measure === "pc" ? L(`Mais por habitante (municípios com ${fmt(10000)} habitantes ou mais)`, `Most per inhabitant (towns of ${fmt(10000)}+)`) : L("Os que mais receberam", "The most"), null, bx));
    C.bars(bx, { rows: towns.slice(0, 20).map((x) => ({ label: `${x.e.ente} (${x.e.uf})`, value: x.v, code: x.c })), format: (v) => (measure === "pc" ? `R$ ${fmt(v, 0)}` : brl(v)), onClick: (r) => { picked = r.code; setParam("m", r.code); showTown(); }, labelWidth: 200 });
    const byUf = new Map(), popUf = new Map();
    for (const e of entes) popUf.set(e.uf, (popUf.get(e.uf) || 0) + +e.populacao);
    for (const [c, v] of val) { const e = ente.get(c); if (e) byUf.set(e.uf, (byUf.get(e.uf) || 0) + v); }
    C.bars(states, { rows: [...byUf].map(([uf, v]) => ({ label: uf, value: v / popUf.get(uf), note: brl(v) })).sort((a, b) => b.value - a.value), format: (v) => `R$ ${fmt(v, 0)}`, barHeight: 14, labelWidth: 40 });
    showTown();
  };
  const showTown = () => {
    if (!picked || !ente.has(picked)) { town.replaceChildren(); return; }
    const e = ente.get(picked), mine = rows.filter((r) => r.municipio_ibge === picked);
    const c = chart();
    town.replaceChildren(card(`${e.ente} (${e.uf}), ${T.inhabitants(+e.populacao)}`, L("Dinheiro de emendas pago a cada ano a favorecidos deste município.", "Amendment money paid each year to recipients in this town."), c));
    C.stack(c, { x: years, height: 200, format: (v) => brl(v),
      series: [{ name: L("“Emendas Pix”", "“Pix” transfers"), color: typeColor("especial"), values: years.map((y) => sum(mine.filter((r) => +r.ano === y).map((r) => +r.pix))) },
        { name: L("Outras emendas", "Other amendments"), color: typeColor("individual"), values: years.map((y) => sum(mine.filter((r) => +r.ano === y).map((r) => +r.valor - +r.pix))) }],
      table: { rows: mine, cols: [{ key: "ano", label: T.year, text: true }, { key: "valor", label: T.paid, fmt: (v) => brl(v) }, { key: "pix", label: L("dos quais “Pix”", "of which “Pix”"), fmt: (v) => brl(v) }], name: `town-${picked}` } });
  };
  later(draw);
}

// ------------------------------------------------------------ authors

async function authors(root) {
  const [pa, ref, deps] = await Promise.all([data("emendas/por_autor.csv"), data("site/emendas/autores.csv"), data("views/deputados_57.csv")]);
  const who = new Map(ref.map((r) => [r.autor_codigo, r]));
  let period = params.get("p") || "57", kind = params.get("k") || "individual";
  const controls = el("div", { className: "controls" }), tb = el("div"), lz = chart(), parties = chart(), sc = chart();
  const g = el("div", { className: "grid2" });
  g.append(card(L("Quão desigual", "How unequal"),
    L("Curva de Lorenz do dinheiro pago entre os autores individuais: quanto mais abaixo da diagonal, mais o dinheiro se concentra em poucos autores.",
      "Lorenz curve of the money paid across individual authors: the further below the diagonal, the more a few authors account for most of it."), lz),
    card(L("Pago, por partido do autor", "Paid, by the author's party"), L("Partido mais recente de cada autor ligado à Câmara ou ao Senado.", "Latest party of each author linked to the Câmara or Senado."), parties));
  root.append(controls, g, card(L("Autores", "Authors"),
    L("Deputados, senadores, bancadas estaduais e comissões, com os nomes que o Portal usa; partido, estado e casa vêm do cruzamento de cadastros do political-eye. Os códigos mudam a cada mandato, então uma mesma pessoa pode ter duas linhas.",
      "Deputies, senators, state benches and committees, as the Portal names them; party, state and house through political-eye's crosswalk. Codes change with each mandate, so one person can have two rows."), tb),
    card(L("Apoio ao governo e emendas pagas, deputados da 57ª legislatura", "Government support and amendments paid, deputies of the 57th legislature"),
      L("Cada ponto é um deputado: com que frequência votou com o governo (votações nominais da Câmara, desde 2023), contra as emendas pagas a ele nos orçamentos de 2024–2027. Uma associação, não uma causa: as emendas individuais têm pagamento obrigatório por lei, então as diferenças são sobretudo de calendário, e alguns deputados tomaram posse depois.",
        "Each dot is a deputy: how often they voted with the Government (Câmara roll calls, 2023–), against the amendments paid to them for the 2024–2027 budgets. An association, not a cause: individual amendments must be paid by law, so differences are mostly of timing, and some deputies took office late."), sc));
  const draw = () => {
    controls.replaceChildren(select(T.period, PERIODS, period, (v) => { period = v; setParam("p", v, "57"); draw(); }),
      select(T.amendments, [{ value: "individual", label: L("Individuais (com Pix)", "Individual (incl. “Pix”)") }, { value: "all", label: T.everyType }], kind, (v) => { kind = v; setParam("k", v, "individual"); draw(); }));
    const keep = pa.filter((r) => r.autor_codigo !== "" && inPeriod(period, r.ano) && (kind === "all" || r.tipo === "individual" || r.tipo === "especial"));
    const by = new Map();
    for (const r of keep) {
      const x = by.get(r.autor_codigo) || { autor_codigo: r.autor_codigo, autor: r.autor, emendas: 0, empenhado: 0, pago: 0 };
      x.emendas += +r.emendas; x.empenhado += +r.empenhado; x.pago += +r.pago; by.set(r.autor_codigo, x);
    }
    const rows = [...by.values()].map((x) => { const w = who.get(x.autor_codigo) || {}; return { ...x, casa: w.casa === "camara" ? "Câmara" : w.casa === "senado" ? "Senado" : "", partido: w.partido || "", uf: w.uf || "", share: x.empenhado ? x.pago / x.empenhado : null }; });
    table(tb, rows, [
      { key: "autor", label: L("Autor", "Author"), text: true }, { key: "casa", label: L("Casa", "House"), text: true }, { key: "partido", label: T.party, text: true }, { key: "uf", label: "UF", text: true },
      { key: "emendas", label: T.amendments, fmt: (v) => fmt(v) }, { key: "empenhado", label: T.committed, fmt: (v) => brl(v) }, { key: "pago", label: T.paid, fmt: (v) => brl(v) }, { key: "share", label: L("Parcela paga", "Paid share"), fmt: (v) => pct(v) },
    ], { sortBy: "pago", pageSize: 15, name: `authors-${period}` });
    const people = rows.filter((r) => r.casa);
    const G = C.lorenz(lz, { values: people.map((r) => r.pago), name: L("Autores", "Authors") });
    lz.querySelector(".legend")?.append(el("span", { textContent: `Gini ${fmt(G, 2)}` }));
    const byParty = new Map();
    for (const r of people) if (r.partido) byParty.set(r.partido, (byParty.get(r.partido) || 0) + r.pago);
    C.bars(parties, { rows: [...byParty].sort((a, b) => b[1] - a[1]).slice(0, 15).map(([label, value]) => ({ label, value, color: label === "PT" ? css("--a") : label === "PL" ? css("--b") : css("--other") })), format: (v) => brl(v),
      legend: [{ label: "PT", color: css("--a") }, { label: "PL", color: css("--b") }, { label: T.otherParties, color: css("--other") }] });
  };
  const drawScatter = () => {
    const pts = deps.filter((d) => d.with_gov !== "" && +d.n_gov >= 50).map((d) => ({ x: +d.with_gov, y: +d.emendas_pago, label: d.nome, title: `${d.nome} (${d.partido}-${d.uf})`, rows: [L(`${fmt(+d.n_gov)} votos com orientação do governo`, `${fmt(+d.n_gov)} votes with a government line`)], color: d.partido === "PT" ? css("--a") : d.partido === "PL" ? css("--b") : css("--other"), z: d.partido === "PT" || d.partido === "PL" ? 1 : 0 }));
    const rank = (xs) => { const s = xs.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]); const r = new Array(xs.length); s.forEach(([, i], k) => { r[i] = k; }); return r; };
    const rx = rank(pts.map((p) => p.x)), ry = rank(pts.map((p) => p.y)), n = pts.length, mx = (n - 1) / 2;
    const rho = sum(rx.map((v, i) => (v - mx) * (ry[i] - mx))) / Math.sqrt(sum(rx.map((v) => (v - mx) ** 2)) * sum(ry.map((v) => (v - mx) ** 2)));
    C.scatter(sc, { points: pts, x: { label: L("Votos com o governo", "Votes with the government"), format: (v) => pct(v), min: 0, max: 1 }, y: { label: L("Emendas pagas", "Amendments paid"), format: (v) => brl(v, 0) }, labels: 6, height: 340,
      legend: [{ label: "PT", color: css("--a"), shape: "dot" }, { label: "PL", color: css("--b"), shape: "dot" }, { label: T.otherParties, color: css("--other"), shape: "dot" }] });
    sc.append(el("p", { className: "finding", textContent: L(`Correlação de postos de Spearman entre ${fmt(n)} deputados: ${fmt(rho, 2)}.`, `Spearman rank correlation over ${fmt(n)} deputies: ${fmt(rho, 2)}.`) }));
  };
  later(draw);
  later(drawScatter);
}

// ------------------------------------------------------------ flows

async function flows(root) {
  const [au, fl, ref] = await Promise.all([data("site/emendas/autor_uf.csv"), data("site/emendas/fluxos.csv"), data("site/emendas/autores.csv")]);
  const who = new Map(ref.map((r) => [r.autor_codigo, r]));
  let period = params.get("p") || "57";
  const controls = el("div", { className: "controls" }), h = chart(), hm = chart();
  root.append(controls, card(L("Quanto do seu dinheiro os autores mandam para o próprio estado", "How much of their money authors send to their own state"),
    L("Cada autor cai numa faixa: a parcela do que foi pago por suas emendas que foi para o estado de origem (emendas aplicadas ao país inteiro contam como fora do estado). Deputados e senadores identificados.",
      "One author per bar range: the share of what was paid for their amendments that went to their home state (amendments applied to the whole country count as not home). Linked deputies and senators."), h),
    card(L("Do estado do autor para onde o dinheiro foi", "From the author's state to where the money went"),
      L("Cada linha é o estado dos autores; cada célula, a parcela do dinheiro desse estado que foi para aquele destino (ou para o país todo). A diagonal é o dinheiro que ficou em casa.",
        "Each row is the authors' state; each cell the share of its money that went to that state (or nationally). The diagonal is money sent home."), hm));
  const draw = () => {
    controls.replaceChildren(select(T.period, PERIODS, period, (v) => { period = v; setParam("p", v, "57"); draw(); }));
    const by = new Map();
    for (const r of au) {
      if (!inPeriod(period, r.ano)) continue;
      const x = by.get(r.autor_codigo) || [0, 0, 0]; x[0] += +r.pago; x[1] += +r.pago_estado; x[2] += +r.pago_nacional; by.set(r.autor_codigo, x);
    }
    const shares = [...by].filter(([, x]) => x[0] > 1e5).map(([c, x]) => x[1] / x[0]);
    const med = [...shares].sort((a, b) => a - b)[Math.floor(shares.length / 2)];
    C.histogram(h, { values: shares, domain: [0, 1], bins: 20, refs: [{ x: med, label: T.median(med) }], format: (v) => pct(v), xLabel: L("parcela paga no próprio estado do autor", "share paid in the author's own state"), unit: L("autores", "authors") });
    const f = fl.filter((r) => inPeriod(period, r.ano));
    const total = new Map(), cell = new Map();
    for (const r of f) { total.set(r.uf_autor, (total.get(r.uf_autor) || 0) + +r.pago); const k = `${r.uf_autor}|${r.uf_destino || "BR"}`; cell.set(k, (cell.get(k) || 0) + +r.pago); }
    const rows = [...total.keys()].sort(), cols = [...rows, "BR"];
    C.heatmap(hm, { rows, cols: cols.map((c) => (c === "BR" ? L("Nacional", "National") : c)), value: (i, j) => { const v = cell.get(`${rows[i]}|${cols[j]}`); return v ? v / total.get(rows[i]) : null; }, color: (v) => C.seq(Math.sqrt(v)),
      cell: 26, rowHeight: 18, labelWidth: 40, colLabelHeight: 50, allColLabels: true, cellText: (v) => (v >= 0.05 ? Math.round(v * 100) : ""), dark: (v) => Math.sqrt(v) > 0.55,
      tip: (i, j, v) => [el("strong", { textContent: `${rows[i]} → ${cols[j] === "BR" ? L("nacional", "national") : cols[j]}` }), el("div", { className: "row", textContent: L(`${pct(v, 1)} de ${brl(total.get(rows[i]))}`, `${pct(v, 1)} of ${brl(total.get(rows[i]))}`) })] });
  };
  later(draw);
}

// ------------------------------------------------------------ recipients

const GROUPS = [
  [L("Municípios", "Municipalities"), /Munic|Consórcio/i], [L("Estados", "States"), /Estad|Distrito Federal/i], [L("Órgãos federais", "Federal bodies"), /Federal|Unidade Gestora|União/i],
  [L("Entidades sem fins lucrativos", "Non-profits"), /Associação|Fundação Privada|Organização|Serviço Social|Entidade/i], [L("Estatais e bancos públicos", "State-owned companies and banks"), /Economia Mista|Empresa Pública/i],
  [L("Empresas", "Companies"), /Sociedade|Empresári|Cooperativa|Limitada|Empresa/i],
];
const OTHER = L("Pessoas físicas e outros", "Individuals and other");
const group = (n) => (GROUPS.find(([, re]) => re.test(n)) || [OTHER])[0];

async function recipients(root) {
  const [nat, top] = await Promise.all([data("site/emendas/natureza.csv"), data("site/emendas/favorecidos.csv")]);
  const years = [...new Set(nat.map((r) => +r.ano))].sort((a, b) => a - b);
  const c1 = chart(), tb = el("div");
  root.append(card(L("Quem recebe o dinheiro", "Who receives the money"),
    L("Pagamentos pela natureza jurídica do favorecido, em grupos. Fundos municipais (saúde, educação) contam como municípios. Pessoas físicas são somadas, nunca nomeadas; bancos aparecem com frequência porque são a conta operadora de um programa.",
      "Payments by the recipient's legal nature, grouped. Municipal funds (health, education) count with municipalities. Private individuals are summed, never named; banks often appear because they are the operating account of a programme."), c1),
    card(L(`Os ${fmt(1000)} favorecidos que mais receberam desde 2014`, `The ${fmt(1000)} recipients paid the most since 2014`),
      L("Pessoas jurídicas e órgãos públicos, por CNPJ ou código de unidade gestora.", "Legal entities and public bodies, by CNPJ or government unit code."), tb));
  const names = [...GROUPS.map(([n]) => n), OTHER];
  later(() => C.stack(c1, { x: years, format: (v) => brl(v, 0), height: 260, series: names.map((g, i) => ({ name: g, color: i < 6 ? C.slot(i + 1) : css("--other"), values: years.map((y) => sum(nat.filter((r) => +r.ano === y && group(r.natureza) === g).map((r) => +r.valor))) })),
    table: { rows: nat.map((r) => ({ ...r, grupo: group(r.natureza) })), cols: [{ key: "ano", label: T.year, text: true }, { key: "grupo", label: L("Grupo", "Group"), text: true }, { key: "natureza", label: T.legalNature, text: true }, { key: "valor", label: T.paid, fmt: (v) => brl(v) }], name: "recipients-nature" } }));
  table(tb, top, [
    { key: "nome", label: L("Favorecido", "Recipient"), text: true, wrap: true }, { key: "favorecido", label: L("CNPJ / código", "CNPJ / code"), text: true }, { key: "natureza_juridica", label: T.legalNature, text: true, wrap: true },
    { key: "uf", label: "UF", text: true }, { key: "emendas", label: T.amendments, fmt: (v) => fmt(v) }, { key: "primeiro", label: L("Primeiro", "First"), text: true, fmt: day }, { key: "ultimo", label: L("Último", "Last"), text: true, fmt: day }, { key: "total", label: T.paid, fmt: (v) => brl(v) },
  ], { sortBy: "total", pageSize: 15, name: "top-recipients" });
}

// ------------------------------------------------------------ timing

async function timing(root) {
  const m = await data("site/emendas/meses.csv");
  const months = [...new Set(m.map((r) => r.ano_mes))].sort();
  const total = (mo, t) => sum(m.filter((r) => r.ano_mes === mo && (!t || r.tipo === t)).map((r) => +r.valor));
  const c1 = chart(), c2 = chart();
  const ELECTIONS = [2016, 2018, 2020, 2022, 2024, 2026].map((y) => ({ x: `${y}-10`, label: L("eleição", "election") }));
  root.append(card(L("Pagamentos a cada mês", "Payments each month"),
    L("Pago a favorecidos a cada mês, para todos os tipos e só para as “emendas Pix”. Tracejado: eleições de outubro (municipais em 2016, 2020 e 2024; gerais em 2018, 2022 e 2026).",
      "Paid to recipients each month, for every type and for “Pix” transfers alone. Dashed: October elections (municipal in 2016, 2020, 2024; general in 2018, 2022, 2026)."), c1),
    card(L("Em que época do ano o dinheiro sai: anos de eleição contra os demais", "When in the year money is paid: election years against the others"),
      L("Parcela média dos pagamentos do ano feita em cada mês, nos anos completos de 2015 a 2025. A lei eleitoral proíbe transferências voluntárias a municípios nos três meses antes da eleição, o que aparece como uma corrida antes de julho.",
        "Average share of a year's payments made in each month, for complete years 2015–2025. Electoral law bars voluntary transfers to towns in the three months before an election, which shows up as a rush before July."), c2));
  later(() => C.line(c1, { x: "month", y: { format: (v) => brl(v, 0) }, marks: ELECTIONS, height: 260,
    series: [{ name: L("Todas as emendas", "All amendments"), color: C.slot(1), points: months.map((mo) => [mo, total(mo)]) }, { name: L("Só “emendas Pix”", "“Pix” only"), color: C.slot(2), points: months.map((mo) => [mo, total(mo, "especial")]) }] }));
  const share = (years) => Array.from({ length: 12 }, (_, i) => {
    const xs = years.map((y) => { const yt = sum(Array.from({ length: 12 }, (_, k) => total(`${y}-${String(k + 1).padStart(2, "0")}`))); return yt ? total(`${y}-${String(i + 1).padStart(2, "0")}`) / yt : null; }).filter((v) => v != null);
    return [i + 1, xs.length ? sum(xs) / xs.length : null];
  });
  const ev = [2016, 2018, 2020, 2022, 2024], od = [2015, 2017, 2019, 2021, 2023, 2025];
  const elect = L("Anos de eleição", "Election years"), other = L("Outros anos", "Other years");
  later(() => C.line(c2, { x: "num", y: { min: 0, format: (v) => pct(v) }, height: 240,
    series: [{ name: elect, color: C.slot(2), points: share(ev) }, { name: other, color: C.slot(1), points: share(od) }],
    table: { rows: share(ev).map(([mo, v], i) => ({ month: mo, election: v, other: share(od)[i][1] })), cols: [{ key: "month", label: L("Mês", "Month") }, { key: "election", label: elect, fmt: (v) => pct(v, 1) }, { key: "other", label: other, fmt: (v) => pct(v, 1) }], name: "payment-seasonality" } }));
}

const SECTIONS = { overview, map, authors, flows, recipients, timing };
tabs((name) => { const box = $(`#tab-${name}`); guard(box, () => SECTIONS[name](box)); });
onResize(() => redraws.forEach((f) => f()));
