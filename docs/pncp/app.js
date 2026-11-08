// Public contracts (PNCP): who buys, who sells, how concentrated, where, and under which mayor's party.
import { $, asset, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";

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
const cnpjFmt = (c) => (/^\d{14}$/.test(c) ? `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}` : c);
const short = (s, k = 34) => { s = String(s || ""); k = /[a-z]/.test(s) ? k : Math.round(k * 0.84); return s.length > k ? `${s.slice(0, k - 1)}…` : s; };
const redraws = [];
const later = (f) => { redraws.push(f); f(); };

const SPH = { F: "Federal", E: "State", M: "Municipal", D: "Federal District", N: "Other" };
const sphColor = (k) => ({ F: C.slot(1), E: C.slot(2), M: C.slot(3), D: C.slot(4), N: css("--other") })[k] || css("--other");
const CAT = { "Serviços": "Services", "Obras": "Public works", "Compras": "Goods", "Serviços de Engenharia": "Engineering services", "Mão de Obra": "Outsourced labour",
  "Informática (TIC)": "IT", "Serviços de Saúde": "Health services", "Locação Imóveis": "Property rental", "Cessão": "Assignment", "Alienação de Bens Móveis/Imóveis": "Sale of assets" };
const cat = (c) => CAT[c] || c || "Not stated";
const R = () => data("site/pncp/resumo.json");
const sancoesLink = (cnpj) => `../sancoes/?tab=company&cnpj=${cnpj}`;

async function coverage() {
  const r = await R(), c = r.coverage, box = $("#coverage");
  box.replaceChildren(el("div", { className: "card wide" },
    el("h2", { textContent: `History read: ${plural(c.days_read, "day")} of ${fmt(c.span_days)}` }),
    el("div", { className: "meter" }, el("i", { style: `width:${Math.max(0.5, 100 * c.share).toFixed(1)}%` })),
    el("p", { className: "note", textContent: c.days_read ? `From ${c.first} to ${c.last}, newest first, out of every day since ${c.since}. The daily job reads more each night; totals below cover the days read, and the large-contract tables hold every large contract published or amended on those days.` : "No day read yet." })));
}

// ------------------------------------------------------------ overview

async function overview(root) {
  const r = await R(), t = r.totals, L = r.large;
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Contracts published", value: fmt(t.contratos), sub: `on the ${plural(r.coverage.days_read, "day")} read` },
    { label: "Their value", value: brl(t.valor), sub: "global value, as published" },
    { label: "Share in contracts of R$ 1 M+", value: pct(L.share_of_value), sub: `${fmt(L.on_days_read.contratos)} large contracts on those days` },
    { label: "Large contracts followed", value: fmt(L.contratos), sub: `${brl(L.valor)}; median ${brl(L.median)}` },
  ]);
  const d = await data("site/pncp/diario.csv");
  let metric = params.get("m") || "valor";
  const ctl = el("div", { className: "controls" }), c1 = chart();
  root.append(card("Contracts published per day", "Every contract the PNCP published each day, by the buyer's sphere.", ctl, c1));
  const daysAll = [...new Set(d.map((x) => x.dia))].sort();
  const draw = () => {
    ctl.replaceChildren(select("Measure", [{ value: "valor", label: "Value" }, { value: "contratos", label: "Number of contracts" }], metric, (v) => { metric = v; setParam("m", v, "valor"); draw(); }));
    const f = metric === "valor" ? (v) => brl(v, 0) : (v) => fmt(v);
    C.line(c1, { x: "day", height: 240, y: { format: f, min: 0 }, empty: "No day read yet.",
      series: ["M", "E", "F", "D", "N"].map((k) => ({ name: SPH[k], color: sphColor(k), points: daysAll.map((dd) => { const x = d.find((y) => y.dia === dd && y.esfera === k); return [dd, x ? +x[metric] : 0]; }) }))
        .filter((s) => s.points.some((p) => p[1] > 0)) });
  };
  later(draw);
  const c2 = chart(), c3 = chart();
  root.append(grid(card("Who buys", "Contracts and value on the days read, by the buyer's sphere.", c2), card("Who sells", "By kind of supplier: companies (PJ), private individuals (PF) and foreign suppliers (PE).", c3)));
  const bs = [...t.by_sphere].sort((a, b) => b.valor - a.valor);
  later(() => C.bars(c2, { rows: bs.map((x) => ({ label: SPH[x.esfera] || x.esfera, value: x.valor, note: `${fmt(x.contratos)} contracts · average ${brl(x.valor / x.contratos)}`, color: sphColor(x.esfera) })), format: (v) => brl(v, 1), labelWidth: 130 }));
  const KIND = { PJ: "Companies", PF: "Individuals", PE: "Foreign" };
  const bt = [...t.by_supplier].sort((a, b) => b.valor - a.valor);
  later(() => C.bars(c3, { rows: bt.map((x) => ({ label: KIND[x.fornecedor_tipo] || x.fornecedor_tipo, value: x.valor, note: `${fmt(x.contratos)} contracts`, color: css("--line") })), format: (v) => brl(v, 1), labelWidth: 130 }));
  if (daysAll.length >= 7) {
    const c4 = chart();
    root.append(card("By day of the week", "Average contracts published per weekday, over the days read.", c4));
    const W = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], acc = W.map(() => ({ n: 0, days: new Set() }));
    for (const x of d) { const w = new Date(`${x.dia}T12:00:00Z`).getUTCDay(); acc[w].n += +x.contratos; acc[w].days.add(x.dia); }
    later(() => C.stack(c4, { x: W, height: 200, series: [{ name: "Contracts per day", color: css("--line"), values: acc.map((a) => (a.days.size ? a.n / a.days.size : 0)) }] }));
  }
}

