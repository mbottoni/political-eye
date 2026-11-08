// Deputies ranked: an index of recorded work, with weights the reader chooses. Red flags are shown, never scored.
import { $, brl, css, data, el, fmt, guard, onResize, params, pct, setParam, table } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L } from "../lib/i18n.js";
import { setupPage } from "../lib/page.js";
import { avatar, partyKey } from "../lib/search.js";

setupPage();

const MIN_MONTHS = 12;
// Who presided over the Câmara (deputy id): the president votes only to break a tie.
const SPEAKERS = { 56: ["74693", "160541"], 57: ["160541", "160674"] };
// The criteria, each a 0–100 score: the deputy's percentile among ranked deputies (allowance: within their state, reversed).
const CRITERIA = [
  { key: "presenca", label: L("Participação nas votações", "Roll-call participation"), short: L("Participação", "Participation"), color: "--s1", w: 3,
    help: L("A parcela das votações nominais em que votou, nos meses de mandato.", "The share of roll calls they voted in, over their months in office."), fmt: (v) => pct(v) },
  { key: "projetos_autor", label: L("Projetos apresentados", "Bills filed"), short: L("Projetos", "Bills"), color: "--s3", w: 2,
    help: L("Projetos de lei, PECs e decretos legislativos como primeiro signatário.", "Bills, constitutional amendments and legislative decrees as first signer."), fmt: (v) => fmt(v) },
  { key: "relatorias", label: L("Pareceres de relator", "Rapporteur opinions"), short: L("Pareceres", "Opinions"), color: "--s4", w: 2,
    help: L("Pareceres e substitutivos assinados como relator. Membros da Mesa assinam milhares de pareceres administrativos.", "Opinions and substitutes signed as rapporteur. Board members sign thousands of administrative ones."), fmt: (v) => fmt(v) },
  { key: "economia", label: L("Economia na cota parlamentar", "Office-allowance thrift"), short: L("Cota por mês", "Allowance a month"), color: "--s2", w: 3,
    help: L("Gasto mensal da cota comparado aos deputados do mesmo estado: quem gasta menos tem nota maior.", "Monthly allowance spending against deputies of the same state: spending less scores higher."), fmt: (v, r) => (r.cota_mes == null ? "–" : `${brl(r.cota_mes, 0)}/${L("mês", "month")}`) },
  { key: "cross_share", label: L("Diálogo com outros partidos", "Ties across parties"), short: L("Diálogo", "Ties across"), color: "--s7", w: 0,
    help: L("A parcela dos laços de voto com deputados de outros partidos. Opcional: votar com o próprio partido não é defeito.", "The share of co-voting ties with other parties' deputies. Optional: voting with one's party is no fault."), fmt: (v) => pct(v) },
  { key: "propostas_coautor", label: L("Coautoria de propostas", "Proposals co-signed"), short: L("Coautoria", "Co-signed"), color: "--s5", w: 0,
    help: L("Propostas de outros deputados que coassinou. Opcional: assinar é fácil.", "Other deputies' proposals they co-signed. Optional: signing is easy."), fmt: (v) => fmt(v) },
];
const PRESETS = [
  { id: "equilibrado", label: L("Equilibrado", "Balanced"), w: [3, 2, 2, 3, 0, 0] },
  { id: "assiduidade", label: L("Assiduidade", "Attendance"), w: [5, 0, 0, 0, 0, 0] },
  { id: "producao", label: L("Produção legislativa", "Legislative output"), w: [1, 4, 4, 0, 0, 1] },
  { id: "economia", label: L("Economia", "Thrift"), w: [0, 0, 0, 5, 0, 0] },
  { id: "dialogo", label: L("Diálogo", "Dialogue"), w: [2, 1, 1, 1, 4, 1] },
];
const FLAG = { emendas_impedidas: L("emendas a impedidas", "amendments to barred firms"), campanha_emendas: L("fornecedor de campanha", "campaign supplier"),
  concentracao: L("emendas concentradas", "concentrated amendments") };
