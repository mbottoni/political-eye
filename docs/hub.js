// political-eye hub: each card's headline and sparkline, four findings and the hero's chart, all read live from
// the pages' own summaries. Portuguese by default (the HTML's own text), English on request.
import { css, data, el } from "./lib/ui.js";
import { brl, date, lang, langSwitch, month, num, pct, tr } from "./lib/i18n.js";
import { deputies, deputySearch } from "./lib/search.js";

const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}, ...kids) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); e.append(...kids); return e; };

// ------------------------------------------------------------ static text

const EN = {
  skip: "Skip to content", nav_congress: "Congress", nav_money: "Money", nav_control: "Accountability", nav_how: "How it works",
  eyebrow: "Official open data, updated every day",
  title: "Brazil's politics and public money, <em>in plain sight</em>.",
  lede: "Scheduled jobs download data from Congress, the electoral court, the comptroller general, the National Treasury and the procurement portal, rebuild tidy tables and commit them to git, so the repository's history shows what changed and when. Each page goes from the big picture down to one deputy, party, company or town.",
  cta_explore: "or see what the data shows ↓", cta_how: "How it works",
  search_label: "Find a deputy and see how they vote, what they propose, where their amendments go and who paid for their campaign.",
  search_try: "Try:",
  ab_kicker: "Red flags", ab_title: "Patterns across the open data that deserve a closer look",
  ab_text: "Amendments and contracts for companies barred from public contracts, campaign suppliers later paid from the same member's amendments, amendment money concentrated on one private recipient. Each flag gives its rule, what it is measured against and the innocent explanations. A flag is not evidence of an irregularity.",
  ab_go: "See the red flags",
  rb_kicker: "Deputies ranked", rb_title: "Who works most, by what the data records, with the weights you choose",
  rb_text: "Roll-call participation, bills filed, rapporteur opinions and thrift with the office allowance, against deputies of the same state. Each criterion becomes a 0–100 score; you decide how much each counts. The ranking does not measure ideology, the quality of laws or honesty.",
  rb_go: "Build the ranking",
  f_pages: "interactive pages", f_sources: "official sources", f_since: "data since", f_updated: "last update", f_stale: "sources overdue",
  swarm_title: "How the Câmara votes", swarm_others: "others", swarm_left: "← votes like PT", swarm_right: "votes like PL →",
  h_findings: "What the data shows", p_findings: "Four numbers read just now from the pages' tables. Click one to see where it comes from.",
  k_amend: "Amendments", k_campaigns: "Campaigns",
  t_orientacoes: "Party orientations", t_deputados: "Deputies across sources", t_sancoes: "Sanctions", t_tse: "Campaign finance",
  t_emendas: "Parliamentary amendments", t_pncp: "Public contracts", t_siconfi: "Municipal finances", t_stf: "STF case reviews", t_rules: "House rules",
  p_congress: "How deputies and senators vote, with whom, and how often they follow their party and the government.",
  weekly: "weekly", daily: "daily", monthly: "monthly", on_hold: "on hold", explore: "Explore",
  d_camara: "Every month since 2015 as two graphs on the same deputies, who votes together and who signs bills together, with their network analysis and each deputy's ideal point.",
  d_senado: "The same two graphs for the Senate, each over the twelve months to date, and how often each senator votes with their party and the government.",
  d_orientacoes: "How often each deputy follows their party's and the government's orientation and votes with their party's majority: government support by party, cohesion, rebels.",
  d_deputados: "Every deputy in one place: how they vote and with whom, the amendments they sent and where they landed, whether they favoured their party's mayors, and who paid for their campaign.",
  s_joined: "All sources, joined",
  nav_money_long: "Public money", p_money: "From campaign finance to amendments, contracts and each town's accounts.",
  d_tse: "Where candidates' money came from in 2018, 2022 and 2026: how parties split public funds, quotas for women and Black candidates, large donors and suppliers.",
  d_emendas: "Every amendment since 2014: who sent it, where the money landed, how much was committed and paid, and who received it, \"Pix\" transfers included.",
  d_pncp: "Who buys and who sells in contracts of R$ 1 million or more: concentration, barred companies, value per inhabitant, and towns by their mayor's party.",
  d_siconfi: "Which towns break the payroll cap or end the year without cash, whether \"Pix\" amendments go to towns in trouble, and each mayor's party.",
  nav_control_long: "Accountability and justice", p_control: "Who is barred from public contracts, what they still receive, and the patterns that deserve a closer look.",
  d_sancoes: "Who is barred from public contracts or fined for corruption, by whom and for how long: repeat offenders, fines, leniency deals, and the amendments and contracts barred companies still get, by member of Congress and by party.",
  d_stf: "How long each justice holds a case after asking for more time to review it. On hold: the STF's server turns away clients that do not present themselves as a web browser.",
  r1: "Official data only, with the source on every number.", r2: "No full CPF is ever published.", r3: "Sanctioned people are counted, never named.",
  r4: "Every rule and data quirk is in the methodology.", methodology: "Methodology",
  h_how: "How it works", p_how: "A \"git scraping\" project: the data lives in the repository itself, under version control.",
  s1_t: "Collect", s1_p: "Scheduled GitHub Actions jobs download each official source: the Câmara and Senate APIs, the electoral court, the Transparency Portal, the National Treasury and the PNCP.",
  s2_t: "Tables", s2_p: "Each run rebuilds sorted CSV tables and commits only when something changed, so the git history records what changed and when.",
  s3_t: "Pages", s3_p: "The pages read those tables straight from the repository, in your browser. The numbers on this page are read just now and change when new data arrives.",
  sources: "Sources:",
  foot: "Data, code and every rule behind the numbers: <a href=\"https://github.com/mbottoni/political-eye\">github.com/mbottoni/political-eye</a> (<a href=\"https://github.com/mbottoni/political-eye/blob/main/METHODOLOGY.md\">methodology</a>). Code under the MIT license.",
};
// Portuguese is what the HTML says; keep it to switch back.
const PT = {};
for (const e of document.querySelectorAll("[data-i]")) PT[e.dataset.i] = e.textContent;
for (const e of document.querySelectorAll("[data-i-html]")) PT[e.dataset.iHtml] = e.innerHTML;

