// Deputies across sources, the election tab: what the general election at the end of a legislature did to its
// deputies (re-elected, lost, ran for another office, stayed out), how those groups compare, and the Chamber it
// chose. Also the line on each deputy's profile. Data: data/site/eleicao/ (politicaleye/site/eleicao.py).
import { brl, css, data, el, fmt, pct, params, setParam, table, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L, month } from "../lib/i18n.js";

const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const head = (text) => el("h3", { className: "dsec", textContent: text });
const num = (v) => (v === "" || v == null ? null : +v);
const median = (xs) => { const v = xs.filter((x) => x != null && !Number.isNaN(x)).sort((a, b) => a - b); return v.length ? (v[Math.floor((v.length - 1) / 2)] + v[Math.ceil((v.length - 1) / 2)]) / 2 : null; };
const MIN_MONTHS = 12;

// The outcomes, in a fixed order with fixed colours (categorical slots; grey for those who did not run or have no result).
const GROUPS = [
  { key: "reeleito", label: L("Reeleitos", "Re-elected"), color: () => C.slot(1) },
  { key: "nao_reeleito", label: L("Não reeleitos", "Not re-elected"), color: () => C.slot(2) },
  { key: "outro_eleito", label: L("Eleitos para outro cargo", "Won another office"), short: L("Outro cargo, eleitos", "Other office, won"), color: () => C.slot(3) },
  { key: "outro_derrotado", label: L("Derrotados em outro cargo", "Lost a race for another office"), short: L("Outro cargo, derrotados", "Other office, lost"), color: () => C.slot(4) },
  { key: "nao_concorreu", label: L("Não concorreram", "Did not run"), color: () => css("--other") },
  { key: "sem_resultado", label: L("Sem resultado no TSE", "No result at TSE"), short: L("Sem resultado", "No result"), color: () => css("--muted") },
];
const G = Object.fromEntries(GROUPS.map((g) => [g.key, g]));
const ORIGINS = [
  { key: "reeleito", label: L("Reeleitos", "Re-elected"), one: L("Reeleito", "Re-elected"), color: () => C.slot(1) },
  { key: "ex_deputado", label: L("Voltam após um intervalo", "Back after a break"), one: L("Volta após um intervalo", "Back after a break"), color: () => C.slot(6) },
  { key: "novo", label: L("Novos na Câmara", "New to the Câmara"), one: L("Novo na Câmara", "New to the Câmara"), color: () => C.slot(5) },
];
const O = Object.fromEntries(ORIGINS.map((o) => [o.key, o]));

// TSE's offices and results, in words (Portuguese by the candidate's gender).
const OFFICE = {
  "Deputado Federal": [L("deputado federal", "federal deputy"), L("deputada federal", "federal deputy")],
  Senador: [L("senador", "senator"), L("senadora", "senator")],
  Governador: [L("governador", "governor"), L("governadora", "governor")],
  "Vice-Governador": [L("vice-governador", "deputy governor"), L("vice-governadora", "deputy governor")],
  "1º Suplente": [L("1º suplente de senador", "first Senate substitute"), L("1ª suplente de senador", "first Senate substitute")],
  "2º Suplente": [L("2º suplente de senador", "second Senate substitute"), L("2ª suplente de senador", "second Senate substitute")],
  "Deputado Estadual": [L("deputado estadual", "state deputy"), L("deputada estadual", "state deputy")],
  "Deputado Distrital": [L("deputado distrital", "district deputy"), L("deputada distrital", "district deputy")],
  Presidente: [L("presidente", "president"), L("presidenta", "president")],
  "Vice-Presidente": [L("vice-presidente", "vice-president"), L("vice-presidenta", "vice-president")],
};
// How many of them won an office, in the plural (counts of people, so the generic form).
const OFFICES = {
  Senador: [L("senador", "senator"), L("senadores", "senators")], Governador: [L("governador", "governor"), L("governadores", "governors")],
  "Vice-Governador": [L("vice-governador", "deputy governor"), L("vice-governadores", "deputy governors")],
  "1º Suplente": [L("suplente de senador", "Senate substitute"), L("suplentes de senador", "Senate substitutes")],
  "2º Suplente": [L("suplente de senador", "Senate substitute"), L("suplentes de senador", "Senate substitutes")],
  "Deputado Estadual": [L("deputado estadual", "state deputy"), L("deputados estaduais", "state deputies")],
  "Deputado Distrital": [L("deputado distrital", "district deputy"), L("deputados distritais", "district deputies")],
  Presidente: [L("presidente", "president"), L("presidentes", "presidents")], "Vice-Presidente": [L("vice-presidente", "vice-president"), L("vice-presidentes", "vice-presidents")],
};
const office = (r) => (OFFICE[r.cargo] || [r.cargo.toLowerCase(), r.cargo.toLowerCase()])[r.genero === "FEMININO" ? 1 : 0];
const fem = (r, m, f) => (r.genero === "FEMININO" ? f : m);
const HOW = { "ELEITO POR QP": L("pelo quociente partidário", "on the party quotient"), "ELEITO POR MÉDIA": L("pelas sobras", "on the remainders") };
const RESULT = { ELEITO: L("eleito", "elected"), "ELEITO POR QP": L("eleito por QP", "elected (quotient)"), "ELEITO POR MÉDIA": L("eleito por média", "elected (remainders)"),
  SUPLENTE: L("suplente", "substitute"), "NÃO ELEITO": L("não eleito", "not elected"), "": L("sem resultado", "no result") };
