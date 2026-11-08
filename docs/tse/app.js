// Campaign finance: where candidates' money came from, how parties split public funds, donors and suppliers.
import { $, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L } from "../lib/i18n.js";
import { setupPage } from "../lib/page.js";

setupPage();

const OFFICES = ["Presidente", "Governador", "Senador", "Deputado Federal", "Deputado Estadual", "Deputado Distrital"];
const OFFICE = { Presidente: L("Presidente", "President"), Governador: L("Governador", "Governor"), Senador: L("Senador", "Senator"), "Deputado Federal": L("Deputado federal", "Federal deputy"),
  "Deputado Estadual": L("Deputado estadual", "State deputy"), "Deputado Distrital": L("Deputado distrital (DF)", "District deputy (DF)") };
const SHORT = { Presidente: L("Presidente", "President"), Governador: L("Governador", "Governor"), Senador: L("Senador", "Senator"), "Deputado Federal": L("Dep. federal", "Fed. deputy"),
  "Deputado Estadual": L("Dep. estadual", "State deputy"), "Deputado Distrital": L("Dep. distrital", "DF deputy") };
/** "Deputado federal" -> "deputado federal", for "candidatos a deputado federal". */
const lower = (s) => (s ? s[0].toLowerCase() + s.slice(1) : s);
const ORIGINS = [["origem_partido", L("Partidos", "Parties")], ["origem_pessoas_fisicas", L("Pessoas físicas", "Individuals")], ["origem_proprios", L("Recursos próprios", "Own money")],
  ["origem_outros_candidatos", L("Outros candidatos", "Other candidates")], ["origem_financiamento_coletivo", L("Financiamento coletivo", "Crowdfunding")]];
// The TSE's result codes, cleaned up in Portuguese.
const RESULT = { ELEITO: L("Eleito", "Elected"), "ELEITO POR QP": L("Eleito por QP", "Elected (quotient)"), "ELEITO POR MÉDIA": L("Eleito por média", "Elected (remainders)"),
  SUPLENTE: L("Suplente", "Substitute"), "NÃO ELEITO": L("Não eleito", "Not elected") };
const officeColor = (o) => C.slot([1, 2, 3, 4, 5, 7][OFFICES.indexOf(o)]);   // slot 6 (green) is too close to slot 3
const partyColor = (p) => (p === "PT" ? css("--a") : p === "PL" ? css("--b") : css("--other"));
const PARTY_LEGEND = () => [{ label: "PT", color: css("--a") }, { label: "PL", color: css("--b") }, { label: L("Outros partidos", "Other parties"), color: css("--other") }];

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
const wonLabel = (r) => (elected(r) ? L("eleito", "elected") : L("não eleito", "not elected"));
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
    { label: L(`Dinheiro declarado em ${year}`, `Money declared in ${year}`), value: brl(total),
      sub: L(`por ${plural(T("candidatos"), "candidato", "candidatos")} a ${R.length} cargos`, `by ${plural(T("candidatos"), "candidate")} for ${R.length} offices`) },
    { label: L("Dinheiro público", "Public money"), value: pct(pub / total),
      sub: L(`${brl(T("fonte_fefc"))} do FEFC, ${brl(T("fonte_fundo_partidario"))} do Fundo Partidário`, `${brl(T("fonte_fefc"))} from the FEFC, ${brl(T("fonte_fundo_partidario"))} from the Party Fund`) },
    { label: L("De pessoas físicas", "From private individuals"), value: pct(indiv / total),
      sub: L(`${pct(large / indiv)} disso de ${plural(gd.length, "doador", "doadores")} que deram R$ 50 mil ou mais`, `${pct(large / indiv)} of it from ${plural(gd.length, "donor")} who gave R$50k or more`) },
    { label: L("Recursos próprios dos candidatos", "Candidates' own money"), value: pct(T("origem_proprios") / total), sub: brl(T("origem_proprios")) },
  ]);
  const c1 = chart(), c2 = chart(), c3 = chart(), g = el("div", { className: "grid2" });
  root.append(card(L("De onde veio o dinheiro de cada cargo", "Where each office's money came from"),
    L("Dinheiro declarado pelos candidatos, por cargo e origem. “Partidos” é o dinheiro repassado pelas direções partidárias, a maior parte dele vinda dos fundos públicos.",
      "Money candidates declared, by office and origin. “Parties” is money passed on by party directorates, most of it from the public funds."), c1));
  g.append(card(L("Dinheiro público em cada eleição", "Public money in each election"),
    L("Todos os cargos somados, por fundo. Os fundos públicos passaram a pagar a maior parte das campanhas depois da criação do FEFC, em 2017; o fundo mais que dobrou para 2022.",
      "Every office together, by fund. Public funds paid for most campaigns once the FEFC was created in 2017; it more than doubled for 2022."), c2),
    card(L("Parcela de dinheiro público, por cargo", "Public money's share, by office"),
      L("A parcela do dinheiro declarado que veio do FEFC ou do Fundo Partidário.", "The share of declared money that came from the FEFC or the Party Fund."), c3));
  root.append(g);
  const offices = OFFICES.filter((o) => R.some((r) => r.cargo === o)), row = (o) => R.find((r) => r.cargo === o);
  const series = [...ORIGINS.map(([k, name], i) => ({ name, color: C.slot(i + 1), values: offices.map((o) => row(o)[k]) })),
    { name: L("Outros", "Other"), color: css("--other"), values: offices.map((o) => row(o).total - sum(ORIGINS.map(([k]) => row(o)[k]))) }];
  const tbl = {
    rows: R.map((r) => ({ ...r, office: OFFICE[r.cargo], per: r.total / r.candidatos, share: r.publico / r.total })),
    cols: [{ key: "office", label: L("Cargo", "Office"), text: true }, { key: "candidatos", label: L("Candidatos", "Candidates"), fmt: (v) => fmt(v) }, { key: "eleitos", label: L("Eleitos", "Elected"), fmt: (v) => fmt(v) },
      { key: "total", label: L("Declarado", "Declared"), fmt: (v) => brl(v) }, { key: "per", label: L("Por candidato", "Per candidate"), fmt: (v) => brl(v) },
      { key: "share", label: L("Parcela pública", "Public share"), fmt: (v) => pct(v) }, { key: "origem_proprios", label: L("Recursos próprios", "Own money"), fmt: (v) => brl(v) }],
    name: `money-by-office-${year}`,
  };
  later(() => C.stack(c1, { x: offices.map((o) => SHORT[o]), series, format: (v) => brl(v, 0), height: 260, table: tbl }));
  const tot = (rows, k) => sum(rows.map((r) => r[k]));
  later(() => C.stack(c2, { x: YEARS, height: 240, format: (v) => brl(v, 0), series: [
    { name: "FEFC", color: C.slot(1), values: all.map((rows) => tot(rows, "fonte_fefc")) },
    { name: L("Fundo Partidário", "Party Fund"), color: C.slot(2), values: all.map((rows) => tot(rows, "fonte_fundo_partidario")) },
    { name: L("Outras fontes", "Other sources"), color: css("--other"), values: all.map((rows) => tot(rows, "total") - tot(rows, "publico")) }] }));
  later(() => C.line(c3, { x: "num", xTicks: YEARS, height: 240, y: { min: 0, max: 1, format: (v) => pct(v) },
    series: offices.map((o) => ({ name: OFFICE[o], color: officeColor(o), points: YEARS.map((y, i) => { const r = all[i].find((x) => x.cargo === o); return [y, r && r.total ? r.publico / r.total : null]; }) })) }));
  const first = all[0], share0 = tot(first, "publico") / tot(first, "total");
  root.append(finding(year === YEARS[0]
    ? L(`Em ${year}, os fundos públicos pagaram ${pct(pub / total)} do dinheiro declarado pelos candidatos.`, `In ${year}, public funds paid for ${pct(pub / total)} of the money candidates declared.`)
    : L(`Em ${year}, os fundos públicos pagaram ${pct(pub / total)} do dinheiro declarado pelos candidatos, contra ${pct(share0)} em ${YEARS[0]}.`,
      `In ${year}, public funds paid for ${pct(pub / total)} of the money candidates declared, against ${pct(share0)} in ${YEARS[0]}.`)));
}

