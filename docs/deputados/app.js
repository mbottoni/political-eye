// Deputies across sources: votes, co-voters, amendments and campaign money, per deputy and compared.
import { $, asset, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tabs, tiles } from "../lib/ui.js";
import { GOVERNMENTS } from "../lib/chamber.js";
import * as C from "../lib/charts.js";
import { L, month } from "../lib/i18n.js";
import { setupPage } from "../lib/page.js";
import { avatar, deputySearch } from "../lib/search.js";

setupPage();

const TYPES = [["individual", L("Individual", "Individual")], ["especial", L("Transferência especial (Pix)", "Special transfer (“Pix”)")], ["bancada", L("De bancada", "State bench")],
  ["comissao", L("De comissão", "Committee")], ["relator", L("De relator", "Rapporteur")]];
const UF_CODE = { RO: "11", AC: "12", AM: "13", RR: "14", PA: "15", AP: "16", TO: "17", MA: "21", PI: "22", CE: "23", RN: "24", PB: "25", PE: "26", AL: "27", SE: "28", BA: "29",
  MG: "31", ES: "32", RJ: "33", SP: "35", PR: "41", SC: "42", RS: "43", MS: "50", MT: "51", GO: "52", DF: "53" };
const typeColor = (t) => C.slot(TYPES.findIndex(([k]) => k === t) + 1);
const GAP = [{ from: "2025-02", to: "2025-10", label: L("um bloco não deu orientação", "one bloc gave no orientation") }];
const ALIASES = { SOLIDARIED: "SOLIDARIEDADE", SOLIDARI: "SOLIDARIEDADE", SD: "SOLIDARIEDADE", SDD: "SOLIDARIEDADE", REPUBLICAN: "REPUBLICANOS",
  REPUBLIC: "REPUBLICANOS", PODEMOS: "PODE", PATRI: "PATRIOTA", "PP**": "PP", PMDB: "MDB", PR: "PL", PPS: "CIDADANIA", PTN: "PODE",
  PEN: "PATRIOTA", PTDOB: "AVANTE", PSDC: "DC", PRB: "REPUBLICANOS" };
const partyKey = (label) => { const k = String(label || "").trim().toUpperCase(); return ALIASES[k] || k; };
const partyColor = (p) => (partyKey(p) === "PT" ? css("--a") : partyKey(p) === "PL" ? css("--b") : css("--other"));
const PARTY_LEGEND = () => [{ label: "PT", color: css("--a"), shape: "dot" }, { label: "PL", color: css("--b"), shape: "dot" }, { label: L("Outros partidos", "Other parties"), color: css("--other"), shape: "dot" }];
// The TSE's result codes, in lower case for a sentence.
const RESULT = { ELEITO: L("eleito", "elected"), "ELEITO POR QP": L("eleito por QP", "elected (quotient)"), "ELEITO POR MÉDIA": L("eleito por média", "elected (remainders)"),
  SUPLENTE: L("suplente", "substitute"), "NÃO ELEITO": L("não eleito", "not elected") };

const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const finding = (text) => el("p", { className: "finding", textContent: text });
const select = (label, options, value, onChange) => {
  const s = el("select", {}, ...options.map((o) => el("option", { value: o.value ?? o, textContent: o.label ?? o, selected: String(o.value ?? o) === String(value) })));
  s.addEventListener("change", () => onChange(s.value));
  return el("label", {}, label, s);
};
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const median = (xs) => { const v = xs.filter((x) => x != null && !Number.isNaN(x)).sort((a, b) => a - b); return v.length ? (v[Math.floor((v.length - 1) / 2)] + v[Math.ceil((v.length - 1) / 2)]) / 2 : null; };
const n = (v) => (v === "" || v == null ? null : +v);
const redraws = [];
const later = (f) => { redraws.push(f); f(); };
function local() {
  const mine = [];
  redraws.push(() => mine.forEach((f) => f()));
  return { later: (f) => { mine.push(f); f(); }, reset: () => { mine.length = 0; } };
}

// The measures a deputy can be compared on; derived ones are computed in load().
const METRICS = [
  { key: "with_party", label: L("Com a orientação do partido", "With their party's orientation"), fmt: (v) => pct(v), min: 0, max: 1 },
  { key: "with_gov", label: L("Com o governo", "With the government"), fmt: (v) => pct(v), min: 0, max: 1 },
  { key: "with_majority", label: L("Com a maioria do partido", "With their party's majority"), fmt: (v) => pct(v), min: 0, max: 1 },
  { key: "pc1", label: L("Posição de voto (lado do PT negativo)", "Voting position (PT's side negative)"), fmt: (v) => fmt(v, 2) },
  { key: "eigen", label: L("Centralidade na rede de votos", "Co-voting centrality"), fmt: (v) => fmt(v, 2) },
  { key: "cross_share", label: L("Laços de voto com outros partidos", "Co-voting ties across parties"), fmt: (v) => pct(v) },
  { key: "n_votes", label: L("Votos em votações disputadas", "Contested votes cast"), fmt: (v) => fmt(v) },
  { key: "presenca", label: L("Participação nas votações nominais", "Roll-call participation"), fmt: (v) => pct(v), min: 0, max: 1 },
  { key: "projetos_autor", label: L("Projetos apresentados como 1º signatário", "Bills filed as first signer"), fmt: (v) => fmt(v) },
  { key: "propostas_coautor", label: L("Propostas que coassinou", "Proposals co-signed"), fmt: (v) => fmt(v) },
  { key: "emendas_pago", money: true, label: L("Emendas pagas", "Amendments paid"), fmt: (v) => brl(v, 0) },
  { key: "emendas_pago_estado", label: L("Parcela das emendas paga no próprio estado", "Share of amendment money paid in their state"), fmt: (v) => pct(v), min: 0, max: 1 },
  { key: "prefeito_mesmo_partido", label: L("Parcela para municípios com prefeito do partido", "Share of town money to towns their party runs"), fmt: (v) => pct(v), min: 0, max: 1 },
  { key: "prefeito_excesso", label: L("…acima do acaso (pontos)", "…above chance (points)"), fmt: (v) => fmt(100 * v, 0) },
  { key: "campanha_total", money: true, label: L("Dinheiro de campanha", "Campaign money"), fmt: (v) => brl(v, 0) },
  { key: "campanha_partido_share", label: L("Parcela da campanha vinda do partido", "Share of campaign money from their party"), fmt: (v) => pct(v), min: 0, max: 1 },
  { key: "campanha_proprios", money: true, label: L("Recursos próprios na campanha", "Own money in their campaign"), fmt: (v) => brl(v, 0) },
  { key: "campanha_doadores_pf", label: L("Doadores pessoas físicas da campanha", "Private donors to their campaign"), fmt: (v) => fmt(v) },
  { key: "grandes_doadores_valor", money: true, label: L("Dinheiro de doadores de R$ 50 mil ou mais", "Campaign money from donors of R$50k+"), fmt: (v) => brl(v, 0) },
  { key: "sancoes_pago_sancionadas", money: true, label: L("Emendas pagas a empresas impedidas (desde 2015)", "Amendment money paid to barred companies (since 2015)"), fmt: (v) => brl(v, 0) },
];
const M = Object.fromEntries(METRICS.map((m) => [m.key, m]));
const SHORT = { with_party: L("Com o partido", "With party"), with_gov: L("Com o governo", "With government"), with_majority: L("Maioria do partido", "With party majority"),
  pc1: L("Posição de voto", "Voting position"), eigen: L("Centralidade", "Centrality"), cross_share: L("Laços entre partidos", "Cross-party ties"), n_votes: L("Votos dados", "Votes cast"), presenca: L("Participação", "Participation"),
  projetos_autor: L("Projetos (autor)", "Bills filed"), propostas_coautor: L("Coassinou", "Co-signed"),
  emendas_pago: L("Emendas pagas", "Amendments paid"), emendas_pago_estado: L("Pago no estado", "Paid in own state"), prefeito_mesmo_partido: L("Prefeitos do partido", "Own-party towns"),
  prefeito_excesso: L("Prefeitos vs. acaso", "Own-party, over chance"), campanha_total: L("Arrecadação", "Campaign money"), campanha_partido_share: L("Do partido", "From party"),
  campanha_proprios: L("Recursos próprios", "Own money"), campanha_doadores_pf: L("Doadores privados", "Private donors"), grandes_doadores_valor: L("Grandes doadores", "Large donors"),
  sancoes_pago_sancionadas: L("Empresas impedidas", "To barred firms") };
