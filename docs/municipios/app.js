// My town: one municipality across the sources (mayors, amendment money, contracts, accounts), against similar towns.
import { $, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L, date } from "../lib/i18n.js";
import { setupPage } from "../lib/page.js";
import { townSearch } from "../lib/towns.js";

setupPage();

const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const finding = (text) => el("p", { className: "finding", textContent: text });
const grid = (...kids) => el("div", { className: "grid2" }, ...kids.map((k) => { k.classList.remove("wide"); return k; }));
const empty = (text) => el("p", { className: "empty", textContent: text });
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const redraws = [];
const later = (f) => { redraws.push(f); f(); };

const R = () => data("site/municipios/resumo.json");
const shard = (cod) => data(`site/municipios/perfil/${cod.slice(0, 4)}.json`);
const DEFAULT = "3550308";   // São Paulo, when no town is asked for

const BAND = { "under 5k": L("até 5 mil habitantes", "under 5,000 inhabitants"), "5k–20k": L("de 5 a 20 mil habitantes", "5,000 to 20,000 inhabitants"),
  "20k–100k": L("de 20 a 100 mil habitantes", "20,000 to 100,000 inhabitants"), "100k–500k": L("de 100 a 500 mil habitantes", "100,000 to 500,000 inhabitants"),
  "500k+": L("de 500 mil habitantes ou mais", "500,000 inhabitants or more") };
const TIPOS = [["especial", L("Pix (transferência especial)", "“Pix” (special transfer)"), 2], ["individual", L("Individual", "Individual"), 1],
  ["bancada", L("De bancada", "State bench"), 3], ["comissao", L("De comissão", "Committee"), 4], ["relator", L("De relator", "Rapporteur"), 5],
  ["", L("Sem código de emenda", "No amendment code"), 0]];
const tipoColor = (slot) => (slot ? C.slot(slot) : css("--other"));
const COLLECTIVE = { bancada: L("Bancada estadual", "State bench"), comissao: L("Comissão", "Committee"), relator: L("Relator-geral do Orçamento", "Budget rapporteur") };
const HOUSE = { camara: L("Câmara", "Câmara"), senado: L("Senado", "Senate") };
const LIMITS = [{ y: 48.6, label: L("alerta 48,6%", "alert 48.6%") }, { y: 51.3, label: L("prudencial 51,3%", "prudential 51.3%") }, { y: 54, label: L("máximo 54%", "maximum 54%") }];
const ST = { abaixo: L("Abaixo de 48,6%", "Below 48.6%"), acima_alerta: L("Faixa de alerta, 48,6–51,3%", "Alert band, 48.6–51.3%"),
  acima_prudencial: L("Faixa prudencial, 51,3–54%", "Prudential band, 51.3–54%"), acima_maximo: L("Acima do máximo, 54%+", "Over the maximum, 54%+") };
const stColor = (s) => ({ abaixo: css("--other"), acima_alerta: css("--warning"), acima_prudencial: css("--serious"), acima_maximo: css("--critical") })[s] || css("--grid");
const stTag = (s) => el("span", { className: "st", style: `--c:${stColor(s)}`, textContent: ST[s] || "" });
const REACH = { sim: L("A sanção alcançava o órgão", "The sanction reached the buyer"), possivel: L("Pode ter alcançado o órgão", "May have reached the buyer"),
  nao: L("Impedida por outro ente", "Barred by another body") };
const reachColor = (r) => ({ sim: css("--critical"), possivel: css("--serious"), nao: css("--other") })[r] || css("--line");
const reachTag = (r) => (r ? el("span", { className: "flag", style: `--c:${reachColor(r)}`, textContent: REACH[r] }) : "");
const WITHHELD = L("Pessoa ou empresa individual (nome omitido)", "Person or individual firm (name withheld)");
const PARTY = { PCDOB: "PCdoB", "UNIÃO": "União", REPUBLICANOS: "Republicanos", SOLIDARIEDADE: "Solidariedade", CIDADANIA: "Cidadania", AVANTE: "Avante", PODE: "Podemos", MOBILIZA: "Mobiliza", AGIR: "Agir", MISSÃO: "Missão" };
const party = (p) => PARTY[p] || p;
const cnpjFmt = (c) => (/^\d{14}$/.test(c) ? `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}` : c);
const above = (q, who) => (q == null ? "" : L(`acima de ${pct(Math.floor(q * 100) / 100)} dos ${who}`, `above ${pct(Math.floor(q * 100) / 100)} of ${who}`));
const perHab = (v) => (v == null ? "–" : brl(v, v < 100 ? 0 : 1));

/** Who governed in a calendar year: the regular winner of the election before the term, or a supplementary winner from the year after theirs. */
function mayorIn(mayors, y) {
  const c = mayors.map(([ano, dia, nome, partido, sup]) => ({ ano, nome, partido, sup, dia, from: sup ? +dia.slice(0, 4) + 1 : ano + 1 }))
    .filter((m) => m.ano + 1 <= y && y <= m.ano + 4 && m.from <= y).sort((a, b) => a.from - b.from || a.dia.localeCompare(b.dia));
  return c[c.length - 1] || null;
}

