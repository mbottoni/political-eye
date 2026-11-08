// Party orientations: who follows their party, the Government and their party's majority.
import { $, css, data, el, fmt, guard, onResize, params, pct, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { GOVERNMENTS } from "../lib/chamber.js";

const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const select = (label, options, value, onChange) => {
  const s = el("select", {}, ...options.map((o) => el("option", { value: o.value ?? o, textContent: o.label ?? o, selected: String(o.value ?? o) === String(value) })));
  s.addEventListener("change", () => onChange(s.value));
  return el("label", {}, label, s);
};
const num = (v) => (v === "" || v == null ? null : +v);
const GAP = [{ from: "2025-02", to: "2025-10", label: "one bloc gave no orientation" }];
const LEGS = [{ value: 57, label: "57th (2023–2027)" }, { value: 56, label: "56th (2019–2023)" }, { value: 55, label: "55th (2015–2019)" }];
const redraws = [];
// The same keys as politicaleye.camara.orientations.party_key: labels cut short or renamed map to one name.
const ALIASES = { SOLIDARIED: "SOLIDARIEDADE", SOLIDARI: "SOLIDARIEDADE", SD: "SOLIDARIEDADE", SDD: "SOLIDARIEDADE", REPUBLICAN: "REPUBLICANOS",
  REPUBLIC: "REPUBLICANOS", PODEMOS: "PODE", PATRI: "PATRIOTA", "PP**": "PP", PMDB: "MDB", PR: "PL", PPS: "CIDADANIA", PTN: "PODE",
  PEN: "PATRIOTA", PTDOB: "AVANTE", PSDC: "DC", PRB: "REPUBLICANOS" };
const partyKey = (label) => { const k = String(label || "").trim().toUpperCase(); return ALIASES[k] || k; };
const later = (f) => { redraws.push(f); f(); };

async function partidos() {
  const p = await data("site/orientacoes/partidos.csv");
  const months = [...new Set(p.map((r) => r.month))].sort();
  const votes = new Map();
  for (const r of p) votes.set(r.partido, (votes.get(r.partido) || 0) + +r.n_votes);
  const big = [...votes.keys()].sort((a, b) => votes.get(b) - votes.get(a));
  const at = new Map(p.map((r) => [`${r.partido}|${r.month}`, r]));
  return { p, months, big, get: (party, m, k) => num(at.get(`${party}|${m}`)?.[k]) };
}

// ------------------------------------------------------------ government

async function gov(root) {
  const idx = (await data("camara/index.csv")).filter((r) => r.with_gov !== "");
  const last = idx[idx.length - 1];
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Votes with the government", value: pct(+last.with_gov), sub: `${last.month}, every deputy pooled` },
    { label: "Votes with their party", value: pct(num(last.with_party)), sub: last.with_party === "" ? "too few roll calls with a party line" : `${pct(+last.oriented_share)} of votes had a party line` },
    { label: "Votes with their party's majority", value: pct(+last.with_majority), sub: "needs no orientation" },
    { label: "Votes matched to an orientation", value: pct(+last.orientation_coverage), sub: "the rest: party in a cut-off bloc name" },
  ]);
  const c1 = chart();
  root.append(card("The chamber as a whole", "Pooled over every deputy's contested votes each month. The shaded months are February to October 2025, when almost every party sat in one bloc that gave no orientation, so 'with party' is left out.", c1));
  const s = (k, name, color) => ({ name, color, points: idx.map((r) => [r.month, num(r[k])]) });
  later(() => C.line(c1, {
    x: "month", y: { min: 0, max: 1, format: (v) => pct(v) }, marks: GOVERNMENTS, bands: GAP, height: 260,
    series: [s("with_gov", "With the government", C.slot(1)), s("with_party", "With their party", C.slot(2)), s("with_majority", "With their party's majority", C.slot(3))],
    table: { rows: idx, cols: [{ key: "month", label: "Month", text: true }, { key: "with_gov", label: "With government", fmt: (v) => pct(v) }, { key: "with_party", label: "With party", fmt: (v) => pct(v) }, { key: "with_majority", label: "With majority", fmt: (v) => pct(v) }, { key: "orientation_coverage", label: "Coverage", fmt: (v) => pct(v) }], name: "camara-discipline" },
  }));
  const P = await partidos();
  const parties = P.big.slice(0, 18);
  const recent = (party) => { const xs = P.months.slice(-12).map((m) => P.get(party, m, "with_gov")).filter((v) => v != null); return xs.length ? xs.reduce((a, b) => a + b) / xs.length : -1; };
  parties.sort((a, b) => recent(b) - recent(a));
  const hm = chart();
  root.append(card("Votes with the government, by party and month", "Share of each party's votes that followed the Government leader. Rows ordered by the last 12 months, the most loyal on top; the 18 parties with the most votes since 2015. Dark: rarely with the government.", hm));
  later(() => {
    C.heatmap(hm, {
      rows: parties, cols: P.months, value: (i, j) => P.get(parties[i], P.months[j], "with_gov"), color: C.seq, minCell: 3, cell: 12, rowHeight: 18, colLabelHeight: 46, labelWidth: 110,
      tip: (i, j, v) => [el("strong", { textContent: `${parties[i]}, ${P.months[j]}` }), el("div", { className: "row", textContent: `${pct(v)} with the government · ${fmt(P.get(parties[i], P.months[j], "deputados"))} deputies` })],
      table: { rows: P.p.filter((r) => parties.includes(r.partido)), cols: [{ key: "month", label: "Month", text: true }, { key: "partido", label: "Party", text: true }, { key: "deputados", label: "Deputies" }, { key: "with_gov", label: "With government", fmt: (v) => pct(v) }], name: "party-government" },
    });
    C.colorKey(hm, { color: C.seq, from: "0%", to: "100%", label: "with the government" });
  });
}

