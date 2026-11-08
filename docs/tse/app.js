// Campaign finance: where candidates' money came from, how parties split public funds, donors and suppliers.
import { $, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";

const OFFICES = ["Presidente", "Governador", "Senador", "Deputado Federal", "Deputado Estadual", "Deputado Distrital"];
const OFFICE = { Presidente: "President", Governador: "Governor", Senador: "Senator", "Deputado Federal": "Federal deputy", "Deputado Estadual": "State deputy", "Deputado Distrital": "District deputy (DF)" };
const SHORT = { Presidente: "President", Governador: "Governor", Senador: "Senator", "Deputado Federal": "Fed. deputy", "Deputado Estadual": "State deputy", "Deputado Distrital": "DF deputy" };
const ORIGINS = [["origem_partido", "Parties"], ["origem_pessoas_fisicas", "Individuals"], ["origem_proprios", "Own money"], ["origem_outros_candidatos", "Other candidates"], ["origem_financiamento_coletivo", "Crowdfunding"]];
const officeColor = (o) => C.slot(OFFICES.indexOf(o) + 1);
const partyColor = (p) => (p === "PT" ? css("--a") : p === "PL" ? css("--b") : css("--other"));
const PARTY_LEGEND = () => [{ label: "PT", color: css("--a") }, { label: "PL", color: css("--b") }, { label: "Other parties", color: css("--other") }];

const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const finding = (text) => el("p", { className: "finding", textContent: text });
const select = (label, options, value, onChange) => {
  const s = el("select", {}, ...options.map((o) => el("option", { value: o.value ?? o, textContent: o.label ?? o, selected: String(o.value ?? o) === String(value) })));
  s.addEventListener("change", () => onChange(s.value));
  return el("label", {}, label, s);
};
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const median = (xs) => { const v = xs.filter((x) => x != null && !Number.isNaN(x)).sort((a, b) => a - b); return v.length ? (v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2) : null; };
const elected = (r) => String(r.resultado).startsWith("ELEITO");
const who = (r) => `${r.nome_urna} (${r.partido}-${r.uf})`;
const redraws = [];
const later = (f) => { redraws.push(f); f(); };
/** Redraws owned by one tab's controls: reset() drops them when the tab redraws itself, and leaves other tabs' alone. */
function local() {
  const mine = [];
  redraws.push(() => mine.forEach((f) => f()));
  return { later: (f) => { mine.push(f); f(); }, reset: () => { mine.length = 0; } };
}

let YEARS = [], year;
const site = (f, y = year) => data(`site/tse/${y}/${f}`);
const raw = (f, y = year) => data(`tse/${y}/${f}`);
const every = (f) => Promise.all(YEARS.map((y) => site(f, y)));
const num = (rows, keys) => { for (const r of rows) for (const k of keys) r[k] = r[k] === "" ? null : +r[k]; return rows; };
const MONEY = ["candidatos", "eleitos", "total", "origem_partido", "origem_pessoas_fisicas", "origem_outros_candidatos", "origem_proprios", "origem_financiamento_coletivo", "fonte_fefc", "fonte_fundo_partidario", "publico", "contratado"];
const PARTY_NUM = ["candidatos", "eleitos", "mulheres", "negros", "total", "publico", "publico_mulheres", "publico_negros", "gini_publico", "top10_publico", "mediana_incumbentes", "mediana_novos", "incumbentes"];
const CAND_NUM = ["incumbente", "n_doadores_pf", "total", "origem_partido", "origem_pessoas_fisicas", "origem_outros_candidatos", "origem_proprios", "origem_financiamento_coletivo", "fonte_fefc", "fonte_fundo_partidario", "publico"];
const resumo = async (y = year) => num(await site("resumo.csv", y), MONEY);
const partidos = async (y = year) => num(await site("partidos.csv", y), PARTY_NUM);
const candidatos = async () => num(await site("candidatos.csv"), CAND_NUM);

// ------------------------------------------------------------ overview

async function overview(root) {
  const [R, all, gd] = await Promise.all([resumo(), Promise.all(YEARS.map((y) => resumo(y))), raw("grandes_doadores.csv")]);
  const T = (k, rows = R) => sum(rows.map((r) => r[k]));
  const total = T("total"), pub = T("publico"), indiv = T("origem_pessoas_fisicas"), large = sum(gd.map((r) => +r.total));
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: `Money declared in ${year}`, value: brl(total), sub: `by ${plural(T("candidatos"), "candidate")} for ${R.length} offices` },
    { label: "Public money", value: pct(pub / total), sub: `${brl(T("fonte_fefc"))} from the FEFC, ${brl(T("fonte_fundo_partidario"))} from the Party Fund` },
    { label: "From private individuals", value: pct(indiv / total), sub: `${pct(large / indiv)} of it from ${plural(gd.length, "donor")} who gave R$50k or more` },
    { label: "Candidates' own money", value: pct(T("origem_proprios") / total), sub: brl(T("origem_proprios")) },
  ]);
  const c1 = chart(), c2 = chart(), c3 = chart(), g = el("div", { className: "grid2" });
  root.append(card("Where each office's money came from", "Money candidates declared, by office and origin. “Parties” is money passed on by party directorates, most of it from the public funds.", c1));
  g.append(card("Public money in each election", "Every office together, by fund. Public funds paid for most campaigns once the FEFC was created in 2017; it more than doubled for 2022.", c2),
    card("Public money's share, by office", "The share of declared money that came from the FEFC or the Party Fund.", c3));
  root.append(g);
  const offices = OFFICES.filter((o) => R.some((r) => r.cargo === o)), row = (o) => R.find((r) => r.cargo === o);
  const series = [...ORIGINS.map(([k, name], i) => ({ name, color: C.slot(i + 1), values: offices.map((o) => row(o)[k]) })),
    { name: "Other", color: css("--other"), values: offices.map((o) => row(o).total - sum(ORIGINS.map(([k]) => row(o)[k]))) }];
  const tbl = {
    rows: R.map((r) => ({ ...r, office: OFFICE[r.cargo], per: r.total / r.candidatos, share: r.publico / r.total })),
    cols: [{ key: "office", label: "Office", text: true }, { key: "candidatos", label: "Candidates" }, { key: "eleitos", label: "Elected" }, { key: "total", label: "Declared", fmt: (v) => brl(v) },
      { key: "per", label: "Per candidate", fmt: (v) => brl(v) }, { key: "share", label: "Public share", fmt: (v) => pct(v) }, { key: "origem_proprios", label: "Own money", fmt: (v) => brl(v) }],
    name: `money-by-office-${year}`,
  };
  later(() => C.stack(c1, { x: offices.map((o) => SHORT[o]), series, format: (v) => brl(v, 0), height: 260, table: tbl }));
  const tot = (rows, k) => sum(rows.map((r) => r[k]));
  later(() => C.stack(c2, { x: YEARS, height: 240, format: (v) => brl(v, 0), series: [
    { name: "FEFC", color: C.slot(1), values: all.map((rows) => tot(rows, "fonte_fefc")) },
    { name: "Party Fund", color: C.slot(2), values: all.map((rows) => tot(rows, "fonte_fundo_partidario")) },
    { name: "Other sources", color: css("--other"), values: all.map((rows) => tot(rows, "total") - tot(rows, "publico")) }] }));
  later(() => C.line(c3, { x: "num", xTicks: YEARS, height: 240, y: { min: 0, max: 1, format: (v) => pct(v) },
    series: offices.map((o) => ({ name: OFFICE[o], color: officeColor(o), points: YEARS.map((y, i) => { const r = all[i].find((x) => x.cargo === o); return [y, r && r.total ? r.publico / r.total : null]; }) })) }));
  const first = all[0], share0 = tot(first, "publico") / tot(first, "total");
  root.append(finding(year === YEARS[0]
    ? `In ${year}, public funds paid for ${pct(pub / total)} of the money candidates declared.`
    : `In ${year}, public funds paid for ${pct(pub / total)} of the money candidates declared, against ${pct(share0)} in ${YEARS[0]}.`));
}