function translate() {
  const d = lang() === "en" ? EN : PT;
  for (const e of document.querySelectorAll("[data-i]")) if (d[e.dataset.i] != null) e.textContent = d[e.dataset.i];
  for (const e of document.querySelectorAll("[data-i-html]")) if (d[e.dataset.iHtml] != null) e.innerHTML = d[e.dataset.iHtml];
  document.title = "political-eye";
}

// ------------------------------------------------------------ sparklines

let uid = 0;
/** A sparkline: an area line for long series, columns for short ones; the last (or marked) value stands out. */
function spark(box, values, { bars = values.length <= 14, color = css("--accent") || css("--line"), labels = [], mark = values.length - 1, height = 44 } = {}) {
  const v = values.map((x) => (x == null || Number.isNaN(x) ? null : +x));
  const ok = v.filter((x) => x != null);
  if (ok.length < 2) return;
  const w = Math.max(160, Math.round(box.clientWidth) || 240), h = height, lo = bars ? 0 : Math.min(...ok), hi = Math.max(...ok);
  const sy = (x) => h - 2 - ((x - lo) / (hi - lo || 1)) * (h - 8);
  const s = svg("svg", { viewBox: `0 0 ${w} ${h}`, preserveAspectRatio: "none", role: "img", "aria-label": labels.length ? `${labels[0]}–${labels[labels.length - 1]}` : "" });
  if (bars) {
    const bw = w / v.length, gap = Math.min(4, bw * 0.25);
    v.forEach((x, i) => {
      if (x == null) return;
      const y = sy(x);
      s.append(svg("rect", { x: i * bw + gap / 2, y, width: Math.max(2, bw - gap), height: Math.max(1, h - 2 - y), rx: Math.min(3, (bw - gap) / 3), fill: color, "fill-opacity": i === mark ? 1 : 0.28 }));
    });
  } else {
    const sx = (i) => 3 + (i / (v.length - 1)) * (w - 8), id = `g${uid++}`;
    let d = "", pen = false, first = null, last = null;
    v.forEach((x, i) => { if (x == null) { pen = false; return; } d += `${pen ? "L" : "M"}${sx(i).toFixed(1)},${sy(x).toFixed(1)}`; pen = true; first ??= i; last = i; });
    s.append(svg("defs", {}, svg("linearGradient", { id, x1: 0, x2: 0, y1: 0, y2: 1 },
      svg("stop", { offset: "0%", "stop-color": color, "stop-opacity": 0.28 }), svg("stop", { offset: "100%", "stop-color": color, "stop-opacity": 0 }))));
    if (!d.slice(1).includes("M")) s.append(svg("path", { d: `${d}L${sx(last).toFixed(1)},${h}L${sx(first).toFixed(1)},${h}Z`, fill: `url(#${id})` }));
    s.append(svg("path", { d, fill: "none", stroke: color, "stroke-width": 1.75, "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" }));
    s.append(svg("circle", { cx: sx(last), cy: sy(v[last]), r: 6, fill: color, "fill-opacity": 0.2 }), svg("circle", { cx: sx(last), cy: sy(v[last]), r: 3, fill: color }));
  }
  box.replaceChildren(s);
  if (labels.length) box.append(el("div", { className: "span" }, el("span", { textContent: labels[0] }), el("span", { textContent: labels[labels.length - 1] })));
}