const NUMERIC = ["meses", "n_votes", "n_party", "with_party", "n_gov", "with_gov", "n_majority", "with_majority", "emendas", "emendas_empenhado", "emendas_pago", "campanha_total", "campanha_partido",
  "campanha_fefc", "campanha_proprios", "campanha_doadores_pf", "pc1", "eigen", "cross_share", "emendas_pago_estado", "emendas_pago_nacional", "grandes_doadores", "grandes_doadores_valor",
  "sancoes_pago_total", "sancoes_pago_sancionadas", "sancoes_empresas", "prefeito_mesmo_partido", "prefeito_base",
  "presenca", "votacoes_mandato", "propostas_autor", "projetos_autor", "propostas_coautor", "relatorias", "partidos"];
// Who presided over the Câmara, and when: the president votes only to break a tie.
const SPEAKERS = { 74693: [["2019-02", "2021-01"]], 160541: [["2021-02", "2025-01"]], 160674: [["2025-02", null]] };
const KINDS = [["projetos", L("Projetos de lei, PECs, decretos", "Bills, PECs, decrees")], ["relatorias", L("Pareceres e substitutivos", "Opinions and substitutes")],
  ["emendas", L("Emendas a proposições", "Amendments to bills")], ["fiscalizacao", L("Pedidos de informação", "Information requests")],
  ["requerimentos", L("Requerimentos e indicações", "Requests and suggestions")], ["outros", L("Outros documentos", "Other documents")]];
// Rankings compare deputies who served at least six months, so a substitute's few weeks don't set the scale.
const RANKED = ["presenca", "projetos_autor", "propostas_coautor", "with_gov", "with_party", "cross_share", "emendas_pago", "emendas_pago_estado", "campanha_total"];

let LEGS = [], leg;
const LEG_NAME = { 57: L("57ª legislatura (2023–2027)", "57th legislature (2023–2027)"), 56: L("56ª legislatura (2019–2023)", "56th legislature (2019–2023)") };
const LEG_YEARS = { 57: [2023, 2024, 2025, 2026, 2027], 56: [2019, 2020, 2021, 2022, 2023] };
const cache = new Map();
async function load(l = leg) {
  if (!cache.has(l)) {
    const rows = await data(`site/deputados/deputados_${l}.csv`);
    for (const r of rows) {
      for (const k of NUMERIC) r[k] = n(r[k]);
      r.campanha_partido_share = r.campanha_total ? r.campanha_partido / r.campanha_total : null;
      r.prefeito_excesso = r.prefeito_mesmo_partido == null ? null : r.prefeito_mesmo_partido - r.prefeito_base;
      r.party = partyKey(r.partido);
      r.label = `${r.nome} (${r.party}-${r.uf})`;
    }
    const byId = new Map(rows.map((r) => [r.deputado_id, r]));
    const parties = new Map();
    for (const r of rows) { if (!parties.has(r.party)) parties.set(r.party, []); parties.get(r.party).push(r); }
    cache.set(l, { rows, byId, parties, partyMedian: (p, k) => median((parties.get(p) || []).map((r) => r[k])) });
  }
  return cache.get(l);
}
const profileLink = (r) => el("a", { href: `?leg=${leg}&dep=${r.deputado_id}`, textContent: r.label, on: { click: (ev) => { ev.preventDefault(); openProfile(r.deputado_id); } } });
let showDeputy = null;   // set by the profile tab once it is drawn
function openProfile(id) {
  setParam("dep", id);
  if (showDeputy) showDeputy(id);
  $("nav.tabs button[data-tab=profile]").click();
  window.scrollTo({ top: 0 });
}

// ------------------------------------------------------------ one deputy