const LEG_ORD = (l) => L(`${l}ª`, `${l}th`);

// What the outcomes are compared on.
const MEASURES = [
  { key: "indice", label: L("Índice do ranking (pesos padrão)", "Ranking index (default weights)"), short: L("Índice", "Index"), fmt: (v) => fmt(v, 0), min: 0, max: 100 },
  { key: "presenca", label: L("Participação nas votações nominais", "Roll-call participation"), short: L("Participação", "Participation"), fmt: (v) => pct(v), min: 0, max: 1 },
  { key: "emendas_pago", label: L("Emendas pagas", "Amendment money paid"), short: L("Emendas pagas", "Amendments paid"), fmt: (v) => brl(v, 0), money: true },
  { key: "prefeito_mesmo_partido", label: L("Parcela das emendas para municípios com prefeito do partido", "Share of town money to towns their party runs"), short: L("Prefeitos do partido", "Own-party towns"), fmt: (v) => pct(v), min: 0, max: 1 },
  { key: "prefeito_excesso", label: L("…acima do acaso (pontos percentuais)", "…above chance (percentage points)"), short: L("Acima do acaso", "Above chance"), fmt: (v) => fmt(100 * v, 0) },
  { key: "prefeito_mesmo_partido_valor", label: L("Dinheiro de emendas para prefeitos do partido", "Amendment money to towns their party runs"), short: L("R$ a prefeitos do partido", "R$ to own-party towns"), fmt: (v) => brl(v, 0), money: true },
  { key: "campanha_total", label: L("Dinheiro arrecadado na campanha", "Campaign money raised"), short: L("Campanha", "Campaign"), fmt: (v) => brl(v, 0), money: true },
];
const M = Object.fromEntries(MEASURES.map((m) => [m.key, m]));
const NUMERIC = ["meses", "campanha_total", "indice", "presenca", "emendas_pago", "prefeito_mesmo_partido", "prefeito_base", "prefeito_mesmo_partido_valor"];

const cache = new Map();
/** The legislature's election: the summary, every deputy of the legislature, and the deputies it elected. */
async function load(leg) {
  if (!cache.has(leg)) cache.set(leg, (async () => {
    const res = await data("site/eleicao/resumo.json"), b = res.builds?.[leg];
    if (!b) return null;
    const [rows, elected, parties] = await Promise.all([data(`site/eleicao/deputados_${leg}.csv`), data(`site/eleicao/eleitos_${b.eleicao}.csv`), data(`site/eleicao/partidos_${b.eleicao}.csv`)]);
    for (const r of rows) {
      for (const k of NUMERIC) r[k] = num(r[k]);
      r.prefeito_excesso = r.prefeito_mesmo_partido == null || r.prefeito_base == null ? null : r.prefeito_mesmo_partido - r.prefeito_base;
      r.party = r.partido_eleicao === "S.PART." || !r.partido_eleicao ? L("sem partido", "no party") : r.partido_eleicao;
      r.label = `${r.nome} (${r.party}-${r.uf})`;
    }
    for (const r of elected) r.campanha_total = num(r.campanha_total);
    for (const p of parties) for (const k of ["eleitos_antes", "em_exercicio", "eleitos", "reeleito", "ex_deputado", "novo"]) p[k] = +p[k];
    return { b, rows, byId: new Map(rows.map((r) => [r.deputado_id, r])), elected, parties };
  })());
  return cache.get(leg);
}