function fill(key, { value, sub, series, opts }) {
  const c = document.querySelector(`[data-key="${key}"]`);
  if (!c) return;
  const color = getComputedStyle(c).getPropertyValue("--accent").trim();
  c.querySelector(".headline").replaceChildren(el("span", { className: "num", textContent: value }), el("span", { className: "what", textContent: sub }));
  const sp = c.querySelector(".spark");
  if (series) spark(sp, series, { color, ...opts }); else sp.replaceChildren();
}

// ------------------------------------------------------------ cards

const years = (rows) => [rows[0].month.slice(0, 4), rows[rows.length - 1].month.slice(0, 4)];
const CARDS = {
  async camara() {
    const net = (await data("site/camara/networks.csv")).filter((r) => r.modularity_party !== "");
    const rows = net.slice(-60), last = rows[rows.length - 1];
    return { value: num(+last.modularity_party, 2), series: rows.map((r) => +r.modularity_party), opts: { labels: years(rows) },
      sub: tr({ pt: `de modularidade por partido em ${month(last.month)}: o quanto os votos se dividem em linhas partidárias (0 = partidos misturados)`,
        en: `party modularity in ${month(last.month)}: how far votes split along party lines (0 = parties mixed)` }) };
  },
  async orientacoes() {
    const rows = (await data("camara/index.csv")).filter((r) => r.with_gov !== "" && +r.votacoes_contested >= 10).slice(-60), last = rows[rows.length - 1];
    return { value: pct(+last.with_gov), series: rows.map((r) => +r.with_gov), opts: { labels: years(rows) },
      sub: tr({ pt: `dos votos dos deputados seguiram o governo em ${month(last.month)} (${num(+last.votacoes_contested)} votações disputadas)`,
        en: `of deputies' votes followed the government in ${month(last.month)} (${num(+last.votacoes_contested)} contested roll calls)` }) };
  },
  async senado() {
    const rows = (await data("senado/index.csv")).filter((r) => r.with_gov !== "").slice(-60), last = rows[rows.length - 1];
    return { value: pct(+last.with_gov), series: rows.map((r) => +r.with_gov), opts: { labels: years(rows) },
      sub: tr({ pt: `dos votos dos senadores seguiram o governo nos 12 meses até ${month(last.month)}`, en: `of senators' votes followed the government in the 12 months to ${month(last.month)}` }) };
  },
  async deputados() {
    const d = await data("site/deputados/deputados_57.csv");
    const m = (r) => +r.emendas_pago || 0, w = d.filter((r) => r.prefeito_mesmo_partido !== "" && m(r) > 0);
    const own = sum(w.map((r) => +r.prefeito_mesmo_partido * m(r))) / sum(w.map(m));
    // How many deputies sent each share of their town money to own-party mayors: a distribution, 10 columns.
    const hist = Array(10).fill(0);
    for (const r of w) hist[Math.min(9, Math.floor(+r.prefeito_mesmo_partido * 10))]++;
    return { value: num(d.length), series: hist, opts: { bars: true, mark: Math.min(9, Math.floor(own * 10)), labels: [tr({ pt: "deputados por parcela: 0%", en: "deputies by share: 0%" }), "100%"] },
      sub: tr({ pt: `deputados da 57ª legislatura, suplentes incluídos; ${pct(own)} do dinheiro deles para municípios foi a prefeitos do próprio partido`,
        en: `deputies of the 57th legislature, substitutes included; ${pct(own)} of their town money went to own-party mayors` }) };
  },
  async tse() {
    const ys = (await data("site/tse/anos.csv")).map((r) => r.ano).sort();
    const tot = await Promise.all(ys.map(async (y) => { const t = await data(`site/tse/${y}/resumo.csv`); return { y, total: sum(t.map((r) => +r.total)), pub: sum(t.map((r) => +r.publico)) }; }));
    const full = tot.filter((x) => x.total > 0), last = full.filter((x) => x.y !== "2026").pop() || full[full.length - 1];
    return { value: pct(last.pub / last.total), series: full.map((x) => x.pub / x.total), opts: { bars: true, mark: full.indexOf(last), labels: [full[0].y, full[full.length - 1].y] },
      sub: tr({ pt: `dos ${brl(last.total)} arrecadados pelos candidatos em ${last.y} eram dinheiro público`, en: `of the ${brl(last.total)} raised by ${last.y} candidates was public money` }) };
  },
  async emendas() {
    const a = await data("site/emendas/anos.csv");
    const ys = [...new Set(a.map((r) => r.ano))].sort(), paid = ys.map((y) => sum(a.filter((r) => r.ano === y).map((r) => +r.pago)));
    const i = ys.length >= 2 ? ys.length - 2 : ys.length - 1, n = ys.length - 1;
    return { value: brl(paid[i]), series: paid, opts: { bars: true, mark: i, labels: [ys[0], ys[n]] },
      sub: tr({ pt: `em emendas pagas em ${ys[i]} (${ys[n]} até agora: ${brl(paid[n])})`, en: `of amendments paid in ${ys[i]} (${ys[n]} so far: ${brl(paid[n])})` }) };
  },
  async pncp() {
    const r = await data("site/pncp/resumo.json"), d = await data("site/pncp/diario.csv");
    const days = [...new Set(d.map((x) => x.dia))].sort(), by = new Map();
    for (const x of d) by.set(x.dia, (by.get(x.dia) || 0) + +x.valor);
    const c = r.coverage;
    return { value: num(r.totals.contratos), series: days.length >= 7 ? days.map((x) => by.get(x)) : null, opts: { bars: false, labels: days.length ? [days[0].slice(0, 7), days[days.length - 1].slice(0, 7)] : [] },
      sub: tr({ pt: `contratos lidos (${brl(r.totals.valor)}), ${num(c.days_read)} de ${num(c.span_days)} dias do histórico até agora`,
        en: `contracts read (${brl(r.totals.valor)}), ${num(c.days_read)} of ${num(c.span_days)} days of history so far` }) };
  },
  async siconfi() {
    const r = await data("site/siconfi/resumo.json"), sy = r.status_by_year;
    if (!sy.length) return { value: "–", sub: tr({ pt: "histórico em leitura", en: "history being read" }) };
    const last = sy[sy.length - 1], above = (x) => (x.acima_alerta + x.acima_prudencial + x.acima_maximo) / x.n;
    return { value: pct(above(last)), series: sy.map(above), opts: { bars: true, color: css("--warning"), labels: [String(sy[0].ano), String(last.ano)] },
      sub: tr({ pt: `dos ${num(last.n)} municípios lidos em ${last.ano} gastam com pessoal acima do limite de alerta`, en: `of ${num(last.n)} towns read for ${last.ano} spend over the payroll alert limit` }) };
  },
  async sancoes() {
    const r = await data("site/sancoes/resumo.json");
    const sy = r.start_year.filter((x) => +x.ano >= 2010), keys = ["FEDERAL", "ESTADUAL", "MUNICIPAL", "outra"];
    return { value: num(r.tiles.ceis + r.tiles.cnep), series: sy.map((x) => sum(keys.map((k) => +x[k] || 0))), opts: { bars: true, labels: [sy[0].ano, sy[sy.length - 1].ano] },
      sub: tr({ pt: `sanções registradas, por ano de início; ${brl(r.money.emendas.barrado)} em emendas pagas a empresas enquanto estavam impedidas`,
        en: `sanctions listed, by the year they began; ${brl(r.money.emendas.barrado)} in amendments paid to companies while barred` }) };
  },
};