async function profile(root) {
  const D = await load();
  const out = el("div");
  // Any deputy of either legislature: one of this legislature opens here, another reloads on theirs.
  const search = deputySearch({ label: L("Encontre um deputado", "Find a deputy"),
    onPick: (d) => { if (D.byId.has(d.id)) { show(d.id); window.scrollTo({ top: 0 }); } else location.search = `?tab=profile&leg=${d.leg}&dep=${d.id}`; } });
  root.append(el("div", { className: "controls" }, el("label", { style: "flex:1 1 360px" }, L("Encontre um deputado", "Find a deputy"), search)), out);
  const lc = local();
  const pool = D.rows.filter((x) => (x.meses || 0) >= 6);
  const rankOf = (k, v) => {
    const xs = pool.map((x) => x[k]).filter((x) => x != null && !Number.isNaN(x));
    if (v == null || Number.isNaN(v) || !xs.length) return null;
    return (xs.filter((x) => x < v).length + xs.filter((x) => x === v).length / 2) / xs.length;
  };
  const sectionHead = (sid, text) => el("h3", { className: "dsec", id: sid, textContent: text });
  const show = async (id) => {
    const r = D.byId.get(id);
    if (!r) return;
    setParam("dep", id);
    lc.reset();
    // Start every download at once; each section awaits only its own.
    const years = LEG_YEARS[leg];
    const got = {
      parties: data("site/orientacoes/partidos.csv"),
      monthly: Promise.all(years.map((y) => data(`site/orientacoes/deputados_mes/${y}.csv`).catch(() => []))),
      members: Promise.all(years.map((y) => data(`site/camara/members/${y}.csv`).catch(() => []))),
      ideal: data("site/camara/ideal.csv"), nb: data(`site/deputados/vizinhos_${leg}.csv`),
      em: data(`site/deputados/emendas_${leg}.csv`), dest: data(`site/deputados/destinos_${leg}.csv`), entes: data("siconfi/entes.csv"),
      maps: Promise.all([asset("maps/municipios.json"), asset("maps/ufs.json")]), donors: data(`site/deputados/doadores_${leg}.csv`),
      act: data(`site/deputados/atividade_${leg}.csv`).catch(() => []), kinds: data(`site/deputados/propostas_${leg}.csv`).catch(() => []),
      co: data(`site/deputados/coautores_${leg}.csv`).catch(() => []), trail: data(`site/deputados/partidos_${leg}.csv`).catch(() => []),
    };
    const med = (k) => D.partyMedian(r.party, k);
    const vs = (k, f) => { const m = med(k); return m == null ? "" : L(`mediana do partido ${f(m)}`, `party median ${f(m)}`); };
    const votes = (v) => L(`${fmt(v)} votos`, `${fmt(v)} votes`);
    const box = el("div");
    out.replaceChildren(box);
    // Who they are
    const trail = el("p", { className: "trail", hidden: true });
    const SECTIONS = [["sec-resumo", L("Resumo", "Summary")], ["sec-votos", L("Votações", "Votes")], ["sec-atividade", L("Atividade legislativa", "Legislative work")],
      ["sec-emendas", L("Emendas", "Amendments")], ["sec-campanha", L("Campanha", "Campaign")]];
    const legFrom = `${LEG_YEARS[leg][0]}-02`, legTo = `${LEG_YEARS[leg][4]}-01`;
    const presided = (SPEAKERS[id] || []).filter(([a, b]) => a <= legTo && (b ?? "9999") >= legFrom);
    box.append(el("div", { className: "dossier", id: "sec-resumo" }, avatar(id, r.nome, 96),
      el("div", { className: "dhead" },
        el("h2", { className: "dname", textContent: r.nome }),
        el("p", { className: "dmeta" }, el("span", { className: "chip", textContent: `${r.party} · ${r.uf}` }), " ",
          L(`${LEG_NAME[leg]} · ${plural(r.meses || 0, "mês", "meses")} de mandato`, `${LEG_NAME[leg]} · ${plural(r.meses || 0, "month")} in office`)),
        trail,
        el("p", { className: "dlinks" }, el("a", { href: `https://www.camara.leg.br/deputados/${id}`, textContent: L("Perfil na Câmara ↗", "Câmara profile ↗") }), " · ",
          el("a", { href: `../orientacoes/?tab=deputy&dep=${id}`, textContent: L("Votos mês a mês", "Votes month by month") })))),
    el("nav", { className: "jump", "aria-label": L("Seções do perfil", "Profile sections") }, ...SECTIONS.map(([k, t]) => el("a", { href: `#${k}`, textContent: t,
      on: { click: (e) => { e.preventDefault(); document.getElementById(k)?.scrollIntoView({ behavior: "smooth", block: "start" }); } } }))));
    for (const [a, b] of presided) box.append(el("p", { className: "about", textContent: L(`Presidiu a Câmara de ${month(a)} a ${b ? month(b) : "hoje"}. O presidente só vota para desempatar, por isso a participação nas votações não se compara à dos outros deputados.`,
      `Presided over the Câmara from ${month(a)} to ${b ? month(b) : "today"}. The president votes only to break a tie, so their roll-call participation does not compare with other deputies'.`) }));
    got.trail.then((T) => {
      const mineT = T.filter((x) => x.deputado_id === id);
      if (mineT.length < 2) return;
      trail.replaceChildren(L("Partidos na legislatura: ", "Parties in this legislature: "), ...mineT.flatMap((x, i) => [i ? " → " : "",
        el("span", { className: "chip soft", textContent: x.partido === "S.PART." ? L("sem partido", "no party") : partyKey(x.partido), title: `${month(x.de)} – ${month(x.ate)}` })]));
      trail.hidden = false;
    });

    // In short, and against everyone else
    const above = (k) => { const q = rankOf(k, r[k]); return q == null ? "" : L(`acima de ${pct(q)} dos deputados`, `above ${pct(q)} of deputies`); };
    tiles(box.appendChild(el("section", { className: "tiles" })), [
      { label: L("Participação nas votações nominais", "Roll-call participation"), value: pct(r.presenca),
        sub: [above("presenca"), r.votacoes_mandato ? L(`${fmt(r.votacoes_mandato)} votações no período`, `${fmt(r.votacoes_mandato)} roll calls held`) : ""].filter(Boolean).join(" · ") },
      { label: L("Projetos apresentados", "Bills filed"), value: fmt(r.projetos_autor), sub: [above("projetos_autor"), L("como 1º signatário", "as first signer")].filter(Boolean).join(" · ") },
      { label: L("Votos com o governo", "Votes with the government"), value: pct(r.with_gov), sub: [above("with_gov"), vs("with_gov", pct)].filter(Boolean).join(" · ") },
      { label: L("Emendas pagas", "Amendments paid"), value: brl(r.emendas_pago), sub: above("emendas_pago") || L("nenhuma emenda paga", "no amendment paid") },
    ]);
    const ranks = el("div", { className: "ranks" });
    for (const k of RANKED) {
      const m = M[k], q = rankOf(k, r[k]), pq = rankOf(k, med(k));
      ranks.append(el("div", { className: "rank" }, el("span", { className: "rl", textContent: m.label }),
        el("span", { className: "track" }, pq == null ? null : el("i", { className: "ptick", style: `left:${100 * pq}%`, title: L(`mediana do ${r.party}`, `${r.party} median`) }),
          q == null ? null : el("b", { className: "dot", style: `left:${100 * q}%`, title: r.nome })),
        el("span", { className: "rv", textContent: r[k] == null ? "–" : m.fmt(r[k]) })));
    }
    box.append(card(L("Como se compara", "How they compare"),
      L(`A posição entre os ${fmt(pool.length)} deputados da legislatura com seis meses ou mais de mandato: menores valores à esquerda, maiores à direita. O traço marca a mediana do ${r.party}.`,
        `Where they stand among the legislature's ${fmt(pool.length)} deputies with six months or more in office: lowest values on the left, highest on the right. The tick marks the ${r.party} median.`), ranks));

    // Votes
    box.append(sectionHead("sec-votos", L("Votações", "Votes")));
    tiles(box.appendChild(el("section", { className: "tiles" })), [
      { label: L("Com a orientação do partido", "With their party's orientation"), value: pct(r.with_party), sub: `${vs("with_party", pct)} · ${votes(r.n_party)}` },
      { label: L("Com o governo", "With the government"), value: pct(r.with_gov), sub: `${vs("with_gov", pct)} · ${votes(r.n_gov)}` },
      { label: L("Posição de voto", "Voting position"), value: r.pc1 == null ? "–" : fmt(r.pc1, 2), sub: `${vs("pc1", (v) => fmt(v, 2))}; ${L("o lado do PT é negativo", "PT's side is negative")}` },
      { label: L("Laços de voto com outros partidos", "Co-voting ties across parties"), value: pct(r.cross_share), sub: `${vs("cross_share", pct)} · ${L("centralidade", "centrality")} ${fmt(r.eigen, 2)}` },
    ]);
    const [P, monthly, members, ideal] = await Promise.all([got.parties, got.monthly.then((xs) => xs.flat().filter((x) => x.deputado_id === id)),
      got.members.then((xs) => xs.flat().filter((x) => x.id === id)), got.ideal]);
    const pg = new Map(P.map((x) => [`${partyKey(x.partido)}|${x.month}`, x]));
    const c1 = chart(), c2 = chart(), g = el("div", { className: "grid2" });
    g.append(card(L("Mês a mês", "Month by month"),
      L("A parcela dos votos com o governo e com a orientação do partido; em cinza, o apoio ao governo do partido em que estava naquele mês. Meses com menos de cinco votos em votações disputadas ficam de fora (lacunas).",
        "Their share of votes with the government and with their party's orientation; in grey, the government support of the party they were in that month. Months where they cast fewer than five contested votes are left out (gaps)."), c1),
    card(L("Onde se situa na principal divisão das votações", "Where they sit on the main voting divide"),
      L("A posição a cada mês na primeira dimensão das votações nominais (lado do PT negativo), comparada à metade central (sombreada) e à mediana do partido em que estava naquele mês.",
        "Their position each month on the first dimension of the roll calls (PT's side negative), against the middle half (shaded) and the median of the party they were in that month."), c2));
    box.append(g);
    lc.later(() => C.line(c1, {
      // Only the legislature the gap falls in: a band past the axis would still print its label (into the next card).
      x: "month", y: { min: 0, max: 1, format: (v) => pct(v) }, marks: GOVERNMENTS, bands: GAP.filter((b) => years.includes(+b.from.slice(0, 4))), height: 240,
      series: [
        { name: L("Partido com o governo", "Their party with the government"), color: css("--other"), width: 1.5, points: monthly.map((x) => [x.month, n(pg.get(`${partyKey(x.partido)}|${x.month}`)?.with_gov)]) },
        { name: L("Com o governo", "With the government"), color: C.slot(1), points: monthly.map((x) => [x.month, +x.n_votes >= 5 ? n(x.with_gov) : null]) },
        { name: L("Com o partido", "With their party"), color: C.slot(2), points: monthly.map((x) => [x.month, +x.n_votes >= 5 ? n(x.with_party) : null]) },
      ],
      empty: L("Nenhuma votação disputada nesta legislatura.", "No contested votes in this legislature."),
    }));
    const band = new Map(ideal.map((x) => [`${x.partido}|${x.month}`, x]));
    lc.later(() => C.line(c2, {
      x: "month", height: 240, y: { format: (v) => fmt(v, 1) }, marks: GOVERNMENTS,
      series: [
        { name: L("Mediana do partido", "Their party's median"), color: css("--other"), width: 1.5, band: members.map((x) => { const b = band.get(`${x.partido}|${x.month}`); return b ? [x.month, +b.q25, +b.q75] : [x.month, null, null]; }),
          points: members.map((x) => [x.month, n(band.get(`${x.partido}|${x.month}`)?.median)]) },
        { name: r.nome, color: C.slot(1), points: members.map((x) => [x.month, n(x.pc1)]) },
      ],
      empty: L("Fora do grafo de votos nesta legislatura.", "Not in the co-voting graph in this legislature."),
    }));

    // Co-voters
    const nb = (await got.nb).filter((x) => x.deputado_id === id);
    const t1 = el("div"), t2 = el("div"), g2 = el("div", { className: "grid2" });
    g2.append(card(L("Votos mais parecidos", "Votes most like theirs"),
      L("Deputados que votaram do mesmo jeito com mais frequência, nas votações disputadas em que ambos votaram (ao menos 50); a ordem favorece um histórico longo sobre um curto.",
        "Deputies who voted the same way most often, over the contested roll calls both voted on (at least 50); ranked so a long record outweighs a short one."), t1),
    card(L("Votos menos parecidos", "Votes least like theirs"), L("Deputados que votaram do jeito oposto com mais frequência.", "Deputies who voted the other way most often."), t2));
    box.append(g2);
    const nbCols = [{ key: "who", label: L("Deputado", "Deputy"), text: true, wrap: true, fmt: (v, x) => (x.other ? profileLink(x.other) : v) }, { key: "party", label: L("Partido", "Party"), text: true },
      { key: "n", label: L("Votos", "Votes"), fmt: (v) => fmt(v) }, { key: "concordancia", label: L("Mesmo voto", "Same way"), fmt: (v) => pct(v) }];
    const nbRows = (kind) => nb.filter((x) => x.tipo === kind).map((x) => { const o = D.byId.get(x.outro_id); return { who: o?.label || x.outro_id, party: o?.party || "", other: o, n: +x.n, concordancia: +x.concordancia }; });
    const near = nbRows("perto"), far = nbRows("longe");
    table(t1, near, nbCols, { search: false, pageSize: 8, name: `closest-${id}` });
    table(t2, far, nbCols, { search: false, pageSize: 8, name: `furthest-${id}` });
    if (near.length) {
      const own = near.filter((x) => x.other && x.other.party === r.party).length;
      g2.after(finding(L(`${own} dos ${near.length} deputados de voto mais parecido ${own === 1 ? "é" : "são"} do mesmo partido${own < near.length / 2 ? ": vota mais parecido com deputados de outros partidos do que com os colegas de partido" : ""}.`,
        `${own} of their ${near.length} closest co-voters ${own === 1 ? "is" : "are"} from their own party${own < near.length / 2 ? ": they vote more like other parties' deputies than like their own" : ""}.`)));
    }

    // Legislative work
    box.append(sectionHead("sec-atividade", L("Atividade legislativa", "Legislative work")));
    const [act, kinds, co] = await Promise.all([got.act, got.kinds, got.co]);
    const mineAct = act.filter((x) => x.deputado_id === id).map((x) => ({ month: x.month, votacoes: +x.votacoes, votos: +x.votos, autor: +x.autor, projetos: +x.projetos }));
    const chamber = new Map();
    for (const x of act) { if (+x.votacoes < 3) continue; if (!chamber.has(x.month)) chamber.set(x.month, []); chamber.get(x.month).push(+x.votos / +x.votacoes); }
    const actMonths = mineAct.map((x) => x.month);
    const c4 = chart(), c5 = chart(), g4 = el("div", { className: "grid2" });
    g4.append(card(L("Participação mês a mês", "Participation month by month"),
      L("A parcela das votações nominais de cada mês em que votou, contra a mediana de todos os deputados (cinza). Meses com menos de três votações ficam de fora.",
        "The share of each month's roll calls they voted in, against the median of all deputies (grey). Months with fewer than three roll calls are left out."), c4),
    card(L("Propostas apresentadas", "Proposals filed"), L("Por mês, como primeiro signatário: projetos (de lei, de emenda à Constituição, de decreto) e os demais documentos, como requerimentos e pareceres.",
      "By month, as first signer: bills (laws, constitutional amendments, decrees) and every other document, such as requests and opinions."), c5));
    box.append(g4);
    lc.later(() => C.line(c4, { x: "month", height: 220, y: { min: 0, max: 1, format: (v) => pct(v) }, series: [
      { name: L("Mediana dos deputados", "All deputies' median"), color: css("--other"), width: 1.5, points: actMonths.map((m) => [m, median(chamber.get(m) || [])]) },
      { name: r.nome, color: C.slot(1), points: mineAct.map((x) => [x.month, x.votacoes >= 3 ? x.votos / x.votacoes : null]) }],
      empty: L("Nenhuma votação nominal registrada para este deputado.", "No roll call on record for this deputy.") }));
    lc.later(() => C.stack(c5, { x: actMonths, height: 220, format: (v) => fmt(v), series: [
      { name: L("Projetos", "Bills"), color: C.slot(1), values: mineAct.map((x) => x.projetos) },
      { name: L("Outros documentos", "Other documents"), color: C.slot(3), values: mineAct.map((x) => x.autor - x.projetos) }].filter((x) => x.values.some((v) => v > 0)) }));
    const kk = new Map(kinds.filter((x) => x.deputado_id === id).map((x) => [x.tipo, x]));
    const c6 = chart(), t6 = el("div"), g5 = el("div", { className: "grid2" });
    g5.append(card(L("Que tipo de proposta", "What kind of proposal"),
      L("Como primeiro signatário, ao longo da legislatura; ao lado, quantas coassinou. Membros da Mesa Diretora assinam milhares de pareceres sobre pedidos de informação, que não são relatorias de projetos.",
        "As first signer, over the legislature; beside each, how many they co-signed. Members of the Câmara's board sign thousands of opinions on information requests, which are not bill rapporteurships."), c6),
    card(L("Com quem mais assina", "Who they sign with most"), L("Os deputados com quem mais dividiu propostas. Abaixo-assinados (mais de 50 signatários) ficam de fora.",
      "The deputies they shared the most proposals with. Signature drives (over 50 signers) are left out."), t6));
    box.append(g5);
    lc.later(() => C.bars(c6, { rows: KINDS.map(([k, label]) => ({ label, value: +(kk.get(k)?.autor || 0),
      note: L(`${fmt(+(kk.get(k)?.coautor || 0))} coassinadas`, `${fmt(+(kk.get(k)?.coautor || 0))} co-signed`), color: k === "projetos" ? C.slot(1) : css("--other") })), format: (v) => fmt(v), labelWidth: 240 }));
    const coRows = co.filter((x) => x.deputado_id === id).map((x) => { const o = D.byId.get(x.outro_id); return { who: o?.label || x.outro_id, other: o, party: o?.party || "", n: +x.n }; });
    if (coRows.length) table(t6, coRows, [{ key: "who", label: L("Deputado", "Deputy"), text: true, wrap: true, fmt: (v, x) => (x.other ? profileLink(x.other) : v) },
      { key: "party", label: L("Partido", "Party"), text: true }, { key: "n", label: L("Propostas em comum", "Shared proposals"), fmt: (v) => fmt(v) }], { search: false, pageSize: 8, name: `cosigners-${id}` });
    else t6.append(el("p", { className: "empty", textContent: L("Nenhuma proposta coassinada nesta legislatura.", "No co-signed proposal in this legislature.") }));

    // Amendments
    box.append(sectionHead("sec-emendas", L("Emendas", "Amendments")));
    const [E, dest, entes] = await Promise.all([got.em, got.dest, got.entes]);
    const mine = E.filter((x) => x.pessoa === r.pessoa), places = dest.filter((x) => x.pessoa === r.pessoa);
    const ente = new Map(entes.map((x) => [x.cod_ibge, x]));
    const budgetYears = [...new Set(E.map((x) => +x.ano))].sort((a, b) => a - b);
    const am = el("div");
    box.append(card(L("Para onde mandou dinheiro", "Where they sent money"), L(`O que destinou por meio de emendas aos orçamentos de ${budgetYears[0]} a ${budgetYears[budgetYears.length - 1]}, pelo valor pago até agora.`,
      `What they directed through amendments to the ${budgetYears[0]}–${budgetYears[budgetYears.length - 1]} budgets, as paid so far.`), am));
    if (!mine.length) am.append(el("p", { className: "empty", textContent: L("Nenhuma emenda ligada a este deputado nestes orçamentos.", "No amendment linked to this deputy for these budgets.") }));
    else {
      const sanc = r.sancoes_pago_sancionadas;
      tiles(am.appendChild(el("section", { className: "tiles" })), [
        { label: L("Emendas", "Amendments"), value: fmt(r.emendas), sub: L(`${brl(r.emendas_empenhado)} empenhados`, `${brl(r.emendas_empenhado)} committed`) },
        { label: L("Pago até agora", "Paid so far"), value: brl(r.emendas_pago), sub: L(`mediana do partido ${brl(med("emendas_pago"))}`, `party median ${brl(med("emendas_pago"))}`) },
        { label: L(`Pago em ${r.uf}`, `Paid in ${r.uf}`), value: pct(r.emendas_pago_estado), sub: L(`${pct(r.emendas_pago_nacional)} para programas nacionais`, `${pct(r.emendas_pago_nacional)} to national programmes`) },
        { label: L("Pago a empresas impedidas", "Paid to barred companies"), value: brl(sanc),
          sub: sanc ? L(`${plural(r.sancoes_empresas, "empresa", "empresas")} com sanção no CEIS ou no CNEP, todos os orçamentos desde 2015`, `${plural(r.sancoes_empresas, "company", "companies")} under a CEIS or CNEP sanction, every budget since 2015`)
            : L("todos os orçamentos desde 2015", "every budget since 2015") },
      ]);
      if (r.prefeito_mesmo_partido != null) am.append(finding(L(`${pct(r.prefeito_mesmo_partido)} do dinheiro que chegou a municípios foi para cidades cujo prefeito era do partido do deputado naquele ano. Por acaso, seria ${pct(r.prefeito_base)}: a parcela dos municípios de ${r.uf} governados pelo partido.`,
        `${pct(r.prefeito_mesmo_partido)} of the money that reached a town went to towns whose mayor was from their party that year. By chance it would be ${pct(r.prefeito_base)}: the share of ${r.uf}'s towns their party ran.`)));
      const c3 = chart(), mbox = chart(), side = el("div"), g3 = el("div", { className: "grid2", style: "margin-top:16px" });
      const home = UF_CODE[r.uf] || "";
      const paidAll = sum(places.map((x) => +x.pago)), outside = sum(places.filter((x) => x.uf !== r.uf).map((x) => +x.pago));
      const towns = places.filter((x) => x.municipio_ibge && x.municipio_ibge.startsWith(home));
      am.append(c3, g3);
      if (towns.length) g3.append(el("div", {}, el("h2", { textContent: L(`Onde o dinheiro chegou em ${r.uf}`, `Where the money landed in ${r.uf}`), style: "font-size:14px" }),
        el("p", { className: "note", textContent: L(`Pagamentos dessas emendas, pelo município do favorecido. ${pct(outside / Math.max(paidAll, 1))} foram para favorecidos fora de ${r.uf} (entre eles, órgãos federais em Brasília): veja a tabela.`,
          `Payments on these amendments, by the recipient's town. ${pct(outside / Math.max(paidAll, 1))} went to recipients outside ${r.uf} (Brasília's federal bodies among them): see the table.`) }), mbox), side);
      else g3.append(side, el("p", { className: "note", textContent: L(`Nenhum pagamento dessas emendas foi para um município de ${r.uf}, por isso não há mapa.`, `No payment on these amendments went to a town in ${r.uf}, so there is no map.`) }));
      lc.later(() => C.stack(c3, { x: budgetYears, height: 200, format: (v) => brl(v, 0),
        series: TYPES.map(([t, name]) => ({ name, color: typeColor(t), values: budgetYears.map((y) => sum(mine.filter((x) => +x.ano === y && x.tipo === t).map((x) => +x.pago))) })).filter((s) => s.values.some((v) => v > 0)) }));
      const [mun, ufs] = await got.maps;
      const val = new Map(towns.map((x) => [x.municipio_ibge, +x.pago]));
      const vmax = Math.max(...val.values(), 1);
      if (towns.length) lc.later(() => {
        const shapes = Object.fromEntries(Object.entries(mun.shapes).filter(([c]) => c.startsWith(home)));
        C.choropleth(mbox, { shapes, viewBox: mun.viewBox, outline: { [home]: ufs.shapes[home] }, outlineWidth: 1.2, fit: true, maxHeight: 440, value: (c) => val.get(c) ?? null, color: (v) => C.seq(0.1 + 0.9 * Math.sqrt(v / vmax)),
          tip: (c, v) => { const e = ente.get(c); return [el("strong", { textContent: e ? `${e.ente} (${e.uf})` : c }),
            el("div", { className: "row", textContent: v == null ? L("nada das emendas deste deputado", "nothing from their amendments") : L(`${brl(v)} pagos a favorecidos daqui`, `${brl(v)} paid to recipients here`) })]; },
          title: L("Onde chegou o dinheiro das emendas", "Where their amendment money landed") });
        C.colorKey(mbox, { color: (t) => C.seq(0.1 + 0.9 * t), from: brl(0), to: brl(vmax), label: L("pago, por município", "paid, by town") });
      });
      const placeName = (x) => (x.municipio_ibge ? `${ente.get(x.municipio_ibge)?.ente || x.municipio_ibge} (${x.uf})`
        : x.uf ? L(`Em algum lugar de ${x.uf} (município não identificado)`, `Somewhere in ${x.uf} (town not matched)`) : L("Local não informado", "No place given"));
      const ts = el("div");
      side.append(el("h2", { textContent: L("Todos os locais", "Every place"), style: "font-size:14px" }), ts);
      table(ts, places.map((x) => ({ place: placeName(x), pago: +x.pago })), [{ key: "place", label: L("Local", "Place"), text: true, wrap: true }, { key: "pago", label: L("Pago", "Paid"), fmt: (v) => brl(v) }],
        { pageSize: 10, sortBy: "pago", name: `places-${id}` });
    }

    // Campaign
    box.append(sectionHead("sec-campanha", L("Campanha", "Campaign")));
    const cp = el("div");
    box.append(card(L("A campanha que levou à Câmara", "The campaign that elected them"),
      L(`A campanha a deputado federal em ${leg === 57 ? 2022 : 2018}, como declarada à Justiça Eleitoral.`, `Their federal-deputy campaign in ${leg === 57 ? 2022 : 2018}, as declared to the electoral court.`), cp));
    if (r.campanha_total == null) cp.append(el("p", { className: "empty", textContent: L("Nenhuma campanha a deputado federal ligada a este deputado.", "No federal-deputy campaign linked to this deputy.") }));
    else {
      const result = RESULT[r.campanha_resultado] ?? r.campanha_resultado.toLowerCase();
      tiles(cp.appendChild(el("section", { className: "tiles" })), [
        { label: L("Arrecadado", "Raised"), value: brl(r.campanha_total), sub: L(`mediana do partido ${brl(med("campanha_total"))} · ${result}`, `party median ${brl(med("campanha_total"))} · ${result}`) },
        { label: L("Do partido", "From their party"), value: pct(r.campanha_partido_share), sub: L(`${brl(r.campanha_fefc)} do fundo público de campanha (FEFC)`, `${brl(r.campanha_fefc)} from the public campaign fund (FEFC)`) },
        { label: L("Recursos próprios", "Own money"), value: brl(r.campanha_proprios), sub: pct(r.campanha_proprios / r.campanha_total, 1) },
        { label: L("Doadores pessoas físicas", "Private donors"), value: fmt(r.campanha_doadores_pf),
          sub: r.grandes_doadores ? L(`${plural(r.grandes_doadores, "doador", "doadores")} de R$ 50 mil ou mais ${r.grandes_doadores === 1 ? "deu" : "deram"} ${brl(r.grandes_doadores_valor)}`, `${plural(r.grandes_doadores, "donor")} of R$50k+ gave ${brl(r.grandes_doadores_valor)}`)
            : L("nenhum deu R$ 50 mil ou mais", "none gave R$50k or more") },
      ]);
      const donors = (await got.donors).filter((x) => x.pessoa === r.pessoa);
      if (donors.length) {
        const td = el("div");
        cp.append(el("h2", { textContent: L("Doadores de R$ 50 mil ou mais", "Donors of R$50,000 or more"), style: "font-size:14px" }), td);
        table(td, donors.map((x) => ({ ...x, valor: +x.valor })), [{ key: "nome", label: L("Doador", "Donor"), text: true, wrap: true }, { key: "doador", label: L("CPF (mascarado)", "CPF (masked)"), text: true },
          { key: "valor", label: L("Doou", "Gave"), fmt: (v) => brl(v) }], { search: false, pageSize: 10, sortBy: "valor", name: `donors-${id}` });
      }
    }
  };
  showDeputy = show;
  const start = D.byId.has(params.get("dep")) ? params.get("dep") : [...D.rows].sort((a, b) => (b.n_votes || 0) - (a.n_votes || 0))[0].deputado_id;
  await show(start);
}

