// Municipal finances (Siconfi): payroll limits, cash, amendments, and towns by their mayor's party.
import { $, asset, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L } from "../lib/i18n.js";
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
const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
const redraws = [];
const later = (f) => { redraws.push(f); f(); };

const LIMITS = [{ x: 48.6, label: L("alerta 48,6%", "alert 48.6%") }, { x: 51.3, label: L("prudencial 51,3%", "prudential 51.3%") }, { x: 54, label: L("máximo 54%", "maximum 54%") }];
const ST = {
  abaixo: L("Abaixo de 48,6%", "Below 48.6%"),
  acima_alerta: L("Faixa de alerta, 48,6–51,3%", "Alert band, 48.6–51.3%"),
  acima_prudencial: L("Faixa prudencial, 51,3–54%", "Prudential band, 51.3–54%"),
  acima_maximo: L("Acima do máximo, 54%+", "Over the maximum, 54%+"),
};
const stColor = (s) => ({ abaixo: css("--other"), acima_alerta: css("--warning"), acima_prudencial: css("--serious"), acima_maximo: css("--critical") })[s] || css("--grid");
const stTag = (s) => el("span", { className: "st", style: `--c:${stColor(s)}`, textContent: ST[s] || L("Não lido", "Not read") });
// Town-size bands as the builder writes them, and the regions in entes.csv.
const SIZE = { "under 5k": L("até 5 mil", "under 5k"), "5k–20k": L("5–20 mil", "5k–20k"), "20k–100k": L("20–100 mil", "20k–100k"), "100k–500k": L("100–500 mil", "100k–500k"), "500k+": L("500 mil+", "500k+") };
const REGION = { NO: L("Norte", "North"), NE: L("Nordeste", "Northeast"), CO: L("Centro-Oeste", "Centre-West"), SE: L("Sudeste", "Southeast"), SU: L("Sul", "South") };
const R = () => data("site/siconfi/resumo.json");
const year = async (y) => (await data(`site/siconfi/anos/${y}.csv`)).map((x) => ({ ...x, dtp_pct: x.dtp_pct === "" ? null : +x.dtp_pct, caixa_hab: x.caixa_hab === "" ? null : +x.caixa_hab, pix_hab: +x.pix_hab, habitantes: +x.habitantes }));
const years = (r) => [...r.years].sort((a, b) => b - a);
const pickYear = (r, k = "y") => { const ys = years(r), p = +params.get(k); return ys.includes(p) ? p : ys[0]; };
const covOf = (r, y) => r.coverage.find((c) => c.ano === y) || { pessoal: 0, caixa: 0 };

async function coverage() {
  const r = await R(), box = $("#coverage");
  const read = sum(r.coverage.map((c) => c.consultados)), possible = r.towns * (new Date().getUTCFullYear() - 2015 + 1);
  box.replaceChildren(el("div", { className: "card wide" },
    el("h2", { textContent: L(`Histórico lido: ${fmt(read)} municípios-ano de cerca de ${fmt(possible)}`, `History read: ${fmt(read)} town-years of about ${fmt(possible)}`) }),
    el("div", { className: "meter" }, el("i", { style: `width:${Math.max(0.5, (100 * read) / possible).toFixed(1)}%` })),
    el("p", { className: "note", textContent: L(
      `${r.coverage.map((c) => `${c.ano}: ${fmt(c.pessoal)} municípios com despesa com pessoal, ${fmt(c.caixa)} com caixa`).join(" · ") || "Nada lido ainda"}. A rotina lê mais duas vezes por dia enquanto o histórico é lido.`,
      `${r.coverage.map((c) => `${c.ano}: ${fmt(c.pessoal)} towns with payroll, ${fmt(c.caixa)} with cash`).join(" · ") || "Nothing read yet"}. The job reads more twice a day while the history is read.`) })));
}

// ------------------------------------------------------------ overview

