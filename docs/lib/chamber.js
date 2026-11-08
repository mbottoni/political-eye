// Analysis tabs shared by the Câmara and Senado explorers: network analysis,
// ideal points and (Senado) party discipline. Data: data/site/<chamber>/.
import { $, css, data, el, fmt, pct, table, tiles, params, setParam, onResize } from "./ui.js";
import * as C from "./charts.js";

export const GOVERNMENTS = [
  { x: "2016-05", label: "Temer" }, { x: "2019-01", label: "Bolsonaro" }, { x: "2023-01", label: "Lula" },
];
const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const box = () => el("div", { className: "chart" });
const select = (label, options, value, onChange) => {
  const s = el("select", {}, ...options.map((o) => el("option", { value: o.value ?? o, textContent: o.label ?? o, selected: (o.value ?? o) === value })));
  s.addEventListener("change", () => onChange(s.value));
  return el("label", {}, label, s);
};
const num = (r, k) => (r[k] === "" || r[k] == null ? null : +r[k]);

// ------------------------------------------------------------ network analysis

export async function networkTab(root, o) {
  const net = (await data(`site/${o.chamber}/networks.csv`)).filter((r) => +r.nodes > 0);
  const months = net.map((r) => r.month), last = net[net.length - 1];
  const unit = o.chamber === "senado" ? "the 12 months to" : "";
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: "Party modularity", value: fmt(+last.modularity_party, 3), sub: `${unit} ${last.month}: how much co-voting splits along parties (0 = not at all)` },
    { label: "Ties that cross parties", value: pct(+last.cross_party_share), sub: `of ${fmt(+last.edges)} vote-together ties` },
    { label: "Communities found", value: fmt(+last.communities), sub: `match parties: NMI ${fmt(+last.nmi_party, 2)}` },
    { label: "Votes vs signatures", value: last.qap_r ? fmt(+last.qap_r, 3) : "–", sub: last.qap_p ? `QAP correlation, p = ${fmt(+last.qap_p, 3)}` : "" },
  ]);
  const series = (key, name, color) => ({ name, color, points: net.map((r) => [r.month, num(r, key)]) });
  const c1 = box();
  root.append(card("Party lines over time",
    `Per ${o.chamber === "senado" ? "12-month window" : "month"}. Modularity measures how much more the vote-together ties fall inside parties than chance would put them; the share of ties that cross parties and the density are read directly from the graph. Dashed lines mark changes of government.`, c1));
  const draw1 = () => C.line(c1, {
    x: "month", y: { min: 0, max: 1, format: (v) => fmt(v, 1) }, marks: GOVERNMENTS, height: 260,
    series: [series("cross_party_share", "Ties that cross parties", C.slot(1)), series("density", "Density", C.slot(2)), series("modularity_party", "Party modularity", C.slot(3))],
    table: { rows: net, cols: [{ key: "month", label: "Month", text: true }, { key: "cross_party_share", label: "Cross-party share" }, { key: "density", label: "Density" }, { key: "modularity_party", label: "Party modularity" }], name: `${o.chamber}-party-lines` },
  });
  const c2 = box();
  root.append(card("Do the communities in the votes follow parties?",
    "Louvain finds groups of members who vote together without being told their parties. NMI and ARI measure how close those groups are to the parties: 1 is identical, 0 is unrelated.", c2));
  const draw2 = () => C.line(c2, {
    x: "month", y: { min: 0, max: 1, format: (v) => fmt(v, 1) }, marks: GOVERNMENTS,
    series: [series("nmi_party", "NMI", C.slot(1)), series("ari_party", "ARI", C.slot(2))],
    table: { rows: net, cols: [{ key: "month", label: "Month", text: true }, { key: "communities", label: "Communities" }, { key: "modularity_louvain", label: "Modularity" }, { key: "nmi_party", label: "NMI" }, { key: "ari_party", label: "ARI" }], name: `${o.chamber}-communities` },
  });
  const c3 = box();
  root.append(card("Voting together and signing together",
    "The QAP correlation between the two graphs on their common members: does voting together go with co-signing bills? Points where the permutation test gives p < 0.05 are in the table; overlap is the Jaccard index of their ties.", c3));
  const draw3 = () => C.line(c3, {
    x: "month", y: { format: (v) => fmt(v, 2) }, marks: GOVERNMENTS,
    series: [series("qap_r", "QAP correlation", C.slot(1)), series("overlap_jaccard", "Overlap (Jaccard)", C.slot(2))],
    table: { rows: net, cols: [{ key: "month", label: "Month", text: true }, { key: "qap_r", label: "QAP r" }, { key: "qap_p", label: "p-value" }, { key: "overlap_jaccard", label: "Jaccard" }], name: `${o.chamber}-qap` },
  });

  // One month in detail.
  const detail = el("div");
  let month = months.includes(params.get("nm")) ? params.get("nm") : months[months.length - 1];
  const controls = el("div", { className: "controls" }, select(o.chamber === "senado" ? "Window up to" : "Month", [...months].reverse(), month, (m) => { month = m; setParam("nm", m); renderMonth(); }));
  root.append(el("h2", { textContent: "One month in detail", style: "font-size:15px;margin:18px 0 0" }), controls, detail);
  const renderMonth = async () => {
    const rows = (await data(`site/${o.chamber}/members/${month.slice(0, 4)}.csv`)).filter((r) => r.month === month);
    detail.replaceChildren();
    const comm = [...new Set(rows.map((r) => +r.community))].sort((a, b) => a - b);
    const parties = [...new Set(rows.map((r) => r.partido))].filter(Boolean);
    const size = (p) => rows.filter((r) => r.partido === p).length;
    parties.sort((a, b) => size(b) - size(a));
    const count = (p, c) => rows.filter((r) => r.partido === p && +r.community === c).length;
    const hm = box(), grid = el("div", { className: "grid2" });
    grid.append(card(`Parties across communities, ${month}`, "Members of each party (rows) in each community the votes reveal (columns), as a share of the party.", hm));
    C.heatmap(hm, {
      rows: parties.map((p) => `${p} (${size(p)})`), cols: comm.map((c) => `Group ${c} (${rows.filter((r) => +r.community === c).length})`),
      value: (i, j) => count(parties[i], comm[j]) / size(parties[i]), color: (v) => C.seq(v), cellText: (v) => Math.round(v * 100), dark: (v) => v > 0.55,
      allColLabels: true, colLabelHeight: 92, labelWidth: 120, cell: 44, rowHeight: 20,
      tip: (i, j, v) => [el("strong", { textContent: `${parties[i]} in group ${comm[j]}` }), el("div", { className: "row", textContent: `${count(parties[i], comm[j])} of ${size(parties[i])} members (${pct(v)})` })],
    });
    const central = box();
    grid.append(card("Most central members", "Eigenvector centrality in the vote-together graph: tied to many members who are themselves well tied.", central));
    const top = [...rows].sort((a, b) => +b.eigen - +a.eigen).slice(0, 15);
    C.bars(central, { rows: top.map((r) => ({ label: `${r.nome} (${r.partido})`, value: +r.eigen, color: r.partido === o.partyA ? css("--a") : r.partido === o.partyB ? css("--b") : css("--line") })), format: (v) => fmt(v, 2), max: 1 });
    detail.append(grid);
    const bridges = el("div");
    detail.append(card("Bridges", `Members whose vote-together ties cross party lines more than their party's size alone would make them (at least 10 ties). In a small party almost every tie crosses party lines, so a member is ranked by the excess over that expectation: the share of the other members who belong to other parties. ${o.chamber === "senado" ? "Senators" : "Deputies"} with no party are left out.`, bridges));
    const N = rows.length;
    const br = rows.filter((r) => +r.degree >= 10 && r.partido).map((r) => {
      const share = +r.cross_degree / +r.degree, expected = N > 1 ? 1 - (size(r.partido) - 1) / (N - 1) : 0;
      return { ...r, share, expected, excess: share - expected };
    });
    table(bridges, br, [
      { key: "nome", label: "Name", text: true }, { key: "partido", label: "Party", text: true }, { key: "uf", label: "UF", text: true },
      { key: "degree", label: "Ties" }, { key: "cross_degree", label: "Across parties" }, { key: "share", label: "Share", fmt: (v) => pct(v) },
      { key: "expected", label: "Expected", fmt: (v) => pct(v) }, { key: "excess", label: "Excess", fmt: (v) => `${v >= 0 ? "+" : ""}${Math.round(v * 100)} pts` },
      { key: "eigen", label: "Centrality", fmt: (v) => fmt(+v, 2) }, { key: "community", label: "Group" },
    ], { sortBy: "excess", pageSize: 12, name: `${o.chamber}-bridges-${month}` });
  };
  const all = () => { draw1(); draw2(); draw3(); renderMonth(); };
  all();
  onResize(() => { if (!root.hidden && root.offsetParent) all(); });
}