// ------------------------------------------------------------ findings

function finding(key, num_, txt, viz) {
  const a = document.querySelector(`[data-hl="${key}"]`);
  if (!a) return;
  a.querySelector(".num").textContent = num_;
  a.querySelector(".txt").textContent = txt;
  a.querySelector(".viz").replaceChildren(...(viz ? [viz] : []));
}
const meter = (x, cls = "") => el("span", { className: `meter ${cls}` }, el("b", { style: `width:${Math.max(0, Math.min(1, x)) * 100}%` }));

const FINDINGS = {
  async gov() {
    const idx = (await data("camara/index.csv")).filter((r) => r.with_gov !== "" && +r.votacoes_contested >= 10), last = idx[idx.length - 1];
    finding("gov", pct(+last.with_gov), tr({ pt: `dos votos na Câmara seguiram a orientação do governo em ${month(last.month)}, o último mês com 10 ou mais votações disputadas`,
      en: `of the Câmara's votes followed the government's orientation in ${month(last.month)}, the latest month with 10 or more contested roll calls` }), meter(+last.with_gov));
  },
  async mayors() {
    const d = await data("site/deputados/deputados_57.csv"), m = (r) => +r.emendas_pago || 0, w = d.filter((r) => r.prefeito_mesmo_partido !== "" && m(r) > 0);
    const own = sum(w.map((r) => +r.prefeito_mesmo_partido * m(r))) / sum(w.map(m)), base = sum(w.map((r) => +r.prefeito_base * m(r))) / sum(w.map(m));
    const top = Math.max(own, base) * 1.1;
    const vs = el("span", { className: "vs" },
      el("span", { textContent: tr({ pt: "próprio partido", en: "own party" }) }), meter(own / top), el("span", { textContent: pct(own) }),
      el("span", { textContent: tr({ pt: "ao acaso", en: "at random" }) }), meter(base / top, "base"), el("span", { textContent: pct(base) }));
    finding("mayors", pct(own), tr({ pt: `do dinheiro de emendas dos deputados para municípios foi a prefeitos do próprio partido, contra ${pct(base)} se fosse ao acaso`,
      en: `of deputies' amendment money for towns went to mayors of their own party, against ${pct(base)} if it went at random` }), vs);
  },
  async barred() {
    const r = await data("site/sancoes/resumo.json"), e = r.money.emendas;
    const by = (e.by_year || []).filter((x) => +x.ano >= 2015), box = el("span", { className: "viz-spark" });
    finding("barred", brl(e.barrado, 0), tr({ pt: `em emendas pagas a ${num(e.empresas_barrado)} empresas enquanto estavam proibidas de contratar com o poder público`,
      en: `in amendments paid to ${num(e.empresas_barrado)} companies while they were barred from public contracts` }), box);
    if (by.length >= 2) spark(box, by.map((x) => +x.sim || 0), { bars: true, color: css("--c-control") || css("--critical"), height: 26 });
  },
  async public() {
    const ys = (await data("site/tse/anos.csv")).map((r) => r.ano).sort();
    const y = ys.includes("2022") ? "2022" : ys[ys.length - 1], t = await data(`site/tse/${y}/resumo.csv`), share = sum(t.map((r) => +r.publico)) / sum(t.map((r) => +r.total));
    finding("public", pct(share), tr({ pt: `do dinheiro arrecadado pelos candidatos em ${y} era público (fundos partidário e eleitoral)`,
      en: `of the money candidates raised in ${y} was public (party and electoral funds)` }), meter(share));
  },
};