// ------------------------------------------------------------ parties

async function parties(root) {
  const L = local();
  const [P, cand] = await Promise.all([partidos(), candidatos()]);
  let office = params.get("po") || "Deputado Federal", measure = params.get("pm") || "per";
  if (!P.some((r) => r.cargo === office)) office = "Deputado Federal";
  const controls = el("div", { className: "controls" }), body = el("div");
  root.append(controls, body);
  const draw = () => {
    L.reset();
    controls.replaceChildren(
      select("Office", OFFICES.filter((o) => P.some((r) => r.cargo === o)).map((o) => ({ value: o, label: OFFICE[o] })), office, (v) => { office = v; setParam("po", v, "Deputado Federal"); draw(); }),
      select("Public money", [{ value: "per", label: "Per candidate" }, { value: "total", label: "Total" }, { value: "elected", label: "Per elected candidate" }], measure, (v) => { measure = v; setParam("pm", v, "per"); draw(); }));
    body.replaceChildren();
    const rows = P.filter((r) => r.cargo === office && r.publico > 0);
    const value = (r) => (measure === "total" ? r.publico : measure === "elected" ? (r.eleitos ? r.publico / r.eleitos : null) : r.publico / r.candidatos);
    const c1 = chart(), c2 = chart();
    const g = el("div", { className: "grid2" });
    const big = rows.filter((r) => r.candidatos >= 20);
    g.append(card("Public money by party", {
      per: "Public money (FEFC and Party Fund) divided by the party's candidates for this office.", total: "All public money the party's candidates for this office received.",
      elected: "Public money divided by the candidates the party elected: what each seat cost in public funds. Parties that elected nobody are left out.",
    }[measure], c1), card("How unevenly each party splits its public money", "Gini coefficient of public money among the party's candidates for this office: 0 if every candidate got the same, near 1 if a few got almost all. Parties with 20 or more candidates.", c2));
    body.append(g);
    L.later(() => C.bars(c1, { rows: rows.filter((r) => value(r) != null).map((r) => ({ label: r.partido, value: value(r), color: partyColor(r.partido), note: `${plural(r.candidatos, "candidate")}, ${fmt(r.eleitos)} elected` })).sort((a, b) => b.value - a.value), format: (v) => brl(v), labelWidth: 120, barHeight: 14, legend: PARTY_LEGEND() }));
    L.later(() => C.bars(c2, { rows: big.map((r) => ({ label: r.partido, value: r.gini_publico, color: partyColor(r.partido), note: `its 10 best-funded candidates got ${pct(r.top10_publico)} · ${plural(r.candidatos, "candidate")}` })).sort((a, b) => b.value - a.value), format: (v) => fmt(v, 2), max: 1, labelWidth: 120, barHeight: 14, legend: PARTY_LEGEND(), empty: "No party had 20 candidates for this office." }));

    if (office === "Deputado Federal") {
      const dep = cand.filter((r) => r.cargo === "Deputado Federal"), inc = dep.filter((r) => r.incumbente), nov = dep.filter((r) => !r.incumbente);
      const rate = (xs) => (xs.length ? xs.filter(elected).length / xs.length : null);
      const tl = el("section", { className: "tiles" }), c3 = chart();
      tiles(tl, [
        { label: "Sitting deputies running again", value: fmt(inc.length), sub: `of ${fmt(dep.length)} federal deputy candidates` },
        { label: "Re-elected", value: pct(rate(inc)), sub: `${fmt(inc.filter(elected).length)} sitting deputies won a seat` },
        { label: "Other candidates elected", value: pct(rate(nov), 1), sub: `${fmt(nov.filter(elected).length)} of ${fmt(nov.length)}` },
        { label: "Median public money", value: brl(median(inc.map((r) => r.publico))), sub: `a sitting deputy, against ${brl(median(nov.map((r) => r.publico)))} for everyone else` },
      ]);
      const pts = P.filter((r) => r.cargo === office && r.incumbentes >= 3 && r.mediana_novos != null && r.mediana_incumbentes != null);
      const ok = pts.filter((r) => r.mediana_novos > 0), more = pts.filter((r) => r.mediana_incumbentes > r.mediana_novos);
      body.append(card("Who leaderships fund: sitting deputies or newcomers", "How many times more public money the party's median sitting federal deputy got than its median other candidate. Parties with three or more incumbents running.", tl, c3,
        finding(`${plural(more.length, "party", "parties")} of ${pts.length} gave the median sitting deputy more public money than the median other candidate.`)));
      L.later(() => C.bars(c3, {
        rows: ok.map((r) => ({ label: r.partido, value: r.mediana_incumbentes / r.mediana_novos, color: partyColor(r.partido),
          note: `median ${brl(r.mediana_incumbentes)} for its ${fmt(r.incumbentes)} incumbents, ${brl(r.mediana_novos)} for the others` })).sort((a, b) => b.value - a.value),
        format: (v) => `${fmt(v, v < 10 ? 1 : 0)}×`, labelWidth: 120, barHeight: 14, legend: PARTY_LEGEND(),
        table: { rows: pts, cols: [{ key: "partido", label: "Party", text: true }, { key: "incumbentes", label: "Incumbents" }, { key: "mediana_incumbentes", label: "Median, incumbents", fmt: (v) => brl(v) }, { key: "mediana_novos", label: "Median, others", fmt: (v) => brl(v) }], name: `incumbents-${year}` },
      }));
    } else {
      body.append(card("Who leaderships fund: sitting deputies or newcomers", "Incumbency is tracked for federal deputies only: pick “Federal deputy” above."));
    }

    const tb = el("div");
    body.append(card(`Every party: ${OFFICE[office]}`, "Public money is the FEFC plus the Party Fund. Medians of incumbents and others are for federal deputies.", tb));
    table(tb, P.filter((r) => r.cargo === office).map((r) => ({ ...r, per: r.publico / r.candidatos })), [
      { key: "partido", label: "Party", text: true }, { key: "candidatos", label: "Candidates" }, { key: "eleitos", label: "Elected" }, { key: "total", label: "Declared", fmt: (v) => brl(v) },
      { key: "publico", label: "Public", fmt: (v) => brl(v) }, { key: "per", label: "Public per candidate", fmt: (v) => brl(v) }, { key: "gini_publico", label: "Gini", fmt: (v) => fmt(v, 2) },
      { key: "top10_publico", label: "Top 10's share", fmt: (v) => pct(v) }, { key: "incumbentes", label: "Incumbents" },
      { key: "mediana_incumbentes", label: "Median, incumbents", fmt: (v) => brl(v) }, { key: "mediana_novos", label: "Median, others", fmt: (v) => brl(v) },
    ], { sortBy: "publico", pageSize: 40, name: `parties-${office}-${year}` });
  };
  draw();
}

