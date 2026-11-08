// Parliamentary amendments: what was committed and paid, where it went, who sent it and who received it.
import { $, asset, brl, css, data, el, fmt, guard, onResize, params, pct, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";

const TYPES = [
  ["individual", "Individual"], ["especial", "Individual “Pix”"], ["bancada", "State bench"], ["comissao", "Committee"], ["relator", "Rapporteur"],
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
const redraws = [];
const later = (f) => { redraws.push(f); f(); };
const PERIODS = [
  { value: "57", label: "Budgets 2024–2027 (57th legislature)", years: [2024, 2025, 2026, 2027] },
  { value: "56", label: "Budgets 2020–2023 (56th legislature)", years: [2020, 2021, 2022, 2023] },
  { value: "55", label: "Budgets 2016–2019 (55th legislature)", years: [2016, 2017, 2018, 2019] },
  { value: "all", label: "Every year since 2014", years: null },
];
const inPeriod = (p, y) => { const P = PERIODS.find((x) => x.value === p); return !P.years || P.years.includes(+y); };

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
    { label: `Paid for the ${y} budget`, value: brl(paid), sub: `of ${brl(committed)} committed (${pct(paid / committed)})` },
    { label: "Sent as “Pix” transfers", value: pct(pix / paid), sub: `${brl(pix)}: straight to state and town accounts, with no defined purpose` },
    { label: `The ${A.current} budget so far`, value: brl(A.get(A.current, null, "pago")), sub: `paid of ${brl(A.get(A.current, null, "empenhado"))} committed` },
    { label: "Paid since 2014", value: brl(sum(A.years.map((x) => A.get(x, null, "pago")))), sub: `${A.years.length} budgets` },
  ]);
  const g = el("div", { className: "grid2" }), c1 = chart(), c2 = chart();
  g.append(card("Committed, by type", "Amounts the government committed to pay (empenhado), by budget year. Rapporteur amendments before 2020 are the general rapporteur's adjustments to the budget (in 2016 and 2017 mostly health transfers to states), not the RP 9 of 2020–2022.", c1),
    card("Paid, by type", `What has actually been paid so far, including carried-over payments. ${A.current} is still running.`, c2));
  root.append(g);
  const tbl = { rows: A.rows, cols: [{ key: "ano", label: "Year", text: true }, { key: "tipo", label: "Type", text: true, fmt: (v) => typeName[v] || v }, { key: "emendas", label: "Amendments" }, { key: "empenhado", label: "Committed", fmt: (v) => brl(v) }, { key: "pago", label: "Paid", fmt: (v) => brl(v) }], name: "amendments-by-year" };
  const stackOf = (k) => TYPES.map(([t, name]) => ({ name, color: typeColor(t), values: A.years.map((x) => A.get(x, t, k)) }));
  later(() => { C.stack(c1, { x: A.years, series: stackOf("empenhado"), format: (v) => brl(v, 0), table: tbl }); C.stack(c2, { x: A.years, series: stackOf("pago"), format: (v) => brl(v, 0), table: { ...tbl, name: "amendments-paid-by-year" } }); });
  const c3 = chart();
  root.append(card("How much of what is committed gets paid", "Paid as a share of committed, by budget year and type. Individual amendments are mandatory (impositivas) since a 2015 constitutional amendment, bench amendments since the 2020 budget; the rapporteur amendments of 2020–2022 (RP 9, the 'secret budget') were not, and were ended by the Supreme Court in December 2022.", c3));
  later(() => C.line(c3, {
    x: "num", y: { min: 0, max: 1, format: (v) => pct(v) }, height: 240,
    series: TYPES.map(([t, name]) => ({ name, color: typeColor(t), points: A.years.map((x) => { const e = A.get(x, t, "empenhado"); return [x, e > 1e6 ? A.get(x, t, "pago") / e : null]; }) })),
  }));
  const rel = sum([2020, 2021, 2022].map((x) => A.get(x, "relator", "pago")));
  const pix0 = A.years.find((x) => A.get(x, "especial", "pago") > 0);
  root.append(el("p", { className: "finding", textContent: `“Pix” transfers start with the ${pix0} budget and reach ${pct(pix / paid)} of what was paid for ${y}. Rapporteur amendments paid ${brl(rel)} in 2020–2022, money whose real sponsors the file does not name.` }));
}