async function overview(root) {
  const r = await R(), sy = r.status_by_year, last = sy[sy.length - 1];
  const above = (x, from) => sum(r.status.slice(from).map((s) => x[s]));
  tiles(root.appendChild(el("section", { className: "tiles" })), last ? [
    { label: L(`Municípios lidos em ${last.ano}`, `Towns read for ${last.ano}`), value: fmt(last.n), sub: L(`de ${fmt(r.towns)}, com relatório de pessoal`, `of ${fmt(r.towns)}, with a payroll report`) },
    { label: L("Acima do limite de alerta", "Above the alert limit"), value: pct(above(last, 1) / last.n), sub: L(`${fmt(above(last, 1))} municípios gastam mais de 48,6% com pessoal`, `${fmt(above(last, 1))} towns spend over 48.6% on payroll`) },
    { label: L("Acima do limite máximo", "Above the maximum"), value: pct(above(last, 3) / last.n, 1), sub: L(`${fmt(above(last, 3))} municípios acima de 54%, descumprindo a lei`, `${fmt(above(last, 3))} towns over 54%, breaking the law`) },
    { label: L("Município mediano", "Median town"), value: `${fmt(last.p50, 1)}%`, sub: L(`da receita com pessoal; um quarto acima de ${fmt(last.p75, 1)}%`, `of revenue on payroll; a quarter above ${fmt(last.p75, 1)}%`) },
  ] : [{ label: L("Municípios lidos", "Towns read"), value: "0", sub: L("nada lido ainda", "nothing read yet") }]);
  const c1 = chart(), c2 = chart();
  root.append(grid(
    card(L("Quantos municípios ultrapassam cada limite", "How many towns break each limit"), L("Parcela dos municípios lidos em cada ano, pela situação da despesa com pessoal.", "Share of the towns read each year, by payroll status."), c1),
    card(L("A despesa com pessoal do município mediano", "The median town's payroll share"), L("Mediana, com a metade do meio (do 25º ao 75º percentil) sombreada, diante dos três limites.", "Median, with the middle half (25th to 75th percentile) shaded, against the three limits."), c2)));
  const few = (box) => { box.replaceChildren(el("p", { className: "empty", textContent: L(`A série aparece quando dois ou mais anos forem lidos (${sy.length ? `só ${sy[0].ano} até agora` : "nenhum ainda"}).`, `The series appears once two or more years are read (${sy.length ? `only ${sy[0].ano} so far` : "none yet"}).`) })); };
  if (sy.length < 2) { few(c1); few(c2); } else later(() => C.stack(c1, { x: sy.map((x) => x.ano), height: 240, format: (v) => pct(v),
    series: r.status.slice(1).map((s) => ({ name: ST[s], color: stColor(s), values: sy.map((x) => x[s] / x.n) })),
    table: { rows: sy, cols: [{ key: "ano", label: L("Ano", "Year") }, { key: "n", label: L("Municípios lidos", "Towns read") }, ...r.status.map((s) => ({ key: s, label: ST[s] }))], name: "status-by-year" } }));
  if (sy.length >= 2) later(() => C.line(c2, { x: "num", xTicks: sy.map((x) => +x.ano), height: 240, y: { min: 30, max: 60, format: (v) => `${fmt(v)}%` }, ref: LIMITS.map((l) => ({ y: l.x, label: l.label })),
    series: [{ name: L("Município mediano", "Median town"), color: css("--line"), points: sy.map((x) => [x.ano, x.p50]), band: sy.map((x) => [x.ano, x.p25, x.p75]) }] }));
  const g = r.growth;
  if (g.length) {
    const c3 = chart();
    root.append(card(L("Quanto a folha cresce, e os anos eleitorais", "How fast payroll grows, and election years"), L("Variação mediana da despesa com pessoal de um município de um ano para o outro, em reais (sem correção pela inflação). Anos eleitorais (2016, 2020, 2024) em vermelho: a lei proíbe reajustes nos últimos 180 dias do mandato do prefeito.", "Median change in a town's payroll from one year to the next, in reais (not adjusted for inflation). Election years (2016, 2020, 2024) in red: the law bars raises in a mayor's last 180 days."), c3));
    later(() => C.bars(c3, { rows: g.map((x) => ({ label: String(x.ano), value: x.p50 * 100, note: L(`${fmt(x.n)} municípios`, `${fmt(x.n)} towns`), color: x.eleicao ? css("--critical") : css("--line") })), format: (v) => `${fmt(v, 1)}%`, labelWidth: 60 }));
  }
}

// ------------------------------------------------------------ map