// ------------------------------------------------------------ women and Black candidates

const LAW = {
  women: "The law (Supreme Court ADI 5617 and TSE, 2018; Constitutional Amendment 117, 2022): at least 30% of a party's public campaign money goes to women, and more if women are more than 30% of its candidates. So a party meets it on or above the dashed line, and above 30%.",
  black: {
    2018: "No rule applied in 2018. The dashed line marks money in proportion to candidates.",
    2022: "From 2020 (TSE and Supreme Court, ADPF 738): public money and airtime for Black candidates in proportion to their share of the party's candidates. A party meets it on or above the dashed line.",
    2026: "Constitutional Amendment 133 (2024), upheld by the Supreme Court in June 2026: at least 30% of public campaign money goes to Black candidates, whatever their share of candidates. The dashed line marks money in proportion to candidates.",
  },
};

async function equity(root) {
  const L = local();
  const all = await Promise.all(YEARS.map((y) => partidos(y)));
  const P = all[YEARS.indexOf(year)];
  let office = params.get("eo") || "all";
  const controls = el("div", { className: "controls" }), body = el("div");
  root.append(controls, body);
  const pick = (rows, o) => (o === "all" ? rows : rows.filter((r) => r.cargo === o));
  const byParty = (rows) => {
    const m = new Map();
    for (const r of rows) {
      const a = m.get(r.partido) || { partido: r.partido, candidatos: 0, mulheres: 0, negros: 0, publico: 0, publico_mulheres: 0, publico_negros: 0 };
      for (const k of ["candidatos", "mulheres", "negros", "publico", "publico_mulheres", "publico_negros"]) a[k] += r[k];
      m.set(r.partido, a);
    }
    return [...m.values()].filter((a) => a.publico > 0 && a.candidatos >= 10);
  };
  const share = (rows, a, b) => sum(rows.map((r) => r[a])) / sum(rows.map((r) => r[b]));
  const draw = () => {
    L.reset();
    controls.replaceChildren(select("Office", [{ value: "all", label: "Every office (as the law counts)" }, ...OFFICES.map((o) => ({ value: o, label: OFFICE[o] }))], office, (v) => { office = v; setParam("eo", v, "all"); draw(); }));
    body.replaceChildren();
    const rows = pick(P, office), parties = byParty(rows);
    tiles(body.appendChild(el("section", { className: "tiles" })), [
      { label: "Women among candidates", value: pct(share(rows, "mulheres", "candidatos"), 1), sub: OFFICE[office] || "every office" },
      { label: "Women's share of public money", value: pct(share(rows, "publico_mulheres", "publico"), 1), sub: `${brl(sum(rows.map((r) => r.publico_mulheres)))} of ${brl(sum(rows.map((r) => r.publico)))}` },
      { label: "Black candidates", value: pct(share(rows, "negros", "candidatos"), 1), sub: "self-declared preta or parda" },
      { label: "Black candidates' share of public money", value: pct(share(rows, "publico_negros", "publico"), 1), sub: brl(sum(rows.map((r) => r.publico_negros))) },
    ]);
    const maxPub = Math.max(...parties.map((a) => a.publico), 1), MIN_PUB = 1e6;
    const scatterOf = (box, k, pk, floor, rule) => {
      const pts = parties.filter((a) => a.publico >= MIN_PUB).map((a) => {
        const x = a[k] / a.candidatos, y = a[pk] / a.publico, need = rule(x), below = y < need - 0.005;
        return { x, y, label: below ? a.partido : "", title: a.partido, color: below ? css("--critical") : css("--other"), r: 3 + 6 * Math.sqrt(a.publico / maxPub), z: below ? 1 : 0,
          rows: [`${pct(x, 1)} of its ${fmt(a.candidatos)} candidates, ${pct(y, 1)} of its ${brl(a.publico)} public money`, below ? `▼ below the rule by ${fmt(100 * (need - y), 1)} points` : "✓ meets the rule"] };
      });
      const up = (v) => Math.min(1, Math.ceil((v + 0.03) * 10) / 10), down = (v) => Math.max(0, Math.floor((v - 0.03) * 10) / 10);
      const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
      const xd = [down(Math.min(...xs)), up(Math.max(...xs))], yd = [Math.min(down(Math.min(...ys)), floor ? 0.2 : 1), up(Math.max(...ys, 0.4))];
      C.scatter(box, {
        points: pts, x: { label: "Share of the party's candidates", format: (v) => pct(v), min: xd[0], max: xd[1] }, y: { label: "Share of its public money", format: (v) => pct(v), min: yd[0], max: yd[1] },
        diagonal: { label: "in proportion" }, refs: floor ? [{ y: 0.3, label: "30% floor" }] : [], labels: 10, labelRank: (a, b) => b.r - a.r, height: 340,
        legend: [{ label: "▼ Below the rule", color: css("--critical") }, { label: "✓ Meets it", color: css("--other") }],
        table: { rows: pts.map((p) => ({ party: p.title, cand: p.x, money: p.y, gap: p.y - p.x })), cols: [{ key: "party", label: "Party", text: true }, { key: "cand", label: "Share of candidates", fmt: (v) => pct(v, 1) }, { key: "money", label: "Share of public money", fmt: (v) => pct(v, 1) }, { key: "gap", label: "Gap (points)", fmt: (v) => fmt(100 * v, 1) }], name: `${k}-${year}` },
      });
      return [pts.filter((p) => p.label).length, pts.length];
    };
    const c1 = chart(), c2 = chart(), n1 = el("p", { className: "finding" }), n2 = el("p", { className: "finding" });
    const g = el("div", { className: "grid2" });
    const blackRule = year >= 2026 ? () => 0.3 : year >= 2022 ? (x) => x : () => -1;
    g.append(card("Women: candidates against public money", `${LAW.women} Each dot is a party with R$1 million or more in public money (every party is in the table below); red ones fall short.`, c1, n1),
      card("Black candidates: candidates against public money", `${LAW.black[year] || LAW.black[2026]} Each dot is a party with R$1 million or more in public money; red ones fall short.`, c2, n2));
    body.append(g);
    L.later(() => { const [k, n] = scatterOf(c1, "mulheres", "publico_mulheres", true, (x) => Math.max(0.3, x)); n1.textContent = `On these numbers, ${plural(k, "party", "parties")} of ${n} gave women less than the rule asks (a tolerance of half a point).`; });
    L.later(() => { const [k, n] = scatterOf(c2, "negros", "publico_negros", year >= 2026, blackRule); n2.textContent = year < 2022 ? "No rule applied in this election." : `On these numbers, ${plural(k, "party", "parties")} of ${n} gave Black candidates less than the rule asks.`; });

    const c3 = chart(), c4 = chart(), g2 = el("div", { className: "grid2" });
    g2.append(card("Women, across elections", OFFICE[office] ? `${OFFICE[office]}, every party.` : "Every office and party.", c3), card("Black candidates, across elections", OFFICE[office] ? `${OFFICE[office]}, every party.` : "Every office and party.", c4));
    body.append(g2);
    const trend = (k, pk) => [
      { name: "Share of candidates", color: C.slot(1), points: YEARS.map((y, i) => [y, share(pick(all[i], office), k, "candidatos")]) },
      { name: "Share of public money", color: C.slot(2), points: YEARS.map((y, i) => [y, share(pick(all[i], office), pk, "publico")]) },
    ];
    L.later(() => C.line(c3, { x: "num", xTicks: YEARS, height: 220, y: { min: 0, max: 0.6, format: (v) => pct(v) }, ref: [{ y: 0.3, label: "30%" }], series: trend("mulheres", "publico_mulheres") }));
    L.later(() => C.line(c4, { x: "num", xTicks: YEARS, height: 220, y: { min: 0, max: 0.6, format: (v) => pct(v) }, series: trend("negros", "publico_negros") }));

    const tb = el("div");
    body.append(card("Every party", "Shares of the party's candidates and of its public money (FEFC and Party Fund). Gap: money share minus candidate share, in percentage points.", tb));
    table(tb, parties.map((a) => ({ partido: a.partido, candidatos: a.candidatos, w: a.mulheres / a.candidatos, wm: a.publico_mulheres / a.publico, wg: 100 * (a.publico_mulheres / a.publico - a.mulheres / a.candidatos),
      b: a.negros / a.candidatos, bm: a.publico_negros / a.publico, bg: 100 * (a.publico_negros / a.publico - a.negros / a.candidatos), publico: a.publico })), [
      { key: "partido", label: "Party", text: true }, { key: "candidatos", label: "Candidates" }, { key: "publico", label: "Public money", fmt: (v) => brl(v) },
      { key: "w", label: "Women, candidates", fmt: (v) => pct(v, 1) }, { key: "wm", label: "Women, money", fmt: (v) => pct(v, 1) }, { key: "wg", label: "Gap", fmt: (v) => fmt(v, 1) },
      { key: "b", label: "Black, candidates", fmt: (v) => pct(v, 1) }, { key: "bm", label: "Black, money", fmt: (v) => pct(v, 1) }, { key: "bg", label: "Gap", fmt: (v) => fmt(v, 1) },
    ], { sortBy: "publico", pageSize: 40, name: `women-black-${year}` });
  };
  draw();
}