// ------------------------------------------------------------ the profile's line

/** Words for one deputy's outcome: [chip, sentence], or null when the legislature has no election built. */
export async function electionNote(leg, deputadoId) {
  const E = await load(leg);
  const r = E?.byId.get(deputadoId);
  if (!r) return null;
  const y = E.b.eleicao, where = r.candidatura_partido ? `(${r.candidatura_partido}-${r.candidatura_uf})` : "";
  const money = r.campanha_total ? L(`; arrecadou ${brl(r.campanha_total)}`, `; raised ${brl(r.campanha_total)}`) : "";
  const sub = r.resultado === "SUPLENTE" ? L("; ficou como suplente", "; now a substitute") : "";
  const text = {
    reeleito: L(`${fem(r, "Reeleito", "Reeleita")} ${office(r)} ${where}${HOW[r.resultado] ? `, ${HOW[r.resultado]}` : ""}${money}.`,
      `Re-elected federal deputy ${where}${HOW[r.resultado] ? `, ${HOW[r.resultado]}` : ""}${money}.`),
    nao_reeleito: L(`Concorreu de novo à Câmara ${where} e não se reelegeu${sub}${money}.`, `Ran for the Câmara again ${where} and was not re-elected${sub}${money}.`),
    outro_eleito: L(`${fem(r, "Eleito", "Eleita")} ${office(r)} ${where}${money}.`, `Elected ${office(r)} ${where}${money}.`),
    outro_derrotado: L(`Concorreu a ${office(r)} ${where} e não foi ${fem(r, "eleito", "eleita")}${sub}${money}.`, `Ran for ${office(r)} ${where} and lost${sub}${money}.`),
    sem_resultado: (E.b.ufs_pendentes || []).includes(r.candidatura_uf)
      ? L(`${fem(r, "Candidato", "Candidata")} a ${office(r)} ${where}; o resultado de ${r.candidatura_uf} ainda não está no arquivo do TSE.`,
        `Ran for ${office(r)} ${where}; ${r.candidatura_uf}'s result is not yet in TSE's file.`)
      : L(`Registrou candidatura a ${office(r)} ${where}, mas ela não teve resultado (renúncia, indeferimento ou recurso pendente).`,
        `Registered to run for ${office(r)} ${where}, but the candidacy has no result (withdrawn, refused or under appeal).`),
    nao_concorreu: L("Não concorreu: não aparece entre os candidatos do TSE.", "Did not run: not among TSE's candidates."),
  }[r.grupo];
  const chip = el("span", { className: "chip soft", textContent: L(`Eleição de ${y}`, `${y} election`) });
  const dot = el("i", { style: `display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 6px 0 2px;background:${G[r.grupo].color()}` });
  return [chip, " ", dot, text, " ", el("a", { href: `?tab=eleicao&leg=${leg}`, textContent: L("Ver a eleição →", "See the election →") })];
}

// ------------------------------------------------------------ the tab