// ------------------------------------------------------------ cohesion

async function cohesion(root) {
  const P = await partidos();
  let metric = params.get("m") || "rice", A = params.get("a") || "PT", B = params.get("b") || "PL";
  const controls = el("div", { className: "controls" }), c1 = chart(), tb = el("div");
  root.append(controls, card("Cohesion over time", "The two parties picked, against the ten next-largest in grey. Rice index: 1 when every deputy of the party votes the same way. With majority: how often a deputy votes with the rest of their party. With party: how often they follow their leader's orientation (missing in the 2025 gap).", c1),
    card("Average cohesion by legislature", "Means of the monthly values, for parties with at least 5 deputies on average.", tb));
  const label = { rice: "Rice index", with_majority: "With party majority", with_party: "With party orientation" };
  const draw = () => {
    controls.replaceChildren(
      select("Measure", Object.entries(label).map(([value, l]) => ({ value, label: l })), metric, (v) => { metric = v; setParam("m", v, "rice"); draw(); }),
      select("Party", P.big, A, (v) => { A = v; setParam("a", v, "PT"); draw(); }),
      select("and party", P.big, B, (v) => { B = v; setParam("b", v, "PL"); draw(); }));
    const ser = (party, color, extra = {}) => ({ name: party, color, points: P.months.map((m) => [m, P.get(party, m, metric)]), ...extra });
    C.line(c1, {
      x: "month", y: { min: metric === "rice" ? 0 : 0.4, max: 1, format: (v) => fmt(v, 2) }, marks: GOVERNMENTS, bands: metric === "with_party" ? GAP : [], height: 280,
      series: [...P.big.slice(0, 12).filter((p) => p !== A && p !== B).map((p) => ser(p, css("--other"), { width: 1, hideLegend: true })), ser(A, css("--a")), ser(B, css("--b"))],
    });
    const rows = [];
    for (const leg of [55, 56, 57]) {
      const ms = P.months.filter((m) => C.monthIndex(m) >= C.monthIndex(`${1795 + 4 * leg}-02`) && C.monthIndex(m) < C.monthIndex(`${1799 + 4 * leg}-02`));
      for (const party of P.big) {
        const vals = (k) => ms.map((m) => P.get(party, m, k)).filter((v) => v != null);
        const mean = (k) => { const v = vals(k); return v.length ? v.reduce((a, b) => a + b) / v.length : null; };
        const dep = mean("deputados");
        if (dep == null || dep < 5) continue;
        rows.push({ leg, partido: party, deputados: dep, rice: mean("rice"), with_majority: mean("with_majority"), with_party: mean("with_party"), with_gov: mean("with_gov") });
      }
    }
    table(tb, rows, [
      { key: "leg", label: "Legislature" }, { key: "partido", label: "Party", text: true }, { key: "deputados", label: "Deputies", fmt: (v) => fmt(v) },
      { key: "rice", label: "Rice index", fmt: (v) => fmt(v, 3) }, { key: "with_majority", label: "With majority", fmt: (v) => pct(v) },
      { key: "with_party", label: "With party", fmt: (v) => pct(v) }, { key: "with_gov", label: "With government", fmt: (v) => pct(v) },
    ], { sortBy: "rice", pageSize: 12, name: "party-cohesion" });
  };
  later(draw);
}