// ------------------------------------------------------------ compare

function spearman(xs, ys) {
  const rank = (v) => { const s = v.map((x, i) => [x, i]).sort((a, b) => a[0] - b[0]), r = new Array(v.length); let i = 0;
    while (i < s.length) { let j = i; while (j + 1 < s.length && s[j + 1][0] === s[i][0]) j++; for (let k = i; k <= j; k++) r[s[k][1]] = (i + j) / 2; i = j + 1; } return r; };
  const rx = rank(xs), ry = rank(ys), N = xs.length, m = (N - 1) / 2;
  const num_ = sum(rx.map((v, i) => (v - m) * (ry[i] - m))), den = Math.sqrt(sum(rx.map((v) => (v - m) ** 2)) * sum(ry.map((v) => (v - m) ** 2)));
  return den ? num_ / den : null;
}
const complete = (rows, a, b) => rows.filter((r) => r[a] != null && r[b] != null && !Number.isNaN(r[a]) && !Number.isNaN(r[b]) && (r.n_votes || 0) >= 50);

async function compare(root) {
  const D = await load(), lc = local();
  const may = D.rows.filter((r) => r.prefeito_mesmo_partido != null && r.emendas_pago >= 1e6);
  if (may.length) {
    const w = (k) => sum(may.map((r) => r[k] * r.emendas_pago)) / sum(may.map((r) => r.emendas_pago));
    const above = may.filter((r) => r.prefeito_mesmo_partido > r.prefeito_base).length;
    const cm = chart(), hi = Math.min(1, Math.ceil(10 * Math.max(...may.map((r) => r.prefeito_base), 0.2) + 0.5) / 10);
    root.append(card(L("Deputados mandam dinheiro para cidades governadas pelo próprio partido?", "Do deputies send money to towns their own party runs?"),
      L("Cada ponto é um deputado com R$ 1 milhão ou mais pagos. Na horizontal, a parcela dos municípios do estado cujo prefeito era do partido do deputado (o que ele mandaria para lá por acaso). Na vertical, a parcela do dinheiro de emendas que chegou a municípios e foi para um desses. Acima da linha tracejada, o deputado favoreceu prefeitos do próprio partido. Os partidos são identificados pelo nome no ano de cada pagamento.",
        "Each dot is a deputy with R$1 million or more paid. Across: the share of their state's towns whose mayor was from their party (what they would send there by chance). Up: the share of their amendment money that reached a town and went to one of those towns. Above the dashed line, a deputy favoured their party's mayors. Parties are matched by their name in the year of each payment."), cm,
      finding(L(`Ponderando pelo dinheiro, ${pct(w("prefeito_mesmo_partido"))} foram para municípios governados pelo partido do autor, contra ${pct(w("prefeito_base"))} por acaso; ${fmt(above)} de ${fmt(may.length)} deputados ficam acima da linha. Prefeitos do partido do deputado também podem pedir mais, ou governar cidades maiores: isto mede associação, não intenção.`,
        `Weighted by money, ${pct(w("prefeito_mesmo_partido"))} of the money went to towns run by the author's party, against ${pct(w("prefeito_base"))} by chance; ${fmt(above)} of ${fmt(may.length)} deputies sit above the line. Mayors from the deputy's party may also ask more, or run larger towns: this measures association, not intent.`))));
    later(() => C.scatter(cm, {
      points: may.map((r) => ({ x: r.prefeito_base, y: r.prefeito_mesmo_partido, label: r.nome, title: r.label, color: partyColor(r.partido), z: partyColor(r.partido) === css("--other") ? 0 : 1, id: r.deputado_id,
        rows: [L(`${brl(r.emendas_pago)} pagos`, `${brl(r.emendas_pago)} paid`)] })),
      x: { label: L("Parcela dos municípios do estado com prefeito do partido", "Their party's share of their state's towns"), format: (v) => pct(v), min: 0, max: hi },
      y: { label: L("Parcela do dinheiro para esses municípios", "Share of their money to those towns"), format: (v) => pct(v), min: 0, max: 1 },
      diagonal: { label: L("acaso", "chance") }, labels: 6, height: 380, legend: PARTY_LEGEND(), onClick: (p) => openProfile(p.id),
      table: { rows: may, cols: [{ key: "label", label: L("Deputado", "Deputy"), text: true }, { key: "prefeito_base", label: L("Por acaso", "By chance"), fmt: (v) => pct(v, 1) },
        { key: "prefeito_mesmo_partido", label: L("Real", "Actual"), fmt: (v) => pct(v, 1) }, { key: "emendas_pago", label: L("Pago", "Paid"), fmt: (v) => brl(v) }], name: "own-party-mayors" },
    }));
  }
  let xk = params.get("x") || "with_gov", yk = params.get("y") || "emendas_pago";
  if (!M[xk]) xk = "with_gov";
  if (!M[yk]) yk = "emendas_pago";
  const controls = el("div", { className: "controls" }), c1 = chart(), note = el("p", { className: "finding" });
  root.append(controls, card(L("Qualquer medida contra qualquer outra", "Any measure against any other"),
    L("Um ponto por deputado com 50 ou mais votos em votações disputadas na legislatura; PT e PL em cor. Clique em um ponto para abrir o perfil do deputado. Abaixo, a correlação de postos (Spearman): vai de −1 a 1 e é 0 quando as duas medidas não têm relação. Ela mede associação, não causa.",
      "One dot per deputy with 50 or more contested votes in the legislature; PT and PL in colour. Click a dot to open that deputy. Rank correlation (Spearman) below: from −1 to 1, 0 when the two are unrelated. It measures association, not cause."), c1, note));
  const draw = () => {
    lc.reset();
    controls.replaceChildren(
      select(L("Horizontal", "Across"), METRICS.map((m) => ({ value: m.key, label: m.label })), xk, (v) => { xk = v; setParam("x", v, "with_gov"); draw(); }),
      select(L("Vertical", "Up"), METRICS.map((m) => ({ value: m.key, label: m.label })), yk, (v) => { yk = v; setParam("y", v, "emendas_pago"); draw(); }));
    const rows = complete(D.rows, xk, yk), X = M[xk], Y = M[yk];
    lc.later(() => C.scatter(c1, {
      points: rows.map((r) => ({ x: r[xk], y: r[yk], label: r.nome, title: r.label, color: partyColor(r.partido), z: partyColor(r.partido) === css("--other") ? 0 : 1, id: r.deputado_id })),
      x: { label: X.label, format: X.fmt, min: X.min, max: X.max }, y: { label: Y.label, format: Y.fmt, min: Y.min, max: Y.max }, labels: 8, height: 400, legend: PARTY_LEGEND(),
      onClick: (p) => openProfile(p.id),
      table: { rows, cols: [{ key: "label", label: L("Deputado", "Deputy"), text: true }, { key: xk, label: X.label, fmt: X.fmt }, { key: yk, label: Y.label, fmt: Y.fmt }], name: `${xk}-vs-${yk}` },
    }));
    const rho = spearman(rows.map((r) => r[xk]), rows.map((r) => r[yk]));
    const within = [...D.parties.entries()].filter(([, ps]) => complete(ps, xk, yk).length >= 20).map(([p, ps]) => { const c = complete(ps, xk, yk); return `${p} ${fmt(spearman(c.map((r) => r[xk]), c.map((r) => r[yk])), 2)}`; });
    note.textContent = L(`Correlação de Spearman entre ${fmt(rows.length)} deputados: ${fmt(rho, 2)}.${within.length ? ` Dentro dos maiores partidos: ${within.join("; ")}.` : ""}`,
      `Spearman rank correlation over ${fmt(rows.length)} deputies: ${fmt(rho, 2)}.${within.length ? ` Within the larger parties: ${within.join(", ")}.` : ""}`);
  };
  draw();

  const c2 = chart();
  root.append(card(L("Como as medidas andam juntas", "How the measures move together"),
    L("Correlação de Spearman entre cada par de medidas, para deputados com 50 ou mais votos em votações disputadas. Azul: uma sobe quando a outra cai; vermelho: as duas sobem juntas.",
      "Spearman rank correlation between every pair of measures, over deputies with 50 or more contested votes. Blue: one rises as the other falls; red: they rise together."), c2));
  const keys = METRICS.map((m) => m.key);
  const corr = keys.map((a) => keys.map((b) => { const rows = complete(D.rows, a, b); return rows.length >= 30 ? spearman(rows.map((r) => r[a]), rows.map((r) => r[b])) : null; }));
  const short = SHORT;
  later(() => {
    C.heatmap(c2, { rows: keys.map((k) => short[k]), cols: keys.map((k) => short[k]), value: (i, j) => (i === j ? null : corr[i][j]), color: (v) => C.div(v), cell: 40, labelWidth: 130, colLabelHeight: 110, allColLabels: true,
      cellText: (v) => fmt(v, 1).replace(/^-0([.,]0)$/, "0$1"), dark: (v) => Math.abs(v) > 0.55, format: (v) => fmt(v, 2),
      tip: (i, j, v) => [el("strong", { textContent: `${METRICS[i].label} × ${METRICS[j].label}` }), el("div", { className: "row", textContent: `Spearman ${fmt(v, 2)}` })],
      table: { rows: keys.flatMap((a, i) => keys.slice(i + 1).map((b, k) => ({ a: M[a].label, b: M[b].label, rho: corr[i][i + 1 + k] }))),
        cols: [{ key: "a", label: L("Medida A", "Measure A"), text: true }, { key: "b", label: L("Medida B", "Measure B"), text: true }, { key: "rho", label: "Spearman", fmt: (v) => fmt(v, 2) }], name: "correlations" } });
    C.colorKey(c2, { color: (t) => C.div(2 * t - 1), from: "−1", to: "+1", label: L("correlação de postos", "rank correlation") });
  });
}