// ------------------------------------------------------------ large contracts

async function large(root) {
  const r = await R(), L = r.large, rows = await data("site/pncp/maiores.csv");
  let uf = params.get("uf") || "", esf = params.get("esf") || "", ct = params.get("cat") || "";
  const c1 = chart(), c2 = chart(), c3 = chart();
  root.append(grid(
    card("How large", "Every contract of R$ 1 million or more on a log scale: each step is ten times the last.", c1),
    card("What is bought", "Large contracts by category, by value.", c2)));
  later(() => C.histogram(c1, { values: L.log_hist.flatMap((n0, i) => Array(n0).fill((L.log_edges[i] + L.log_edges[i + 1]) / 2)), domain: [6, 11], bins: 20, format: (v) => brl(10 ** v, 0), xLabel: "contract value (log scale)", unit: "contracts", height: 220, refs: L.median ? [{ x: Math.log10(L.median), label: `median ${brl(L.median)}` }] : [] }));
  later(() => C.bars(c2, { rows: L.by_category.map((x) => ({ label: cat(x.categoria), value: x.valor, note: `${fmt(x.contratos)} contracts`, color: css("--line") })), format: (v) => brl(v, 1), labelWidth: 170 }));
  root.append(card("Large contracts by month of publication", "Value, by the buyer's sphere. Months before the history read so far hold only contracts amended on the days read.", c3));
  const months = [...new Set(L.by_month.map((x) => x.mes))].sort();
  later(() => C.stack(c3, { x: months, height: 220, format: (v) => brl(v, 0), series: ["F", "E", "M", "D", "N"].map((k) => ({ name: SPH[k], color: sphColor(k), values: months.map((m) => sum(L.by_month.filter((x) => x.mes === m && x.esfera === k).map((x) => x.valor))) })).filter((s) => s.values.some((v) => v > 0)) }));
  const ctl = el("div", { className: "controls" }), tb = el("div");
  const I = L.implausible;
  root.append(card("The largest contracts", `The ${fmt(rows.length)} largest, filtered below; search any column. ${I.contratos ? `${fmt(I.contratos)} contracts were published with a global value more than ${I.ratio} times their initial value (together ${brl(I.publicado)} instead of ${brl(I.usado)}); they are counted at their initial value and marked "fixed".` : ""}`, ctl, tb));
  const ufs = [...new Set(rows.map((x) => x.uf))].filter(Boolean).sort(), cats = [...new Set(rows.map((x) => x.categoria))].sort();
  const t = table(tb, [], [{ key: "assinatura", label: "Signed", text: true, fmt: day }, { key: "orgao", label: "Buyer", text: true, wrap: true }, { key: "uf", label: "UF", text: true },
    { key: "fornecedor_nome", label: "Supplier", text: true, wrap: true }, { key: "objeto", label: "Object", text: true, wrap: true }, { key: "categoria", label: "Category", text: true, fmt: cat },
    { key: "valor", label: "Value", fmt: (v, x) => (+x.suspeito ? el("span", { title: `Published as ${brl(x.valor_publicado)}, ${fmt(+x.valor_publicado / +v, 0)} times its initial value: taken as a typo` }, brl(v), " ", el("span", { className: "flag bad", textContent: "fixed" })) : brl(v)) }],
  { sortBy: "valor", pageSize: 12, name: "large-contracts" });
  const draw = () => {
    ctl.replaceChildren(
      select("State", [{ value: "", label: "Every state" }, ...ufs], uf, (v) => { uf = v; setParam("uf", v, ""); draw(); }),
      select("Sphere", [{ value: "", label: "Every sphere" }, ...Object.entries(SPH).map(([value, label]) => ({ value, label }))], esf, (v) => { esf = v; setParam("esf", v, ""); draw(); }),
      select("Category", [{ value: "", label: "Every category" }, ...cats.map((x) => ({ value: x, label: cat(x) }))], ct, (v) => { ct = v; setParam("cat", v, ""); draw(); }));
    t.update(rows.filter((x) => (!uf || x.uf === uf) && (!esf || x.esfera === esf) && (!ct || x.categoria === ct)));
  };
  draw();
}