/** ctx: {leg, later (draw now and on resize), openProfile (id)} */
export async function electionTab(root, { leg, later, openProfile }) {
  const E = await load(leg);
  if (!E) { root.append(el("p", { className: "empty", textContent: L("Sem eleição para esta legislatura.", "No election for this legislature.") })); return; }
  const { b, rows, elected, parties } = E, y = b.eleicao, next = b.legislatura_seguinte;
  const ranFed = rows.filter((r) => r.grupo === "reeleito" || r.grupo === "nao_reeleito");
  const other = rows.filter((r) => r.grupo === "outro_eleito" || r.grupo === "outro_derrotado");
  const count = (g, xs = rows) => xs.filter((r) => r.grupo === g).length;
  const pend = b.ufs_pendentes || [];
  const pendText = pend.length ? L(`O TSE ainda não publicou o resultado de ${pend.join(", ")} (${fmt(b.cadeiras_pendentes)} cadeiras).`,
    `TSE has not yet published ${pend.join(", ")}'s result (${fmt(b.cadeiras_pendentes)} seats).`) : "";

  root.append(el("p", { className: "about", textContent: L(
    `A eleição de outubro de ${y} escolheu a Câmara da ${LEG_ORD(next)} legislatura, que toma posse em 1º de fevereiro de ${y + 1}. Aqui, o que ela fez com os ${fmt(rows.length)} deputados da ${LEG_ORD(leg)} legislatura (suplentes que assumiram incluídos) e quem chega. Candidaturas ligadas aos deputados pela tabela de correspondência de políticos, para qualquer cargo; resultados como o TSE os publica. ${pendText}`,
    `The October ${y} election chose the Câmara of the ${LEG_ORD(next)} legislature, which takes office on 1 February ${y + 1}. Here: what it did to the ${LEG_ORD(leg)} legislature's ${fmt(rows.length)} deputies (substitutes who took a seat included), and who comes in. Candidacies are tied to deputies through the politicians crosswalk, for any office; results as TSE publishes them. ${pendText}`) }));

  // ---- who came back
  root.append(head(L(`O que aconteceu com os deputados da ${LEG_ORD(leg)} legislatura`, `What happened to the ${LEG_ORD(leg)} legislature's deputies`)));
  const subs = count("nao_reeleito") ? rows.filter((r) => r.grupo === "nao_reeleito" && r.resultado === "SUPLENTE").length : 0;
  const byOffice = (xs) => Object.entries(xs.reduce((a, r) => { const k = OFFICES[r.cargo]?.[1] ?? r.cargo; a[k] = (a[k] || 0) + 1; return a; }, {})).sort((a, b2) => b2[1] - a[1]);
  const singular = Object.fromEntries(Object.values(OFFICES).map(([one, many]) => [many, one]));
  const wonOther = byOffice(rows.filter((r) => r.grupo === "outro_eleito")).slice(0, 2).map(([o, n]) => `${fmt(n)} ${n === 1 ? singular[o] ?? o : o}`).join(", ");
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Reeleitos", "Re-elected"), value: fmt(count("reeleito")),
      sub: L(`${pct(b.taxa_reeleicao)} dos ${fmt(ranFed.length)} que concorreram de novo à Câmara e têm resultado`, `${pct(b.taxa_reeleicao)} of the ${fmt(ranFed.length)} who ran for the Câmara again and have a result`) },
    { label: L("Não reeleitos", "Not re-elected"), value: fmt(count("nao_reeleito")),
      sub: L(`${fmt(subs)} ficaram como suplentes, primeiros na fila se uma vaga abrir`, `${fmt(subs)} are substitutes, first in line if a seat opens`) },
    { label: L("Concorreram a outro cargo", "Ran for another office"), value: fmt(other.length),
      sub: L(`${fmt(count("outro_eleito"))} eleitos${wonOther ? ` (${wonOther})` : ""}`, `${fmt(count("outro_eleito"))} won${wonOther ? ` (${wonOther})` : ""}`) },
    { label: L("Não concorreram", "Did not run"), value: fmt(count("nao_concorreu")),
      sub: count("sem_resultado") ? L(`e ${fmt(count("sem_resultado"))} com candidatura sem resultado no TSE`, `and ${fmt(count("sem_resultado"))} whose candidacy has no result at TSE`) : L("nenhuma candidatura encontrada", "no candidacy found") },
  ]);
  const c0 = chart(), t0 = el("div"), g0 = el("div", { className: "grid2" });
  g0.append(card(L("Todos os deputados da legislatura", "Every deputy of the legislature"),
    L(`O desfecho de cada um em ${y}. Quem registrou mais de uma candidatura conta pela que foi às urnas. "Não concorreram" inclui quem deixou a Câmara antes (para assumir uma prefeitura, por exemplo) e quem a tabela de correspondência não conseguiu ligar a uma candidatura.`,
      `Each one's outcome in ${y}. Someone who registered for two offices counts under the one that went to the ballot. "Did not run" includes those who left the Câmara earlier (to become a mayor, say) and anyone the crosswalk could not tie to a candidacy.`), c0),
  card(L("Quem tentou outro cargo", "Who ran for another office"), L("Senado, governo, vice e assembleias estaduais. Clique no nome para abrir o perfil.", "Senate, governorships, running mates and state assemblies. Click a name to open the profile."), t0));
  root.append(g0);
  later(() => C.bars(c0, { rows: GROUPS.map((g) => ({ label: c0.clientWidth < 560 ? g.short || g.label : g.label, title: g.label, value: count(g.key), color: g.color(), note: pct(count(g.key) / rows.length) })), format: (v) => fmt(v), labelWidth: 170,
    table: { rows: GROUPS.map((g) => ({ g: g.label, n: count(g.key) })), cols: [{ key: "g", label: L("Desfecho", "Outcome"), text: true }, { key: "n", label: L("Deputados", "Deputies"), fmt: (v) => fmt(v) }], name: `outcomes-${y}` } }));
  const link = (r) => el("a", { href: `?tab=profile&leg=${leg}&dep=${r.deputado_id}`, textContent: r.nome, on: { click: (e) => { e.preventDefault(); openProfile(r.deputado_id); } } });
  const officeOrder = Object.keys(OFFICE);
  table(t0, other.map((r) => ({ ...r, off: office(r), res: RESULT[r.resultado] ?? r.resultado.toLowerCase(), o: officeOrder.indexOf(r.cargo) })), [
    { key: "nome", label: L("Deputado", "Deputy"), text: true, wrap: true, fmt: (v, r) => link(r) },
    { key: "off", label: L("Cargo", "Office"), text: true, sort: (r) => r.o, fmt: (v, r) => `${v} (${r.candidatura_partido}-${r.candidatura_uf})` },
    { key: "res", label: L("Resultado", "Result"), text: true, sort: (r) => (r.grupo === "outro_eleito" ? 1 : 0) },
  ], { pageSize: 8, sortBy: "res", name: `other-office-${y}` });

  // ---- the groups compared
  root.append(head(L("Reeleitos, derrotados e quem saiu, lado a lado", "The re-elected, the defeated and those who left, side by side")));
  let mk = M[params.get("em")] ? params.get("em") : "indice";
  const pool = rows.filter((r) => (r.meses || 0) >= MIN_MONTHS);
  const controls = el("div", { className: "controls" }), c1 = chart(), note1 = el("p", { className: "finding" });
  root.append(controls, card(L("Como cada grupo se distribui", "How each group spreads"),
    L(`Um ponto por deputado com ${MIN_MONTHS} meses ou mais de mandato na legislatura (os mesmos que o ranking pontua); o traço escuro é a mediana do grupo. Isto descreve os grupos, não explica o resultado: quem foi reeleito também difere em partido, estado, tempo de mandato e dinheiro de campanha. Clique em um ponto para abrir o perfil.`,
      `One dot per deputy with ${MIN_MONTHS} months or more in office in the legislature (those the ranking scores); the dark tick is the group's median. This describes the groups; it does not explain the result: the re-elected also differ in party, state, time in office and campaign money. Click a dot to open the profile.`), c1, note1));
  const shownGroups = GROUPS.filter((g) => pool.some((r) => r.grupo === g.key));
  const draw = () => {
    const m = M[mk];
    controls.replaceChildren(el("label", {}, L("Comparar por", "Compare by"), (() => {
      const s = el("select", {}, ...MEASURES.map((x) => el("option", { value: x.key, textContent: x.label, selected: x.key === mk })));
      s.addEventListener("change", () => { mk = s.value; setParam("em", mk, "indice"); draw(); });
      return s;
    })()));
    const grp = shownGroups.map((g) => ({ g, pts: pool.filter((r) => r.grupo === g.key && r[mk] != null) }));
    // On a phone the long names would leave the dots no room: short names, a narrower label column.
    later(() => { const narrow = c1.clientWidth < 560; C.strip(c1, { rows: grp.map(({ g, pts }) => ({ label: `${narrow ? g.short || g.label : g.label} (${fmt(pts.length)})`,
      points: pts.map((r) => ({ x: r[mk], title: r.label, rows: [m.fmt(r[mk]), r.cargo && r.grupo !== "reeleito" ? `${office(r)}: ${RESULT[r.resultado] ?? ""}` : ""].filter(Boolean), color: g.color(), id: r.deputado_id })) })),
      x: { label: m.label, format: m.fmt, min: m.min, max: m.max }, labelWidth: narrow ? 150 : 230, rowHeight: 34, onClick: (p) => openProfile(p.id),
      table: { rows: grp.flatMap(({ g, pts }) => pts.map((r) => ({ who: r.label, g: g.label, v: r[mk] }))), cols: [{ key: "who", label: L("Deputado", "Deputy"), text: true }, { key: "g", label: L("Grupo", "Group"), text: true },
        { key: "v", label: m.short, fmt: m.fmt }], name: `${mk}-by-outcome-${y}` } }); });
    const med = (k) => median(pool.filter((r) => r.grupo === k).map((r) => r[mk]));
    note1.textContent = mk === "campanha_total"
      ? L(`Mediana de quem concorreu de novo à Câmara: ${m.fmt(med("reeleito"))} entre os reeleitos, ${m.fmt(med("nao_reeleito"))} entre os não reeleitos. Quem não concorreu não tem campanha; disputas para o Senado e governos custam mais.`,
        `Median among those who ran for the Câmara again: ${m.fmt(med("reeleito"))} for the re-elected, ${m.fmt(med("nao_reeleito"))} for those who lost. Those who did not run have no campaign; Senate and governor races cost more.`)
      : L(`Medianas: ${m.fmt(med("reeleito"))} entre os reeleitos, ${m.fmt(med("nao_reeleito"))} entre os não reeleitos, ${m.fmt(med("nao_concorreu"))} entre os que não concorreram.`,
        `Medians: ${m.fmt(med("reeleito"))} for the re-elected, ${m.fmt(med("nao_reeleito"))} for those not re-elected, ${m.fmt(med("nao_concorreu"))} for those who did not run.`);
  };
  draw();
  const t1 = el("div");
  root.append(card(L("As medianas de cada grupo", "Each group's medians"),
    L(`Deputados com ${MIN_MONTHS} meses ou mais de mandato. Índice: a nota da página de ranking com os pesos padrão (participação, projetos, pareceres e economia na cota). Emendas: as pagas até agora para os orçamentos que a legislatura votou. Prefeitos do partido: o dinheiro de emendas que chegou a municípios governados pelo partido do deputado naquele ano, e quanto isso passa do que o acaso daria. A participação do presidente da Câmara fica de fora.`,
      `Deputies with ${MIN_MONTHS} months or more in office. Index: the ranking page's score with its default weights (participation, bills, opinions and allowance thrift). Amendments: paid so far for the budgets the legislature voted. Own-party towns: amendment money that reached towns run by the deputy's party that year, and how far that is above chance. The Speaker's participation is left out.`), t1));
  table(t1, shownGroups.map((g) => {
    const xs = pool.filter((r) => r.grupo === g.key);
    return { g: g.label, o: GROUPS.indexOf(g), n: xs.length, ...Object.fromEntries(MEASURES.map((m) => [m.key, median(xs.map((r) => r[m.key]))])) };
  }), [{ key: "g", label: L("Grupo", "Group"), text: true, sort: (r) => -r.o }, { key: "n", label: L("Deputados", "Deputies"), fmt: (v) => fmt(v) },
    ...MEASURES.map((m) => ({ key: m.key, label: m.short, fmt: m.fmt }))], { search: false, pageSize: 10, sortBy: "g", name: `medians-by-outcome-${y}` });

  // ---- by party
  root.append(head(L("Por partido", "By party")));
  const byParty = new Map();
  for (const r of rows) { if (!byParty.has(r.party)) byParty.set(r.party, []); byParty.get(r.party).push(r); }
  const big = [...byParty].filter(([, xs]) => xs.length >= 5).sort((a, b2) => b2[1].length - a[1].length);
  const c2 = chart(), t2 = el("div");
  root.append(card(L("O desfecho de cada bancada", "Each party's outcomes"),
    L(`Deputados da legislatura por partido (aquele pelo qual concorreram em ${y}, ou o último na Câmara para quem não concorreu), partidos com cinco ou mais. Passe o mouse para ver os números.`,
      `The legislature's deputies by party (the one they ran under in ${y}, or their last in the Câmara for those who did not run), parties with five or more. Hover for the numbers.`), c2));
  later(() => C.stack(c2, { x: big.map(([p]) => p), height: 260, format: (v) => fmt(v), rotate: true,
    series: GROUPS.map((g) => ({ name: g.label, color: g.color(), values: big.map(([, xs]) => count(g.key, xs)) })).filter((s) => s.values.some((v) => v > 0)),
    table: { rows: big.map(([p, xs]) => ({ p, ...Object.fromEntries(GROUPS.map((g) => [g.key, count(g.key, xs)])) })), cols: [{ key: "p", label: L("Partido", "Party"), text: true },
      ...GROUPS.map((g) => ({ key: g.key, label: g.label, fmt: (v) => fmt(v) }))], name: `outcomes-by-party-${y}` } }));
  root.append(card(L("Taxa de reeleição por partido", "Re-election rate by party"),
    L("Entre os deputados de cada partido que concorreram de novo à Câmara e têm resultado. Partidos pequenos têm poucos casos: uma reeleição a mais muda muito a taxa.",
      "Among each party's deputies who ran for the Câmara again and have a result. Small parties have few cases: one more win moves the rate a lot."), t2));
  table(t2, [...byParty].map(([p, xs]) => {
    const ran = xs.filter((r) => r.grupo === "reeleito" || r.grupo === "nao_reeleito");
    return { p, n: xs.length, ran: ran.length, won: count("reeleito", xs), rate: ran.length ? count("reeleito", xs) / ran.length : null,
      other: xs.filter((r) => r.grupo === "outro_eleito" || r.grupo === "outro_derrotado").length, out: count("nao_concorreu", xs) };
  }), [{ key: "p", label: L("Partido", "Party"), text: true }, { key: "n", label: L("Deputados", "Deputies"), fmt: (v) => fmt(v) },
    { key: "ran", label: L("Tentaram a reeleição", "Ran again"), fmt: (v) => fmt(v) }, { key: "won", label: L("Reeleitos", "Re-elected"), fmt: (v) => fmt(v) },
    { key: "rate", label: L("Taxa", "Rate"), fmt: (v) => pct(v) }, { key: "other", label: L("Outro cargo", "Other office"), fmt: (v) => fmt(v) },
    { key: "out", label: L("Não concorreram", "Did not run"), fmt: (v) => fmt(v) }], { pageSize: 12, sortBy: "n", name: `reelection-by-party-${y}` });

  // ---- the next Chamber
  root.append(head(L(`A Câmara eleita para ${y + 1}–${y + 5} (${LEG_ORD(next)} legislatura)`, `The Câmara elected for ${y + 1}–${y + 5} (${LEG_ORD(next)} legislature)`)));
  const nO = (k) => elected.filter((r) => r.origem === k).length;
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: pend.length ? L("Eleitos até agora", "Elected so far") : L("Eleitos", "Elected"), value: fmt(elected.length),
      sub: pend.length ? L(`de ${fmt(b.cadeiras)} cadeiras; faltam as de ${pend.join(", ")}`, `of ${fmt(b.cadeiras)} seats; ${pend.join(", ")} still to come`) : L(`todas as ${fmt(b.cadeiras)} cadeiras`, `all ${fmt(b.cadeiras)} seats`) },
    { label: L("Reeleitos", "Re-elected"), value: pct(nO("reeleito") / elected.length), sub: L(`${fmt(nO("reeleito"))} estavam na ${LEG_ORD(leg)} legislatura`, `${fmt(nO("reeleito"))} sat in the ${LEG_ORD(leg)} legislature`) },
    { label: L("Voltam após um intervalo", "Back after a break"), value: fmt(nO("ex_deputado")), sub: L("foram deputados antes, mas não nesta legislatura", "were deputies before, but not in this legislature") },
    { label: L("Novos na Câmara", "New to the Câmara"), value: pct(nO("novo") / elected.length), sub: L(`${fmt(nO("novo"))} sem passagem pela Câmara desde 2011`, `${fmt(nO("novo"))} with no seat in the Câmara since 2011`) },
  ]);
  const shown = parties.filter((p) => p.eleitos > 0 || p.em_exercicio >= 3);
  const top = Math.max(...shown.map((p) => Math.max(p.eleitos, p.em_exercicio)), 1);
  const sitMonth = b.em_exercicio_mes ? month(b.em_exercicio_mes) : "";
  const pname = (p) => (p.partido === "S.PART." || !p.partido ? L("sem partido", "no party") : p.partido);
  const c3 = chart(), c4 = chart(), g3 = el("div", { className: "grid2" });
  g3.append(card(L(`Bancadas em ${sitMonth}`, `Seats in ${sitMonth}`),
    L(`Os ${fmt(b.em_exercicio)} deputados que votaram ou apresentaram propostas no mês da eleição, pelo partido de então (depois das trocas de partido da legislatura).`,
      `The ${fmt(b.em_exercicio)} deputies who voted or filed a proposal in the election month, by their party then (after the legislature's party switches).`), c3),
  card(L(`Bancadas eleitas em ${y}`, `Seats won in ${y}`), L(`Os ${fmt(elected.length)} eleitos${pend.length ? " até agora" : ""}, pelo partido da candidatura; mesma ordem e mesma escala ao lado.`,
    `The ${fmt(elected.length)} elected${pend.length ? " so far" : ""}, by the party they ran under; same order and scale as beside.`), c4));
  root.append(g3);
  later(() => C.bars(c3, { rows: shown.map((p) => ({ label: pname(p), value: p.em_exercicio, color: css("--other") })), max: top, format: (v) => fmt(v), labelWidth: 110 }));
  later(() => C.bars(c4, { rows: shown.map((p) => ({ label: pname(p), value: p.eleitos, color: C.slot(1), note: L(`${p.eleitos - p.em_exercicio >= 0 ? "+" : "−"}${fmt(Math.abs(p.eleitos - p.em_exercicio))} vs. ${sitMonth}`, `${p.eleitos - p.em_exercicio >= 0 ? "+" : "−"}${fmt(Math.abs(p.eleitos - p.em_exercicio))} vs ${sitMonth}`) })),
    max: top, format: (v) => fmt(v), labelWidth: 110 }));
  const c5 = chart(), t5 = el("div");
  root.append(card(L("Quem forma cada bancada eleita", "Who makes up each party's new bench"),
    L("Reeleitos, ex-deputados que voltam e estreantes, por partido. A Câmara só dá um número aos novos deputados na posse; até lá, quem não tem passagem desde 2011 conta como novo.",
      "Re-elected deputies, former deputies coming back and newcomers, by party. The Câmara numbers new deputies only when they take office; until then, anyone without a seat since 2011 counts as new."), c5));
  const withSeats = parties.filter((p) => p.eleitos > 0);
  later(() => C.stack(c5, { x: withSeats.map(pname), height: 240, format: (v) => fmt(v), rotate: true,
    series: ORIGINS.map((o) => ({ name: o.label, color: o.color(), values: withSeats.map((p) => p[o.key]) })) }));
  root.append(card(L("Partido a partido", "Party by party"),
    L(`Cadeiras ganhas na eleição de ${b.anterior}, ocupadas em ${sitMonth} e ganhas em ${y}. Partidos que se fundiram contam pelo nome atual (PTB e Patriota como PRD, PSC como Podemos, PROS como Solidariedade).`,
      `Seats won at the ${b.anterior} election, held in ${sitMonth}, and won in ${y}. Merged parties count under today's name (PTB and Patriota as PRD, PSC as Podemos, PROS as Solidariedade).`), t5));
  table(t5, parties.map((p) => ({ ...p, p: pname(p), d: p.eleitos - p.em_exercicio })), [
    { key: "p", label: L("Partido", "Party"), text: true }, { key: "eleitos_antes", label: L(`Eleitos em ${b.anterior}`, `Won in ${b.anterior}`), fmt: (v) => fmt(v) },
    { key: "em_exercicio", label: sitMonth, fmt: (v) => fmt(v) }, { key: "eleitos", label: L(`Eleitos em ${y}`, `Won in ${y}`), fmt: (v) => fmt(v) },
    { key: "d", label: L("Variação", "Change"), fmt: (v) => (v > 0 ? `+${fmt(v)}` : v < 0 ? `−${fmt(-v)}` : "0") },
    { key: "reeleito", label: L("Reeleitos", "Re-elected"), fmt: (v) => fmt(v) }, { key: "novo", label: L("Novos", "New"), fmt: (v) => fmt(v) },
  ], { search: false, pageSize: 30, sortBy: "eleitos", name: `seats-by-party-${y}` });
  const t6 = el("div");
  root.append(card(L(`Os eleitos de ${y}`, `Elected in ${y}`), L("Busque por nome, partido ou estado. Reeleitos abrem o perfil; ex-deputados, a página da Câmara.", "Search by name, party or state. The re-elected open their profile; former deputies, the Câmara's page."), t6));
  table(t6, elected.map((r) => ({ ...r, origin: O[r.origem]?.one || r.origem, res: RESULT[r.resultado] ?? r.resultado })), [
    { key: "nome_urna", label: L("Eleito", "Elected"), text: true, wrap: true, fmt: (v, r) => (r.origem === "reeleito" && r.deputado_id ? el("a", { href: `?tab=profile&leg=${leg}&dep=${r.deputado_id}`, textContent: v, on: { click: (e) => { e.preventDefault(); openProfile(r.deputado_id); } } })
      : r.deputado_id ? el("a", { href: `https://www.camara.leg.br/deputados/${r.deputado_id}`, textContent: `${v} ↗` }) : v) },
    { key: "partido", label: L("Partido", "Party"), text: true }, { key: "uf", label: "UF", text: true },
    { key: "origin", label: L("Origem", "Background"), text: true }, { key: "res", label: L("Resultado", "Result"), text: true },
    { key: "campanha_total", label: L("Arrecadou", "Raised"), fmt: (v) => brl(v) },
  ], { pageSize: 15, sortBy: "campanha_total", name: `elected-${y}` });
}