async function map(root) {
  const r = await R();
  let y = pickYear(r);
  const ctl = el("div", { className: "controls" }), c1 = chart(), c2 = chart();
  root.append(ctl, card(L("Situação da despesa com pessoal de cada município lido", "Payroll status of every town read"), L("Cinza: abaixo dos limites. Os municípios não lidos naquele ano ficam em branco.", "Grey: below the limits. Towns not read for that year are left blank."), c1),
    card(L("Estados: parcela dos municípios acima do limite de alerta", "States: share of towns above the alert limit"), L("Entre os municípios lidos em cada estado.", "Of the towns read in each state."), c2));
  const [muns, ufs] = await Promise.all([asset("maps/municipios.json"), asset("maps/ufs.json")]);
  const draw = async () => {
    ctl.replaceChildren(select(L("Ano", "Year"), years(r), y, (v) => { y = +v; setParam("y", v); draw(); }));
    const rows = await year(y), by = new Map(rows.map((x) => [x.cod_ibge, x]));
    C.choropleth(c1, { shapes: muns.shapes, viewBox: muns.viewBox, maxWidth: 760, outline: ufs.shapes, outlineWidth: 0.6,
      value: (k) => (by.get(k)?.situacao ? by.get(k).situacao : null), color: stColor,
      tip: (k) => { const x = by.get(k); return x ? [el("strong", { textContent: `${x.ente} (${x.uf})` }), el("div", { className: "row", textContent: L(`${fmt(x.dtp_pct, 1)}% da receita com pessoal`, `${fmt(x.dtp_pct, 1)}% of revenue on payroll`) }), el("div", { className: "row" }, stTag(x.situacao)), x.partido ? el("div", { className: "row", textContent: L(`Prefeito: ${x.prefeito} (${x.partido})`, `Mayor: ${x.prefeito} (${x.partido})`) }) : null] : [el("strong", { textContent: L("Não lido neste ano", "Not read for this year") })]; },
      legend: el("div", { className: "legend" }, ...r.status.map((s) => el("span", {}, el("i", { style: `background:${stColor(s)}` }), ST[s]))) });
    const u = r.by_uf.filter((x) => x.ano === y && x.n >= 5).map((x) => ({ ...x, share: x.alerta / x.n })).sort((a, b) => b.share - a.share);
    C.bars(c2, { rows: u.map((x) => ({ label: x.uf, value: x.share, note: L(`${fmt(x.alerta)} de ${fmt(x.n)} municípios · ${fmt(x.maximo)} acima do máximo`, `${x.alerta} of ${x.n} towns · ${x.maximo} above the maximum`), color: css("--warning") })), format: (v) => pct(v), barHeight: 12, empty: L("Nenhum estado com cinco ou mais municípios lidos.", "No state with five or more towns read.") });
  };
  later(draw);
}

// ------------------------------------------------------------ distribution

async function dist(root) {
  const r = await R();
  let y = pickYear(r);
  const ctl = el("div", { className: "controls" }), c1 = chart(), c2 = chart(), f1 = el("div");
  root.append(ctl, card(L("Despesa com pessoal como parcela da receita", "Payroll as a share of revenue"), L("Todos os municípios lidos, com os três limites legais: alerta (48,6%), prudencial (51,3%) e máximo (54%).", "Every town read, with the three legal limits: alert (48.6%), prudential (51.3%) and maximum (54%)."), c1, f1),
    card(L("Por porte do município", "By town size"), L("Parcela de municípios acima do alerta e acima do máximo, por população.", "Share of towns above the alert and above the maximum, by population."), c2));
  const draw = () => {
    ctl.replaceChildren(select(L("Ano", "Year"), years(r), y, (v) => { y = +v; setParam("y", v); draw(); }));
    const h = r.hist.years[String(y)] || [], e = r.hist.edges;
    C.histogram(c1, { values: h.flatMap((n, i) => Array(n).fill(e[i] + 1)), domain: [20, 80], bins: 30, refs: LIMITS.map((l) => ({ x: l.x, label: `${fmt(l.x, l.x % 1 ? 1 : 0)}%` })), format: (v) => `${fmt(v)}%`, xLabel: L("despesa com pessoal, % da receita corrente líquida ajustada", "payroll, % of adjusted net current revenue"), unit: L("municípios", "towns"), height: 240, color: (v) => (v >= 54 ? css("--critical") : v >= 51.3 ? css("--serious") : v >= 48.6 ? css("--warning") : css("--line")) });
    const s = r.status_by_year.find((x) => x.ano === y);
    f1.replaceChildren(s ? finding(L(`${fmt(s.n)} municípios lidos em ${y}: o mediano gasta ${fmt(s.p50, 1)}% da receita com pessoal; um em cada dez gasta mais de ${fmt(s.p90, 1)}%.`, `${fmt(s.n)} towns read for ${y}: the median spends ${fmt(s.p50, 1)}% of its revenue on payroll; one in ten spends more than ${fmt(s.p90, 1)}%.`)) : "");
    const z = r.sizes.map((k) => r.by_size.find((x) => x.ano === y && x.porte === k)).filter(Boolean);
    C.stack(c2, { x: z.map((x) => `${SIZE[x.porte] || x.porte} (${fmt(x.n)})`), height: 220, format: (v) => pct(v),
      series: [{ name: L("Faixa de alerta ou prudencial, 48,6–54%", "Alert or prudential band, 48.6–54%"), color: css("--warning"), values: z.map((x) => (x.alerta - x.maximo) / x.n) }, { name: ST.acima_maximo, color: css("--critical"), values: z.map((x) => x.maximo / x.n) }] });
  };
  later(draw);
}