// ------------------------------------------------------------ suppliers

async function suppliers(root) {
  const r = await R(), S = r.suppliers, rows = await data("site/pncp/fornecedores.csv");
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Suppliers of large contracts", value: fmt(S.n), sub: "distinct CNPJs (and masked CPFs)" },
    { label: "Concentration (Gini)", value: S.gini == null ? "–" : fmt(S.gini, 2), sub: "0: every supplier gets the same; 1: one gets everything" },
    { label: "Top 1% of suppliers", value: pct(S.top1_share), sub: `of the value; the top 10%: ${pct(S.top10_share)}` },
    { label: "Also on the sanctions lists", value: fmt(S.linked.sancionadas), sub: `of the ${fmt(S.linked.of)} largest suppliers` },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(
    card("How unequal", "Lorenz curve: the share of value (up) held by the smallest suppliers (across). The further below the diagonal, the more the money goes to few.", c1),
    card("The largest suppliers", "By the value of their large contracts.", c2)));
  later(() => C.line(c1, { x: "num", height: 240, y: { min: 0, max: 1, format: (v) => `${Math.round(v * 100)}%` },
    series: [{ name: "Equal shares", color: css("--axis"), width: 1.5, points: [[0, 0], [1, 1]] }, { name: "Actual", color: css("--line"), points: S.lorenz }] }));
  later(() => C.bars(c2, { rows: rows.slice(0, 20).map((x) => ({ label: short(x.nome, 36), title: x.nome, value: +x.valor, note: `${fmt(x.contratos)} contracts · ${fmt(x.orgaos)} buyers`, color: +x.sancionada ? css("--critical") : css("--line") })), format: (v) => brl(v, 1), labelWidth: 260, legend: [{ label: "On CEIS or CNEP", color: css("--critical") }, { label: "Not listed", color: css("--line") }] }));
  const tb = el("div");
  root.append(card("Who they are", "The largest suppliers, and what else ties them to the State: a CEIS or CNEP sanction (click through to its profile), contracts signed while barred, amendment money paid to them directly, and what election campaigns paid them (2018–2026).", tb));
  table(tb, rows, [
    { key: "nome", label: "Supplier", text: true, wrap: true, fmt: (v, x) => (+x.sancionada ? el("a", { className: "linkish", href: sancoesLink(x.cnpj), textContent: v }) : v) },
    { key: "cnpj", label: "CNPJ", text: true, fmt: (v) => day(cnpjFmt(v)) }, { key: "contratos", label: "Contracts" }, { key: "valor", label: "Value", fmt: (v) => brl(v) },
    { key: "orgaos", label: "Buyers" }, { key: "ufs", label: "States" },
    { key: "sancionada", label: "Sanctioned", text: true, fmt: (v, x) => (+v ? el("span", { className: "flag bad", textContent: +x.contratos_sancionada ? `${x.contratos_sancionada} while barred` : "listed" }) : "") },
    { key: "emendas", label: "Amendments", fmt: (v) => (+v ? brl(v) : "") }, { key: "campanhas", label: "Campaigns paid it", fmt: (v, x) => (+v ? `${brl(v)} · ${fmt(x.campanhas_candidatos)} cand.` : "") },
  ], { sortBy: "valor", pageSize: 15, name: "suppliers" });
  const sv = r.sanctioned.by_cobre_sphere;
  if (sv.length) {
    const c3 = chart();
    root.append(card("Contracts signed with a barred supplier", "Contracts of any value whose supplier was under a CEIS or CNEP sanction barring contracting on the signing day, by whether the sanction's scope reaches the buyer. Most sanctions bind only the body or sphere that imposed them. Each one is listed, with the company's sanctions, on the sanctions page.", c3,
      el("p", { className: "finding" }, el("a", { href: "../sancoes/?tab=money", textContent: "See them on the sanctions page →" }))));
    const COBRE = { sim: "Reaches the buyer", possivel: "May reach the buyer", nao: "Does not reach the buyer" };
    const col = (k) => ({ sim: css("--critical"), possivel: css("--warning"), nao: css("--other") })[k];
    const agg = ["sim", "possivel", "nao"].map((k) => ({ k, n: sum(sv.filter((x) => x.cobre === k).map((x) => x.contratos)), v: sum(sv.filter((x) => x.cobre === k).map((x) => x.valor)) }));
    later(() => C.bars(c3, { rows: agg.map((x) => ({ label: COBRE[x.k], value: x.n, note: brl(x.v), color: col(x.k) })), labelWidth: 190 }));
  }
}