// ------------------------------------------------------------ rebels

async function rebels(root) {
  let leg = +(params.get("leg") || 57), min = 100;
  const controls = el("div", { className: "controls" }), h = chart(), tb = el("div");
  root.append(controls, card("How often deputies vote with the rest of their party", "One bar per range; dashed: the median deputy. Deputies with at least 100 contested votes in the legislature.", h),
    card("Every deputy", "Sorted from the least to the most loyal to their party's majority. A deputy who changed parties is counted against the party of each vote; the party shown is their latest.", tb));
  const draw = async () => {
    controls.replaceChildren(select("Legislature", LEGS, leg, (v) => { leg = +v; setParam("leg", v, "57"); draw(); }),
      select("At least", [50, 100, 300, 600].map((v) => ({ value: v, label: `${v} votes` })), min, (v) => { min = +v; draw(); }));
    const rows = (await data(`site/orientacoes/deputados/${leg}.csv`)).filter((r) => +r.n_votes >= min && r.with_majority !== "");
    const vals = rows.map((r) => +r.with_majority).sort((a, b) => a - b);
    const med = vals[Math.floor(vals.length / 2)];
    C.histogram(h, { values: vals, domain: [0.4, 1], bins: 30, refs: [{ x: med, label: `median ${pct(med)}` }], format: (v) => pct(v), xLabel: "share of votes with their party's majority", unit: "deputies" });
    table(tb, rows, [
      { key: "nome", label: "Deputy", text: true }, { key: "partido", label: "Party", text: true }, { key: "uf", label: "UF", text: true },
      { key: "meses", label: "Months" }, { key: "n_votes", label: "Votes" }, { key: "with_majority", label: "With majority", fmt: (v) => pct(v, 1) },
      { key: "with_party", label: "With party", fmt: (v) => pct(v, 1) }, { key: "with_gov", label: "With government", fmt: (v) => pct(v, 1) },
    ], { sortBy: "with_majority", desc: false, pageSize: 15, name: `deputies-${leg}` });
  };
  await draw();
  redraws.push(draw);
}

// ------------------------------------------------------------ orientations given