// ------------------------------------------------------------ one town

async function show(cod) {
  const [r, sh] = await Promise.all([R(), shard(cod).catch(() => ({}))]);
  const t = sh[cod];
  const out = $("#profile");
  if (!t) { out.replaceChildren(empty(L("Município não encontrado.", "Town not found."))); return; }
  setParam("town", cod, null);
  redraws.length = 0;
  document.title = `${t.n} (${t.uf}) · ${L("Meu município", "My town")} · political-eye`;
  const nowYear = +String(r.emendas.last_month || new Date().getFullYear()).slice(0, 4);
  const mayor = mayorIn(t.m, nowYear), band = BAND[t.k] || t.k;
  const inUF = L(`municípios de ${t.uf}`, `towns in ${t.uf}`), inBand = L(`municípios ${band}`, `towns of ${band}`);
  const box = el("div");
  out.replaceChildren(box);

  // Who they are
  const SECTIONS = [["sec-resumo", L("Resumo", "Summary")], ["sec-prefeitos", L("Prefeitos", "Mayors")], ["sec-emendas", L("Emendas", "Amendments")],
    ["sec-contratos", L("Contratos", "Contracts")], ["sec-contas", L("Contas", "Accounts")]];
  box.append(el("div", { className: "dossier", id: "sec-resumo" },
    el("h2", { className: "dname", textContent: t.n }),
    el("p", { className: "dmeta" }, el("span", { className: "chip", textContent: t.uf }), " ",
      el("span", { className: "chip soft", textContent: t.cap ? L("capital", "state capital") : band }), " ",
      L(`${fmt(t.p)} habitantes`, `${fmt(t.p)} inhabitants`),
      mayor ? L(` · prefeito(a): ${mayor.nome} (${party(mayor.partido)}), eleito(a) em ${mayor.sup ? date(mayor.dia) : mayor.ano}`,
        ` · mayor: ${mayor.nome} (${party(mayor.partido)}), elected in ${mayor.sup ? date(mayor.dia) : mayor.ano}`) : ""),
    el("p", { className: "dlinks" }, el("a", { href: `../siconfi/?tab=town&town=${cod}`, textContent: L("Finanças no painel do Siconfi", "Finances on the Siconfi page") }), " · ",
      el("a", { href: "../emendas/", textContent: L("Todas as emendas", "Every amendment") }), " · ", el("a", { href: "../pncp/", textContent: L("Todos os contratos", "Every contract") }))),
  el("nav", { className: "jump", "aria-label": L("Seções do perfil", "Profile sections") }, ...SECTIONS.map(([k, label]) => el("a", { href: `#${k}`, textContent: label,
    on: { click: (e) => { e.preventDefault(); document.getElementById(k)?.scrollIntoView({ behavior: "smooth", block: "start" }); } } }))));

  // In short
  const Y = t.a.y.map(([ano, total, especial, individual, bancada, comissao, relator, sem, municipal, privado, mesmo, conhecido]) =>
    ({ ano, total, especial, individual, bancada, comissao, relator, "": sem, municipal, privado, mesmo, conhecido }));
  const byYear = new Map(Y.map((y) => [y.ano, y]));
  const ref = r.ano_ref, refRow = byYear.get(ref), peerOf = (k, y) => (y == null ? r.peers[k] : r.peers[k]?.[String(y)]) || {};
  const F = t.f.y.map(([ano, dtp_pct, situacao, rcl, dtp, liquida]) => ({ ano, dtp_pct, situacao, rcl, dtp, liquida, caixa_hab: liquida == null || !t.p ? null : liquida / t.p }));
  const lastPay = F.filter((x) => x.dtp_pct != null).slice(-1)[0], lastCash = F.filter((x) => x.caixa_hab != null).slice(-1)[0];
  const rk = t.r, cv = t.c, cov = r.pncp;
  const medUF = (k, y) => peerOf(k, y)?.[t.uf], medBand = (k, y) => peerOf(k, y)?.[t.k];
  tiles(box.appendChild(el("section", { className: "tiles" })), [
    { label: L(`Emendas recebidas em ${ref}`, `Amendments received in ${ref}`), value: brl(refRow?.total || 0),
      sub: L(`${perHab(rk.emendas_hab?.[1])} por habitante; mediana de ${t.uf}: ${perHab(medUF("emendas_hab", ref))}`, `${perHab(rk.emendas_hab?.[1])} per inhabitant; ${t.uf} median: ${perHab(medUF("emendas_hab", ref))}`) },
    { label: L("Do partido do prefeito", "From the mayor's party"), value: t.a.mp ? pct(t.a.mp[0]) : L("sem dados", "no data"),
      sub: t.a.mp ? L(`desde 2017; pela divisão do dinheiro entre os partidos em ${t.uf}, seria ${pct(t.a.mp[1])}`, `since 2017; by how the money splits among parties in ${t.uf}, it would be ${pct(t.a.mp[1])}`)
        : L("nenhuma emenda de parlamentar com partido conhecido desde 2017", "no amendment from a member with a known party since 2017") },
    { label: L("Contratos de R$ 1 milhão ou mais", "Contracts of R$ 1 million or more"), value: brl(cv.v),
      sub: L(`${plural(cv.n, "contrato", "contratos")} em ${fmt(cov.days_read)} dias do PNCP lidos; mediana de ${t.uf}: ${perHab(medUF("contratos_hab"))} por habitante, aqui ${perHab(rk.contratos_hab?.[1])}`,
        `${plural(cv.n, "contract")} in ${fmt(cov.days_read)} PNCP days read; ${t.uf} median: ${perHab(medUF("contratos_hab"))} per inhabitant, here ${perHab(rk.contratos_hab?.[1])}`) },
    { label: L("Despesa com pessoal", "Payroll share"), value: lastPay ? `${fmt(lastPay.dtp_pct, 1)}%` : L("não lida", "not read"),
      sub: lastPay ? L(`${lastPay.ano}: ${(ST[lastPay.situacao] || "").toLowerCase()}; mediana de ${t.uf}: ${fmt(medUF("dtp_pct", lastPay.ano), 1)}%`,
        `${lastPay.ano}: ${(ST[lastPay.situacao] || "").toLowerCase()}; ${t.uf} median: ${fmt(medUF("dtp_pct", lastPay.ano), 1)}%`) : L("nenhum relatório de pessoal lido", "no payroll report read") },
  ]);

  // How it compares
  const RANKS = [
    ["emendas_hab", L(`Emendas recebidas por habitante, ${ref}`, `Amendments received per inhabitant, ${ref}`), perHab, ref],
    ["contratos_hab", L("Contratos de R$ 1 milhão ou mais por habitante", "Contracts of R$ 1 million or more per inhabitant"), perHab, null],
    ["dtp_pct", L(`Despesa com pessoal, % da receita${lastPay ? `, ${lastPay.ano}` : ""}`, `Payroll, % of revenue${lastPay ? `, ${lastPay.ano}` : ""}`), (v) => `${fmt(v, 1)}%`, lastPay?.ano],
    ["caixa_hab", L(`Caixa livre por habitante${lastCash ? `, ${lastCash.ano}` : ""}`, `Free cash per inhabitant${lastCash ? `, ${lastCash.ano}` : ""}`), perHab, lastCash?.ano],
  ];
  const ranks = el("div", { className: "ranks" });
  for (const [k, label, f, y] of RANKS) {
    const q = rk[k];
    ranks.append(el("div", { className: "rank" },
      el("span", { className: "rl" }, label, el("small", { textContent: L(`mediana de ${t.uf}: ${f(medUF(k, y))} · ${band}: ${f(medBand(k, y))}`, `${t.uf} median: ${f(medUF(k, y))} · ${band}: ${f(medBand(k, y))}`) })),
      el("span", { className: "track" }, el("i", { className: "mid" }),
        q?.[3] == null ? null : el("i", { className: "ring", style: `left:${100 * q[3]}%`, title: inBand }),
        q?.[2] == null ? null : el("b", { className: "dot", style: `left:${100 * q[2]}%`, title: inUF })),
      el("span", { className: "rv", textContent: q ? f(q[1]) : L("sem dado", "no data") })));
  }
  box.append(card(L("Como se compara", "How it compares"),
    L(`A posição de ${t.n} entre os municípios do mesmo estado (ponto) e entre os de porte parecido no país (círculo): menores valores à esquerda, maiores à direita; o traço marca a mediana.`,
      `Where ${t.n} stands among its state's towns (dot) and among towns of similar size nationwide (ring): lowest values on the left, highest on the right; the tick marks the median.`),
    ranks, el("div", { className: "rkey" }, el("span", {}, el("i", { style: "background:var(--accent)" }), inUF.replace(/^./, (c) => c.toUpperCase())),
      el("span", {}, el("i", { style: "border:2px solid var(--ink2);width:8px;height:8px" }), inBand.replace(/^./, (c) => c.toUpperCase())))));

  // ---------------------------------------------------------- mayors
  box.append(el("h3", { className: "dsec", id: "sec-prefeitos", textContent: L("Prefeitos", "Mayors") }));
  const tm = el("div");
  box.append(card(L("Quem governou", "Who governed"), L("Eleitos nas eleições municipais de 2016, 2020 e 2024 e em eventuais eleições suplementares, segundo o TSE. Uma eleição suplementar substitui o prefeito a partir do ano seguinte.",
    "Elected in the municipal elections of 2016, 2020 and 2024 and in any supplementary election, as TSE records them. A supplementary election replaces the mayor from the year after it."), tm));
  const M = t.m.map(([ano, dia, nome, partido, sup]) => ({ ano, dia, nome, partido: party(partido), sup, mandato: `${sup ? +dia.slice(0, 4) + 1 : ano + 1}–${ano + 4}` }));
  if (M.length) table(tm, M, [{ key: "mandato", label: L("Mandato", "Term"), text: true }, { key: "nome", label: L("Prefeito(a)", "Mayor"), text: true },
    { key: "partido", label: L("Partido", "Party"), text: true }, { key: "dia", label: L("Eleição", "Election"), text: true, fmt: (v) => date(v) },
    { key: "sup", label: L("Tipo", "Kind"), text: true, fmt: (v) => (v ? L("suplementar", "supplementary") : L("ordinária", "regular")) }], { search: false, sortBy: "dia", desc: false, name: `mayors-${cod}` });
  else tm.append(empty(L("O TSE não registra prefeito eleito para este município (Brasília e Fernando de Noronha não elegem prefeito).", "TSE records no elected mayor for this town (Brasília and Fernando de Noronha elect none).")));

  // ---------------------------------------------------------- amendments
  box.append(el("h3", { className: "dsec", id: "sec-emendas", textContent: L("Emendas parlamentares", "Parliamentary amendments") }));
  const all = sum(Y.map((y) => y.total)), pix = sum(Y.map((y) => y.especial)), priv = sum(Y.map((y) => y.privado)), first = r.emendas.first;
  const years = []; for (let y = first; y <= nowYear; y++) years.push(y);
  tiles(box.appendChild(el("section", { className: "tiles" })), [
    { label: L(`Recebido desde ${first}`, `Received since ${first}`), value: brl(all), sub: L("pagos à prefeitura e aos fundos e órgãos do município", "paid to the town government, its funds and bodies") },
    { label: L("Por Pix", "By “Pix”"), value: brl(pix), sub: all ? L(`${pct(pix / all)} do total, direto na conta da prefeitura`, `${pct(pix / all)} of the total, straight into the town's account`) : "" },
    { label: L(`Por habitante em ${ref}`, `Per inhabitant in ${ref}`), value: perHab(rk.emendas_hab?.[1]),
      sub: [above(rk.emendas_hab?.[2], inUF), L(`mediana ${band}: ${perHab(medBand("emendas_hab", ref))}`, `${band} median: ${perHab(medBand("emendas_hab", ref))}`)].filter(Boolean).join(" · ") },
    { label: L("A entidades e empresas locais", "To local organisations and firms"), value: brl(priv), sub: L("pagos a associações, fundações e empresas sediadas no município, fora do total", "paid to associations, foundations and firms based in the town, not in the total") },
  ]);
  const c1 = chart(), c2 = chart();
  box.append(grid(card(L("Por ano e tipo de emenda", "By year and type of amendment"), L("Pagamentos ao governo municipal no ano em que foram feitos. As emendas Pix caem direto na conta da prefeitura, sem finalidade definida.",
    "Payments to the town government in the year they were made. “Pix” amendments land straight in the town's account, with no defined purpose."), c1),
  card(L("Por habitante, diante de municípios parecidos", "Per inhabitant, against similar towns"), L(`Comparado com a mediana dos municípios de ${t.uf} e dos municípios ${band} no país.`,
    `Against the median of ${t.uf}'s towns and of towns of ${band} nationwide.`), c2)));
  later(() => C.stack(c1, { x: years, height: 230, format: (v) => brl(v, 0), series: TIPOS.map(([k, label, slot]) => ({ name: label, color: tipoColor(slot), values: years.map((y) => byYear.get(y)?.[k] || 0) }))
    .filter((s) => s.values.some((v) => v > 0)) }));
  later(() => C.line(c2, { x: "num", xTicks: years.filter((y) => y % 2 === 0), height: 230, y: { min: 0, format: (v) => brl(v, 0) },
    series: [{ name: L(`Mediana de ${t.uf}`, `${t.uf} median`), color: css("--other"), width: 1.5, points: years.map((y) => [y, medUF("emendas_hab", y) ?? null]) },
      { name: L("Mediana do porte", "Size-band median"), color: C.slot(3), width: 1.5, points: years.map((y) => [y, medBand("emendas_hab", y) ?? null]) },
      { name: t.n, color: C.slot(1), points: years.map((y) => [y, (byYear.get(y)?.total || 0) / t.p]) }] }));
  const health = years.filter((y) => y >= 2025).some((y) => byYear.get(y)?.municipal) ;
  box.append(el("p", { className: "about", textContent: L(
    `Até 2024 o Portal da Transparência registrava a maior parte dos repasses de saúde ("fundo a fundo") como pagos ao Banco do Brasil, em Brasília, sem o município de destino: R$ 14 a 19 bilhões por ano no país. A partir de 2025 eles aparecem pagos ao fundo de saúde de cada município. ${health ? "Por isso o salto deste município em 2025 é, em boa parte, uma mudança no registro." : "Os anos anteriores a 2025 subestimam o dinheiro da saúde."}`,
    `Until 2024 the Transparency Portal recorded most health transfers ("fundo a fundo") as paid to Banco do Brasil in Brasília, with no destination town: R$ 14 to 19 billion a year nationwide. From 2025 they appear paid to each town's health fund. ${health ? "So this town's jump in 2025 is largely a change in the record." : "Years before 2025 understate health money."}`) }));

  const ta = el("div"), c3 = chart();
  box.append(grid(card(L("Quem mandou o dinheiro", "Who sent the money"), L("Os autores das emendas pagas ao município, de todos os anos; o partido é o do parlamentar no último pagamento, com o nome de hoje. Bancadas, comissões e o relator do Orçamento não têm partido.",
    "The authors of the amendments paid to the town, every year; the party is the member's at the latest payment, under today's name. Benches, committees and the budget rapporteur have no party."), ta),
  card(L("Por partido do autor", "By the author's party"), L(`Com o nome de hoje dos partidos que se fundiram ou mudaram de nome. ${mayor ? `Em destaque, o partido do prefeito atual (${party(mayor.partido)}).` : ""}`,
    `Under today's name of parties that merged or were renamed. ${mayor ? `Highlighted: the current mayor's party (${party(mayor.partido)}).` : ""}`), c3)));
  const AU = t.a.au.map(([kind, nome, partido, casa, total, pixv, y0, y1, extra]) => {
    const who = kind === "p" || kind === "u" ? nome : kind === "c" ? (extra === "relator" || !nome ? COLLECTIVE[extra] || nome : nome)
      : kind === "n" ? L("Pagamentos sem código de emenda", "Payments with no amendment code") : L(`Outros ${extra} autores`, `${extra} other authors`);
    return { kind, who, partido: party(partido), casa: HOUSE[casa] || "", total, pix: pixv, anos: y0 === y1 ? String(y0) : `${y0}–${y1}`, link: kind === "p" && extra ? extra : "" };
  });
  if (AU.length) table(ta, AU, [
    { key: "who", label: L("Autor", "Author"), text: true, wrap: true, fmt: (v, x) => (x.link ? el("a", { href: `../deputados/?tab=profile&leg=${x.link.split(":")[0]}&dep=${x.link.split(":")[1]}`, textContent: v }) : v) },
    { key: "partido", label: L("Partido", "Party"), text: true }, { key: "casa", label: L("Casa", "House"), text: true },
    { key: "total", label: L("Pago", "Paid"), fmt: (v) => brl(v) }, { key: "pix", label: "Pix", fmt: (v) => (v ? brl(v) : "") }, { key: "anos", label: L("Anos", "Years"), text: true }],
  { search: false, pageSize: 13, sortBy: "total", name: `authors-${cod}` });
  else ta.append(empty(L("Nenhuma emenda paga ao governo municipal.", "No amendment paid to the town government.")));
  const mine = mayor ? party(mayor.partido) : null;
  later(() => C.bars(c3, { rows: t.a.pa.map(([p, v]) => ({ label: party(p), value: v, color: party(p) === mine ? C.slot(1) : css("--other") })), format: (v) => brl(v), labelWidth: 90,
    empty: L("Nenhum autor com partido conhecido.", "No author with a known party.") }));
  if (t.a.mp) box.append(finding(L(
    `Desde 2017, ${pct(t.a.mp[0])} dos ${brl(t.a.mp[2])} enviados por parlamentares com partido conhecido vieram do partido do prefeito da época. Se ${t.n} recebesse como os municípios de ${t.uf} recebem, partido a partido, seria ${pct(t.a.mp[1])}. Mais do que isso é uma associação, não prova de favorecimento: prefeitos podem pedir mais a quem é do seu partido.`,
    `Since 2017, ${pct(t.a.mp[0])} of the ${brl(t.a.mp[2])} sent by members with a known party came from the party of the mayor at the time. Had ${t.n} received as ${t.uf}'s towns do, party by party, it would be ${pct(t.a.mp[1])}. More than that is an association, not proof of favour: mayors may ask more of their own party.`)));
  const ty = el("div");
  box.append(card(L("Ano a ano", "Year by year"), L("O partido é o do prefeito no ano; a parcela do partido do prefeito conta só o dinheiro de parlamentares com partido conhecido. Fundos: o que foi pago aos fundos (saúde, educação) e demais órgãos do município, e não ao CNPJ da prefeitura.",
    "The party is the mayor's that year; the mayor's-party share counts only money from members with a known party. Funds: what was paid to the town's funds (health, education) and other bodies rather than the town's own CNPJ."), ty));
  const YT = years.map((y) => { const x = byYear.get(y) || {}, m = mayorIn(t.m, y); return { ano: y, prefeito: m ? party(m.partido) : "", total: x.total || 0, pix: x.especial || 0, fundos: x.municipal || 0,
    hab: (x.total || 0) / t.p, mesmo: x.conhecido ? x.mesmo / x.conhecido : null, privado: x.privado || 0 }; }).filter((x) => x.total || x.privado);
  table(ty, YT, [{ key: "ano", label: L("Ano", "Year") }, { key: "prefeito", label: L("Prefeito", "Mayor"), text: true }, { key: "total", label: L("Recebido", "Received"), fmt: (v) => brl(v) },
    { key: "pix", label: "Pix", fmt: (v) => (v ? brl(v) : "") }, { key: "fundos", label: L("A fundos", "To funds"), fmt: (v) => (v ? brl(v) : "") },
    { key: "hab", label: L("Por habitante", "Per inhabitant"), fmt: (v) => perHab(v) }, { key: "mesmo", label: L("Do partido do prefeito", "From mayor's party"), fmt: (v) => (v == null ? "" : pct(v)) },
    { key: "privado", label: L("A entidades locais", "To local bodies"), fmt: (v) => (v ? brl(v) : "") }], { search: false, pageSize: 15, sortBy: "ano", name: `amendments-${cod}` });

  // ---------------------------------------------------------- contracts
  box.append(el("h3", { className: "dsec", id: "sec-contratos", textContent: L("Contratos", "Contracts") }));
  box.append(el("p", { className: "cover" }, el("b", { textContent: L(`Histórico em leitura: ${fmt(cov.days_read)} de ${fmt(cov.span_days)} dias`, `History being read: ${fmt(cov.days_read)} of ${fmt(cov.span_days)} days`) }),
    L(` de publicação no PNCP desde ${date(cov.since)} (lidos de ${date(cov.first)} a ${date(cov.last)}). Os contratos grandes são os de R$ 1 milhão ou mais; com empresas impedidas, todos. Todo número abaixo cobre só esses dias.`,
      ` of PNCP publications since ${date(cov.since)} (read from ${date(cov.first)} to ${date(cov.last)}). Large contracts are those of R$ 1 million or more; with barred companies, all of them. Every number below covers only those days.`)));
  const s = cv.s, sim = s.sim || [0, 0], poss = s.possivel || [0, 0], nao = s.nao || [0, 0];
  tiles(box.appendChild(el("section", { className: "tiles" })), [
    { label: L("Contratos grandes", "Large contracts"), value: fmt(cv.n), sub: L(`${brl(cv.v)} assinados pelos órgãos do município`, `${brl(cv.v)} signed by the town's bodies`) },
    { label: L("Por habitante", "Per inhabitant"), value: perHab(rk.contratos_hab?.[1]), sub: [above(rk.contratos_hab?.[2], inUF), L(`mediana ${band}: ${perHab(medBand("contratos_hab"))}`, `${band} median: ${perHab(medBand("contratos_hab"))}`)].filter(Boolean).join(" · ") },
    { label: L("Com empresa impedida de contratar com ele", "With a company barred from contracting with it"), value: fmt(sim[0] + poss[0]),
      sub: L(`${brl(sim[1] + poss[1])}; a sanção alcançava (${fmt(sim[0])}) ou pode ter alcançado (${fmt(poss[0])}) o órgão`, `${brl(sim[1] + poss[1])}; the sanction reached (${fmt(sim[0])}) or may have reached (${fmt(poss[0])}) the buyer`) },
    { label: L("Com empresa impedida por outro ente", "With a company barred by another body"), value: fmt(nao[0]), sub: L(`${brl(nao[1])}; uma sanção de outro município ou esfera, que não proíbe este contrato`, `${brl(nao[1])}; a sanction by another town or sphere, which does not bar this contract`) },
  ]);
  const c4 = chart(), tt = el("div");
  box.append(card(L("Os maiores fornecedores", "The largest suppliers"), L("Pelo valor dos contratos de R$ 1 milhão ou mais. Em cor, os que assinaram algum contrato com o município enquanto estavam impedidos de contratar.",
    "By the value of contracts of R$ 1 million or more. In colour, those who signed a contract with the town while barred from public contracts."), c4),
  card(L("Os maiores contratos", "The largest contracts"), "", tt));
  const FO = cv.f.map(([doc, nome, n, v, reach]) => ({ doc, nome, n, v, reach }));
  later(() => C.bars(c4, { rows: FO.map((x) => ({ label: x.nome || WITHHELD, value: x.v, color: x.reach ? reachColor(x.reach) : css("--line"),
    note: `${plural(x.n, L("contrato", "contract"), L("contratos", "contracts"))}${x.reach ? ` · ${REACH[x.reach]}` : ""}`, title: `${x.nome || WITHHELD} · ${cnpjFmt(x.doc)}` })),
  format: (v) => brl(v), labelWidth: 120, empty: L("Nenhum contrato de R$ 1 milhão ou mais nos dias lidos.", "No contract of R$ 1 million or more in the days read."),
  legend: FO.some((x) => x.reach) ? Object.keys(REACH).filter((k) => FO.some((x) => x.reach === k)).map((k) => ({ label: REACH[k], color: reachColor(k) })).concat([{ label: L("Sem sanção na data", "Not barred on the day"), color: css("--line") }]) : [] }));
  if (cv.t.length) table(tt, cv.t.map(([dia, orgao, nome, obj, v]) => ({ dia, orgao, nome: nome || WITHHELD, obj, v })), [
    { key: "dia", label: L("Assinado", "Signed"), text: true }, { key: "orgao", label: L("Órgão", "Body"), text: true, wrap: true },
    { key: "nome", label: L("Fornecedor", "Supplier"), text: true, wrap: true }, { key: "obj", label: L("Objeto", "Object"), text: true, wrap: true }, { key: "v", label: L("Valor", "Value"), fmt: (v) => brl(v) }],
  { search: false, pageSize: 5, sortBy: "v", name: `contracts-${cod}` });
  else tt.append(empty(L("Nenhum contrato de R$ 1 milhão ou mais nos dias lidos.", "No contract of R$ 1 million or more in the days read.")));
  if (cv.x) box.append(el("p", { className: "about", textContent: L(`${plural(cv.x, "contrato ficou", "contratos ficaram")} de fora por um valor implausível (acima de R$ 10 bilhões ou de três anos da receita do município); veja a página de contratos.`,
    `${plural(cv.x, "contract was", "contracts were")} left out for an implausible value (over R$ 10 billion or three years of the town's revenue); see the contracts page.`) }));
  const tb = el("div");
  box.append(card(L("Contratos com empresas impedidas na data", "Contracts with companies barred on the day"), L("Contratos de qualquer valor assinados pelos órgãos do município com uma empresa que estava no CEIS ou no CNEP, com sanção que proíbe contratar, no dia da assinatura, quando a sanção alcançava ou pode ter alcançado o órgão. Não é prova de irregularidade: pode ser um aditivo de contrato anterior à sanção, ou uma decisão judicial que a lista não mostra.",
    "Contracts of any value the town's bodies signed with a company on CEIS or CNEP, under a sanction that bars contracting, on the day it was signed, when the sanction reached or may have reached the buyer. Not proof of wrongdoing: it may amend a contract older than the sanction, or follow a court order the list does not show."), tb));
  if (cv.sl.length) table(tb, cv.sl.map(([dia, orgao, doc, nome, obj, v, reach, cat, quem]) => ({ dia, orgao, doc, nome: nome || WITHHELD, obj, v, reach, cat, quem })), [
    { key: "dia", label: L("Assinado", "Signed"), text: true }, { key: "orgao", label: L("Órgão", "Body"), text: true, wrap: true },
    { key: "nome", label: L("Empresa", "Company"), text: true, wrap: true, fmt: (v, x) => el("a", { href: `../sancoes/?tab=company&cnpj=${x.doc}`, textContent: v, title: cnpjFmt(x.doc) }) },
    { key: "obj", label: L("Objeto", "Object"), text: true, wrap: true }, { key: "v", label: L("Valor", "Value"), fmt: (v) => brl(v) },
    { key: "reach", label: L("Alcance", "Reach"), text: true, fmt: (v) => reachTag(v) }, { key: "quem", label: L("Quem puniu", "Sanctioned by"), text: true, wrap: true }],
  { search: false, pageSize: 10, sortBy: "v", name: `barred-${cod}` });
  else tb.append(empty(L("Nenhum nos dias lidos.", "None in the days read.")));

  // ---------------------------------------------------------- accounts
  box.append(el("h3", { className: "dsec", id: "sec-contas", textContent: L("Contas", "Accounts") }));
  tiles(box.appendChild(el("section", { className: "tiles" })), [
    { label: L("Despesa com pessoal", "Payroll share"), value: lastPay ? `${fmt(lastPay.dtp_pct, 1)}%` : L("não lida", "not read"),
      sub: lastPay ? [L(`da receita corrente líquida em ${lastPay.ano}`, `of net current revenue in ${lastPay.ano}`), above(rk.dtp_pct?.[2], inUF)].filter(Boolean).join(" · ") : L("nenhum relatório de pessoal lido", "no payroll report read") },
    { label: L("Situação", "Status"), value: lastPay ? ({ abaixo: L("Regular", "Within"), acima_alerta: L("Alerta", "Alert"), acima_prudencial: L("Prudencial", "Prudential"), acima_maximo: L("Acima do máximo", "Over the maximum") })[lastPay.situacao] || L("Regular", "Within") : L("não lida", "not read"),
      sub: lastPay ? ST[lastPay.situacao] || "" : "" },
    { label: L("Caixa livre por habitante", "Free cash per inhabitant"), value: lastCash ? perHab(lastCash.caixa_hab) : L("não lido", "not read"),
      sub: lastCash ? L(`fim de ${lastCash.ano}; mediana de ${t.uf}: ${perHab(medUF("caixa_hab", lastCash.ano))}`, `end of ${lastCash.ano}; ${t.uf} median: ${perHab(medUF("caixa_hab", lastCash.ano))}`) : "" },
    { label: L("Receita corrente líquida", "Net current revenue"), value: lastPay?.rcl ? brl(lastPay.rcl) : L("não lida", "not read"), sub: lastPay?.rcl ? L(`${perHab(lastPay.rcl / t.p)} por habitante, ${lastPay.ano}`, `${perHab(lastPay.rcl / t.p)} per inhabitant, ${lastPay.ano}`) : "" },
  ]);
  if (t.f.nf.length) box.append(el("p", { className: "about", textContent: L(`O município não entregou o relatório fiscal de ${t.f.nf.join(", ")} ao Siconfi (até a última consulta).`, `The town filed no fiscal report for ${t.f.nf.join(", ")} on Siconfi (as of the latest check).`) }));
  const c5 = chart(), c6 = chart();
  box.append(grid(card(L("Despesa com pessoal ao longo do tempo", "Payroll share over time"), L(`Diante dos três limites da Lei de Responsabilidade Fiscal e da mediana dos municípios de ${t.uf} e dos ${band}.`,
    `Against the Fiscal Responsibility Law's three limits and the median of ${t.uf}'s towns and of towns of ${band}.`), c5),
  card(L("Caixa livre no fim do ano, por habitante", "Free cash at year end, per inhabitant"), L("O caixa sem vinculação depois dos restos a pagar. Abaixo de zero, o município fecha o ano devendo mais do que tem livre.",
    "Unrestricted cash after commitments carried over. Below zero, the town ends the year owing more than it holds free."), c6)));
  const FY = F.map((x) => x.ano), fx = FY.length ? FY : years;
  later(() => (F.some((x) => x.dtp_pct != null) ? C.line(c5, { x: "num", xTicks: fx.filter((y) => y % 2 === 1), height: 230, ref: LIMITS,
    y: { min: Math.min(30, ...F.map((x) => x.dtp_pct ?? 99)), max: Math.max(60, ...F.map((x) => x.dtp_pct ?? 0)), format: (v) => `${fmt(v)}%` },
    series: [{ name: L(`Mediana de ${t.uf}`, `${t.uf} median`), color: css("--other"), width: 1.5, points: fx.map((y) => [y, medUF("dtp_pct", y) ?? null]) },
      { name: L("Mediana do porte", "Size-band median"), color: C.slot(3), width: 1.5, points: fx.map((y) => [y, medBand("dtp_pct", y) ?? null]) },
      { name: t.n, color: C.slot(1), points: F.map((x) => [x.ano, x.dtp_pct]) }] }) : c5.replaceChildren(empty(L("Nenhum relatório de pessoal lido.", "No payroll report read.")))));
  later(() => (F.some((x) => x.caixa_hab != null) ? C.line(c6, { x: "num", xTicks: fx.filter((y) => y % 2 === 1), height: 230, y: { format: (v) => brl(v, 0) }, ref: [{ y: 0, label: "" }],
    series: [{ name: L(`Mediana de ${t.uf}`, `${t.uf} median`), color: css("--other"), width: 1.5, points: fx.map((y) => [y, medUF("caixa_hab", y) ?? null]) },
      { name: L("Mediana do porte", "Size-band median"), color: C.slot(3), width: 1.5, points: fx.map((y) => [y, medBand("caixa_hab", y) ?? null]) },
      { name: t.n, color: C.slot(1), points: F.map((x) => [x.ano, x.caixa_hab]) }] }) : c6.replaceChildren(empty(L("Nenhum relatório de caixa lido.", "No cash report read.")))));
  const tf = el("div");
  box.append(card(L("Ano a ano", "Year by year"), L("Do último relatório lido de cada ano; no ano corrente, pode ser ainda o do segundo quadrimestre.", "From each year's latest report read; for the current year it may still be the second four-month period's."), tf));
  if (F.length) table(tf, F, [{ key: "ano", label: L("Ano", "Year") }, { key: "dtp_pct", label: L("Pessoal (%)", "Payroll %"), fmt: (v) => (v == null ? "" : fmt(v, 1)) },
    { key: "situacao", label: L("Situação", "Status"), text: true, fmt: (v) => (v ? stTag(v) : "") }, { key: "rcl", label: L("Receita (RCL)", "Revenue"), fmt: (v) => (v == null ? "" : brl(v)) },
    { key: "dtp", label: L("Pessoal", "Payroll"), fmt: (v) => (v == null ? "" : brl(v)) }, { key: "liquida", label: L("Caixa livre", "Free cash"), fmt: (v) => (v == null ? "" : brl(v)) }],
  { search: false, pageSize: 15, sortBy: "ano", name: `accounts-${cod}` });
  else tf.append(empty(L("Nenhum relatório fiscal lido.", "No fiscal report read.")));
}

// ------------------------------------------------------------ page

function start() {
  const search = townSearch({ label: L("Encontre um município", "Find a town"), onPick: (t) => { show(t.cod); window.scrollTo({ top: 0 }); } });
  $("#find").replaceChildren(el("label", { style: "flex:1 1 360px" }, L("Encontre um município", "Find a town"), search));
  return show(params.get("town") || DEFAULT);
}
guard($("#profile"), start);
onResize(() => redraws.forEach((f) => f()));