// ------------------------------------------------------------ buyers

async function buyers(root) {
  const r = await R(), B = r.buyers, rows = await data("site/pncp/orgaos.csv");
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Buyers of large contracts", value: fmt(B.n), sub: "distinct public bodies (CNPJ)" },
    { label: "With enough contracts to measure", value: fmt(B.with_hhi), sub: "five or more large contracts" },
    { label: "Typical supplier concentration", value: B.hhi_median == null ? "–" : fmt(B.hhi_median, 2), sub: "median HHI: 1 means one supplier takes it all" },
    { label: "Single supplier", value: fmt(B.single_supplier), sub: "buyers whose five or more large contracts all went to one supplier" },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(
    card("How concentrated each buyer's suppliers are", "Herfindahl index of each buyer's large-contract value across its suppliers (the sum of squared shares), for buyers with five or more. Above 0.25 is usually called highly concentrated.", c1),
    card("The largest buyers", "By the value of their large contracts.", c2)));
  later(() => C.histogram(c1, { values: B.hhi_hist.flatMap((n0, i) => Array(n0).fill((i + 0.5) / 20)), domain: [0, 1], bins: 20, format: (v) => fmt(v, 2), xLabel: "HHI", unit: "buyers", height: 220, refs: B.hhi_median != null ? [{ x: 0.25, label: "0.25" }] : [] }));
  later(() => C.bars(c2, { rows: rows.slice(0, 20).map((x) => ({ label: short(x.orgao, 38), title: x.orgao, value: +x.valor, note: `${SPH[x.esfera] || x.esfera}, ${x.uf} · ${fmt(x.contratos)} contracts`, color: sphColor(x.esfera) })), format: (v) => brl(v, 1), labelWidth: 280 }));
  const tb = el("div");
  root.append(card("Buyers and their main supplier", "Sort by HHI or by the main supplier's share to find the bodies that buy almost everything from one company.", tb));
  table(tb, rows, [{ key: "orgao", label: "Buyer", text: true, wrap: true }, { key: "esfera", label: "Sphere", text: true, fmt: (v) => SPH[v] || v }, { key: "uf", label: "UF", text: true },
    { key: "contratos", label: "Contracts" }, { key: "valor", label: "Value", fmt: (v) => brl(v) }, { key: "fornecedores", label: "Suppliers" },
    { key: "hhi", label: "HHI", fmt: (v) => (v === "" ? "" : fmt(+v, 2)) }, { key: "maior_fornecedor_nome", label: "Main supplier", text: true, wrap: true }, { key: "maior_share", label: "Its share", fmt: (v) => pct(+v) }],
  { sortBy: "valor", pageSize: 15, name: "buyers" });
}