async function orient(root) {
  const k = await data("site/orientacoes/orientacoes.csv"), agree = await data("site/orientacoes/concordancia.csv");
  let leg = +(params.get("leg") || 57);
  const controls = el("div", { className: "controls" }), c1 = chart(), c2 = chart();
  root.append(controls, card("What each bench orients", "Every bench that orients: parties, federations (Fdr), blocs (Bl, names as published, cut off by the Câmara) and the Government, Majority, Minority and Opposition leaders. Share of the contested roll calls on which it gave each orientation; 'None' means it was listed but gave none, which starts in 2021. Benches with at least 50 orientations in the legislature.", c1),
    card("How often two benches agree", "Of the roll calls where both oriented Sim or Não (obstruction as Não), the share where they gave the same orientation. Ordered by agreement with the Government's leader.", c2));
  const KINDS = [["sim", "Sim"], ["nao", "Não"], ["obstrucao", "Obstrução"], ["liberado", "Liberado (free)"], ["none", "None given"]];
  const draw = () => {
    controls.replaceChildren(select("Legislature", LEGS, leg, (v) => { leg = +v; setParam("leg", v, "57"); draw(); }));
    const rows = k.filter((r) => +r.legislatura === leg && +r.total >= 50).sort((a, b) => +b.total - +a.total).slice(0, 24);
    C.stack(c1, {
      x: rows.map((r) => r.partido), height: 260, format: (v) => pct(v), rotate: true,
      series: KINDS.map(([key, name], i) => ({ name, color: key === "none" ? css("--other") : C.slot(i + 1), values: rows.map((r) => +r[key] / +r.total) })),
      table: { rows, cols: [{ key: "partido", label: "Party", text: true }, { key: "total", label: "Roll calls" }, ...KINDS.map(([key, name]) => ({ key, label: name }))], name: `orientations-${leg}` },
    });
    const keep = new Set(rows.map((r) => r.partido));
    const pairs = agree.filter((r) => +r.legislatura === leg && keep.has(r.a) && keep.has(r.b));
    const parties = [...new Set(pairs.flatMap((r) => [r.a, r.b]))];
    const val = new Map();
    for (const r of pairs) { val.set(`${r.a}|${r.b}`, [+r.agree / +r.n, +r.n]); val.set(`${r.b}|${r.a}`, [+r.agree / +r.n, +r.n]); }
    const anchor = "Governo";
    const toAnchor = (p) => (p === anchor ? 2 : val.get(`${p}|${anchor}`)?.[0] ?? -1);
    parties.sort((a, b) => toAnchor(b) - toAnchor(a));
    C.heatmap(c2, {
      rows: parties, cols: parties, value: (i, j) => (i === j ? null : val.get(`${parties[i]}|${parties[j]}`)?.[0] ?? null), color: C.seq,
      cell: 30, rowHeight: 22, labelWidth: 150, colLabelHeight: 130, allColLabels: true, cellText: (v) => Math.round(v * 100), dark: (v) => v > 0.55,
      tip: (i, j, v) => [el("strong", { textContent: `${parties[i]} and ${parties[j]}` }), el("div", { className: "row", textContent: `agreed on ${pct(v)} of ${fmt(val.get(`${parties[i]}|${parties[j]}`)[1])} roll calls` })],
      table: { rows: pairs.map((r) => ({ ...r, share: +r.agree / +r.n })), cols: [{ key: "a", label: "Party", text: true }, { key: "b", label: "Party", text: true }, { key: "n", label: "Both oriented" }, { key: "share", label: "Agreed", fmt: (v) => pct(v) }], name: `agreement-${leg}` },
    });
  };
  later(draw);
}

// ------------------------------------------------------------ one deputy