const TAB = { emendas_impedidas: "barred", campanha_emendas: "campaign", concentracao: "concentration" };

const median = (xs) => { const v = xs.filter((x) => x != null && !Number.isNaN(x)).sort((a, b) => a - b); return v.length ? (v[Math.floor((v.length - 1) / 2)] + v[Math.ceil((v.length - 1) / 2)]) / 2 : null; };
const num = (v) => (v === "" || v == null ? null : +v);
/** Percentile rank (0–100) of v among xs, ties sharing the middle. */
const pctile = (xs, v) => (v == null || !xs.length ? null : (100 * (xs.filter((x) => x < v).length + xs.filter((x) => x === v).length / 2)) / xs.length);

async function load(leg) {
  const rows = await data(`site/ranking/deputados_${leg}.csv`);
  for (const r of rows) {
    for (const k of ["meses", "presenca", "projetos_autor", "relatorias", "propostas_coautor", "cross_share", "cota_mes", "cota_mes_uf", "cota_divulgacao", "votacoes_mandato"]) r[k] = num(r[k]);
    r.party = partyKey(r.partido);
    r.speaker = (SPEAKERS[leg] || []).includes(r.deputado_id);
    r.ranked = (r.meses || 0) >= MIN_MONTHS;
  }
  // Scores among the ranked: participation leaves the Speaker out; the allowance compares each state's deputies.
  const ranked = rows.filter((r) => r.ranked);
  const pool = (k) => ranked.filter((r) => r[k] != null && !(k === "presenca" && r.speaker)).map((r) => r[k]);
  const pools = Object.fromEntries(["presenca", "projetos_autor", "relatorias", "cross_share", "propostas_coautor"].map((k) => [k, pool(k)]));
  const byUf = new Map();
  for (const r of ranked) if (r.cota_mes != null && r.cota_mes > 0) { if (!byUf.has(r.uf)) byUf.set(r.uf, []); byUf.get(r.uf).push(r.cota_mes); }
  for (const r of rows) {
    r.s = {};
    for (const k of Object.keys(pools)) r.s[k] = k === "presenca" && r.speaker ? null : pctile(pools[k], r[k]);
    const st = byUf.get(r.uf) || [];
    r.s.economia = r.cota_mes != null && r.cota_mes > 0 && st.length >= 3 ? 100 - pctile(st, r.cota_mes) : null;
  }
  return rows;
}

const scoreOf = (r, w) => {
  let tot = 0, wt = 0;
  CRITERIA.forEach((c, i) => { const s = r.s[c.key]; if (s != null && w[i] > 0) { tot += w[i] * s; wt += w[i]; } });
  return wt ? tot / wt : null;
};

