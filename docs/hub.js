// political-eye hub: each card's headline number and sparkline, read from the pages' own summaries.
import { brl, css, data, el, fmt, pct } from "./lib/ui.js";

const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const month = (m) => `${MONTHS[+m.slice(5, 7) - 1]} ${m.slice(0, 4)}`;
const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };

/** A sparkline: a line for long series, columns for short ones; the last value marked. */
function spark(box, values, { bars = values.length <= 12, color = css("--line"), labels = [], mark = values.length - 1 } = {}) {
  const v = values.map((x) => (x == null || Number.isNaN(x) ? null : +x));
  const ok = v.filter((x) => x != null);
  if (ok.length < 2) return;
  const w = Math.max(160, box.clientWidth || 240), h = 34, lo = bars ? 0 : Math.min(...ok), hi = Math.max(...ok);
  const sy = (x) => h - 3 - ((x - lo) / (hi - lo || 1)) * (h - 8);
  const s = svg("svg", { width: w, height: h, role: "img", "aria-label": labels.length ? `${labels[0]} to ${labels[labels.length - 1]}` : "trend" });
  if (bars) {
    const bw = w / v.length;
    v.forEach((x, i) => { if (x == null) return; s.append(svg("rect", { x: i * bw + 1, y: sy(x), width: Math.max(2, bw - 3), height: h - 3 - sy(x), rx: 1.5, fill: i === mark ? color : css("--axis") })); });
  } else {
    const sx = (i) => 2 + (i / (v.length - 1)) * (w - 6);
    let d = "", pen = false;
    v.forEach((x, i) => { if (x == null) { pen = false; return; } d += `${pen ? "L" : "M"}${sx(i).toFixed(1)},${sy(x).toFixed(1)}`; pen = true; });
    s.append(svg("path", { d, fill: "none", stroke: color, "stroke-width": 1.6, "stroke-linejoin": "round" }));
    const li = v.map((x, i) => [x, i]).filter(([x]) => x != null).pop();
    s.append(svg("circle", { cx: sx(li[1]), cy: sy(li[0]), r: 2.6, fill: color }));
  }
  box.replaceChildren(s);
  if (labels.length) box.append(el("div", { className: "span", textContent: `${labels[0]}–${labels[labels.length - 1]}` }));
}

function fill(key, { value, sub, series, opts }) {
  const c = document.querySelector(`[data-key="${key}"]`);
  if (!c) return;
  const hl = c.querySelector(".headline");
  hl.replaceChildren(el("span", { className: "num", textContent: value }), el("span", { className: "what", textContent: sub }));
  if (series) spark(c.querySelector(".spark"), series, opts);
}

const lastMonths = (rows, n) => rows.slice(-n);