// ------------------------------------------------------------ cash

async function cash(root) {
  const r = await R(), cy = r.cash_by_year;
  if (!cy.length) {
    root.append(card(L("Caixa no fim do ano", "Cash at year end"), "", el("p", { className: "empty", textContent: L("Nenhum relatório de caixa de fim de ano lido ainda. O caixa vem do último relatório de cada ano (Anexo 05), então o ano corrente só tem esse dado depois que fecha; os anos anteriores se completam à medida que o histórico é lido.", "No year-end cash report read yet. Cash comes from each year's last report (Annex 05), so the current year has none until it closes; past years fill in as the history is read.") })));
    return;
  }
  const last = cy[cy.length - 1];
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L(`Municípios lidos em ${last.ano}`, `Towns read for ${last.ano}`), value: fmt(last.n), sub: L("com relatório de caixa de fim de ano", "with a year-end cash report") },
    { label: L("Caixa livre negativo", "Negative free cash"), value: pct(last.negativa / last.n), sub: L(`${fmt(last.negativa)} municípios devem mais do que têm`, `${fmt(last.negativa)} towns owe more than they hold`) },
    { label: L("Caixa livre mediano", "Median free cash"), value: `R$ ${fmt(last.p50, 0)}`, sub: L("por habitante, depois dos restos a pagar", "per inhabitant, after carried-over commitments") },
    { label: L("Os 10% mais baixos", "Bottom tenth"), value: `R$ ${fmt(last.p10, 0)}`, sub: L("por habitante ou menos", "per inhabitant or less") },
  ]);
  let y = pickYear({ years: cy.map((x) => x.ano) }, "cy");
  const ctl = el("div", { className: "controls" }), c1 = chart(), c2 = chart();
  root.append(ctl, card(L("Caixa livre por habitante no fim do ano", "Free cash per inhabitant at year end"), L("Caixa líquido sem vinculação (depois dos restos a pagar inscritos para o ano seguinte), por habitante. Abaixo de zero, o município fecha o ano devendo mais do que tem.", "Unrestricted net cash (after commitments carried over to next year), per inhabitant. Below zero, the town closes the year owing more than it holds."), c1),
    card(L("Municípios com caixa livre negativo, por ano", "Towns with negative free cash, by year"), "", c2));
  const draw = async () => {
    ctl.replaceChildren(select(L("Ano", "Year"), cy.map((x) => x.ano).reverse(), y, (v) => { y = +v; setParam("cy", v); draw(); }));
    const rows = (await year(y)).filter((x) => x.caixa_hab != null);
    C.histogram(c1, { values: rows.map((x) => Math.max(-1500, Math.min(3000, x.caixa_hab))), domain: [-1500, 3000], bins: 30, format: (v) => `R$ ${fmt(v)}`, xLabel: L("R$ por habitante (limitado a −1.500 e 3.000)", "R$ per inhabitant (clipped at −1,500 and 3,000)"), unit: L("municípios", "towns"), height: 220, refs: [{ x: 0, label: L("zero", "zero") }], color: (v) => (v < 0 ? css("--critical") : css("--line")) });
  };
  later(draw);
  later(() => C.stack(c2, { x: cy.map((x) => x.ano), height: 200, format: (v) => pct(v), series: [{ name: L("Caixa livre negativo", "Negative free cash"), color: css("--critical"), values: cy.map((x) => x.negativa / x.n) }] }));
}

// ------------------------------------------------------------ mayors' parties