// ------------------------------------------------------------ map

async function map(root) {
  const [rows, entes, mun, ufs] = await Promise.all([data("site/emendas/municipios.csv"), data("siconfi/entes.csv"), asset("maps/municipios.json"), asset("maps/ufs.json")]);
  const ente = new Map(entes.map((r) => [r.cod_ibge, r]));
  const years = [...new Set(rows.map((r) => +r.ano))].sort((a, b) => a - b);
  let year = +(params.get("y") || years[years.length - 2]), pix = params.get("t") === "pix", measure = params.get("v") || "pc", picked = params.get("m") || "";
  const controls = el("div", { className: "controls" }), mbox = chart(), side = el("div"), town = el("div"), states = chart();
  const grid = el("div", { className: "grid2" });
  grid.append(card("Where the money landed", "Amendment money paid in the year to recipients located in each town: the town hall and its funds, and the organisations and companies there. Colour: the town's rank among all towns (see the key). Click a town for its history.", mbox), side);
  root.append(controls, grid, card("By state", "Paid to recipients in each state, per inhabitant.", states), town);
  const draw = () => {
    controls.replaceChildren(
      select("Year paid", [...years].reverse(), year, (v) => { year = +v; setParam("y", v); draw(); }),
      select("Amendments", [{ value: "", label: "Every type" }, { value: "pix", label: "“Pix” transfers only" }], pix ? "pix" : "", (v) => { pix = v === "pix"; setParam("t", v, ""); draw(); }),
      select("Measure", [{ value: "pc", label: "Per inhabitant" }, { value: "total", label: "Total" }], measure, (v) => { measure = v; setParam("v", v, "pc"); draw(); }));
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
    const f = measure === "pc" ? (v) => `R$ ${fmt(v, 2)} per inhabitant` : (v) => brl(v);
    C.choropleth(mbox, {
      shapes: mun.shapes, viewBox: mun.viewBox, outline: ufs.shapes, outlineWidth: 1.2,
      value, color: (v) => C.seq(0.08 + 0.92 * rank(v)),
      tip: (c, v) => { const e = ente.get(c); return [el("strong", { textContent: e ? `${e.ente} (${e.uf})` : c }), el("div", { className: "row", textContent: v == null ? "nothing paid here this year" : f(v) }), e ? el("div", { className: "row", textContent: `${fmt(+e.populacao)} inhabitants` }) : null].filter(Boolean); },
      onClick: (c) => { picked = c; setParam("m", c); showTown(); },
      title: `Amendment money paid by municipality, ${year}`,
    });
    C.colorKey(mbox, { color: (t) => C.seq(0.08 + 0.92 * t), from: "less", to: "more", label: "towns ranked" });
    const towns = [...val.keys()].map((c) => ({ c, v: value(c), e: ente.get(c) })).filter((x) => x.v != null && x.e && (measure !== "pc" || +x.e.populacao >= 10000));
    towns.sort((a, b) => b.v - a.v);
    const bx = chart();
    side.replaceChildren(card(measure === "pc" ? "Most per inhabitant (towns of 10,000+)" : "The most", null, bx));
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
    town.replaceChildren(card(`${e.ente} (${e.uf}), ${fmt(+e.populacao)} inhabitants`, "Amendment money paid each year to recipients in this town.", c));
    C.stack(c, { x: years, height: 200, format: (v) => brl(v),
      series: [{ name: "“Pix” transfers", color: typeColor("especial"), values: years.map((y) => sum(mine.filter((r) => +r.ano === y).map((r) => +r.pix))) },
        { name: "Other amendments", color: typeColor("individual"), values: years.map((y) => sum(mine.filter((r) => +r.ano === y).map((r) => +r.valor - +r.pix))) }],
      table: { rows: mine, cols: [{ key: "ano", label: "Year", text: true }, { key: "valor", label: "Paid", fmt: (v) => brl(v) }, { key: "pix", label: "of which “Pix”", fmt: (v) => brl(v) }], name: `town-${picked}` } });
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
  g.append(card("How unequal", "Lorenz curve of the money paid across individual authors: the further below the diagonal, the more a few authors account for most of it.", lz), card("Paid, by the author's party", "Latest party of each author linked to the Câmara or Senado.", parties));
  root.append(controls, g, card("Authors", "Deputies, senators, state benches and committees, as the Portal names them; party, state and house through political-eye's crosswalk. Codes change with each mandate, so one person can have two rows.", tb),
    card("Government support and amendments paid, deputies of the 57th legislature", "Each dot is a deputy: how often they voted with the Government (Câmara roll calls, 2023–), against the amendments paid to them for the 2024–2027 budgets. An association, not a cause: individual amendments must be paid by law, so differences are mostly of timing, and some deputies took office late.", sc));
  const draw = () => {
    controls.replaceChildren(select("Period", PERIODS, period, (v) => { period = v; setParam("p", v, "57"); draw(); }),
      select("Amendments", [{ value: "individual", label: "Individual (incl. “Pix”)" }, { value: "all", label: "Every type" }], kind, (v) => { kind = v; setParam("k", v, "individual"); draw(); }));
    const keep = pa.filter((r) => r.autor_codigo !== "" && inPeriod(period, r.ano) && (kind === "all" || r.tipo === "individual" || r.tipo === "especial"));
    const by = new Map();
    for (const r of keep) {
      const x = by.get(r.autor_codigo) || { autor_codigo: r.autor_codigo, autor: r.autor, emendas: 0, empenhado: 0, pago: 0 };
      x.emendas += +r.emendas; x.empenhado += +r.empenhado; x.pago += +r.pago; by.set(r.autor_codigo, x);
    }
    const rows = [...by.values()].map((x) => { const w = who.get(x.autor_codigo) || {}; return { ...x, casa: w.casa === "camara" ? "Câmara" : w.casa === "senado" ? "Senado" : "", partido: w.partido || "", uf: w.uf || "", share: x.empenhado ? x.pago / x.empenhado : null }; });
    table(tb, rows, [
      { key: "autor", label: "Author", text: true }, { key: "casa", label: "House", text: true }, { key: "partido", label: "Party", text: true }, { key: "uf", label: "UF", text: true },
      { key: "emendas", label: "Amendments" }, { key: "empenhado", label: "Committed", fmt: (v) => brl(v) }, { key: "pago", label: "Paid", fmt: (v) => brl(v) }, { key: "share", label: "Paid share", fmt: (v) => pct(v) },
    ], { sortBy: "pago", pageSize: 15, name: `authors-${period}` });
    const people = rows.filter((r) => r.casa);
    const G = C.lorenz(lz, { values: people.map((r) => r.pago), name: "Authors" });
    lz.querySelector(".legend")?.append(el("span", { textContent: `Gini ${fmt(G, 2)}` }));
    const byParty = new Map();
    for (const r of people) if (r.partido) byParty.set(r.partido, (byParty.get(r.partido) || 0) + r.pago);
    C.bars(parties, { rows: [...byParty].sort((a, b) => b[1] - a[1]).slice(0, 15).map(([label, value]) => ({ label, value, color: label === "PT" ? css("--a") : label === "PL" ? css("--b") : css("--other") })), format: (v) => brl(v),
      legend: [{ label: "PT", color: css("--a") }, { label: "PL", color: css("--b") }, { label: "Other parties", color: css("--other") }] });
  };
  const drawScatter = () => {
    const pts = deps.filter((d) => d.with_gov !== "" && +d.n_gov >= 50).map((d) => ({ x: +d.with_gov, y: +d.emendas_pago, label: d.nome, title: `${d.nome} (${d.partido}-${d.uf})`, rows: [`${fmt(+d.n_gov)} votes with a government line`], color: d.partido === "PT" ? css("--a") : d.partido === "PL" ? css("--b") : css("--other"), z: d.partido === "PT" || d.partido === "PL" ? 1 : 0 }));
    const rank = (xs) => { const s = xs.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]); const r = new Array(xs.length); s.forEach(([, i], k) => { r[i] = k; }); return r; };
    const rx = rank(pts.map((p) => p.x)), ry = rank(pts.map((p) => p.y)), n = pts.length, mx = (n - 1) / 2;
    const rho = sum(rx.map((v, i) => (v - mx) * (ry[i] - mx))) / Math.sqrt(sum(rx.map((v) => (v - mx) ** 2)) * sum(ry.map((v) => (v - mx) ** 2)));
    C.scatter(sc, { points: pts, x: { label: "Votes with the government", format: (v) => pct(v), min: 0, max: 1 }, y: { label: "Amendments paid", format: (v) => brl(v, 0) }, labels: 6, height: 340,
      legend: [{ label: "PT", color: css("--a"), shape: "dot" }, { label: "PL", color: css("--b"), shape: "dot" }, { label: "Other parties", color: css("--other"), shape: "dot" }] });
    sc.append(el("p", { className: "finding", textContent: `Spearman rank correlation over ${n} deputies: ${fmt(rho, 2)}.` }));
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
  root.append(controls, card("How much of their money authors send to their own state", "One author per bar range: the share of what was paid for their amendments that went to their home state (amendments applied to the whole country count as not home). Linked deputies and senators.", h),
    card("From the author's state to where the money went", "Each row is the authors' state; each cell the share of its money that went to that state (or nationally). The diagonal is money sent home.", hm));
  const draw = () => {
    controls.replaceChildren(select("Period", PERIODS, period, (v) => { period = v; setParam("p", v, "57"); draw(); }));
    const by = new Map();
    for (const r of au) {
      if (!inPeriod(period, r.ano)) continue;
      const x = by.get(r.autor_codigo) || [0, 0, 0]; x[0] += +r.pago; x[1] += +r.pago_estado; x[2] += +r.pago_nacional; by.set(r.autor_codigo, x);
    }
    const shares = [...by].filter(([, x]) => x[0] > 1e5).map(([c, x]) => x[1] / x[0]);
    const med = [...shares].sort((a, b) => a - b)[Math.floor(shares.length / 2)];
    C.histogram(h, { values: shares, domain: [0, 1], bins: 20, refs: [{ x: med, label: `median ${pct(med)}` }], format: (v) => pct(v), xLabel: "share paid in the author's own state", unit: "authors" });
    const f = fl.filter((r) => inPeriod(period, r.ano));
    const total = new Map(), cell = new Map();
    for (const r of f) { total.set(r.uf_autor, (total.get(r.uf_autor) || 0) + +r.pago); const k = `${r.uf_autor}|${r.uf_destino || "BR"}`; cell.set(k, (cell.get(k) || 0) + +r.pago); }
    const rows = [...total.keys()].sort(), cols = [...rows, "BR"];
    C.heatmap(hm, { rows, cols: cols.map((c) => (c === "BR" ? "National" : c)), value: (i, j) => { const v = cell.get(`${rows[i]}|${cols[j]}`); return v ? v / total.get(rows[i]) : null; }, color: (v) => C.seq(Math.sqrt(v)),
      cell: 26, rowHeight: 18, labelWidth: 40, colLabelHeight: 50, allColLabels: true, cellText: (v) => (v >= 0.05 ? Math.round(v * 100) : ""), dark: (v) => Math.sqrt(v) > 0.55,
      tip: (i, j, v) => [el("strong", { textContent: `${rows[i]} → ${cols[j] === "BR" ? "national" : cols[j]}` }), el("div", { className: "row", textContent: `${pct(v, 1)} of ${brl(total.get(rows[i]))}` })] });
  };
  later(draw);
}