// ------------------------------------------------------------ red flags banner

async function redFlags() {
  const r = await data("site/alertas/resumo.json"), box = document.querySelector("#ab-stats");
  if (!box) return;
  const stat = (n, label) => el("div", {}, el("b", { textContent: n }), el("span", { textContent: label }));
  box.replaceChildren(
    stat(brl(r.emendas_impedidas.valor, 0), tr({ pt: "em emendas pagas a empresas sob sanção que alcança verba federal", en: "in amendments paid to companies under a bar that reaches federal money" })),
    stat(num(r.contratos_impedidas.casos), tr({ pt: "contratos com empresas impedidas na data", en: "contracts with companies barred on the day" })),
    stat(num(r.campanha_emendas.casos), tr({ pt: "fornecedores de campanha pagos com emendas do mesmo deputado", en: "campaign suppliers paid from the same deputy's amendments" })),
    stat(num(r.cruzamentos.entidades), tr({ pt: "empresas e entidades em duas listas ou mais", en: "companies and bodies on two lists or more" })));
}

// ------------------------------------------------------------ ranking banner

async function ranking() {
  const r = await data("site/ranking/resumo.json"), b = r.builds?.["57"] || r.builds?.[String(r.legislaturas?.[0])], box = document.querySelector("#rb-stats");
  if (!b || !box) return;
  const stat = (n, label) => el("div", {}, el("b", { textContent: n }), el("span", { textContent: label }));
  box.replaceChildren(
    stat(num(b.ranked), tr({ pt: "deputados ranqueados, com 12 meses ou mais de mandato", en: "deputies ranked, with 12 months or more in office" })),
    stat(pct(b.participation_median), tr({ pt: "das votações nominais, na mediana", en: "of roll calls voted in, at the median" })),
    stat(brl(b.allowance_median_month, 0), tr({ pt: "por mês de cota parlamentar, na mediana", en: "a month of office allowance, at the median" })),
    stat(num(b.bills_median), tr({ pt: "projetos apresentados, na mediana", en: "bills filed, at the median" })));
}