// ------------------------------------------------------------ parties

async function parties(root) {
  const mine = local();
  const [P, cand] = await Promise.all([partidos(), candidatos()]);
  let office = params.get("po") || "Deputado Federal", measure = params.get("pm") || "per";
  if (!P.some((r) => r.cargo === office)) office = "Deputado Federal";
  const controls = el("div", { className: "controls" }), body = el("div");
  root.append(controls, body);
  const draw = () => {
    mine.reset();
    controls.replaceChildren(
      select(L("Cargo", "Office"), OFFICES.filter((o) => P.some((r) => r.cargo === o)).map((o) => ({ value: o, label: OFFICE[o] })), office, (v) => { office = v; setParam("po", v, "Deputado Federal"); draw(); }),
      select(L("Dinheiro público", "Public money"), [{ value: "per", label: L("Por candidato", "Per candidate") }, { value: "total", label: "Total" }, { value: "elected", label: L("Por eleito", "Per elected candidate") }], measure,
        (v) => { measure = v; setParam("pm", v, "per"); draw(); }));
    body.replaceChildren();
    const rows = P.filter((r) => r.cargo === office && r.publico > 0);
    const value = (r) => (measure === "total" ? r.publico : measure === "elected" ? (r.eleitos ? r.publico / r.eleitos : null) : r.publico / r.candidatos);
    const c1 = chart(), c2 = chart();
    const g = el("div", { className: "grid2" });
    const big = rows.filter((r) => r.candidatos >= 20);
    g.append(card(L("Dinheiro público por partido", "Public money by party"), {
      per: L("Dinheiro público (FEFC e Fundo Partidário) dividido pelo número de candidatos do partido a este cargo.", "Public money (FEFC and Party Fund) divided by the party's candidates for this office."),
      total: L("Todo o dinheiro público recebido pelos candidatos do partido a este cargo.", "All public money the party's candidates for this office received."),
      elected: L("Dinheiro público dividido pelo número de candidatos que o partido elegeu: quanto cada cadeira custou em fundos públicos. Partidos que não elegeram ninguém ficam de fora.",
        "Public money divided by the candidates the party elected: what each seat cost in public funds. Parties that elected nobody are left out."),
    }[measure], c1), card(L("Quão desigual é a divisão do dinheiro público em cada partido", "How unevenly each party splits its public money"),
      L("Índice de Gini do dinheiro público entre os candidatos do partido a este cargo: 0 se todos receberam o mesmo, perto de 1 se poucos levaram quase tudo. Partidos com 20 candidatos ou mais.",
        "Gini coefficient of public money among the party's candidates for this office: 0 if every candidate got the same, near 1 if a few got almost all. Parties with 20 or more candidates."), c2));
    body.append(g);
    mine.later(() => C.bars(c1, { rows: rows.filter((r) => value(r) != null).map((r) => ({ label: r.partido, value: value(r), color: partyColor(r.partido),
      note: L(`${plural(r.candidatos, "candidato", "candidatos")}, ${plural(r.eleitos, "eleito", "eleitos")}`, `${plural(r.candidatos, "candidate")}, ${fmt(r.eleitos)} elected`) })).sort((a, b) => b.value - a.value),
    format: (v) => brl(v), labelWidth: 120, barHeight: 14, legend: PARTY_LEGEND() }));
    mine.later(() => C.bars(c2, { rows: big.map((r) => ({ label: r.partido, value: r.gini_publico, color: partyColor(r.partido),
      note: L(`seus 10 candidatos mais bem financiados levaram ${pct(r.top10_publico)} · ${plural(r.candidatos, "candidato", "candidatos")}`, `its 10 best-funded candidates got ${pct(r.top10_publico)} · ${plural(r.candidatos, "candidate")}`) })).sort((a, b) => b.value - a.value),
    format: (v) => fmt(v, 2), max: 1, labelWidth: 120, barHeight: 14, legend: PARTY_LEGEND(), empty: L("Nenhum partido teve 20 candidatos a este cargo.", "No party had 20 candidates for this office.") }));

    if (office === "Deputado Federal") {
      const dep = cand.filter((r) => r.cargo === "Deputado Federal"), inc = dep.filter((r) => r.incumbente), nov = dep.filter((r) => !r.incumbente);
      const rate = (xs) => (xs.length ? xs.filter(elected).length / xs.length : null);
      const tl = el("section", { className: "tiles" }), c3 = chart();
      tiles(tl, [
        { label: L("Deputados que tentaram a reeleição", "Sitting deputies running again"), value: fmt(inc.length),
          sub: L(`de ${fmt(dep.length)} candidatos a deputado federal`, `of ${fmt(dep.length)} federal deputy candidates`) },
        { label: L("Reeleitos", "Re-elected"), value: pct(rate(inc)),
          sub: L(`${fmt(inc.filter(elected).length)} deputados em exercício ganharam uma cadeira`, `${fmt(inc.filter(elected).length)} sitting deputies won a seat`) },
        { label: L("Demais candidatos eleitos", "Other candidates elected"), value: pct(rate(nov), 1),
          sub: L(`${fmt(nov.filter(elected).length)} de ${fmt(nov.length)}`, `${fmt(nov.filter(elected).length)} of ${fmt(nov.length)}`) },
        { label: L("Dinheiro público mediano", "Median public money"), value: brl(median(inc.map((r) => r.publico))),
          sub: L(`de um deputado em exercício, contra ${brl(median(nov.map((r) => r.publico)))} dos demais`, `a sitting deputy, against ${brl(median(nov.map((r) => r.publico)))} for everyone else`) },
      ]);
      const pts = P.filter((r) => r.cargo === office && r.incumbentes >= 3 && r.mediana_novos != null && r.mediana_incumbentes != null);
      const ok = pts.filter((r) => r.mediana_novos > 0), more = pts.filter((r) => r.mediana_incumbentes > r.mediana_novos);
      body.append(card(L("Quem as direções financiam: deputados em exercício ou novatos", "Who leaderships fund: sitting deputies or newcomers"),
        L("Quantas vezes mais dinheiro público recebeu o deputado federal em exercício mediano do partido do que o candidato mediano entre os demais. Partidos com três ou mais deputados em exercício na disputa.",
          "How many times more public money the party's median sitting federal deputy got than its median other candidate. Parties with three or more incumbents running."), tl, c3,
        finding(L(`Em ${fmt(more.length)} de ${fmt(pts.length)} partidos, o deputado em exercício mediano recebeu mais dinheiro público do que o candidato mediano entre os demais.`,
          `${plural(more.length, "party", "parties")} of ${pts.length} gave the median sitting deputy more public money than the median other candidate.`))));
      mine.later(() => C.bars(c3, {
        rows: ok.map((r) => ({ label: r.partido, value: r.mediana_incumbentes / r.mediana_novos, color: partyColor(r.partido),
          note: L(`mediana de ${brl(r.mediana_incumbentes)} para seus ${fmt(r.incumbentes)} deputados em exercício, ${brl(r.mediana_novos)} para os demais`,
            `median ${brl(r.mediana_incumbentes)} for its ${fmt(r.incumbentes)} incumbents, ${brl(r.mediana_novos)} for the others`) })).sort((a, b) => b.value - a.value),
        format: (v) => `${fmt(v, v < 10 ? 1 : 0)}×`, labelWidth: 120, barHeight: 14, legend: PARTY_LEGEND(),
        table: { rows: pts, cols: [{ key: "partido", label: L("Partido", "Party"), text: true }, { key: "incumbentes", label: L("Em exercício", "Incumbents"), fmt: (v) => fmt(v) },
          { key: "mediana_incumbentes", label: L("Mediana, em exercício", "Median, incumbents"), fmt: (v) => brl(v) }, { key: "mediana_novos", label: L("Mediana, demais", "Median, others"), fmt: (v) => brl(v) }], name: `incumbents-${year}` },
      }));
    } else {
      body.append(card(L("Quem as direções financiam: deputados em exercício ou novatos", "Who leaderships fund: sitting deputies or newcomers"),
        L("Só acompanhamos quem tenta a reeleição entre os deputados federais: escolha “Deputado federal” acima.", "Incumbency is tracked for federal deputies only: pick “Federal deputy” above.")));
    }

    const tb = el("div");
    body.append(card(L(`Todos os partidos: ${OFFICE[office]}`, `Every party: ${OFFICE[office]}`),
      L("Dinheiro público é o FEFC mais o Fundo Partidário; “por candidato” é o dinheiro público dividido pelos candidatos, e “10 maiores”, a parcela dele que foi para os 10 candidatos mais bem financiados. As medianas de deputados em exercício e dos demais valem para deputado federal.", "Public money is the FEFC plus the Party Fund. Medians of incumbents and others are for federal deputies."), tb));
    table(tb, P.filter((r) => r.cargo === office).map((r) => ({ ...r, per: r.publico / r.candidatos })), [
      { key: "partido", label: L("Partido", "Party"), text: true }, { key: "candidatos", label: L("Candidatos", "Candidates"), fmt: (v) => fmt(v) }, { key: "eleitos", label: L("Eleitos", "Elected"), fmt: (v) => fmt(v) },
      { key: "total", label: L("Declarado", "Declared"), fmt: (v) => brl(v) }, { key: "publico", label: L("Público", "Public"), fmt: (v) => brl(v) },
      { key: "per", label: L("Por candidato", "Public per candidate"), fmt: (v) => brl(v) }, { key: "gini_publico", label: "Gini", fmt: (v) => fmt(v, 2) },
      { key: "top10_publico", label: L("10 maiores", "Top 10's share"), fmt: (v) => pct(v) }, { key: "incumbentes", label: L("Em exercício", "Incumbents"), fmt: (v) => fmt(v) },
      { key: "mediana_incumbentes", label: L("Mediana, em exercício", "Median, incumbents"), fmt: (v) => brl(v) }, { key: "mediana_novos", label: L("Mediana, demais", "Median, others"), fmt: (v) => brl(v) },
    ], { sortBy: "publico", pageSize: 40, name: `parties-${office}-${year}` });
  };
  draw();
}

