// Analysis tabs shared by the Câmara and Senado explorers: network analysis,
// ideal points and (Senado) party discipline. Data: data/site/<chamber>/.
import { $, css, data, el, fmt, pct, table, tiles, params, setParam, onResize } from "./ui.js";
import * as C from "./charts.js";
import { L, month as monthName } from "./i18n.js";

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
// Table cells for decimal CSV columns, in the page's number format (blank stays blank).
const dec = (d) => (v) => (v === "" || v == null ? "" : fmt(+v, d));

// ------------------------------------------------------------ network analysis

export async function networkTab(root, o) {
  const net = (await data(`site/${o.chamber}/networks.csv`)).filter((r) => +r.nodes > 0);
  const months = net.map((r) => r.month), last = net[net.length - 1];
  const senado = o.chamber === "senado", when = monthName(last.month);
  const period = senado ? L(`Nos 12 meses até ${when}`, `The 12 months to ${when}`) : L(`Em ${when}`, `In ${when}`);
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Modularidade partidária", "Party modularity"), value: fmt(+last.modularity_party, 3), sub: L(`${period}: quanto os votos se dividem por partido (0 = nada)`, `${period}: how much co-voting splits along parties (0 = not at all)`) },
    { label: L("Ligações entre partidos", "Ties that cross parties"), value: pct(+last.cross_party_share), sub: L(`das ${fmt(+last.edges)} ligações de voto`, `of ${fmt(+last.edges)} vote-together ties`) },
    { label: L("Comunidades encontradas", "Communities found"), value: fmt(+last.communities), sub: L(`semelhança com os partidos: NMI ${fmt(+last.nmi_party, 2)}`, `match parties: NMI ${fmt(+last.nmi_party, 2)}`) },
    { label: L("Votos × assinaturas", "Votes vs signatures"), value: last.qap_r ? fmt(+last.qap_r, 3) : "–", sub: last.qap_p ? L(`correlação QAP, p = ${fmt(+last.qap_p, 3)}`, `QAP correlation, p = ${fmt(+last.qap_p, 3)}`) : "" },
  ]);
  const series = (key, name, color) => ({ name, color, points: net.map((r) => [r.month, num(r, key)]) });
  const c1 = box();
  root.append(card(L("Linhas partidárias ao longo do tempo", "Party lines over time"),
    L(`Por ${senado ? "janela de 12 meses" : "mês"}. A modularidade mede quanto as ligações de voto ficam mais dentro dos partidos do que o acaso colocaria; a parcela de ligações entre partidos e a densidade são lidas diretamente do grafo. As linhas tracejadas marcam as trocas de governo.`,
      `Per ${senado ? "12-month window" : "month"}. Modularity measures how much more the vote-together ties fall inside parties than chance would put them; the share of ties that cross parties and the density are read directly from the graph. Dashed lines mark changes of government.`), c1));
  const draw1 = () => C.line(c1, {
    x: "month", y: { min: 0, max: 1, format: (v) => fmt(v, 1) }, marks: GOVERNMENTS, height: 260,
    series: [series("cross_party_share", L("Ligações entre partidos", "Ties that cross parties"), C.slot(1)), series("density", L("Densidade", "Density"), C.slot(2)), series("modularity_party", L("Modularidade partidária", "Party modularity"), C.slot(3))],
    table: { rows: net, cols: [{ key: "month", label: L("Mês", "Month"), text: true }, { key: "cross_party_share", label: L("Parcela entre partidos", "Cross-party share"), fmt: dec(4) }, { key: "density", label: L("Densidade", "Density"), fmt: dec(4) }, { key: "modularity_party", label: L("Modularidade partidária", "Party modularity"), fmt: dec(4) }], name: `${o.chamber}-party-lines` },
  });
  const c2 = box();
  root.append(card(L("As comunidades nos votos seguem os partidos?", "Do the communities in the votes follow parties?"),
    L("O algoritmo de Louvain encontra grupos de parlamentares que votam juntos sem saber o partido de cada um. NMI e ARI medem quão perto esses grupos estão dos partidos: 1 é idêntico, 0 é sem relação.",
      "Louvain finds groups of members who vote together without being told their parties. NMI and ARI measure how close those groups are to the parties: 1 is identical, 0 is unrelated."), c2));
  const draw2 = () => C.line(c2, {
    x: "month", y: { min: 0, max: 1, format: (v) => fmt(v, 1) }, marks: GOVERNMENTS,
    series: [series("nmi_party", "NMI", C.slot(1)), series("ari_party", "ARI", C.slot(2))],
    table: { rows: net, cols: [{ key: "month", label: L("Mês", "Month"), text: true }, { key: "communities", label: L("Comunidades", "Communities") }, { key: "modularity_louvain", label: L("Modularidade", "Modularity"), fmt: dec(4) }, { key: "nmi_party", label: "NMI", fmt: dec(4) }, { key: "ari_party", label: "ARI", fmt: dec(4) }], name: `${o.chamber}-communities` },
  });
  const c3 = box();
  root.append(card(L("Votar junto e assinar junto", "Voting together and signing together"),
    L("A correlação QAP entre os dois grafos, nos parlamentares presentes em ambos: quem vota junto também assina projetos junto? A tabela traz o p do teste de permutação de cada ponto (abaixo de 0,05, a correlação é significativa); a sobreposição é o índice de Jaccard das ligações.",
      "The QAP correlation between the two graphs on their common members: does voting together go with co-signing bills? The table gives every point with its permutation-test p-value; overlap is the Jaccard index of their ties."), c3));
  const draw3 = () => C.line(c3, {
    x: "month", y: { format: (v) => fmt(v, 2) }, marks: GOVERNMENTS,
    series: [series("qap_r", L("Correlação QAP", "QAP correlation"), C.slot(1)), series("overlap_jaccard", L("Sobreposição (Jaccard)", "Overlap (Jaccard)"), C.slot(2))],
    table: { rows: net, cols: [{ key: "month", label: L("Mês", "Month"), text: true }, { key: "qap_r", label: L("r QAP", "QAP r"), fmt: dec(4) }, { key: "qap_p", label: L("Valor de p", "p-value"), fmt: dec(4) }, { key: "overlap_jaccard", label: "Jaccard", fmt: dec(4) }], name: `${o.chamber}-qap` },
  });

  // One month in detail.
  const detail = el("div");
  let month = months.includes(params.get("nm")) ? params.get("nm") : months[months.length - 1];
  const controls = el("div", { className: "controls" }, select(senado ? L("Janela até", "Window up to") : L("Mês", "Month"), [...months].reverse(), month, (m) => { month = m; setParam("nm", m); renderMonth(); }));
  root.append(el("h2", { textContent: L("Um mês em detalhe", "One month in detail"), style: "font-size:15px;margin:18px 0 0" }), controls, detail);
  const renderMonth = async () => {
    const rows = (await data(`site/${o.chamber}/members/${month.slice(0, 4)}.csv`)).filter((r) => r.month === month);
    detail.replaceChildren();
    const comm = [...new Set(rows.map((r) => +r.community))].sort((a, b) => a - b);
    const parties = [...new Set(rows.map((r) => r.partido))].filter(Boolean);
    const size = (p) => rows.filter((r) => r.partido === p).length;
    parties.sort((a, b) => size(b) - size(a));
    const count = (p, c) => rows.filter((r) => r.partido === p && +r.community === c).length;
    const hm = box(), grid = el("div", { className: "grid2" });
    detail.append(grid);   // in the page before drawing, so the charts measure their real width
    grid.append(card(L(`Partidos nas comunidades, ${monthName(month)}`, `Parties across communities, ${monthName(month)}`),
      L("Parlamentares de cada partido (linhas) em cada comunidade revelada pelos votos (colunas), como parcela do partido.", "Members of each party (rows) in each community the votes reveal (columns), as a share of the party."), hm));
    C.heatmap(hm, {
      rows: parties.map((p) => `${p} (${size(p)})`), cols: comm.map((c) => `${L("Grupo", "Group")} ${c} (${rows.filter((r) => +r.community === c).length})`),
      value: (i, j) => count(parties[i], comm[j]) / size(parties[i]), color: (v) => C.seq(v), cellText: (v) => Math.round(v * 100), dark: (v) => v > 0.55,
      allColLabels: true, colLabelHeight: 92, labelWidth: 120, cell: 44, rowHeight: 20,
      tip: (i, j, v) => [el("strong", { textContent: L(`${parties[i]} no grupo ${comm[j]}`, `${parties[i]} in group ${comm[j]}`) }),
        el("div", { className: "row", textContent: L(`${count(parties[i], comm[j])} de ${size(parties[i])} parlamentares (${pct(v)})`, `${count(parties[i], comm[j])} of ${size(parties[i])} members (${pct(v)})`) })],
    });
    const central = box();
    grid.append(card(L("Parlamentares mais centrais", "Most central members"),
      L("Centralidade de autovetor no grafo de voto: ligados a muitos parlamentares que, por sua vez, também são bem ligados.", "Eigenvector centrality in the vote-together graph: tied to many members who are themselves well tied."), central));
    const top = [...rows].sort((a, b) => +b.eigen - +a.eigen).slice(0, 15);
    C.bars(central, { rows: top.map((r) => ({ label: `${r.nome} (${r.partido})`, value: +r.eigen, color: r.partido === o.partyA ? css("--a") : r.partido === o.partyB ? css("--b") : css("--line") })), format: (v) => fmt(v, 2), max: 1 });
    const bridges = el("div");
    detail.append(card(L("Pontes", "Bridges"), L(
      `Parlamentares cujas ligações de voto cruzam as linhas partidárias mais do que o tamanho do partido, sozinho, explicaria (com pelo menos 10 ligações). Num partido pequeno quase toda ligação é com outro partido, por isso cada um é ordenado pelo excesso sobre essa expectativa: a parcela dos demais parlamentares que pertencem a outros partidos. ${senado ? "Senadores" : "Deputados"} sem partido ficam de fora.`,
      `Members whose vote-together ties cross party lines more than their party's size alone would make them (at least 10 ties). In a small party almost every tie crosses party lines, so a member is ranked by the excess over that expectation: the share of the other members who belong to other parties. ${senado ? "Senators" : "Deputies"} with no party are left out.`), bridges));
    const N = rows.length;
    const br = rows.filter((r) => +r.degree >= 10 && r.partido).map((r) => {
      const share = +r.cross_degree / +r.degree, expected = N > 1 ? 1 - (size(r.partido) - 1) / (N - 1) : 0;
      return { ...r, share, expected, excess: share - expected };
    });
    table(bridges, br, [
      { key: "nome", label: L("Nome", "Name"), text: true }, { key: "partido", label: L("Partido", "Party"), text: true }, { key: "uf", label: "UF", text: true },
      { key: "degree", label: L("Ligações", "Ties") }, { key: "cross_degree", label: L("Com outros partidos", "Across parties") }, { key: "share", label: L("Parcela", "Share"), fmt: (v) => pct(v) },
      { key: "expected", label: L("Esperado", "Expected"), fmt: (v) => pct(v) }, { key: "excess", label: L("Excesso", "Excess"), fmt: (v) => `${v >= 0 ? "+" : ""}${Math.round(v * 100)} ${L("p.p.", "pts")}` },
      { key: "eigen", label: L("Centralidade", "Centrality"), fmt: (v) => fmt(+v, 2) }, { key: "community", label: L("Grupo", "Group") },
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
  const senado = o.chamber === "senado";
  root.append(el("p", { className: "about", style: "margin-bottom:16px", textContent: L(
    `O “ponto ideal” de cada ${senado ? "senador" : "deputado"} é a sua posição no primeiro componente principal dos seus votos nas votações disputadas ${senado ? "da janela de 12 meses" : "do mês"} (o eixo horizontal do mapa da aba Grafos), padronizada para que uma unidade seja um desvio-padrão, com a média do PT no lado negativo. As posições se comparam dentro ${senado ? "de uma janela" : "de um mês"}; a escala não é fixa ao longo do tempo.`,
    `Each ${senado ? "senator" : "deputy"}'s "ideal point" is their position on the first principal component of their contested votes ${senado ? "in the 12-month window" : "that month"} (the horizontal axis of the explorer's map), standardised so that one unit is one standard deviation, with PT's mean on the negative side. Positions compare within a ${senado ? "window" : "month"}; their scale is not fixed across time.`) }));
  root.append(controls,
    card(L("Onde os partidos se posicionam", "Where parties sit"),
      L("Posição mediana de cada partido por mês; a faixa sombreada é a metade central dos seus parlamentares (do 25º ao 75º percentil) para os dois partidos escolhidos. Os demais partidos aparecem em cinza.",
        "Median position of each party per month; the shaded band is the middle half of its members (25th to 75th percentile) for the two parties picked. Other parties in grey."), c1),
    card(L("Distância entre os dois partidos", "Distance between the two parties"),
      L("Mediana do segundo partido menos a mediana do primeiro, em desvios-padrão da Casa.", "Median of the second party minus median of the first, in standard deviations of the chamber."), c2));
  const strip = el("div");
  root.append(strip);
  const draw = () => {
    controls.replaceChildren(
      select(L("Partido", "Party"), parties, A, (v) => { A = v; setParam("ia", v, o.partyA); draw(); }),
      select(L("e partido", "and party"), parties, B, (v) => { B = v; setParam("ib", v, o.partyB); draw(); }));
    const by = (p, k) => months.map((m) => { const r = ideal.find((x) => x.month === m && x.partido === p); return [m, r ? +r[k] : null]; });
    const band = (p) => months.map((m) => { const r = ideal.find((x) => x.month === m && x.partido === p); return r ? [m, +r.q25, +r.q75] : [m, null, null]; });
    const others = parties.slice(0, 14).filter((p) => p !== A && p !== B).map((p) => ({ name: p, color: css("--other"), points: by(p, "median"), width: 1, hideLegend: true, opacity: 0.8 }));
    C.line(c1, {
      x: "month", height: 300, marks: GOVERNMENTS, y: { format: (v) => fmt(v, 1) },
      series: [...others, { name: A, color: css("--a"), points: by(A, "median"), band: band(A) }, { name: B, color: css("--b"), points: by(B, "median"), band: band(B) }],
      table: { rows: ideal.filter((r) => r.partido === A || r.partido === B), cols: [{ key: "month", label: L("Mês", "Month"), text: true }, { key: "partido", label: L("Partido", "Party"), text: true }, { key: "n", label: L("Parlamentares", "Members") }, { key: "q25", label: L("25º percentil", "25th"), fmt: dec(4) }, { key: "median", label: L("Mediana", "Median"), fmt: dec(4) }, { key: "q75", label: L("75º percentil", "75th"), fmt: dec(4) }], name: `${o.chamber}-ideal` },
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
    const sel = el("div", { className: "controls" }, select(senado ? L("Janela até", "Window up to") : L("Mês", "Month"), [...months].reverse(), month, (m) => { month = m; renderStrip(); }));
    strip.append(card(L(`Todos os parlamentares, ${monthName(month)}`, `Every member, ${monthName(month)}`),
      L("Cada ponto é um parlamentar, por partido (partidos com pelo menos 3 parlamentares), em ordem pela mediana (o traço vertical).", "Each dot is a member, by party (parties with at least 3 members), ordered by their median (the vertical tick)."), sel, c));
    C.strip(c, {
      rows: keep.map(([p, xs]) => ({ label: `${p} (${xs.length})`, points: xs.map((r) => ({ x: +r.pc1, title: r.nome, rows: [`${r.partido} · ${r.uf}`, `${L("posição", "position")} ${fmt(+r.pc1, 2)}`], color: p === A ? css("--a") : p === B ? css("--b") : css("--other") })) })),
      x: { label: L("← primeira dimensão dos votos →", "← first dimension of the votes →"), format: (v) => fmt(v, 1) }, rowHeight: 24,
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
  root.append(el("p", { className: "about", style: "margin-bottom:16px", textContent: L(
    "Nas votações nominais disputadas de cada janela de 12 meses, com que frequência os senadores de cada partido votaram conforme a orientação do líder do governo (“com o governo”), conforme a orientação do líder do próprio partido (“com o partido”) e com a maioria dos colegas de partido (“com a maioria”). As orientações são publicadas desde outubro de 2018, em cerca de metade das votações.",
    "Over the contested roll calls of each 12-month window, how often each party's senators voted as the Government leader oriented (“with gov”), as their own party leader oriented (“with party”), and with the majority of their party colleagues (“with majority”). Orientations are published from October 2018, for about half the roll calls.") }));
  const hm = box();
  root.append(card(L("Votos com o governo, por partido", "Votes with the government, by party"),
    L("Parcela dos votos de cada partido que seguiu a orientação do líder do governo, por janela. Células vazias: o partido não teve senador votando em votação com orientação.",
      "Share of each party's votes that followed the Government leader's orientation, per window. Empty cells: the party had no senator voting on an oriented roll call."), hm));
  const cols = months.filter((m) => m >= "2019-04");
  // One label per year (at January): a label per month is too dense to read at this cell size.
  C.heatmap(hm, {
    rows: parties, cols: cols.map((m) => (m.endsWith("-01") ? m.slice(0, 4) : "")), allColLabels: true,
    value: (i, j) => get(parties[i], cols[j], "with_gov"), color: (v) => C.seq(v), minCell: 4, cell: 24, rowHeight: 18, colLabelHeight: 40, labelWidth: 110,
    tip: (i, j, v) => [el("strong", { textContent: L(`${parties[i]}, janela até ${monthName(cols[j])}`, `${parties[i]}, window to ${monthName(cols[j])}`) }), el("div", { className: "row", textContent: L(`${pct(v)} com o governo`, `${pct(v)} with the government`) })],
    table: { rows: t.filter((r) => parties.includes(r.partido)), cols: [{ key: "month", label: L("Janela até", "Window to"), text: true }, { key: "partido", label: L("Partido", "Party"), text: true }, { key: "senadores", label: L("Senadores", "Senators") }, { key: "with_gov", label: L("Com o governo", "With gov"), fmt: (v) => pct(v) }, { key: "with_party", label: L("Com o partido", "With party"), fmt: (v) => pct(v) }, { key: "with_majority", label: L("Com a maioria", "With majority"), fmt: (v) => pct(v) }], name: "senado-discipline" },
  });
  C.colorKey(hm, { color: C.seq, from: "0%", to: "100%", label: L("com o governo", "with the government") });
  const c2 = box();
  root.append(card(L("Coesão: votos com a maioria do partido", "Cohesion: votes with their party's majority"),
    L("Os dois partidos escolhidos na aba Grafos, contra os demais em cinza.", "The two parties picked on the Graphs tab, against the others in grey."), c2));
  const ser = (p, k, color, extra = {}) => ({ name: p, color, points: cols.map((m) => [m, get(p, m, k)]), ...extra });
  const drawLines = () => C.line(c2, { x: "month", y: { min: 0, max: 1, format: (v) => pct(v) }, marks: GOVERNMENTS,
    series: [...parties.filter((p) => p !== o.partyA && p !== o.partyB).map((p) => ser(p, "with_majority", css("--other"), { width: 1, hideLegend: true })), ser(o.partyA, "with_majority", css("--a")), ser(o.partyB, "with_majority", css("--b"))] });
  drawLines();
  let month = months[months.length - 1];
  const tb = el("div");
  const sel = el("div", { className: "controls" }, select(L("Janela até", "Window up to"), [...months].reverse(), month, (m) => { month = m; renderPeople(); }));
  root.append(card(L("Senadores", "Senators"),
    L("Todos os senadores com voto em alguma votação disputada da janela. As parcelas são calculadas sobre os votos em que havia uma orientação a seguir.",
      "Every senator with a contested vote in the window. Shares are over the votes where there was a line to follow."), sel, tb));
  const renderPeople = () => table(tb, people.filter((r) => r.month === month), [
    { key: "nome", label: L("Senador", "Senator"), text: true }, { key: "partido", label: L("Partido", "Party"), text: true }, { key: "uf", label: "UF", text: true },
    { key: "n_votes", label: L("Votos", "Votes") }, { key: "with_party", label: L("Com o partido", "With party"), fmt: (v) => pct(v) }, { key: "with_gov", label: L("Com o governo", "With government"), fmt: (v) => pct(v) },
    { key: "with_majority", label: L("Com a maioria do partido", "With party majority"), fmt: (v) => pct(v) },
  ], { sortBy: "with_gov", pageSize: 15, name: `senado-senators-${month}` });
  renderPeople();
  onResize(() => { if (root.offsetParent) drawLines(); });
}