// ------------------------------------------------------------ money and results

const ORD = ["", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"];

async function results(root) {
  const L = local();
  const [D, cand] = await Promise.all([site("decis.csv"), candidatos()]);
  num(D, ["decil", "candidatos", "eleitos", "min", "max", "mediana"]);
  const offices = OFFICES.filter((o) => D.some((r) => r.cargo === o));
  let office = params.get("ro") || "Deputado Federal";
  if (!offices.includes(office)) office = offices[0];
  const controls = el("div", { className: "controls" }), body = el("div");
  root.append(controls, body);
  const draw = () => {
    L.reset();
    controls.replaceChildren(select("Office", offices.map((o) => ({ value: o, label: OFFICE[o] })), office, (v) => { office = v; setParam("ro", v, "Deputado Federal"); draw(); }));
    body.replaceChildren();
    const rows = D.filter((r) => r.cargo === office).sort((a, b) => a.decil - b.decil);
    const c1 = chart();
    body.append(card("The more money, the more likely to win", `${OFFICE[office]} candidates split into ten equal groups by money raised, from the least funded tenth to the best funded. The bar is the share of each group that was elected.`, c1));
    L.later(() => C.bars(c1, {
      rows: rows.map((r) => ({ label: `${ORD[r.decil]} tenth`, value: r.eleitos / r.candidatos, title: `${ORD[r.decil]} tenth: ${brl(r.min)} to ${brl(r.max)} raised`, note: `${fmt(r.eleitos)} of ${fmt(r.candidatos)} elected · median ${brl(r.mediana)}` })),
      format: (v) => pct(v, 1), max: 1, labelWidth: 90, barHeight: 16,
      table: { rows, cols: [{ key: "decil", label: "Tenth" }, { key: "min", label: "From", fmt: (v) => brl(v) }, { key: "max", label: "To", fmt: (v) => brl(v) }, { key: "mediana", label: "Median raised", fmt: (v) => brl(v) }, { key: "candidatos", label: "Candidates" }, { key: "eleitos", label: "Elected" }], name: `deciles-${office}-${year}` },
    }));
    const top = rows.find((r) => r.decil === 10), low = rows.filter((r) => r.decil <= 5);
    const seats = sum(rows.map((r) => r.eleitos));
    if (top && seats) body.append(finding(`The best-funded tenth won ${pct(top.eleitos / top.candidatos)} of its races and took ${pct(top.eleitos / seats)} of the seats; the less-funded half of candidates took ${pct(sum(low.map((r) => r.eleitos)) / seats, 1)}.`));

    const sel = cand.filter((r) => r.cargo === office);
    if (sel.length) {
      const won = sel.filter(elected), lost = sel.filter((r) => !elected(r));
      tiles(body.appendChild(el("section", { className: "tiles" })), [
        { label: "Median raised, elected", value: brl(median(won.map((r) => r.total))), sub: plural(won.length, "candidate") },
        { label: "Median raised, not elected", value: brl(median(lost.map((r) => r.total))), sub: plural(lost.length, "candidate") },
        { label: "Elected: money from their party", value: pct(sum(won.map((r) => r.origem_partido)) / sum(won.map((r) => r.total))), sub: "share of what the winners raised" },
        { label: "Elected: own money", value: pct(sum(won.map((r) => r.origem_proprios)) / sum(won.map((r) => r.total)), 1), sub: brl(sum(won.map((r) => r.origem_proprios))) },
      ]);
    }
    const self = cand.filter((r) => r.origem_proprios > 0).sort((a, b) => b.origem_proprios - a.origem_proprios).slice(0, 20), c2 = chart();
    body.append(card("Who paid for their own campaign", "Candidates for president, governor, senator and federal deputy who put the most of their own money into their campaign, across every state.", c2));
    L.later(() => C.bars(c2, { rows: self.map((r) => ({ label: who(r), value: r.origem_proprios, color: elected(r) ? C.slot(1) : css("--other"), note: `${OFFICE[r.cargo]} · ${elected(r) ? "elected" : "not elected"} · ${pct(r.origem_proprios / r.total)} of what they raised` })),
      format: (v) => brl(v), labelWidth: 220, barHeight: 14, legend: [{ label: "Elected", color: C.slot(1) }, { label: "Not elected", color: css("--other") }] }));
  };
  draw();
  const tb = el("div");
  root.append(card("Find a candidate", "Every candidate for president, governor, senator and federal deputy, with what they raised and from where. Filter by name, party, state or office.", tb));
  table(tb, cand.map((r) => ({ ...r, office: OFFICE[r.cargo], inc: r.incumbente ? "yes" : "" })), [
    { key: "nome_urna", label: "Candidate", text: true, wrap: true }, { key: "office", label: "Office", text: true }, { key: "uf", label: "UF", text: true }, { key: "partido", label: "Party", text: true },
    { key: "resultado", label: "Result", text: true }, { key: "inc", label: "Incumbent", text: true }, { key: "total", label: "Raised", fmt: (v) => brl(v) }, { key: "publico", label: "Public", fmt: (v) => brl(v) },
    { key: "origem_pessoas_fisicas", label: "Individuals", fmt: (v) => brl(v) }, { key: "origem_proprios", label: "Own", fmt: (v) => brl(v) }, { key: "n_doadores_pf", label: "Donors" },
  ], { sortBy: "total", pageSize: 15, name: `candidates-${year}` });
}

// ------------------------------------------------------------ donors

/** Connected components of the network, largest first (union-find). */
function components(n, edges) {
  const up = Array.from({ length: n }, (_, i) => i);
  const find = (i) => { while (up[i] !== i) { up[i] = up[up[i]]; i = up[i]; } return i; };
  for (const [a, b] of edges) up[find(a)] = find(b);
  const size = new Map();
  for (let i = 0; i < n; i++) size.set(find(i), (size.get(find(i)) || 0) + 1);
  return [...size.values()].sort((a, b) => b - a);
}

async function donors(root) {
  const [gd, dd, rede, rec, R] = await Promise.all([raw("grandes_doadores.csv"), raw("doacoes_grandes_doadores.csv"), site("rede.json"), site("receptores.csv"), resumo()]);
  for (const r of gd) { r.total = +r.total; r.n_candidatos = +r.n_candidatos; }
  const indiv = sum(R.map((r) => r.origem_pessoas_fisicas)), given = sum(gd.map((r) => r.total));
  const top = [...gd].sort((a, b) => b.total - a.total)[0];
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Donors of R$50k or more", value: fmt(gd.length), sub: `private individuals, ${year}` },
    { label: "What they gave", value: brl(given), sub: `${pct(given / indiv)} of all money from individuals` },
    { label: "Candidates they funded", value: fmt(new Set(dd.map((r) => r.sq_candidato)).size), sub: `${fmt(dd.length)} donor–candidate pairs` },
    { label: "Largest donor", value: brl(top?.total), sub: top ? `${top.nome}, to ${plural(top.n_candidatos, "candidate")}` : "" },
  ]);
  const N = rede.nodes, E = rede.edges, nd = N.filter((n) => n.kind === "doador"), nc = N.filter((n) => n.kind === "candidato");
  const comp = components(N.length, E), maxV = Math.max(...nd.map((n) => n.valor), 1);
  const deg = N.map(() => 0);
  for (const [a, b] of E) { deg[a]++; deg[b]++; }
  const c1 = chart();
  root.append(card(`The ${nd.length} largest donors and the candidates they funded`, "Each orange dot is a donor (bigger for more money), each blue or grey dot a candidate they gave to; a line is a donation. Donors who back the same candidates are pulled together, so clusters are groups of donors behind one slate. Hover a dot to see its connections.", c1,
    finding(`${fmt(nd.length)} donors and ${fmt(nc.length)} candidates. The largest connected group holds ${pct(comp[0] / N.length)} of them: ${comp.length > 1 ? `the other ${fmt(N.length - comp[0])} sit in ${plural(comp.length - 1, "separate group")}` : "every donor is linked to every other through shared candidates"}.`)));
  later(() => C.network(c1, {
    height: Math.min(640, Math.max(380, (c1.clientWidth || 600) * 0.7)),
    nodes: N.map((n, i) => n.kind === "doador"
      ? { x: n.x, y: n.y, r: 3 + 7 * Math.sqrt(n.valor / maxV), color: C.slot(2), title: n.label, rows: [`Large donor · gave ${brl(n.valor)} in all`] }
      : { x: n.x, y: n.y, r: 2.5, color: n.eleito ? C.slot(1) : css("--other"), title: `${n.label} (${n.partido}-${n.uf})`, rows: [`${OFFICE[n.cargo] || n.cargo} · ${n.eleito ? "elected" : "not elected"}`, `${deg[i]} of these donors`] }),
    edges: E, legend: [{ label: "Donor", color: C.slot(2) }, { label: "Elected candidate", color: C.slot(1) }, { label: "Not elected", color: css("--other") }],
  }));

  // Donor pairs that back the same candidates.
  const backers = new Map();
  for (const [a, b] of E) { const [d, c] = N[a].kind === "doador" ? [a, b] : [b, a]; if (!backers.has(c)) backers.set(c, []); backers.get(c).push(d); }
  const pairs = new Map();
  for (const ds of backers.values()) for (let i = 0; i < ds.length; i++) for (let j = i + 1; j < ds.length; j++) {
    const k = ds[i] < ds[j] ? `${ds[i]}|${ds[j]}` : `${ds[j]}|${ds[i]}`; pairs.set(k, (pairs.get(k) || 0) + 1);
  }
  const pr = [...pairs].filter(([, n]) => n >= 2).map(([k, n]) => { const [a, b] = k.split("|").map(Number); return { a: N[a].label, b: N[b].label, n, ja: n / (deg[a] + deg[b] - n) }; });
  const t1 = el("div"), c2 = chart();
  root.append(card("Donors who back the same candidates", "Pairs among the largest donors who gave to two or more of the same candidates. Overlap: shared candidates over all the candidates either funded (Jaccard).", t1),
    card("Candidates with the most money from large donors", "Money from donors of R$50,000 or more, every office.", c2));
  table(t1, pr, [{ key: "a", label: "Donor", text: true, wrap: true }, { key: "b", label: "Donor", text: true, wrap: true }, { key: "n", label: "Shared candidates" }, { key: "ja", label: "Overlap", fmt: (v) => pct(v) }], { sortBy: "n", pageSize: 10, name: `donor-pairs-${year}` });
  num(rec, ["grandes_doadores", "valor"]);
  later(() => C.bars(c2, { rows: rec.slice(0, 20).map((r) => ({ label: who(r), value: r.valor, color: elected(r) ? C.slot(1) : css("--other"), note: `${OFFICE[r.cargo] || r.cargo} · ${plural(r.grandes_doadores, "large donor")}` })),
    format: (v) => brl(v), labelWidth: 200, barHeight: 14, legend: [{ label: "Elected", color: C.slot(1) }, { label: "Not elected", color: css("--other") }] }));
  const t2 = el("div");
  root.append(card("Every donor of R$50,000 or more", "Private individuals, with their CPF masked the way the federal comptroller (CGU) does. Smaller donors appear only as a count in each candidate's totals.", t2));
  table(t2, gd, [{ key: "nome", label: "Donor", text: true, wrap: true }, { key: "doador", label: "CPF (masked)", text: true }, { key: "total", label: "Gave", fmt: (v) => brl(v) }, { key: "n_candidatos", label: "Candidates" }], { sortBy: "total", pageSize: 15, name: `large-donors-${year}` });
}