// ------------------------------------------------------------ ideal points

export async function idealTab(root, o) {
  const ideal = await data(`site/${o.chamber}/ideal.csv`);
  const months = [...new Set(ideal.map((r) => r.month))].sort();
  const count = new Map();
  for (const r of ideal) count.set(r.partido, (count.get(r.partido) || 0) + +r.n);
  const parties = [...count.keys()].sort((a, b) => count.get(b) - count.get(a));
  let A = params.get("ia") || o.partyA, B = params.get("ib") || o.partyB;
  const controls = el("div", { className: "controls" });
  const c1 = box(), c2 = box(), c3 = box();
  root.append(el("p", { className: "about", textContent: `Each ${o.chamber === "senado" ? "senator" : "deputy"}'s "ideal point" is their position on the first principal component of their contested votes ${o.chamber === "senado" ? "in the 12-month window" : "that month"} (the horizontal axis of the explorer's map), standardised so that one unit is one standard deviation, with PT's mean on the negative side. Positions compare within a ${o.chamber === "senado" ? "window" : "month"}; their scale is not fixed across time.` }));
  root.append(controls,
    card("Where parties sit", "Median position of each party per month; the shaded band is the middle half of its members (25th to 75th percentile) for the two parties picked. Other parties in grey.", c1),
    card("Distance between the two parties", "Median of the second party minus median of the first, in standard deviations of the chamber.", c2));
  const strip = el("div");
  root.append(strip);
  const draw = () => {
    controls.replaceChildren(
      select("Party", parties, A, (v) => { A = v; setParam("ia", v, o.partyA); draw(); }),
      select("and party", parties, B, (v) => { B = v; setParam("ib", v, o.partyB); draw(); }));
    const by = (p, k) => months.map((m) => { const r = ideal.find((x) => x.month === m && x.partido === p); return [m, r ? +r[k] : null]; });
    const band = (p) => months.map((m) => { const r = ideal.find((x) => x.month === m && x.partido === p); return r ? [m, +r.q25, +r.q75] : [m, null, null]; });
    const others = parties.slice(0, 14).filter((p) => p !== A && p !== B).map((p) => ({ name: p, color: css("--other"), points: by(p, "median"), width: 1, hideLegend: true, opacity: 0.8 }));
    C.line(c1, {
      x: "month", height: 300, marks: GOVERNMENTS, y: { format: (v) => fmt(v, 1) },
      series: [...others, { name: A, color: css("--a"), points: by(A, "median"), band: band(A) }, { name: B, color: css("--b"), points: by(B, "median"), band: band(B) }],
      table: { rows: ideal.filter((r) => r.partido === A || r.partido === B), cols: [{ key: "month", label: "Month", text: true }, { key: "partido", label: "Party", text: true }, { key: "n", label: "Members" }, { key: "q25", label: "25th" }, { key: "median", label: "Median" }, { key: "q75", label: "75th" }], name: `${o.chamber}-ideal` },
    });
    const a = by(A, "median"), b = by(B, "median");
    C.line(c2, { x: "month", marks: GOVERNMENTS, y: { format: (v) => fmt(v, 1) }, series: [{ name: `${B} − ${A}`, color: css("--line"), points: a.map((p, i) => [p[0], p[1] != null && b[i][1] != null ? b[i][1] - p[1] : null]) }] });
    renderStrip();
  };
  let month = months[months.length - 1];
  const renderStrip = async () => {
    const rows = (await data(`site/${o.chamber}/members/${month.slice(0, 4)}.csv`)).filter((r) => r.month === month && r.pc1 !== "");
    const groups = new Map();
    for (const r of rows) { if (!groups.has(r.partido)) groups.set(r.partido, []); groups.get(r.partido).push(r); }
    const med = (xs) => { const s = xs.map((r) => +r.pc1).sort((p, q) => p - q); return s[Math.floor(s.length / 2)]; };
    const keep = [...groups].filter(([p, xs]) => p && xs.length >= 3).sort((x, y) => med(x[1]) - med(y[1]));
    strip.replaceChildren();
    const c = box();
    const sel = el("div", { className: "controls" }, select(o.chamber === "senado" ? "Window up to" : "Month", [...months].reverse(), month, (m) => { month = m; renderStrip(); }));
    strip.append(card(`Every member, ${month}`, "Each dot is a member, by party (parties with at least 3 members), ordered by their median (the black tick).", sel, c));
    C.strip(c, {
      rows: keep.map(([p, xs]) => ({ label: `${p} (${xs.length})`, points: xs.map((r) => ({ x: +r.pc1, title: r.nome, rows: [`${r.partido} · ${r.uf}`, `position ${fmt(+r.pc1, 2)}`], color: p === A ? css("--a") : p === B ? css("--b") : css("--other") })) })),
      x: { label: "← first dimension of the votes →", format: (v) => fmt(v, 1) }, rowHeight: 24,
    });
  };
  draw();
  onResize(() => { if (root.offsetParent) draw(); });
}