async function parties(root) {
  const r = await R(), all = await data("site/siconfi/partidos.csv");
  let y = pickYear(r), m = params.get("pm") || "alerta";
  const ctl = el("div", { className: "controls" }), c1 = chart(), tb = el("div"), warn = el("div");
  root.append(ctl, warn, card(L("Municípios que ultrapassam os limites de pessoal, pelo partido do prefeito", "Towns breaking the payroll limits, by the mayor's party"), L(`Municípios lidos naquele ano, agrupados pelo partido do prefeito então no cargo (partidos fundidos ou renomeados aparecem com o nome atual). Partidos com pelo menos ${fmt(r.min_party)} municípios lidos.`, `Towns read that year, grouped by the party of the mayor then in office (merged or renamed parties under today's name). Parties with at least ${r.min_party} towns read.`), c1),
    card(L("Todos os partidos", "Every party"), "", tb));
  const M = { alerta: [L("Parcela acima do alerta (48,6%)", "Share above the alert (48.6%)"), (x) => x.alerta / x.n], maximo: [L("Parcela acima do máximo (54%)", "Share above the maximum (54%)"), (x) => x.maximo / x.n], mediana: [L("Despesa com pessoal mediana", "Median payroll share"), (x) => +x.mediana / 100], caixa: [L("Parcela com caixa livre negativo", "Share with negative free cash"), (x) => (+x.caixa_n ? +x.caixa_negativa / +x.caixa_n : null)] };
  const draw = () => {
    ctl.replaceChildren(select(L("Ano", "Year"), years(r), y, (v) => { y = +v; setParam("y", v); draw(); }), select(L("Medida", "Measure"), Object.entries(M).map(([value, [label]]) => ({ value, label })), m, (v) => { m = v; setParam("pm", v, "alerta"); draw(); }));
    const rows = all.filter((x) => +x.ano === y).map((x) => ({ ...x, n: +x.n, alerta: +x.alerta, maximo: +x.maximo }));
    const big = rows.filter((x) => x.n >= r.min_party).map((x) => ({ ...x, v: M[m][1](x) })).filter((x) => x.v != null).sort((a, b) => b.v - a.v);
    const tot = sum(rows.map((x) => x.n)), avg = m === "alerta" ? sum(rows.map((x) => x.alerta)) / tot : m === "maximo" ? sum(rows.map((x) => x.maximo)) / tot : null;
    warn.replaceChildren(tot < 2000 ? el("div", { className: "card wide" }, el("h2", { textContent: L("Ainda cedo: poucos municípios lidos neste ano", "Early: few towns read for this year") }), el("p", { className: "note", textContent: L(`${fmt(tot)} municípios com prefeito conhecido foram lidos em ${y}. As parcelas de partidos com poucos municípios lidos mudam bastante à medida que outros chegam.`, `${fmt(tot)} towns with a known mayor have been read for ${y}. Shares for parties with few towns read move a lot as more arrive.`) })) : "");
    C.bars(c1, { rows: big.map((x) => ({ label: x.partido, value: x.v, note: L(`${fmt(x.n)} municípios lidos · ${fmt(x.alerta)} acima do alerta · ${fmt(x.maximo)} acima do máximo`, `${fmt(x.n)} towns read · ${x.alerta} above alert · ${x.maximo} above maximum`), color: avg != null && x.v > avg ? css("--serious") : css("--line") })),
      format: (v) => pct(v, 1), labelWidth: 120, empty: L(`Nenhum partido tem ${fmt(r.min_party)} municípios lidos em ${y} ainda.`, `No party has ${r.min_party} towns read for ${y} yet.`),
      legend: avg != null ? [{ label: L(`Acima da parcela de todos os municípios lidos (${pct(avg, 1)})`, `Above the share of all towns read (${pct(avg, 1)})`), color: css("--serious") }, { label: L("Abaixo", "Below"), color: css("--line") }] : [] });
    table(tb, rows, [{ key: "partido", label: L("Partido", "Party"), text: true }, { key: "n", label: L("Municípios lidos", "Towns read") }, { key: "alerta", label: L("Acima do alerta", "Above alert") }, { key: "prudencial", label: L("Acima do prudencial", "Above prudential") }, { key: "maximo", label: L("Acima do máximo", "Above maximum") },
      { key: "mediana", label: L("Pessoal (mediana)", "Median payroll"), fmt: (v) => `${fmt(+v, 1)}%` }, { key: "caixa_negativa", label: L("Caixa negativo", "Negative cash"), fmt: (v, x) => (+x.caixa_n ? L(`${v} de ${x.caixa_n}`, `${v} of ${x.caixa_n}`) : "") }, { key: "pix_hab_mediana", label: L("Pix por habitante (mediana)", "Median Pix per inhabitant"), fmt: (v) => (v === "" ? "" : `R$ ${fmt(+v, 0)}`) }],
    { sortBy: "n", pageSize: 12, name: `mayor-parties-${y}` });
  };
  later(draw);
  root.append(el("p", { className: "about", textContent: L("São associações, não causas: os partidos governam municípios diferentes, e a despesa com pessoal reflete anos de decisões, muitas vezes de prefeitos anteriores.", "Associations, not causes: parties govern different kinds of towns, and a payroll share reflects years of decisions, often by earlier mayors.") }));
}