async function deputy(root) {
  const people = new Map();
  for (const leg of [57, 56, 55]) for (const r of await data(`site/orientacoes/deputados/${leg}.csv`)) if (!people.has(r.deputado_id)) people.set(r.deputado_id, r);
  const list = el("datalist", { id: "deplist" }, ...[...people.values()].map((r) => el("option", { value: `${r.nome} (${r.partido}-${r.uf})` })));
  const input = el("input", { type: "search", placeholder: "Name…", list: "deplist", autocomplete: "off" });
  const out = el("div");
  root.append(el("div", { className: "controls" }, el("label", {}, "Find a deputy", input), list), out);
  const P = await partidos();
  const show = async (id) => {
    const who = people.get(id);
    if (!who) return;
    setParam("dep", id);
    const years = [...new Set(P.months.map((m) => m.slice(0, 4)))];
    const rows = (await Promise.all(years.map((y) => data(`site/orientacoes/deputados_mes/${y}.csv`)))).flat().filter((r) => r.deputado_id === id);
    const c = chart();
    out.replaceChildren(card(`${who.nome} (${who.partido}-${who.uf})`, `Month by month, over their contested votes; their party's pooled government support in grey for comparison. ${rows.length} months with votes.`, c));
    const draw = () => C.line(c, {
      x: "month", y: { min: 0, max: 1, format: (v) => pct(v) }, marks: GOVERNMENTS, bands: GAP, height: 280,
      series: [
        { name: "Their party with the government", color: css("--other"), width: 1.5, points: rows.map((r) => [r.month, P.get(partyKey(r.partido), r.month, "with_gov")]) },
        { name: "With the government", color: C.slot(1), points: rows.map((r) => [r.month, num(r.with_gov)]) },
        { name: "With their party", color: C.slot(2), points: rows.map((r) => [r.month, num(r.with_party)]) },
        { name: "With their party's majority", color: C.slot(3), points: rows.map((r) => [r.month, num(r.with_majority)]) },
      ],
      table: { rows, cols: [{ key: "month", label: "Month", text: true }, { key: "partido", label: "Party", text: true }, { key: "n_votes", label: "Votes" }, { key: "with_party", label: "With party", fmt: (v) => pct(v) }, { key: "with_gov", label: "With government", fmt: (v) => pct(v) }, { key: "with_majority", label: "With majority", fmt: (v) => pct(v) }], name: `deputy-${id}` },
    });
    draw();
    redraws.push(draw);
  };
  input.addEventListener("change", () => {
    const q = input.value.trim().toLowerCase();
    const hit = [...people.values()].find((r) => `${r.nome} (${r.partido}-${r.uf})`.toLowerCase() === q || r.nome.toLowerCase() === q);
    if (hit) show(hit.deputado_id);
  });
  const current = await data("site/orientacoes/deputados/57.csv");
  const start = params.get("dep") && people.has(params.get("dep")) ? params.get("dep") : [...current].sort((a, b) => +b.n_votes - +a.n_votes)[0].deputado_id;
  await show(start);
}

// ------------------------------------------------------------ blocs

async function blocs(root) {
  const b = await data("camara/blocos/blocos.csv"), m = await data("camara/blocos/members.csv");
  const members = new Map();
  for (const r of m) { if (!members.has(r.bloco_id)) members.set(r.bloco_id, []); members.get(r.bloco_id).push(r); }
  const rows = b.map((r) => ({ ...r, kind: r.federacao === "1" ? "Federation" : "Bloc", partidos: (members.get(r.bloco_id) || []).filter((x) => x.listed_until === "").map((x) => x.partido).sort().join(", ") }));
  const tb = el("div");
  root.append(el("p", { className: "about", textContent: "The Câmara's blocs API lists today's blocs with their members but keeps no dates and forgets dissolved blocs. political-eye records it every day from 7 November 2026, so this table grows a history: when a bloc or a member appears or leaves, the day is recorded. That record also fills in the parties hidden behind bloc names the vote files cut off (Bl UniPpPsd...)." }),
    card("Blocs and federations the API lists", "Members as last recorded; 'Listed from' is the first daily record that listed the bloc (7 November 2026 means on or before).", tb));
  table(tb, rows, [
    { key: "bloco_id", label: "Id" }, { key: "legislatura", label: "Legislature" }, { key: "kind", label: "Kind", text: true },
    { key: "nome", label: "Name", text: true, wrap: true }, { key: "partidos", label: "Members", text: true, wrap: true },
    { key: "listed_from", label: "Listed from", text: true }, { key: "listed_until", label: "Until", text: true },
  ], { sortBy: "legislatura", pageSize: 30, name: "camara-blocs" });
}

// ------------------------------------------------------------ boot

const SECTIONS = { gov, cohesion, rebels, orient, deputy, blocs };
tabs((name) => { const box = $(`#tab-${name}`); guard(box, () => SECTIONS[name](box)); });
onResize(() => redraws.forEach((f) => f()));