// ------------------------------------------------------------ women and Black candidates

const LAW = {
  women: L("A regra (STF, na ADI 5617, e TSE, em 2018; Emenda Constitucional 117, de 2022): ao menos 30% do dinheiro público de campanha de um partido vai para mulheres, e mais se elas forem mais de 30% dos candidatos. Assim, um partido cumpre a regra se estiver sobre ou acima da linha tracejada, e acima de 30%.",
    "The law (Supreme Court ADI 5617 and TSE, 2018; Constitutional Amendment 117, 2022): at least 30% of a party's public campaign money goes to women, and more if women are more than 30% of its candidates. So a party meets it on or above the dashed line, and above 30%."),
  black: {
    2018: L("Nenhuma regra valia em 2018. A linha tracejada marca o dinheiro proporcional ao número de candidatos.", "No rule applied in 2018. The dashed line marks money in proportion to candidates."),
    2022: L("Desde 2020 (TSE e STF, na ADPF 738): dinheiro público e tempo de propaganda para candidatos negros na proporção da sua parcela entre os candidatos do partido. Um partido cumpre a regra se estiver sobre ou acima da linha tracejada.",
      "From 2020 (TSE and Supreme Court, ADPF 738): public money and airtime for Black candidates in proportion to their share of the party's candidates. A party meets it on or above the dashed line."),
    2026: L("Emenda Constitucional 133 (2024), mantida pelo STF em junho de 2026: ao menos 30% do dinheiro público de campanha vai para candidatos negros, qualquer que seja a parcela deles entre os candidatos. A linha tracejada marca o dinheiro proporcional ao número de candidatos.",
      "Constitutional Amendment 133 (2024), upheld by the Supreme Court in June 2026: at least 30% of public campaign money goes to Black candidates, whatever their share of candidates. The dashed line marks money in proportion to candidates."),
  },
};