// ------------------------------------------------------------ parties

/** Mean of k over deputies, weighted by the amendment money they had paid. */
function wmean(rows, k) {
  const ok = rows.filter((r) => r[k] != null && r.emendas_pago > 0), W = sum(ok.map((r) => r.emendas_pago));
  return W ? sum(ok.map((r) => r[k] * r.emendas_pago)) / W : null;
}

async function parties(root) {
  const D = await load(), lc = local();
  let mk = params.get("pm") || "with_gov";
  if (!M[mk]) mk = "with_gov";
  const big = [...D.parties.entries()].filter(([, ps]) => ps.length >= 5).sort((a, b) => b[1].length - a[1].length);
  const controls = el("div", { className: "controls" }), c1 = chart();
  root.append(controls, card(L("Todos os deputados, por partido", "Every deputy, by party"),
    L("Um ponto por deputado, uma linha por partido com cinco ou mais deputados na legislatura; o traço escuro é a mediana do partido. Clique em um ponto para abrir o perfil do deputado.",
      "One dot per deputy, one row per party with five or more deputies in the legislature; the dark tick is the party's median. Click a dot to open that deputy."), c1));
  const draw = () => {
    lc.reset();
    controls.replaceChildren(select(L("Medida", "Measure"), METRICS.map((m) => ({ value: m.key, label: m.label })), mk, (v) => { mk = v; setParam("pm", v, "with_gov"); draw(); }));
    const m = M[mk];
    const rows = big.map(([p, ps]) => ({ label: `${p} (${ps.length})`, med: median(ps.map((r) => r[mk])), points: ps.filter((r) => r[mk] != null).map((r) => ({ x: r[mk], title: r.label, rows: [m.fmt(r[mk])], color: partyColor(p), id: r.deputado_id })) }))
      .sort((a, b) => (b.med ?? -Infinity) - (a.med ?? -Infinity));
    lc.later(() => C.strip(c1, { rows, x: { label: m.label, format: m.fmt, min: m.min, max: m.max }, labelWidth: 130, onClick: (p) => openProfile(p.id) }));
  };
  draw();
  const t = el("div");
  root.append(card(L("Partido a partido", "Party by party"),
    L("Medianas entre os deputados do partido que ficaram 12 meses ou mais na legislatura (suplentes que passaram pouco tempo não têm emendas próprias), pelo partido mais recente; prefeitos do partido e acaso são ponderados pelo dinheiro pago; empresas impedidas é um total.",
      "Medians over the party's deputies who served 12 months or more in the legislature (substitutes who sat briefly have no amendments of their own), by their latest party; own-party towns and chance are weighted by money paid; barred firms is a total."), t));
  table(t, big.concat([...D.parties.entries()].filter(([, ps]) => ps.length < 5)).map(([p, all]) => {
    const ps = all.filter((r) => (r.meses || 0) >= 12);
    return {
      party: p, deputies: all.length, regular: ps.length, with_party: median(ps.map((r) => r.with_party)), with_gov: median(ps.map((r) => r.with_gov)), pc1: median(ps.map((r) => r.pc1)),
      paid_med: median(ps.map((r) => r.emendas_pago)), camp: median(ps.map((r) => r.campanha_total)), from_party: median(ps.map((r) => r.campanha_partido_share)),
      may: wmean(all, "prefeito_mesmo_partido"), may0: wmean(all, "prefeito_base"), barred: sum(all.map((r) => r.sancoes_pago_sancionadas || 0)),
    };
  }), [
    { key: "party", label: L("Partido", "Party"), text: true }, { key: "deputies", label: L("Deputados", "Deputies"), fmt: (v) => fmt(v) }, { key: "regular", label: L("12+ meses", "12+ months"), fmt: (v) => fmt(v) },
    { key: "with_party", label: L("Com o partido", "With party"), fmt: (v) => pct(v) }, { key: "with_gov", label: L("Com o governo", "With gov."), fmt: (v) => pct(v) },
    { key: "pc1", label: L("Posição", "Position"), fmt: (v) => fmt(v, 2) }, { key: "paid_med", label: L("Emendas pagas", "Amendments paid"), fmt: (v) => brl(v) },
    { key: "may", label: L("Prefeitos do partido", "Own-party towns"), fmt: (v) => pct(v) }, { key: "may0", label: L("Acaso", "Chance"), fmt: (v) => pct(v) },
    { key: "camp", label: L("Campanha", "Campaign"), fmt: (v) => brl(v) }, { key: "from_party", label: L("Do partido", "From party"), fmt: (v) => pct(v) },
    { key: "barred", label: L("Empresas impedidas", "To barred firms"), fmt: (v) => brl(v) },
  ], { sortBy: "deputies", pageSize: 40, name: `parties-${leg}` });
}