// ------------------------------------------------------------ recipients

const GROUPS = [
  ["Municipalities", /Munic|Consórcio/i], ["States", /Estad|Distrito Federal/i], ["Federal bodies", /Federal|Unidade Gestora|União/i],
  ["Non-profits", /Associação|Fundação Privada|Organização|Serviço Social|Entidade/i], ["State-owned companies and banks", /Economia Mista|Empresa Pública/i],
  ["Companies", /Sociedade|Empresári|Cooperativa|Limitada|Empresa/i],
];
const group = (n) => (GROUPS.find(([, re]) => re.test(n)) || ["Individuals and other"])[0];

async function recipients(root) {
  const [nat, top] = await Promise.all([data("site/emendas/natureza.csv"), data("site/emendas/favorecidos.csv")]);
  const years = [...new Set(nat.map((r) => +r.ano))].sort((a, b) => a - b);
  const c1 = chart(), tb = el("div");
  root.append(card("Who receives the money", "Payments by the recipient's legal nature, grouped. Municipal funds (health, education) count with municipalities. Private individuals are summed, never named; banks often appear because they are the operating account of a programme.", c1),
    card("The 1,000 recipients paid the most since 2014", "Legal entities and public bodies, by CNPJ or government unit code.", tb));
  const names = [...GROUPS.map(([n]) => n), "Individuals and other"];
  later(() => C.stack(c1, { x: years, format: (v) => brl(v, 0), height: 260, series: names.map((g, i) => ({ name: g, color: i < 6 ? C.slot(i + 1) : css("--other"), values: years.map((y) => sum(nat.filter((r) => +r.ano === y && group(r.natureza) === g).map((r) => +r.valor))) })),
    table: { rows: nat.map((r) => ({ ...r, grupo: group(r.natureza) })), cols: [{ key: "ano", label: "Year", text: true }, { key: "grupo", label: "Group", text: true }, { key: "natureza", label: "Legal nature", text: true }, { key: "valor", label: "Paid", fmt: (v) => brl(v) }], name: "recipients-nature" } }));
  table(tb, top, [
    { key: "nome", label: "Recipient", text: true, wrap: true }, { key: "favorecido", label: "CNPJ / code", text: true }, { key: "natureza_juridica", label: "Legal nature", text: true, wrap: true },
    { key: "uf", label: "UF", text: true }, { key: "emendas", label: "Amendments" }, { key: "primeiro", label: "First", text: true }, { key: "ultimo", label: "Last", text: true }, { key: "total", label: "Paid", fmt: (v) => brl(v) },
  ], { sortBy: "total", pageSize: 15, name: "top-recipients" });
}