// ------------------------------------------------------------ map

async function map(root) {
  const r = await R(), mun = await data("site/pncp/municipios.csv");
  const [ufs, muns] = await Promise.all([asset("maps/ufs.json"), asset("maps/municipios.json")]);
  const c1 = chart(), c2 = chart();
  root.append(grid(
    card("Large contracts per inhabitant, by state", "Every sphere, by the buyer's state. Federal bodies in Brasília weigh on the Federal District.", c1),
    card("States ranked", "", c2)));
  const by = new Map(r.by_uf.map((x) => [String(x.ibge), x]));
  const mx = Math.max(1e-9, ...r.by_uf.map((x) => x.por_habitante || 0));
  later(() => { C.choropleth(c1, { shapes: ufs.shapes, viewBox: ufs.viewBox, stroke: 0.6, maxWidth: 520, value: (k) => by.get(k)?.por_habitante ?? null, color: (v) => C.seq(Math.sqrt(v / mx)),
    tip: (k, v) => { const x = by.get(k); return x ? [el("strong", { textContent: x.uf }), el("div", { className: "row", textContent: `R$ ${fmt(v, 2)} per inhabitant · ${brl(x.valor)} in ${fmt(x.contratos)} contracts` })] : [el("strong", { textContent: k })]; } });
    C.colorKey(c1, { color: (t) => C.seq(Math.sqrt(t)), from: "R$ 0", to: `R$ ${fmt(mx, 0)} per inhabitant` }); });
  const ranked = [...r.by_uf].sort((a, b) => b.por_habitante - a.por_habitante);
  later(() => C.bars(c2, { rows: ranked.map((x) => ({ label: x.uf, value: x.por_habitante, note: brl(x.valor), color: css("--line") })), barHeight: 12, format: (v) => `R$ ${fmt(v, 0)}` }));
  const c3 = chart();
  root.append(card("Municipal bodies' large contracts per inhabitant", "Contracts of R$ 1 million or more signed by each town's own bodies (prefeitura, funds, municipal companies), per inhabitant. Grey: none on the days read.", c3));
  const mm = new Map(mun.map((x) => [x.cod_ibge, x]));
  const vals = mun.map((x) => +x.por_habitante).filter((v) => v > 0).sort((a, b) => a - b);
  const cap = vals[Math.floor(vals.length * 0.95)] || 1;
  later(() => { C.choropleth(c3, { shapes: muns.shapes, viewBox: muns.viewBox, maxWidth: 760, outline: ufs.shapes, outlineWidth: 0.6,
    value: (k) => (mm.get(k) ? +mm.get(k).por_habitante : null), color: (v) => C.seq(Math.sqrt(Math.min(1, v / cap))),
    tip: (k, v) => { const x = mm.get(k); return x ? [el("strong", { textContent: `${x.municipio} (${x.uf})` }), el("div", { className: "row", textContent: `R$ ${fmt(v, 2)} per inhabitant · ${brl(x.valor)} in ${fmt(x.contratos)} contracts, ${fmt(x.fornecedores)} suppliers` })] : [el("strong", { textContent: "No large municipal contract on the days read" })]; } });
    C.colorKey(c3, { color: (t) => C.seq(Math.sqrt(t)), from: "R$ 0", to: `R$ ${fmt(cap, 0)}+ per inhabitant` }); });
}

// ------------------------------------------------------------ mayors' parties