async function equity(root) {
  const mine = local();
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
    mine.reset();
    controls.replaceChildren(select(L("Cargo", "Office"), [{ value: "all", label: L("Todos os cargos (como a lei conta)", "Every office (as the law counts)") }, ...OFFICES.map((o) => ({ value: o, label: OFFICE[o] }))], office,
      (v) => { office = v; setParam("eo", v, "all"); draw(); }));
    body.replaceChildren();
    const rows = pick(P, office), parties = byParty(rows);
    tiles(body.appendChild(el("section", { className: "tiles" })), [
      { label: L("Mulheres entre os candidatos", "Women among candidates"), value: pct(share(rows, "mulheres", "candidatos"), 1), sub: OFFICE[office] || L("todos os cargos", "every office") },
      { label: L("Parcela das mulheres no dinheiro público", "Women's share of public money"), value: pct(share(rows, "publico_mulheres", "publico"), 1),
        sub: L(`${brl(sum(rows.map((r) => r.publico_mulheres)))} de ${brl(sum(rows.map((r) => r.publico)))}`, `${brl(sum(rows.map((r) => r.publico_mulheres)))} of ${brl(sum(rows.map((r) => r.publico)))}`) },
      { label: L("Candidatos negros", "Black candidates"), value: pct(share(rows, "negros", "candidatos"), 1), sub: L("autodeclarados pretos ou pardos", "self-declared preta or parda") },
      { label: L("Parcela dos negros no dinheiro público", "Black candidates' share of public money"), value: pct(share(rows, "publico_negros", "publico"), 1), sub: brl(sum(rows.map((r) => r.publico_negros))) },
    ]);
    const maxPub = Math.max(...parties.map((a) => a.publico), 1), MIN_PUB = 1e6;
    const scatterOf = (box, k, pk, floor, rule) => {
      const ruled = rule(0.5) >= 0;   // Black candidates in 2018: no rule, so nobody is flagged and the largest parties are named
      const pts = parties.filter((a) => a.publico >= MIN_PUB).map((a) => {
        const x = a[k] / a.candidatos, y = a[pk] / a.publico, need = rule(x), below = ruled && y < need - 0.005;
        return { x, y, label: below || !ruled ? a.partido : "", title: a.partido, color: below ? css("--critical") : css("--other"), r: 3 + 6 * Math.sqrt(a.publico / maxPub), z: below ? 1 : 0,
          rows: [L(`${pct(x, 1)} dos seus ${fmt(a.candidatos)} candidatos, ${pct(y, 1)} dos seus ${brl(a.publico)} de dinheiro público`, `${pct(x, 1)} of its ${fmt(a.candidatos)} candidates, ${pct(y, 1)} of its ${brl(a.publico)} public money`),
            ...(!ruled ? [] : [below ? L(`▼ abaixo da regra em ${fmt(100 * (need - y), 1)} pontos`, `▼ below the rule by ${fmt(100 * (need - y), 1)} points`) : L("✓ cumpre a regra", "✓ meets the rule")])] };
      });
      const up = (v) => Math.min(1, Math.ceil((v + 0.03) * 10) / 10), down = (v) => Math.max(0, Math.floor((v - 0.03) * 10) / 10);
      const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
      const xd = [down(Math.min(...xs)), up(Math.max(...xs))], yd = [Math.min(down(Math.min(...ys)), floor ? 0.2 : 1), up(Math.max(...ys, 0.4))];
      C.scatter(box, {
        points: pts, x: { label: L("Parcela dos candidatos do partido", "Share of the party's candidates"), format: (v) => pct(v), min: xd[0], max: xd[1] },
        y: { label: L("Parcela do seu dinheiro público", "Share of its public money"), format: (v) => pct(v), min: yd[0], max: yd[1] },
        diagonal: { label: L("proporcional", "in proportion") }, refs: floor ? [{ y: 0.3, label: L("piso de 30%", "30% floor") }] : [], labels: 10, labelRank: (a, b) => b.r - a.r, height: 340,
        legend: ruled ? [{ label: L("▼ Abaixo da regra", "▼ Below the rule"), color: css("--critical") }, { label: L("✓ Cumpre", "✓ Meets it"), color: css("--other") }] : [],
        table: { rows: pts.map((p) => ({ party: p.title, cand: p.x, money: p.y, gap: p.y - p.x })), cols: [{ key: "party", label: L("Partido", "Party"), text: true },
          { key: "cand", label: L("Parcela dos candidatos", "Share of candidates"), fmt: (v) => pct(v, 1) }, { key: "money", label: L("Parcela do dinheiro público", "Share of public money"), fmt: (v) => pct(v, 1) },
          { key: "gap", label: L("Diferença (pontos)", "Gap (points)"), fmt: (v) => fmt(100 * v, 1) }], name: `${k}-${year}` },
      });
      return [pts.filter((p) => p.label).length, pts.length];
    };
    const c1 = chart(), c2 = chart(), n1 = el("p", { className: "finding" }), n2 = el("p", { className: "finding" });
    const g = el("div", { className: "grid2" });
    const blackRule = year >= 2026 ? () => 0.3 : year >= 2022 ? (x) => x : () => -1;
    g.append(card(L("Mulheres: candidaturas e dinheiro público", "Women: candidates against public money"),
      L(`${LAW.women} Cada ponto é um partido com R$ 1 milhão ou mais em dinheiro público (todos os partidos estão na tabela abaixo); os vermelhos ficam abaixo da regra.`,
        `${LAW.women} Each dot is a party with R$1 million or more in public money (every party is in the table below); red ones fall short.`), c1, n1),
    card(L("Candidatos negros: candidaturas e dinheiro público", "Black candidates: candidates against public money"),
      L(`${LAW.black[year] || LAW.black[2026]} Cada ponto é um partido com R$ 1 milhão ou mais em dinheiro público${year >= 2022 ? "; os vermelhos ficam abaixo da regra" : ""}.`,
        `${LAW.black[year] || LAW.black[2026]} Each dot is a party with R$1 million or more in public money${year >= 2022 ? "; red ones fall short" : ""}.`), c2, n2));
    body.append(g);
    mine.later(() => { const [k, n] = scatterOf(c1, "mulheres", "publico_mulheres", true, (x) => Math.max(0.3, x));
      n1.textContent = L(`Por estes números, ${fmt(k)} de ${fmt(n)} partidos deram às mulheres menos do que a regra exige (com tolerância de meio ponto).`,
        `On these numbers, ${plural(k, "party", "parties")} of ${n} gave women less than the rule asks (a tolerance of half a point).`); });
    mine.later(() => { const [k, n] = scatterOf(c2, "negros", "publico_negros", year >= 2026, blackRule);
      n2.textContent = year < 2022 ? L("Nenhuma regra valia nesta eleição.", "No rule applied in this election.")
        : L(`Por estes números, ${fmt(k)} de ${fmt(n)} partidos deram aos candidatos negros menos do que a regra exige.`, `On these numbers, ${plural(k, "party", "parties")} of ${n} gave Black candidates less than the rule asks.`); });

    const c3 = chart(), c4 = chart(), g2 = el("div", { className: "grid2" });
    const scope = OFFICE[office] ? L(`${OFFICE[office]}, todos os partidos.`, `${OFFICE[office]}, every party.`) : L("Todos os cargos e partidos.", "Every office and party.");
    g2.append(card(L("Mulheres, eleição a eleição", "Women, across elections"), scope, c3), card(L("Candidatos negros, eleição a eleição", "Black candidates, across elections"), scope, c4));
    body.append(g2);
    const trend = (k, pk) => [
      { name: L("Parcela dos candidatos", "Share of candidates"), color: C.slot(1), points: YEARS.map((y, i) => [y, share(pick(all[i], office), k, "candidatos")]) },
      { name: L("Parcela do dinheiro público", "Share of public money"), color: C.slot(2), points: YEARS.map((y, i) => [y, share(pick(all[i], office), pk, "publico")]) },
    ];
    mine.later(() => C.line(c3, { x: "num", xTicks: YEARS, height: 220, y: { min: 0, max: 0.6, format: (v) => pct(v) }, ref: [{ y: 0.3, label: "30%" }], series: trend("mulheres", "publico_mulheres") }));
    mine.later(() => C.line(c4, { x: "num", xTicks: YEARS, height: 220, y: { min: 0, max: 0.6, format: (v) => pct(v) }, series: trend("negros", "publico_negros") }));

    const tb = el("div");
    body.append(card(L("Todos os partidos", "Every party"),
      L("Parcelas dos candidatos do partido e do seu dinheiro público (FEFC e Fundo Partidário). Diferença: parcela do dinheiro menos parcela dos candidatos, em pontos percentuais.",
        "Shares of the party's candidates and of its public money (FEFC and Party Fund). Gap: money share minus candidate share, in percentage points."), tb));
    table(tb, parties.map((a) => ({ partido: a.partido, candidatos: a.candidatos, w: a.mulheres / a.candidatos, wm: a.publico_mulheres / a.publico, wg: 100 * (a.publico_mulheres / a.publico - a.mulheres / a.candidatos),
      b: a.negros / a.candidatos, bm: a.publico_negros / a.publico, bg: 100 * (a.publico_negros / a.publico - a.negros / a.candidatos), publico: a.publico })), [
      { key: "partido", label: L("Partido", "Party"), text: true }, { key: "candidatos", label: L("Candidatos", "Candidates"), fmt: (v) => fmt(v) }, { key: "publico", label: L("Dinheiro público", "Public money"), fmt: (v) => brl(v) },
      { key: "w", label: L("Mulheres, candidatas", "Women, candidates"), fmt: (v) => pct(v, 1) }, { key: "wm", label: L("Mulheres, dinheiro", "Women, money"), fmt: (v) => pct(v, 1) },
      { key: "wg", label: L("Diferença", "Gap"), fmt: (v) => fmt(v, 1) },
      { key: "b", label: L("Negros, candidatos", "Black, candidates"), fmt: (v) => pct(v, 1) }, { key: "bm", label: L("Negros, dinheiro", "Black, money"), fmt: (v) => pct(v, 1) },
      { key: "bg", label: L("Diferença", "Gap"), fmt: (v) => fmt(v, 1) },
    ], { sortBy: "publico", pageSize: 40, name: `women-black-${year}` });
  };
  draw();
}