// ------------------------------------------------------------ hero: every deputy by how they vote

let swarmRows = null;
async function swarm() {
  const box = document.querySelector("#swarm");
  if (!swarmRows) {
    const net = (await data("site/camara/networks.csv")).filter((r) => r.modularity_party !== "");
    const m = net[net.length - 1].month;
    swarmRows = { month: m, rows: (await data(`site/camara/members/${m.slice(0, 4)}.csv`)).filter((r) => r.month === m && r.pc1 !== "") };
  }
  const { rows, month: m } = swarmRows;
  const mean = (p) => { const xs = rows.filter((r) => r.partido === p).map((r) => +r.pc1); return xs.length ? sum(xs) / xs.length : 0; };
  const flip = mean("PT") > mean("PL") ? -1 : 1;
  const W = Math.max(280, Math.round(box.clientWidth) || 480), R = W < 420 ? 2.7 : 3.5, gap = 0.6, D = 2 * R + gap;
  const xs = rows.map((r) => flip * +r.pc1), lo = Math.min(...xs), hi = Math.max(...xs);
  const sx = (x) => R + 2 + ((x - lo) / (hi - lo || 1)) * (W - 2 * R - 4);
  // Beeswarm: in order across, each dot takes the free spot closest to the middle line.
  const pts = rows.map((r, i) => ({ r, x: sx(xs[i]), y: 0 })).sort((a, b) => a.x - b.x || a.r.id.localeCompare(b.r.id));
  const placed = [];
  for (const p of pts) {
    const near = placed.filter((q) => p.x - q.x < D);
    for (let k = 0; ; k++) {
      const y = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * (D / 2);
      if (near.every((q) => (p.x - q.x) ** 2 + (y - q.y) ** 2 >= D * D)) { p.y = y; break; }
    }
    placed.push(p);
  }
  const top = Math.max(...pts.map((p) => Math.abs(p.y))) + R + 2, H = Math.ceil(2 * top);
  const color = (p) => (p === "PT" ? css("--a") : p === "PL" ? css("--b") : css("--other"));
  const order = (p) => (p === "PT" || p === "PL" ? 1 : 0);
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}` });
  s.append(svg("line", { x1: 0, x2: W, y1: top, y2: top, stroke: css("--grid"), "stroke-width": 1 }));
  for (const p of [...pts].sort((a, b) => order(a.r.partido) - order(b.r.partido))) {
    s.append(svg("circle", { cx: p.x.toFixed(1), cy: (top + p.y).toFixed(1), r: R, fill: color(p.r.partido) }, svg("title", {}, `${p.r.nome} (${p.r.partido}-${p.r.uf})`)));
  }
  box.replaceChildren(s);
  document.querySelector("#swarm-cap").replaceChildren(...(lang() === "en"
    ? [`Each dot is one of the ${num(rows.length)} deputies who voted in ${month(m)}, placed by how they voted (the main axis of all roll calls). `, el("a", { href: "camara/?tab=ideal", textContent: "Ideal points over time →" })]
    : [`Cada ponto é um dos ${num(rows.length)} deputados que votaram em ${month(m)}, posicionado pelo seu padrão de votos (o eixo principal de todas as votações nominais). `, el("a", { href: "camara/?tab=ideal", textContent: "Pontos ideais ao longo do tempo →" })]));
}

// ------------------------------------------------------------ last update

let updated = null;
async function lastUpdate() {
  try {
    if (!updated) {
      const r = await fetch("https://api.github.com/repos/mbottoni/political-eye/commits?per_page=1");
      if (!r.ok) return;
      updated = (await r.json())[0]?.commit?.committer?.date;
    }
    if (!updated) return;
    const box = document.querySelector("#updated");
    box.querySelector("dd").textContent = date(updated);
    box.hidden = false;
  } catch { /* offline or rate-limited: leave it out */ }
}

// ------------------------------------------------------------ is each source up to date?

// Each card's scheduled job, and how many days may pass since its last successful run before the card says it is
// overdue (the schedule plus a day's slack: GitHub starts scheduled runs hours late). A run that reads nothing new
// still succeeds, so a quiet source is not mistaken for a stuck one.
const JOBS = {
  camara: ["camara", 9], senado: ["senado", 9], orientacoes: ["camara-blocos", 2], deputados: ["ref", 9],
  tse: ["tse", 9], emendas: ["emendas", 2], pncp: ["pncp", 2], siconfi: ["siconfi", 2], sancoes: ["sancoes", 2],
};
let runs = null;
async function freshness() {
  try {
    if (!runs) {
      const r = await fetch("https://api.github.com/repos/mbottoni/political-eye/actions/runs?event=schedule&status=completed&per_page=100");
      if (!r.ok) return;
      runs = (await r.json()).workflow_runs || [];
    }
    if (!runs.length) return;
    const en = lang() === "en", now = Date.now(), days = (t) => (now - Date.parse(t)) / 864e5;
    const reach = days(runs[runs.length - 1].updated_at);   // how far back the runs read go
    const late = [];
    for (const [key, [job, maxDays]] of Object.entries(JOBS)) {
      const badge = document.querySelector(`[data-key="${key}"] .cadence`);
      if (!badge) continue;
      const mine = runs.filter((x) => x.path === `.github/workflows/${job}.yml`);
      const ok = mine.find((x) => x.conclusion === "success");
      if (!ok && reach <= maxDays) continue;   // no run in what was read, and it may not be due yet: say nothing
      const overdue = !ok || days(ok.updated_at) > maxDays;
      const failed = mine[0]?.conclusion === "failure";
      badge.querySelector(".fresh")?.remove();
      badge.classList.toggle("late", overdue);
      badge.classList.toggle("failed", failed && !overdue);
      badge.title = ok ? (en ? `Last successful run: ${date(ok.updated_at)}` : `Última execução bem-sucedida: ${date(ok.updated_at)}`)
        : (en ? "No successful run recently" : "Nenhuma execução bem-sucedida recente");
      if (overdue || failed) {
        badge.append(el("span", { className: "fresh", textContent: overdue ? (en ? " · overdue" : " · atrasado") : (en ? " · last run failed" : " · última falhou") }));
      }
      if (overdue) late.push(badge.closest(".card")?.querySelector("h3")?.textContent || key);
    }
    const box = document.querySelector("#stale");
    box.querySelector("dd").textContent = num(late.length);
    box.querySelector("dt").textContent = late.length === 1 ? (en ? "source overdue" : "fonte atrasada") : (en ? "sources overdue" : "fontes atrasadas");
    box.title = late.join(", ");
    box.hidden = !late.length;
  } catch { /* offline or rate-limited: leave the badges as they are */ }
}

// ------------------------------------------------------------ find a deputy

const profileHref = (d) => `deputados/?tab=profile&leg=${d.leg}&dep=${d.id}`;
let searchLang = null;
function searchBox() {
  if (searchLang === lang()) return;   // a resize redraws the charts, not the box someone may be typing in
  searchLang = lang();
  document.querySelector("#deputy-search").replaceChildren(deputySearch({ href: profileHref, large: true }));
  // Three deputies of the current legislature, at random, so the suggestion favours no one.
  const go = () => deputies().then((all) => {
    const now = all.filter((d) => d.leg === 57 && d.votes >= 50);
    if (!now.length) return;
    const pickN = [];
    while (pickN.length < Math.min(3, now.length)) { const d = now[Math.floor(Math.random() * now.length)]; if (!pickN.includes(d)) pickN.push(d); }
    document.querySelector("#try-list").replaceChildren(...pickN.flatMap((d, i) => [i ? ", " : "", el("a", { href: profileHref(d), textContent: d.nome })]));
    document.querySelector("#try").hidden = false;
  }).catch(() => {});
  if ("requestIdleCallback" in window) requestIdleCallback(go, { timeout: 2500 }); else setTimeout(go, 800);
}

// ------------------------------------------------------------ render

function render() {
  translate();
  searchBox();
  for (const [k, f] of Object.entries(CARDS)) f().then((x) => fill(k, x)).catch((e) => console.warn(`hub ${k}:`, e));
  for (const [k, f] of Object.entries(FINDINGS)) f().catch((e) => { console.warn(`hub ${k}:`, e); finding(k, "–", "", null); });
  swarm().catch((e) => console.warn("hub swarm:", e));
  redFlags().catch((e) => console.warn("hub red flags:", e));
  ranking().catch((e) => console.warn("hub ranking:", e));
  lastUpdate();
  freshness();
}

document.querySelector("#lang-slot").replaceWith(langSwitch());
window.addEventListener("langchange", render);
let lastW = 0, timer;
new ResizeObserver(([e]) => {
  const w = Math.round(e.contentRect.width);
  if (Math.abs(w - lastW) < 2) return;
  const first = !lastW;
  lastW = w; clearTimeout(timer);
  if (!first) timer = setTimeout(render, 150);
}).observe(document.querySelector("main"));
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
render();