async function parties(root) {
  const r = await R(), rows = (await data("site/pncp/partidos.csv")).map((x) => ({ ...x, municipios: +x.municipios, contratos: +x.contratos, valor: +x.valor, pop_anos: +x.pop_anos, sancionadas: +x.sancionadas, ph: +x.por_habitante_ano, pm: +x.contratos_por_milhao_hab }));
  const big = rows.filter((x) => x.municipios >= 50).sort((a, b) => b.ph - a.ph);
  const allPop = sum(rows.map((x) => x.pop_anos)), allV = sum(rows.map((x) => x.valor)), nContracts = sum(rows.map((x) => x.contratos));
  const early = nContracts < 2000;
  if (early) root.append(el("div", { className: "card wide" }, el("h2", { textContent: "Too early to compare parties" }),
    el("p", { className: "note", textContent: `Only ${fmt(nContracts)} large municipal contracts have been read so far (${plural(r.coverage.days_read, "day")} of history). At this size one large contract moves a party to the top, so the ranking below is noise until more of the history is read; it firms up as the backfill fills in.` })));
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Parties governing 50+ towns", value: fmt(big.length), sub: `in the years ${r.parties.years.join(", ") || "–"}` },
    { label: "Municipal value attributed", value: pct(r.parties.attributed), sub: "of municipal large contracts, to the mayor then in office" },
    { label: "Average, every town", value: `R$ ${fmt(allPop ? allV / allPop : null, 2)}`, sub: "large contracts per inhabitant-year" },
    early ? { label: "Municipal contracts read", value: fmt(nContracts), sub: "too few to rank parties yet" }
      : { label: "Highest party", value: big[0] ? big[0].partido : "–", sub: big[0] ? `R$ ${fmt(big[0].ph, 2)} per inhabitant-year` : "" },
  ]);
  let metric = params.get("pm") || "ph";
  const ctl = el("div", { className: "controls" }), c1 = chart();
  root.append(card("Large municipal contracts by the mayor's party", "Towns grouped by the party of the mayor in office in the year each contract was signed (merged or renamed parties under today's name). Per inhabitant-year: the value over the population those mayors governed, year by year, so big and small parties compare. Parties governing at least 50 towns. The PNCP history read so far is partial, but evenly across parties: every party's towns are on the same days.", ctl, c1));
  const M = { ph: ["R$ per inhabitant-year", (v) => `R$ ${fmt(v, 2)}`], pm: ["Contracts per million inhabitant-years", (v) => fmt(v, 1)] };
  const draw = () => {
    ctl.replaceChildren(select("Measure", Object.entries(M).map(([value, [label]]) => ({ value, label })), metric, (v) => { metric = v; setParam("pm", v, "ph"); draw(); }));
    const avg = metric === "ph" ? (allPop ? allV / allPop : 0) : (allPop ? (sum(rows.map((x) => x.contratos)) / allPop) * 1e6 : 0);
    const sorted = [...big].sort((a, b) => b[metric] - a[metric]);
    C.bars(c1, { rows: sorted.map((x) => ({ label: x.partido, value: x[metric], note: `${fmt(x.municipios)} towns · ${fmt(x.contratos)} contracts, ${brl(x.valor)}`, color: x[metric] > avg ? C.slot(2) : css("--line") })),
      format: M[metric][1], labelWidth: 120, legend: [{ label: "Above the average of every town", color: C.slot(2) }, { label: "Below", color: css("--line") }],
      table: { rows: big, cols: [{ key: "partido", label: "Party", text: true }, { key: "municipios", label: "Towns" }, { key: "pop_anos", label: "Inhabitant-years" }, { key: "contratos", label: "Contracts" }, { key: "valor", label: "Value", fmt: (v) => brl(v) }, { key: "ph", label: "R$ per inhabitant-year", fmt: (v) => fmt(v, 2) }, { key: "sancionadas", label: "With barred suppliers" }], name: "mayor-parties" } });
  };
  later(draw);
  const c2 = chart();
  root.append(card("Contracts with barred suppliers, by the mayor's party", "Municipal contracts of any value signed with a supplier under a sanction whose scope reaches or may reach the town, per million inhabitant-years governed.", c2));
  const sb = big.map((x) => ({ ...x, rate: x.pop_anos ? (x.sancionadas / x.pop_anos) * 1e6 : 0 })).sort((a, b) => b.rate - a.rate);
  later(() => C.bars(c2, { rows: sb.map((x) => ({ label: x.partido, value: x.rate, note: `${fmt(x.sancionadas)} contracts`, color: x.sancionadas ? css("--critical") : css("--other") })), format: (v) => fmt(v, 2), labelWidth: 120 }));
  root.append(el("p", { className: "about", textContent: "These are associations, not causes: parties govern different kinds of towns (big and small, rich and poor, in different states), and a town's spending reflects its size and needs more than its mayor's party." }));
}

const SECTIONS = { overview, large, suppliers, buyers, map, parties };
guard($("#coverage"), coverage);
tabs((name) => { const box = $(`#tab-${name}`); guard(box, () => SECTIONS[name](box)); });
onResize(() => redraws.forEach((f) => f()));