// ------------------------------------------------------------ timing

async function timing(root) {
  const m = await data("site/emendas/meses.csv");
  const months = [...new Set(m.map((r) => r.ano_mes))].sort();
  const total = (mo, t) => sum(m.filter((r) => r.ano_mes === mo && (!t || r.tipo === t)).map((r) => +r.valor));
  const c1 = chart(), c2 = chart();
  const ELECTIONS = [2016, 2018, 2020, 2022, 2024, 2026].map((y) => ({ x: `${y}-10`, label: `${y} election` }));
  root.append(card("Payments each month", "Paid to recipients each month, for every type and for “Pix” transfers alone. Dashed: October elections (municipal in 2016, 2020, 2024; general in 2018, 2022, 2026).", c1),
    card("When in the year money is paid: election years against the others", "Average share of a year's payments made in each month, for complete years 2015–2025. Electoral law bars voluntary transfers to towns in the three months before an election, which shows up as a rush before July.", c2));
  later(() => C.line(c1, { x: "month", y: { format: (v) => brl(v, 0) }, marks: ELECTIONS, height: 260,
    series: [{ name: "All amendments", color: C.slot(1), points: months.map((mo) => [mo, total(mo)]) }, { name: "“Pix” only", color: C.slot(2), points: months.map((mo) => [mo, total(mo, "especial")]) }] }));
  const share = (years) => Array.from({ length: 12 }, (_, i) => {
    const xs = years.map((y) => { const yt = sum(Array.from({ length: 12 }, (_, k) => total(`${y}-${String(k + 1).padStart(2, "0")}`))); return yt ? total(`${y}-${String(i + 1).padStart(2, "0")}`) / yt : null; }).filter((v) => v != null);
    return [i + 1, xs.length ? sum(xs) / xs.length : null];
  });
  const ev = [2016, 2018, 2020, 2022, 2024], od = [2015, 2017, 2019, 2021, 2023, 2025];
  later(() => C.line(c2, { x: "num", y: { min: 0, format: (v) => pct(v) }, height: 240,
    series: [{ name: "Election years", color: C.slot(2), points: share(ev) }, { name: "Other years", color: C.slot(1), points: share(od) }],
    table: { rows: share(ev).map(([mo, v], i) => ({ month: mo, election: v, other: share(od)[i][1] })), cols: [{ key: "month", label: "Month" }, { key: "election", label: "Election years", fmt: (v) => pct(v, 1) }, { key: "other", label: "Other years", fmt: (v) => pct(v, 1) }], name: "payment-seasonality" } }));
}

const SECTIONS = { overview, map, authors, flows, recipients, timing };
tabs((name) => { const box = $(`#tab-${name}`); guard(box, () => SECTIONS[name](box)); });
onResize(() => redraws.forEach((f) => f()));