// ------------------------------------------------------------ stand-outs

/** A list's title in this language, and its CSV file name from the English one (unchanged across languages). */
const titled = (pt, en) => ({ title: L(pt, en), file: en.toLowerCase().replace(/[^a-z]+/g, "-") });

async function outliers(root) {
  const D = await load();
  const active = D.rows.filter((r) => (r.n_votes || 0) >= 100);
  const total = D.rows.length;
  const excess = (r) => r.cross_share - (1 - ((D.parties.get(r.party)?.length || 1) - 1) / (total - 1));   // against the share of other parties' deputies
  const off = (r, k) => (r[k] == null || D.partyMedian(r.party, k) == null ? null : r[k] - D.partyMedian(r.party, k));
  const lists = [
    { ...titled("Os que menos seguem a orientação do partido", "Least loyal to their party's orientation"),
      note: L("Menor parcela de votos que seguem o líder do partido, entre deputados com 100 ou mais votos em votações disputadas.", "Lowest share of votes following their party leader, among deputies with 100 or more contested votes."),
      rows: active.filter((r) => (r.n_party || 0) >= 100).sort((a, b) => a.with_party - b.with_party), k: "with_party" },
    { ...titled("Mais distantes do partido no apoio ao governo", "Most out of step with their party on the government"),
      note: L("Os mais afastados da mediana de apoio ao governo do próprio partido, para mais ou para menos.", "Furthest from their party's median government support, either way."),
      rows: active.filter((r) => off(r, "with_gov") != null).sort((a, b) => Math.abs(off(b, "with_gov")) - Math.abs(off(a, "with_gov"))), k: "with_gov",
      xl: L("Vs. partido", "Vs party"), extra: (r) => `${off(r, "with_gov") > 0 ? "+" : "−"}${fmt(100 * Math.abs(off(r, "with_gov")), 0)} ${L("p.p.", "pts")}` },
    { ...titled("Pontes", "Bridges"),
      note: L("Laços de voto com deputados de outros partidos, acima do que o tamanho do partido sozinho explicaria (um deputado de um partido de três membros tem, por construção, quase só laços com outros partidos).",
        "Co-voting ties to other parties' deputies, above what their party's size alone would give (a deputy of a three-member party has almost only cross-party ties by construction)."),
      rows: active.filter((r) => r.cross_share != null).sort((a, b) => excess(b) - excess(a)), k: "cross_share", xl: L("Acima do esperado", "Over expected"), extra: (r) => `+${fmt(100 * excess(r), 0)} ${L("p.p.", "pts")}` },
    { ...titled("Mais dinheiro de emendas pago", "Most amendment money paid"),
      note: L("Valor pago até agora pelas emendas que apresentaram aos orçamentos da legislatura.", "Paid so far on the amendments they authored for the legislature's budgets."),
      rows: D.rows.filter((r) => r.emendas_pago).sort((a, b) => b.emendas_pago - a.emendas_pago), k: "emendas_pago" },
    { ...titled("Mais dinheiro de emendas enviado para fora do estado", "Most amendment money sent outside their state"),
      note: L("Parcela paga a outros estados (sem contar programas nacionais), entre deputados com R$ 1 milhão ou mais pagos.", "Share paid to other states (national programmes excluded), deputies with R$1 million or more paid."),
      rows: D.rows.filter((r) => r.emendas_pago >= 1e6 && r.emendas_pago_estado != null).sort((a, b) => (1 - b.emendas_pago_estado - b.emendas_pago_nacional) - (1 - a.emendas_pago_estado - a.emendas_pago_nacional)), k: "emendas_pago",
      xl: L("Fora do estado", "Outside the state"), extra: (r) => pct(1 - r.emendas_pago_estado - r.emendas_pago_nacional) },
    { ...titled("Mais dinheiro a prefeitos do partido, acima do acaso", "Most money to towns their party runs, above chance"),
      note: L("Parcela do dinheiro a municípios que foi para cidades com prefeito do partido naquele ano, menos a parcela dos municípios do estado governados pelo partido. Deputados com R$ 5 milhões ou mais pagos.",
        "Share of their town money to towns whose mayor was from their party that year, minus the share of their state's towns their party ran. Deputies with R$5 million or more paid."),
      rows: D.rows.filter((r) => r.prefeito_excesso != null && r.emendas_pago >= 5e6).sort((a, b) => b.prefeito_excesso - a.prefeito_excesso), k: "prefeito_mesmo_partido", xl: L("Acaso", "Chance"), extra: (r) => pct(r.prefeito_base) },
    { ...titled("Emendas pagas a empresas impedidas", "Amendment money paid to barred companies"),
      note: L("Pago a empresas enquanto estavam sob sanção do CEIS ou do CNEP, todos os orçamentos desde 2015 (veja a página de Sanções).", "Paid to companies while under a CEIS or CNEP sanction, every budget since 2015 (see the Sanctions page)."),
      rows: D.rows.filter((r) => r.sancoes_pago_sancionadas > 0).sort((a, b) => b.sancoes_pago_sancionadas - a.sancoes_pago_sancionadas), k: "sancoes_pago_sancionadas",
      xl: L("Empresas", "Firms"), extra: (r) => fmt(r.sancoes_empresas) },
    { ...titled("Mais recursos próprios na campanha", "Most of their own money in their campaign"),
      note: L("Autofinanciamento da campanha que levou à Câmara. A lei limita a 10% do teto de gastos do cargo, por isso vários aparecem com o mesmo valor.",
        "Self-funding of the campaign that elected them. The law caps it at 10% of the office's spending limit, which is why several sit at the same amount."),
      rows: D.rows.filter((r) => r.campanha_proprios > 0).sort((a, b) => b.campanha_proprios - a.campanha_proprios), k: "campanha_proprios",
      xl: L("Do arrecadado", "Of money raised"), extra: (r) => L(`${pct(r.campanha_proprios / r.campanha_total)} de ${brl(r.campanha_total)}`, `${pct(r.campanha_proprios / r.campanha_total)} of ${brl(r.campanha_total)}`) },
    { ...titled("Mais dinheiro de grandes doadores", "Most money from large donors"),
      note: L("De doadores pessoas físicas que deram R$ 50 mil ou mais à campanha.", "From private donors who gave their campaign R$50,000 or more."),
      rows: D.rows.filter((r) => r.grandes_doadores_valor > 0).sort((a, b) => b.grandes_doadores_valor - a.grandes_doadores_valor), k: "grandes_doadores_valor",
      xl: L("Doadores", "Donors"), extra: (r) => fmt(r.grandes_doadores) },
  ];
  const g = el("div", { className: "grid2" });
  for (const x of lists) {
    const t = el("div");
    g.append(el("div", { className: "card" }, el("h2", { textContent: x.title }), el("p", { className: "note", textContent: x.note }), t));
    table(t, x.rows.slice(0, 10).map((r, i) => ({ i: i + 1, r, who: r.label, v: r[x.k], extra: x.extra ? x.extra(r) : "" })), [
      { key: "i", label: "#" }, { key: "who", label: L("Deputado", "Deputy"), text: true, wrap: true, fmt: (v, y) => profileLink(y.r) }, { key: "v", label: SHORT[x.k], fmt: M[x.k].money ? (v) => brl(v) : M[x.k].fmt },
      ...(x.extra ? [{ key: "extra", label: x.xl }] : []),
    ], { search: false, pageSize: 10, name: x.file });
  }
  root.append(g);
}

// ------------------------------------------------------------ page

const SECTIONS = { profile, compare, parties, outliers };
const shown = new Set();
function render(name) {
  const inner = el("div");
  $(`#tab-${name}`).replaceChildren(inner);
  return guard(inner, () => SECTIONS[name](inner));
}
function legControl() {
  const latest = LEGS[LEGS.length - 1];
  $("#legislature").replaceChildren(select(L("Legislatura", "Legislature"), [...LEGS].reverse().map((l) => ({ value: l, label: LEG_NAME[l] || L(`${l}ª legislatura`, `${l}th legislature`) })), leg, (v) => {
    leg = +v; setParam("leg", v, String(latest)); setParam("dep", null); showDeputy = null; redraws.length = 0; legControl(); shown.forEach(render);
  }));
}

(async () => {
  LEGS = (await data("site/deputados/legislaturas.csv")).map((r) => +r.legislatura).sort((a, b) => a - b);
  leg = LEGS.includes(+params.get("leg")) ? +params.get("leg") : LEGS[LEGS.length - 1];
  legControl();
  tabs((name) => { shown.add(name); render(name); });
  onResize(() => redraws.forEach((f) => f()));
})();