async function main() {
  const root = $("#app"), res = await data("site/ranking/resumo.json");
  const LEGS = res.legislaturas || [57];
  let leg = LEGS.includes(+params.get("leg")) ? +params.get("leg") : LEGS[0];
  const fromUrl = (params.get("w") || "").split(",").map(Number);
  let w = fromUrl.length === CRITERIA.length && fromUrl.every((x) => x >= 0 && x <= 5) ? fromUrl : CRITERIA.map((c) => c.w);
  let party = params.get("partido") || "", uf = params.get("uf") || "";

  // Controls: the legislature, the weights and their presets, and filters.
  const legSel = el("select", {}, ...LEGS.map((l) => el("option", { value: l, textContent: l === 57 ? L("57ª legislatura (2023–2027)", "57th legislature (2023–2027)") : L("56ª legislatura (2019–2023)", "56th legislature (2019–2023)"), selected: l === leg })));
  const partySel = el("select"), ufSel = el("select");
  const presets = el("div", { className: "presets", role: "group", "aria-label": L("Perfis de peso", "Weight presets") });
  const outputs = [], sliders = CRITERIA.map((c, i) => {
    const out = el("output", { textContent: w[i] });
    const s = el("input", { type: "range", min: 0, max: 5, step: 1, value: w[i], "aria-label": c.label });
    s.addEventListener("input", () => { w[i] = +s.value; out.textContent = s.value; changed(); });
    outputs.push(out);
    return el("label", { className: "weight" }, el("span", { textContent: c.label }), out, s, el("small", { textContent: c.help }));
  });
  const paintPresets = () => presets.replaceChildren(el("span", { className: "hint", textContent: L("Perfis:", "Presets:"), style: "font-size:13px;align-self:center" }),
    ...PRESETS.map((p) => el("button", { type: "button", textContent: p.label, "aria-pressed": String(p.w.join() === w.join()),
      on: { click: () => { w = [...p.w]; sliders.forEach((s, i) => { s.querySelector("input").value = w[i]; outputs[i].textContent = w[i]; }); changed(); } } })));
  const weightsCard = el("div", { className: "card wide" }, el("h2", { textContent: L("Quanto cada critério vale", "How much each criterion counts") }),
    el("p", { className: "note", textContent: L("De 0 (não conta) a 5. A nota de cada critério vai de 0 a 100: a posição do deputado entre os ranqueados. A nota final é a média ponderada.",
      "From 0 (doesn't count) to 5. Each criterion's score runs 0–100: the deputy's percentile among those ranked. The final score is the weighted average.") }),
    presets, el("div", { className: "weights" }, ...sliders));
  root.append(el("div", { className: "controls" }, el("label", {}, L("Legislatura", "Legislature"), legSel), el("label", {}, L("Partido", "Party"), partySel), el("label", {}, "UF", ufSel)), weightsCard);

  const c1 = el("div", { className: "chart" }), c2 = el("div", { className: "chart" }), tb = el("div");
  const keyline = el("p", { className: "keyline" });
  const g = el("div", { className: "grid2" },
    el("div", { className: "card" }, el("h2", { textContent: L("Nota mediana por partido", "Median score by party") }), el("p", { className: "note", textContent: L("Partidos com ao menos 5 deputados ranqueados, com os pesos escolhidos acima.", "Parties with at least 5 ranked deputies, under the weights chosen above.") }), c1),
    el("div", { className: "card" }, el("h2", { textContent: L("Como as notas se distribuem", "How the scores spread") }), el("p", { className: "note", textContent: L("Todos os deputados ranqueados, com os pesos escolhidos acima.", "Every ranked deputy, under the weights chosen above.") }), c2));
  root.append(el("div", { className: "card wide" }, el("h2", { textContent: L("O ranking", "The ranking") }),
    el("p", { className: "note", textContent: L("Clique em um nome para ver o perfil completo do deputado. As barrinhas mostram a nota de cada critério; um traço tracejado é um critério sem dado.",
      "Click a name for the deputy's full profile. The small bars show each criterion's score; a dashed one has no data.") }), keyline, tb), g);

  let rows = [], t = null;
  const draw = () => {
    for (const r of rows) r.score = r.ranked ? scoreOf(r, w) : null;
    const shown = rows.filter((r) => r.ranked && r.score != null).sort((a, b) => b.score - a.score);
    shown.forEach((r, i) => { r.rank = i + 1; });
    for (const r of rows) if (!r.ranked) r.rank = null;
    const view = rows.filter((r) => (!party || r.party === party) && (!uf || r.uf === uf));
    const cols = [
      { key: "rank", label: "#", fmt: (v) => el("span", { className: "rank-n", textContent: v ?? "–" }) },
      { key: "nome", label: L("Deputado", "Deputy"), text: true, fmt: (v, r) => el("span", { className: "who" }, avatar(r.deputado_id, r.nome, 34),
        el("span", {}, el("a", { href: `../deputados/?tab=profile&leg=${leg}&dep=${r.deputado_id}`, textContent: r.nome }),
          el("small", { textContent: `${r.party}-${r.uf}${r.speaker ? L(" · presidente da Câmara", " · Speaker") : ""}${r.ranked ? "" : L(` · ${fmt(r.meses)} meses, não ranqueado`, ` · ${fmt(r.meses)} months, not ranked`)}` }))) },
      { key: "score", label: L("Nota", "Score"), fmt: (v) => el("span", { className: "score" }, el("i", { style: `--w:${v ?? 0}%` }), el("b", { textContent: v == null ? "–" : fmt(v, 0) })) },
      { key: "dims", label: L("Critérios", "Criteria"), sort: (r) => r.score, fmt: (v, r) => el("span", { className: "dims", title: CRITERIA.map((c) => `${c.label}: ${r.s[c.key] == null ? "–" : fmt(r.s[c.key], 0)}`).join("\n") },
        ...CRITERIA.filter((c, i) => w[i] > 0).map((c) => el("i", { className: r.s[c.key] == null ? "na" : "", style: `--c:var(${c.color});height:${Math.max(8, r.s[c.key] ?? 0)}%` }))) },
      ...CRITERIA.filter((c, i) => w[i] > 0).map((c) => ({ key: c.key, label: c.short, sort: (r) => r.s[c.key], fmt: (v, r) => c.fmt(r[c.key], r) })),
      { key: "alertas", label: L("Sinais de alerta", "Red flags"), text: true, fmt: (v) => (v ? el("span", {}, ...v.split(";").map((k) => el("a", { className: "flagb", href: `../alertas/?tab=${TAB[k]}`, textContent: FLAG[k] || k, style: "margin:0 4px 4px 0" }))) : "") },
    ];
    keyline.replaceChildren(...CRITERIA.filter((c, i) => w[i] > 0).map((c) => el("span", {}, el("i", { style: `background:var(${c.color})` }), c.label)));
    t = table(tb, view, cols, { sortBy: "score", pageSize: 25, name: `deputies-ranked-${leg}` });
    // Parties and the spread.
    const byP = new Map();
    for (const r of shown) { if (!byP.has(r.party)) byP.set(r.party, []); byP.get(r.party).push(r.score); }
    const pr = [...byP].filter(([, xs]) => xs.length >= 5).map(([p, xs]) => ({ label: p, value: median(xs), note: L(`${xs.length} deputados`, `${xs.length} deputies`),
      color: p === party ? css("--critical") : css("--accent") })).sort((a, b) => b.value - a.value);
    C.bars(c1, { rows: pr, format: (v) => fmt(v, 0), max: 100 });
    C.histogram(c2, { values: shown.map((r) => r.score), domain: [0, 100], bins: 20, format: (v) => fmt(v, 0), unit: L("deputados", "deputies"), xLabel: L("nota", "score"), height: 220,
      refs: party && byP.has(party) ? [{ x: median(byP.get(party)), label: L(`mediana do ${party}`, `${party} median`) }] : [] });
    paintPresets();
  };
  const changed = () => { setParam("w", w.join(), CRITERIA.map((c) => c.w).join()); draw(); };
  const filters = () => {
    const ps = [...new Set(rows.filter((r) => r.ranked).map((r) => r.party))].sort(), us = [...new Set(rows.map((r) => r.uf))].filter(Boolean).sort();
    if (party && !ps.includes(party)) party = "";
    partySel.replaceChildren(el("option", { value: "", textContent: L("Todos os partidos", "Every party") }), ...ps.map((p) => el("option", { value: p, textContent: p, selected: p === party })));
    ufSel.replaceChildren(el("option", { value: "", textContent: L("Todos os estados", "Every state") }), ...us.map((u) => el("option", { value: u, textContent: u, selected: u === uf })));
  };
  partySel.addEventListener("change", () => { party = partySel.value; setParam("partido", party, ""); draw(); });
  ufSel.addEventListener("change", () => { uf = ufSel.value; setParam("uf", uf, ""); draw(); });
  legSel.addEventListener("change", async () => { leg = +legSel.value; setParam("leg", leg, String(LEGS[0])); rows = await load(leg); filters(); draw(); });
  rows = await load(leg);
  filters();
  draw();
  onResize(draw);
}

guard($("#app"), main);