const CARDS = {
  async camara() {
    const net = (await data("site/camara/networks.csv")).filter((r) => r.modularity_party !== "");
    const rows = lastMonths(net, 60), last = rows[rows.length - 1];
    return { value: fmt(+last.modularity_party, 2), sub: `how far votes split along party lines (graph modularity: 0 = parties mixed), ${month(last.month)}, the latest month with enough votes for a graph`, series: rows.map((r) => +r.modularity_party), opts: { labels: [rows[0].month.slice(0, 4), last.month.slice(0, 4)] } };
  },
  async orientacoes() {
    const idx = (await data("camara/index.csv")).filter((r) => r.with_gov !== "" && +r.votacoes_contested >= 10);
    const rows = lastMonths(idx, 60), last = rows[rows.length - 1];
    return { value: pct(+last.with_gov), sub: `of deputies' votes followed the government in ${month(last.month)} (${last.votacoes_contested} contested roll calls)`, series: rows.map((r) => +r.with_gov), opts: { labels: [rows[0].month.slice(0, 4), last.month.slice(0, 4)] } };
  },
  async senado() {
    const idx = (await data("senado/index.csv")).filter((r) => r.with_gov !== "");
    const rows = lastMonths(idx, 60), last = rows[rows.length - 1];
    return { value: pct(+last.with_gov), sub: `of senators' votes followed the government, in the 12 months to ${month(last.month)}`, series: rows.map((r) => +r.with_gov), opts: { labels: [rows[0].month.slice(0, 4), last.month.slice(0, 4)] } };
  },
  async deputados() {
    const d = await data("site/deputados/deputados_57.csv");
    const money = (r) => +r.emendas_pago || 0, w = d.filter((r) => r.prefeito_mesmo_partido !== "" && money(r) > 0);
    const own = sum(w.map((r) => +r.prefeito_mesmo_partido * money(r))) / sum(w.map(money));
    const base = sum(w.map((r) => +r.prefeito_base * money(r))) / sum(w.map(money));
    return { value: fmt(d.length), sub: `deputies of the 57th legislature, substitutes included, each in one profile${Number.isFinite(own) ? `; ${pct(own)} of their town money went to own-party mayors` : ""}` };
  },
  async tse() {
    const ys = (await data("site/tse/anos.csv")).map((r) => r.ano).sort();
    const tot = await Promise.all(ys.map(async (y) => { const t = await data(`site/tse/${y}/resumo.csv`); return { y, total: sum(t.map((r) => +r.total)), pub: sum(t.map((r) => +r.publico)) }; }));
    const full = tot.filter((x) => x.total > 0), last = full.filter((x) => x.y !== "2026").pop() || full[full.length - 1];
    return { value: pct(last.pub / last.total), sub: `of the ${brl(last.total)} raised by ${last.y} candidates was public money`, series: full.map((x) => x.pub / x.total), opts: { bars: true, mark: full.indexOf(last), labels: [full[0].y, full[full.length - 1].y] } };
  },
  async emendas() {
    const a = await data("site/emendas/anos.csv");
    const ys = [...new Set(a.map((r) => r.ano))].sort(), paid = ys.map((y) => sum(a.filter((r) => r.ano === y).map((r) => +r.pago)));
    const i = ys.length >= 2 ? ys.length - 2 : ys.length - 1;
    return { value: brl(paid[i]), sub: `of amendments paid in ${ys[i]} (${ys[ys.length - 1]} so far: ${brl(paid[paid.length - 1])})`, series: paid, opts: { bars: true, labels: [ys[0], ys[ys.length - 1]] } };
  },
  async sancoes() {
    const r = await data("site/sancoes/resumo.json");
    const sy = r.start_year.filter((x) => +x.ano >= 2015), keys = ["FEDERAL", "ESTADUAL", "MUNICIPAL", "outra"];
    return { value: fmt(r.tiles.ceis + r.tiles.cnep), sub: `sanctions listed; ${brl(r.money.emendas.barrado)} in amendments paid to companies while barred`, series: sy.map((x) => sum(keys.map((k) => +x[k] || 0))), opts: { bars: true, color: css("--critical"), labels: [sy[0].ano, sy[sy.length - 1].ano] } };
  },
  async siconfi() {
    const r = await data("site/siconfi/resumo.json"), sy = r.status_by_year;
    if (!sy.length) return { value: "–", sub: "history being read" };
    const last = sy[sy.length - 1], above = (x) => (x.acima_alerta + x.acima_prudencial + x.acima_maximo) / x.n;
    return { value: pct(above(last)), sub: `of ${fmt(last.n)} towns read for ${last.ano} spend over the payroll alert limit`, series: sy.map(above), opts: { bars: true, color: css("--warning"), labels: [sy[0].ano, last.ano] } };
  },
  async pncp() {
    const r = await data("site/pncp/resumo.json"), d = await data("site/pncp/diario.csv");
    const days = [...new Set(d.map((x) => x.dia))].sort(), v = days.map((x) => sum(d.filter((y) => y.dia === x).map((y) => +y.valor)));
    return { value: fmt(r.totals.contratos), sub: `contracts read (${brl(r.totals.valor)}), ${fmt(r.coverage.days_read)} of ${fmt(r.coverage.span_days)} days of history so far`, series: v, opts: { labels: days.length ? [days[0], days[days.length - 1]] : [] } };
  },
};

for (const [k, f] of Object.entries(CARDS)) f().then((x) => fill(k, x)).catch((e) => console.warn(`hub ${k}:`, e));

// ------------------------------------------------------------ highlights

function hl(key, num, txt) {
  const a = document.querySelector(`[data-hl="${key}"]`);
  if (!a) return;
  a.querySelector(".num").textContent = num;
  if (txt) a.querySelector(".txt").textContent = txt;
}
const HIGHLIGHTS = {
  async gov() {
    const idx = (await data("camara/index.csv")).filter((r) => r.with_gov !== "" && +r.votacoes_contested >= 10), last = idx[idx.length - 1];
    hl("gov", pct(+last.with_gov), `of the Câmara's votes followed the government's orientation in ${month(last.month)}, the latest month with 10 or more contested roll calls`);
  },
  async mayors() {
    const d = await data("site/deputados/deputados_57.csv"), m = (r) => +r.emendas_pago || 0, w = d.filter((r) => r.prefeito_mesmo_partido !== "" && m(r) > 0);
    const own = sum(w.map((r) => +r.prefeito_mesmo_partido * m(r))) / sum(w.map(m)), base = sum(w.map((r) => +r.prefeito_base * m(r))) / sum(w.map(m));
    hl("mayors", pct(own), `of deputies' amendment money for towns went to mayors of their own party, against ${pct(base)} if it went at random`);
  },
  async barred() {
    const r = await data("site/sancoes/resumo.json");
    hl("barred", brl(r.money.emendas.barrado, 0), `in amendments paid to ${fmt(r.money.emendas.empresas_barrado)} companies while they were barred from public contracts`);
  },
  async public() {
    const ys = (await data("site/tse/anos.csv")).map((r) => r.ano).sort();
    const y = ys.includes("2022") ? "2022" : ys[ys.length - 1], t = await data(`site/tse/${y}/resumo.csv`);
    hl("public", pct(sum(t.map((r) => +r.publico)) / sum(t.map((r) => +r.total))), `of the money candidates raised in ${y} was public (party and electoral funds)`);
  },
};
for (const [k, f] of Object.entries(HIGHLIGHTS)) f().catch((e) => { console.warn(`hub ${k}:`, e); hl(k, "–"); });