// ------------------------------------------------------------ suppliers

async function suppliers(root) {
  const [F, R] = await Promise.all([site("fornecedores.csv"), resumo()]);
  for (const r of F) { r.total = +r.total; r.n_candidatos = +r.n_candidatos; }
  const spent = sum(R.map((r) => r.contratado)), top10 = sum(F.slice(0, 10).map((r) => r.total)), listed = sum(F.map((r) => r.total));
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Contracted by campaigns", value: brl(spent), sub: `every office, ${year}` },
    { label: `The ${fmt(F.length)} companies paid the most`, value: pct(listed / spent), sub: brl(listed) },
    { label: "The top 10 alone", value: pct(top10 / spent), sub: brl(top10) },
    { label: "Largest supplier", value: brl(F[0]?.total), sub: F[0] ? `${F[0].nome}, for ${plural(F[0].n_candidatos, "campaign")}` : "" },
  ]);
  const g = el("div", { className: "grid2" }), c1 = chart(), c2 = chart();
  g.append(card("The companies campaigns paid the most", "Expenses candidates contracted with each company (CNPJ), every office.", c1),
    card("What the money bought", `The ${fmt(F.length)} largest suppliers grouped by their registered activity (CNAE).`, c2));
  root.append(g);
  later(() => C.bars(c1, { rows: F.slice(0, 20).map((r) => ({ label: r.nome, value: r.total, note: `${plural(r.n_candidatos, "campaign")} · ${r.cnae}` })), format: (v) => brl(v), labelWidth: 200, barHeight: 14 }));
  const act = new Map();
  for (const r of F) act.set(r.cnae || "Not given", (act.get(r.cnae || "Not given") || 0) + r.total);
  later(() => C.bars(c2, { rows: [...act].map(([label, value]) => ({ label, value, note: pct(value / listed) + " of these suppliers" })).sort((a, b) => b.value - a.value).slice(0, 12), format: (v) => brl(v), labelWidth: 220, barHeight: 14 }));
  const t = el("div");
  root.append(card("Every listed supplier", "Companies only: people paid by campaigns (canvassers, drivers) are not listed.", t));
  table(t, F, [{ key: "nome", label: "Company", text: true, wrap: true }, { key: "cnpj", label: "CNPJ", text: true }, { key: "cnae", label: "Activity", text: true, wrap: true }, { key: "total", label: "Contracted", fmt: (v) => brl(v) }, { key: "n_candidatos", label: "Campaigns" }],
    { sortBy: "total", pageSize: 15, name: `suppliers-${year}` });
}

// ------------------------------------------------------------ page

const SECTIONS = { overview, parties, equity, results, donors, suppliers };
const shown = new Set();
function render(name) {
  const inner = el("div");   // a fresh holder: a render still loading for a previous election writes into a detached node
  $(`#tab-${name}`).replaceChildren(inner);
  return guard(inner, () => SECTIONS[name](inner));
}
function electionControl() {
  const latest = YEARS[YEARS.length - 1];
  $("#election").replaceChildren(
    select("Election", [...YEARS].reverse().map((y) => ({ value: y, label: `${y} general election` })), year, (v) => {
      year = +v; setParam("e", v, String(latest)); redraws.length = 0; electionControl(); shown.forEach(render);
    }),
    year >= new Date().getFullYear() ? el("p", { className: "note", textContent: `${year} accounts are still being filed and judged: these numbers will change.` }) : "");
}

(async () => {
  YEARS = (await data("site/tse/anos.csv")).map((r) => +r.ano).sort((a, b) => a - b);
  year = YEARS.includes(+params.get("e")) ? +params.get("e") : YEARS[YEARS.length - 1];
  electionControl();
  tabs((name) => { shown.add(name); render(name); });
  onResize(() => redraws.forEach((f) => f()));
})();