// ------------------------------------------------------------ amendments and stress

function spearman(xs, ys) {
  const rank = (v) => { const o = v.map((x, i) => [x, i]).sort((a, b) => a[0] - b[0]), r = Array(v.length); o.forEach(([, i], k) => { r[i] = k; }); return r; };
  const a = rank(xs), b = rank(ys), n = xs.length, ma = (n - 1) / 2;
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { num += (a[i] - ma) * (b[i] - ma); da += (a[i] - ma) ** 2; db += (b[i] - ma) ** 2; }
  return da && db ? num / Math.sqrt(da * db) : null;
}

async function pix(root) {
  const r = await R();
  let y = pickYear(r);
  const ctl = el("div", { className: "controls" }), c1 = chart(), f1 = el("div");
  root.append(ctl, card(L("As emendas Pix vão para municípios em dificuldade?", "Do \"Pix\" amendments go to towns in trouble?"), L("Cada ponto é um município lido naquele ano. Na horizontal, as transferências especiais (\"emendas Pix\", sem finalidade definida) pagas a ele por habitante, em escala logarítmica; na vertical, sua despesa com pessoal como parcela da receita. Cor: situação da despesa com pessoal. Os municípios que não receberam Pix naquele ano ficam na borda esquerda.", "Each dot is a town read that year: across, the \"Pix\" amendments (special transfers with no defined purpose) paid to it per inhabitant, on a log scale; up, its payroll share. Colour: payroll status. Towns that received no Pix that year sit at the left edge."), c1, f1));
  const draw = async () => {
    ctl.replaceChildren(select(L("Ano", "Year"), years(r), y, (v) => { y = +v; setParam("y", v); draw(); }));
    const rows = (await year(y)).filter((x) => x.dtp_pct != null);
    C.scatter(c1, { height: 340, x: { log: true, label: L("Pix por habitante (R$, escala log)", "Pix per inhabitant (R$, log)"), format: (v) => `R$ ${fmt(v, v < 10 ? 1 : 0)}`, min: 0 }, y: { label: L("pessoal, % da receita", "payroll, % of revenue"), format: (v) => `${fmt(v)}%`, min: 20, max: 80 },
      points: rows.map((x) => ({ x: Math.max(1, x.pix_hab), y: Math.min(80, x.dtp_pct), color: stColor(x.situacao), r: 3.2, label: x.ente, title: `${x.ente} (${x.uf})`, rows: [L(`R$ ${fmt(x.pix_hab, 2)} de Pix por habitante`, `R$ ${fmt(x.pix_hab, 2)} of Pix per inhabitant`), L(`${fmt(x.dtp_pct, 1)}% com pessoal`, `${fmt(x.dtp_pct, 1)}% on payroll`), x.partido ? L(`Prefeito: ${x.prefeito} (${x.partido})`, `Mayor: ${x.prefeito} (${x.partido})`) : ""].filter(Boolean) })),
      legend: r.status.map((s) => ({ label: ST[s], color: stColor(s) })) });
    const got = rows.filter((x) => x.pix_hab > 0), rho = got.length > 10 ? spearman(got.map((x) => x.pix_hab), got.map((x) => x.dtp_pct)) : null;
    const share = (k) => { const g = rows.filter((x) => (k ? x.situacao !== "abaixo" : x.situacao === "abaixo")); return g.length ? g.filter((x) => x.pix_hab > 0).length / g.length : null; };
    f1.replaceChildren(finding(L(
      `${fmt(got.length)} de ${fmt(rows.length)} municípios lidos em ${y} receberam Pix: ${pct(share(true))} dos municípios acima do limite de alerta, contra ${pct(share(false))} dos que estão abaixo dele.${rho != null ? ` Entre os que receberam, a correlação de postos entre o Pix por habitante e a despesa com pessoal é de ${fmt(rho, 2)}${Math.abs(rho) < 0.1 ? ", praticamente nenhuma" : ""}.` : ""}`,
      `${fmt(got.length)} of ${fmt(rows.length)} towns read for ${y} received Pix. ${pct(share(true))} of towns above the alert limit did, against ${pct(share(false))} of towns below it.${rho != null ? ` Among recipients, the rank correlation between Pix per inhabitant and payroll share is ${fmt(rho, 2)}${Math.abs(rho) < 0.1 ? ", next to none" : ""}.` : ""}`)));
  };
  later(draw);
}