// ------------------------------------------------------------ discipline (Senado)

export async function disciplineTab(root, o) {
  const t = await data(`site/${o.chamber}/disciplina.csv`);
  const people = await data(`site/${o.chamber}/disciplina_senadores.csv`);
  const months = [...new Set(t.map((r) => r.month))].sort();
  const weight = new Map();
  for (const r of t) weight.set(r.partido, (weight.get(r.partido) || 0) + +r.n_votes);
  const parties = [...weight.keys()].filter((p) => p && p !== "S/Partido").sort((a, b) => weight.get(b) - weight.get(a)).slice(0, 14);
  const get = (p, m, k) => { const r = t.find((x) => x.partido === p && x.month === m); return r && r[k] !== "" ? +r[k] : null; };
  root.append(el("p", { className: "about", textContent: "Over the contested roll calls of each 12-month window, how often each party's senators voted as the Government leader oriented (with_gov), as their own party leader oriented (with_party), and with the majority of their party colleagues (with_majority). Orientations are published from October 2018, for about half the roll calls." }));
  const hm = box();
  root.append(card("Votes with the government, by party", "Share of each party's votes that followed the Government leader's orientation, per window. Empty cells: the party had no senator voting on an oriented roll call.", hm));
  const cols = months.filter((m) => m >= "2019-04");
  C.heatmap(hm, {
    rows: parties, cols, value: (i, j) => get(parties[i], cols[j], "with_gov"), color: (v) => C.seq(v), minCell: 4, cell: 24, rowHeight: 18, colLabelHeight: 46, labelWidth: 110,
    tip: (i, j, v) => [el("strong", { textContent: `${parties[i]}, window to ${cols[j]}` }), el("div", { className: "row", textContent: `${pct(v)} with the government` })],
    table: { rows: t.filter((r) => parties.includes(r.partido)), cols: [{ key: "month", label: "Window to", text: true }, { key: "partido", label: "Party", text: true }, { key: "senadores", label: "Senators" }, { key: "with_gov", label: "With gov", fmt: (v) => pct(v) }, { key: "with_party", label: "With party", fmt: (v) => pct(v) }, { key: "with_majority", label: "With majority", fmt: (v) => pct(v) }], name: "senado-discipline" },
  });
  C.colorKey(hm, { color: C.seq, from: "0%", to: "100%", label: "with the government" });
  const c2 = box();
  root.append(card("Cohesion: votes with their party's majority", "The two parties picked on the Graphs tab, against the others in grey.", c2));
  const ser = (p, k, color, extra = {}) => ({ name: p, color, points: cols.map((m) => [m, get(p, m, k)]), ...extra });
  const drawLines = () => C.line(c2, { x: "month", y: { min: 0, max: 1, format: (v) => pct(v) }, marks: GOVERNMENTS,
    series: [...parties.filter((p) => p !== o.partyA && p !== o.partyB).map((p) => ser(p, "with_majority", css("--other"), { width: 1, hideLegend: true })), ser(o.partyA, "with_majority", css("--a")), ser(o.partyB, "with_majority", css("--b"))] });
  drawLines();
  let month = months[months.length - 1];
  const tb = el("div");
  const sel = el("div", { className: "controls" }, select("Window up to", [...months].reverse(), month, (m) => { month = m; renderPeople(); }));
  root.append(card("Senators", "Every senator with a contested vote in the window. Shares are over the votes where there was a line to follow.", sel, tb));
  const renderPeople = () => table(tb, people.filter((r) => r.month === month), [
    { key: "nome", label: "Senator", text: true }, { key: "partido", label: "Party", text: true }, { key: "uf", label: "UF", text: true },
    { key: "n_votes", label: "Votes" }, { key: "with_party", label: "With party", fmt: (v) => pct(v) }, { key: "with_gov", label: "With government", fmt: (v) => pct(v) },
    { key: "with_majority", label: "With party majority", fmt: (v) => pct(v) },
  ], { sortBy: "with_gov", pageSize: 15, name: `senado-senators-${month}` });
  renderPeople();
  onResize(() => { if (root.offsetParent) drawLines(); });
}