// ------------------------------------------------------------ money and results

const ORD = ["", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"];
const tenth = (d) => L(`${d}º decil`, `${ORD[d]} tenth`);

async function results(root) {
  const mine = local();
  const [D, cand] = await Promise.all([site("decis.csv"), candidatos()]);
  num(D, ["decil", "candidatos", "eleitos", "min", "max", "mediana"]);
  const offices = OFFICES.filter((o) => D.some((r) => r.cargo === o));
  let office = params.get("ro") || "Deputado Federal";
  if (!offices.includes(office)) office = offices[0];
  const controls = el("div", { className: "controls" }), body = el("div");
  root.append(controls, body);
  const draw = () => {
    mine.reset();
    controls.replaceChildren(select(L("Cargo", "Office"), offices.map((o) => ({ value: o, label: OFFICE[o] })), office, (v) => { office = v; setParam("ro", v, "Deputado Federal"); draw(); }));
    body.replaceChildren();
    const rows = D.filter((r) => r.cargo === office).sort((a, b) => a.decil - b.decil);
    const c1 = chart();
    body.append(card(L("Quanto mais dinheiro, maior a chance de vencer", "The more money, the more likely to win"),
      L(`Candidatos a ${lower(OFFICE[office])} divididos em dez grupos do mesmo tamanho (decis) pelo dinheiro arrecadado, do décimo com menos recursos ao mais bem financiado. A barra é a parcela de cada grupo que se elegeu.`,
        `${OFFICE[office]} candidates split into ten equal groups by money raised, from the least funded tenth to the best funded. The bar is the share of each group that was elected.`), c1));
    mine.later(() => C.bars(c1, {
      rows: rows.map((r) => ({ label: tenth(r.decil), value: r.eleitos / r.candidatos,
        title: L(`${tenth(r.decil)}: de ${brl(r.min)} a ${brl(r.max)} arrecadados`, `${tenth(r.decil)}: ${brl(r.min)} to ${brl(r.max)} raised`),
        note: L(`${fmt(r.eleitos)} de ${fmt(r.candidatos)} eleitos · mediana de ${brl(r.mediana)}`, `${fmt(r.eleitos)} of ${fmt(r.candidatos)} elected · median ${brl(r.mediana)}`) })),
      format: (v) => pct(v, 1), max: 1, labelWidth: 90, barHeight: 16,
      table: { rows, cols: [{ key: "decil", label: L("Decil", "Tenth") }, { key: "min", label: L("De", "From"), fmt: (v) => brl(v) }, { key: "max", label: L("Até", "To"), fmt: (v) => brl(v) },
        { key: "mediana", label: L("Mediana arrecadada", "Median raised"), fmt: (v) => brl(v) }, { key: "candidatos", label: L("Candidatos", "Candidates"), fmt: (v) => fmt(v) }, { key: "eleitos", label: L("Eleitos", "Elected"), fmt: (v) => fmt(v) }], name: `deciles-${office}-${year}` },
    }));
    const top = rows.find((r) => r.decil === 10), low = rows.filter((r) => r.decil <= 5);
    const seats = sum(rows.map((r) => r.eleitos));
    if (top && seats) body.append(finding(L(`Entre os 10% mais bem financiados, ${pct(top.eleitos / top.candidatos)} se elegeram, e eles ficaram com ${pct(top.eleitos / seats)} das cadeiras; a metade com menos dinheiro ficou com ${pct(sum(low.map((r) => r.eleitos)) / seats, 1)}.`,
      `The best-funded tenth won ${pct(top.eleitos / top.candidatos)} of its races and took ${pct(top.eleitos / seats)} of the seats; the less-funded half of candidates took ${pct(sum(low.map((r) => r.eleitos)) / seats, 1)}.`)));

    const sel = cand.filter((r) => r.cargo === office);
    if (sel.length) {
      const won = sel.filter(elected), lost = sel.filter((r) => !elected(r));
      const cands = (n) => plural(n, L("candidato", "candidate"), L("candidatos", "candidates"));
      tiles(body.appendChild(el("section", { className: "tiles" })), [
        { label: L("Arrecadação mediana, eleitos", "Median raised, elected"), value: brl(median(won.map((r) => r.total))), sub: cands(won.length) },
        { label: L("Arrecadação mediana, não eleitos", "Median raised, not elected"), value: brl(median(lost.map((r) => r.total))), sub: cands(lost.length) },
        { label: L("Eleitos: dinheiro do partido", "Elected: money from their party"), value: pct(sum(won.map((r) => r.origem_partido)) / sum(won.map((r) => r.total))), sub: L("parcela do que os eleitos arrecadaram", "share of what the winners raised") },
        { label: L("Eleitos: recursos próprios", "Elected: own money"), value: pct(sum(won.map((r) => r.origem_proprios)) / sum(won.map((r) => r.total)), 1), sub: brl(sum(won.map((r) => r.origem_proprios))) },
      ]);
    }
    const self = cand.filter((r) => r.origem_proprios > 0).sort((a, b) => b.origem_proprios - a.origem_proprios).slice(0, 20), c2 = chart();
    body.append(card(L("Quem pagou a própria campanha", "Who paid for their own campaign"),
      L("Candidatos a presidente, governador, senador e deputado federal que mais puseram dinheiro do próprio bolso na campanha, em todos os estados.",
        "Candidates for president, governor, senator and federal deputy who put the most of their own money into their campaign, across every state."), c2));
    mine.later(() => C.bars(c2, { rows: self.map((r) => ({ label: who(r), value: r.origem_proprios, color: elected(r) ? C.slot(1) : css("--other"),
      note: L(`${OFFICE[r.cargo]} · ${wonLabel(r)} · ${pct(r.origem_proprios / r.total)} do que arrecadou`, `${OFFICE[r.cargo]} · ${wonLabel(r)} · ${pct(r.origem_proprios / r.total)} of what they raised`) })),
    format: (v) => brl(v), labelWidth: 220, barHeight: 14, legend: [{ label: L("Eleito", "Elected"), color: C.slot(1) }, { label: L("Não eleito", "Not elected"), color: css("--other") }] }));
  };
  draw();
  const tb = el("div");
  root.append(card(L("Encontre um candidato", "Find a candidate"),
    L("Todos os candidatos a presidente, governador, senador e deputado federal, com quanto arrecadaram e de onde. Filtre por nome, partido, estado ou cargo.",
      "Every candidate for president, governor, senator and federal deputy, with what they raised and from where. Filter by name, party, state or office."), tb));
  table(tb, cand.map((r) => ({ ...r, office: OFFICE[r.cargo], result: RESULT[r.resultado] ?? r.resultado, inc: r.incumbente ? L("sim", "yes") : "" })), [
    { key: "nome_urna", label: L("Candidato", "Candidate"), text: true, wrap: true }, { key: "office", label: L("Cargo", "Office"), text: true }, { key: "uf", label: L("UF", "State"), text: true },
    { key: "partido", label: L("Partido", "Party"), text: true }, { key: "result", label: L("Resultado", "Result"), text: true }, { key: "inc", label: L("Em exercício", "Incumbent"), text: true },
    { key: "total", label: L("Arrecadado", "Raised"), fmt: (v) => brl(v) }, { key: "publico", label: L("Público", "Public"), fmt: (v) => brl(v) },
    { key: "origem_pessoas_fisicas", label: L("Pessoas físicas", "Individuals"), fmt: (v) => brl(v) }, { key: "origem_proprios", label: L("Próprios", "Own"), fmt: (v) => brl(v) },
    { key: "n_doadores_pf", label: L("Doadores", "Donors"), fmt: (v) => fmt(v) },
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
    { label: L("Doadores de R$ 50 mil ou mais", "Donors of R$50k or more"), value: fmt(gd.length), sub: L(`pessoas físicas, ${year}`, `private individuals, ${year}`) },
    { label: L("Quanto doaram", "What they gave"), value: brl(given), sub: L(`${pct(given / indiv)} de todo o dinheiro de pessoas físicas`, `${pct(given / indiv)} of all money from individuals`) },
    { label: L("Candidatos que financiaram", "Candidates they funded"), value: fmt(new Set(dd.map((r) => r.sq_candidato)).size), sub: L(`${fmt(dd.length)} pares doador–candidato`, `${fmt(dd.length)} donor–candidate pairs`) },
    { label: L("Maior doador", "Largest donor"), value: brl(top?.total),
      sub: top ? L(`${top.nome}, para ${plural(top.n_candidatos, "candidato", "candidatos")}`, `${top.nome}, to ${plural(top.n_candidatos, "candidate")}`) : "" },
  ]);
  const N = rede.nodes, E = rede.edges, nd = N.filter((n) => n.kind === "doador"), nc = N.filter((n) => n.kind === "candidato");
  const comp = components(N.length, E), maxV = Math.max(...nd.map((n) => n.valor), 1);
  const deg = N.map(() => 0);
  for (const [a, b] of E) { deg[a]++; deg[b]++; }
  const c1 = chart();
  root.append(card(L(`Os ${fmt(nd.length)} maiores doadores e os candidatos que financiaram`, `The ${nd.length} largest donors and the candidates they funded`),
    L("Cada ponto laranja é um doador (maior quanto mais dinheiro); cada ponto azul ou cinza, um candidato que recebeu dele; cada linha, uma doação. Doadores que apoiam os mesmos candidatos ficam próximos, então os aglomerados são grupos de doadores por trás de um mesmo conjunto de candidatos. Passe o mouse sobre um ponto para ver suas conexões.",
      "Each orange dot is a donor (bigger for more money), each blue or grey dot a candidate they gave to; a line is a donation. Donors who back the same candidates are pulled together, so clusters are groups of donors behind one slate. Hover a dot to see its connections."), c1,
    finding(L(`${fmt(nd.length)} doadores e ${fmt(nc.length)} candidatos. O maior grupo conectado reúne ${pct(comp[0] / N.length)} deles: ${comp.length > 1 ? `os outros ${fmt(N.length - comp[0])} estão em ${plural(comp.length - 1, "grupo separado", "grupos separados")}` : "todo doador está ligado a todos os outros por candidatos em comum"}.`,
      `${fmt(nd.length)} donors and ${fmt(nc.length)} candidates. The largest connected group holds ${pct(comp[0] / N.length)} of them: ${comp.length > 1 ? `the other ${fmt(N.length - comp[0])} sit in ${plural(comp.length - 1, "separate group")}` : "every donor is linked to every other through shared candidates"}.`))));
  later(() => C.network(c1, {
    height: Math.min(640, Math.max(380, (c1.clientWidth || 600) * 0.7)),
    nodes: N.map((n, i) => n.kind === "doador"
      ? { x: n.x, y: n.y, r: 3 + 7 * Math.sqrt(n.valor / maxV), color: C.slot(2), title: n.label, rows: [L(`Grande doador · doou ${brl(n.valor)} no total`, `Large donor · gave ${brl(n.valor)} in all`)] }
      : { x: n.x, y: n.y, r: 2.5, color: n.eleito ? C.slot(1) : css("--other"), title: `${n.label} (${n.partido}-${n.uf})`,
        rows: [`${OFFICE[n.cargo] || n.cargo} · ${n.eleito ? L("eleito", "elected") : L("não eleito", "not elected")}`, L(`${fmt(deg[i])} destes doadores`, `${deg[i]} of these donors`)] }),
    edges: E, legend: [{ label: L("Doador", "Donor"), color: C.slot(2) }, { label: L("Candidato eleito", "Elected candidate"), color: C.slot(1) }, { label: L("Não eleito", "Not elected"), color: css("--other") }],
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
  root.append(card(L("Doadores que apoiam os mesmos candidatos", "Donors who back the same candidates"),
    L("Pares entre os maiores doadores que deram a dois ou mais candidatos em comum. Sobreposição: candidatos em comum sobre todos os candidatos que qualquer um dos dois financiou (índice de Jaccard).",
      "Pairs among the largest donors who gave to two or more of the same candidates. Overlap: shared candidates over all the candidates either funded (Jaccard)."), t1),
  card(L("Candidatos com mais dinheiro de grandes doadores", "Candidates with the most money from large donors"),
    L("Dinheiro de doadores de R$ 50 mil ou mais, todos os cargos.", "Money from donors of R$50,000 or more, every office."), c2));
  table(t1, pr, [{ key: "a", label: L("Doador A", "Donor A"), text: true, wrap: true }, { key: "b", label: L("Doador B", "Donor B"), text: true, wrap: true },
    { key: "n", label: L("Candidatos em comum", "Shared candidates"), fmt: (v) => fmt(v) }, { key: "ja", label: L("Sobreposição", "Overlap"), fmt: (v) => pct(v) }], { sortBy: "n", pageSize: 10, name: `donor-pairs-${year}` });
  num(rec, ["grandes_doadores", "valor"]);
  later(() => C.bars(c2, { rows: rec.slice(0, 20).map((r) => ({ label: who(r), value: r.valor, color: elected(r) ? C.slot(1) : css("--other"),
    note: `${OFFICE[r.cargo] || r.cargo} · ${plural(r.grandes_doadores, L("grande doador", "large donor"), L("grandes doadores", "large donors"))}` })),
  format: (v) => brl(v), labelWidth: 200, barHeight: 14, legend: [{ label: L("Eleito", "Elected"), color: C.slot(1) }, { label: L("Não eleito", "Not elected"), color: css("--other") }] }));
  const t2 = el("div");
  root.append(card(L("Todos os doadores de R$ 50 mil ou mais", "Every donor of R$50,000 or more"),
    L("Pessoas físicas, com o CPF mascarado como faz a Controladoria-Geral da União (CGU). Doadores menores aparecem apenas como contagem nos totais de cada candidato.",
      "Private individuals, with their CPF masked the way the federal comptroller (CGU) does. Smaller donors appear only as a count in each candidate's totals."), t2));
  table(t2, gd, [{ key: "nome", label: L("Doador", "Donor"), text: true, wrap: true }, { key: "doador", label: L("CPF (mascarado)", "CPF (masked)"), text: true },
    { key: "total", label: L("Doou", "Gave"), fmt: (v) => brl(v) }, { key: "n_candidatos", label: L("Candidatos", "Candidates"), fmt: (v) => fmt(v) }], { sortBy: "total", pageSize: 15, name: `large-donors-${year}` });
}

// ------------------------------------------------------------ suppliers

async function suppliers(root) {
  const [F, R] = await Promise.all([site("fornecedores.csv"), resumo()]);
  for (const r of F) { r.total = +r.total; r.n_candidatos = +r.n_candidatos; }
  const spent = sum(R.map((r) => r.contratado)), top10 = sum(F.slice(0, 10).map((r) => r.total)), listed = sum(F.map((r) => r.total));
  const campaigns = (n) => plural(n, L("campanha", "campaign"), L("campanhas", "campaigns"));
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Contratado pelas campanhas", "Contracted by campaigns"), value: brl(spent), sub: L(`todos os cargos, ${year}`, `every office, ${year}`) },
    { label: L(`As ${fmt(F.length)} empresas que mais receberam`, `The ${fmt(F.length)} companies paid the most`), value: pct(listed / spent), sub: brl(listed) },
    { label: L("Só as 10 maiores", "The top 10 alone"), value: pct(top10 / spent), sub: brl(top10) },
    { label: L("Maior fornecedor", "Largest supplier"), value: brl(F[0]?.total), sub: F[0] ? L(`${F[0].nome}, para ${campaigns(F[0].n_candidatos)}`, `${F[0].nome}, for ${campaigns(F[0].n_candidatos)}`) : "" },
  ]);
  const g = el("div", { className: "grid2" }), c1 = chart(), c2 = chart();
  g.append(card(L("As empresas que mais receberam das campanhas", "The companies campaigns paid the most"),
    L("Despesas que os candidatos contrataram com cada empresa (CNPJ), todos os cargos.", "Expenses candidates contracted with each company (CNPJ), every office."), c1),
  card(L("O que o dinheiro comprou", "What the money bought"),
    L(`Os ${fmt(F.length)} maiores fornecedores agrupados pela atividade registrada (CNAE).`, `The ${fmt(F.length)} largest suppliers grouped by their registered activity (CNAE).`), c2));
  root.append(g);
  later(() => C.bars(c1, { rows: F.slice(0, 20).map((r) => ({ label: r.nome, value: r.total, note: `${campaigns(r.n_candidatos)} · ${r.cnae}` })), format: (v) => brl(v), labelWidth: 200, barHeight: 14 }));
  const act = new Map(), none = L("Não informada", "Not given");
  for (const r of F) act.set(r.cnae || none, (act.get(r.cnae || none) || 0) + r.total);
  later(() => C.bars(c2, { rows: [...act].map(([label, value]) => ({ label, value, note: L(`${pct(value / listed)} destes fornecedores`, `${pct(value / listed)} of these suppliers`) })).sort((a, b) => b.value - a.value).slice(0, 12),
    format: (v) => brl(v), labelWidth: 220, barHeight: 14 }));
  const t = el("div");
  root.append(card(L("Todos os fornecedores listados", "Every listed supplier"),
    L("Só empresas: pessoas pagas pelas campanhas (cabos eleitorais, motoristas) não aparecem.", "Companies only: people paid by campaigns (canvassers, drivers) are not listed."), t));
  table(t, F, [{ key: "nome", label: L("Empresa", "Company"), text: true, wrap: true }, { key: "cnpj", label: "CNPJ", text: true }, { key: "cnae", label: L("Atividade", "Activity"), text: true, wrap: true },
    { key: "total", label: L("Contratado", "Contracted"), fmt: (v) => brl(v) }, { key: "n_candidatos", label: L("Campanhas", "Campaigns"), fmt: (v) => fmt(v) }],
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
    select(L("Eleição", "Election"), [...YEARS].reverse().map((y) => ({ value: y, label: L(`Eleições gerais de ${y}`, `${y} general election`) })), year, (v) => {
      year = +v; setParam("e", v, String(latest)); redraws.length = 0; electionControl(); shown.forEach(render);
    }),
    year >= new Date().getFullYear() ? el("p", { className: "note", textContent: L(`As contas de ${year} ainda estão sendo entregues e julgadas: estes números vão mudar.`, `${year} accounts are still being filed and judged: these numbers will change.`) }) : "");
}

(async () => {
  YEARS = (await data("site/tse/anos.csv")).map((r) => +r.ano).sort((a, b) => a - b);
  year = YEARS.includes(+params.get("e")) ? +params.get("e") : YEARS[YEARS.length - 1];
  electionControl();
  tabs((name) => { shown.add(name); render(name); });
  onResize(() => redraws.forEach((f) => f()));
})();