// ------------------------------------------------------------ one town

async function town(root) {
  const r = await R();
  const entes = await data("siconfi/entes.csv");
  const input = el("input", { type: "search", placeholder: L("Nome do município…", "Town name…"), autocomplete: "off", style: "min-width:280px" });
  const results = el("ul", { className: "search-results" }), out = el("div");
  root.append(el("div", { className: "controls" }, el("label", {}, L("Encontre um município", "Find a town"), input)), results, out);
  const idx = entes.map((e) => [norm(e.ente), e]);
  input.addEventListener("input", () => {
    const q = norm(input.value.trim());
    if (q.length < 3) { results.replaceChildren(); return; }
    const hits = idx.filter(([k]) => k.includes(q)).map(([, e]) => e).sort((a, b) => +b.populacao - +a.populacao).slice(0, 10);
    results.replaceChildren(...hits.map((e) => el("li", {}, el("button", { type: "button", on: { click: () => { results.replaceChildren(); input.value = ""; show(e.cod_ibge); } } }, el("span", { textContent: `${e.ente} (${e.uf})` }), el("span", { className: "n", textContent: L(`${fmt(+e.populacao)} habitantes`, `${fmt(+e.populacao)} inhabitants`) })))));
  });
  const show = async (cod) => {
    const e = entes.find((x) => x.cod_ibge === cod);
    if (!e) return;
    setParam("town", cod);
    const shard = await data(`site/siconfi/uf/${e.uf}.json`), t = shard[cod] || { y: [], a: [], m: [] };
    const Y = t.y.map(([ano, dtp_pct, situacao, rcl, dtp, liquida]) => ({ ano, dtp_pct, situacao, rcl, dtp, liquida }));
    const A = t.a.map(([ano, total, pixv]) => ({ ano, total, pix: pixv })).sort((a, b) => a.ano - b.ano);
    const Mm = t.m.map(([ano, partido, nome, sup, data_]) => ({ ano, partido, nome, sup, data: data_ }));
    const last = Y.filter((x) => x.dtp_pct != null).slice(-1)[0];
    const box = el("div");
    box.append(el("h2", { textContent: `${e.ente} (${e.uf})`, style: "margin:4px 0 10px" }));
    box.append(el("p", { style: "margin:0 0 14px;font-size:14px" }, el("a", { href: `../municipios/?town=${cod}`,
      textContent: L("Perfil completo do município: prefeitos, emendas por autor, contratos e comparação com municípios parecidos →", "Full town profile: mayors, amendments by author, contracts, and similar towns →") })));
    const tl = el("section", { className: "tiles" });
    box.append(tl);
    tiles(tl, [
      { label: L("Habitantes", "Inhabitants"), value: fmt(+e.populacao), sub: e.capital === "1" ? L("capital do estado", "state capital") : REGION[e.regiao] || e.regiao },
      { label: L("Despesa com pessoal", "Payroll share"), value: last ? `${fmt(last.dtp_pct, 1)}%` : L("não lida", "not read"), sub: last ? `${last.ano}: ${ST[last.situacao] || ""}` : L("nenhum relatório de pessoal lido ainda", "no payroll report read yet") },
      { label: L("Emendas pagas à prefeitura", "Amendments paid to its own accounts"), value: brl(sum(A.map((x) => x.total))), sub: L(`ao CNPJ do município desde 2014; ${brl(sum(A.map((x) => x.pix)))} como Pix`, `to the town's CNPJ since 2014; ${brl(sum(A.map((x) => x.pix)))} as Pix`) },
      { label: L("Prefeito atual", "Mayor now"), value: Mm.length ? Mm[Mm.length - 1].partido : "–", sub: Mm.length ? Mm[Mm.length - 1].nome : "" },
    ]);
    const c1 = chart(), c2 = chart();
    box.append(grid(card(L("Despesa com pessoal ao longo do tempo", "Payroll share over time"), L("Diante dos três limites.", "Against the three limits."), c1),
      card(L("Emendas pagas à prefeitura, por ano", "Amendments paid to its own accounts, by year"), L("Pagamentos ao CNPJ do próprio município (a prefeitura): Pix (transferências especiais) e as demais. O dinheiro para seus fundos, ou para empresas e organizações sediadas no município, não entra; a página de emendas conta esses valores por local.", "Payments to the town's own CNPJ (the prefeitura): Pix (special transfers) and the rest. Money to its separate funds, or to companies and organisations located in the town, is not included; the amendments page counts those by place."), c2)));
    out.replaceChildren(box);
    const draw = () => {
      const pts = Y.filter((x) => x.dtp_pct != null);
      if (pts.length < 2) c1.replaceChildren(el("p", { className: "empty", textContent: pts.length
        ? L(`Só ${pts[0].ano} foi lido até agora: ${fmt(pts[0].dtp_pct, 1)}% da receita com pessoal. A série aparece quando mais anos forem lidos.`, `Only ${pts[0].ano} read so far: ${fmt(pts[0].dtp_pct, 1)}% of revenue on payroll. The series appears once more years are read.`)
        : L("Nenhum relatório de pessoal lido ainda para este município.", "No payroll report read yet for this town.") }));
      else C.line(c1, { x: "num", xTicks: Y.map((x) => +x.ano), height: 220, y: { min: Math.min(30, ...Y.map((x) => x.dtp_pct ?? 99)), max: Math.max(60, ...Y.map((x) => x.dtp_pct ?? 0)), format: (v) => `${fmt(v)}%` }, ref: LIMITS.map((l) => ({ y: l.x, label: l.label })), empty: L("Nenhum relatório de pessoal lido ainda para este município.", "No payroll report read yet for this town."),
        series: [{ name: L("Despesa com pessoal", "Payroll share"), color: css("--line"), points: Y.filter((x) => x.dtp_pct != null).map((x) => [x.ano, x.dtp_pct]) }] });
      C.stack(c2, { x: A.map((x) => x.ano), height: 220, format: (v) => brl(v, 0), series: [{ name: "Pix", color: C.slot(2), values: A.map((x) => x.pix) }, { name: L("Outras emendas", "Other amendments"), color: css("--line"), values: A.map((x) => x.total - x.pix) }] });
    };
    draw();
    redraws.push(draw);
    const tm = el("div"), ty = el("div");
    box.append(grid(card(L("Seus prefeitos", "Its mayors"), L("Eleitos nas eleições regulares e em eventuais eleições suplementares.", "Elected in the regular elections and any supplementary one."), tm), card(L("Ano a ano", "Year by year"), "", ty)));
    table(tm, Mm, [{ key: "ano", label: L("Eleição", "Election"), text: true }, { key: "data", label: L("Data", "Date"), text: true }, { key: "nome", label: L("Prefeito", "Mayor"), text: true }, { key: "partido", label: L("Partido", "Party"), text: true }, { key: "sup", label: L("Tipo", "Kind"), text: true, fmt: (v) => (v === "1" ? L("suplementar", "supplementary") : L("ordinária", "regular")) }], { search: false, sortBy: "data", desc: false, name: `mayors-${cod}` });
    table(ty, Y, [{ key: "ano", label: L("Ano", "Year") }, { key: "dtp_pct", label: L("Pessoal (%)", "Payroll %"), fmt: (v) => (v == null ? "" : fmt(v, 1)) }, { key: "situacao", label: L("Situação", "Status"), text: true, fmt: (v) => (v ? stTag(v) : "") }, { key: "rcl", label: L("Receita (RCL)", "Revenue"), fmt: (v) => brl(v) }, { key: "dtp", label: L("Pessoal", "Payroll"), fmt: (v) => brl(v) }, { key: "liquida", label: L("Caixa livre", "Free cash"), fmt: (v) => (v == null ? "" : brl(v)) }], { search: false, sortBy: "ano", name: `town-${cod}` });
  };
  const first = params.get("town") || (await year(pickYear(r))).sort((a, b) => b.habitantes - a.habitantes)[0]?.cod_ibge || "3550308";
  await show(first);
}

const SECTIONS = { overview, map, dist, cash, parties, pix, town };
guard($("#coverage"), coverage);
tabs((name) => { const box = $(`#tab-${name}`); guard(box, () => SECTIONS[name](box)); });
onResize(() => redraws.forEach((f) => f()));
