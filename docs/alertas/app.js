// Red flags: patterns across the open data worth a closer look. A flag is not evidence of an irregularity.
import { $, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L, month } from "../lib/i18n.js";
import { setupPage } from "../lib/page.js";

setupPage();

const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const grid = (...kids) => el("div", { className: "grid2" }, ...kids.map((k) => { k.classList.remove("wide"); return k; }));
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const later = (() => { const fs = []; onResize(() => fs.forEach((f) => f())); return (f) => { fs.push(f); f(); }; })();
const R = (() => { let p; return () => (p ??= data("site/alertas/resumo.json")); })();

// ------------------------------------------------------------ names and links

const WITHHELD = L("Empresa individual (nome omitido)", "Individual firm (name withheld)");
const cnpjFmt = (c) => (/^\d{14}$/.test(c) ? `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}` : c);
/** A company: its name (or that it is withheld), linked to its sanctions profile when it has one. */
function company(r, { sanctioned = false } = {}) {
  const name = +r.pf ? el("span", { className: "withheld", textContent: WITHHELD }) : r.nome || cnpjFmt(r.cnpj);
  const label = el("span", {}, name, el("br"), el("small", { className: "hint", textContent: cnpjFmt(r.cnpj) }));
  return sanctioned ? el("a", { href: `../sancoes/?tab=company&cnpj=${r.cnpj}` }, label) : label;
}
/** A member of Congress: their profile on this site (deputies), the Senate's (senators), or just the name. */
function member(r) {
  const name = r.deputado || r.autor || "–";
  const href = r.deputado_id && +r.leg ? `../deputados/?tab=profile&leg=${r.leg}&dep=${r.deputado_id}`
    : r.senador_id ? `https://www25.senado.leg.br/web/senadores/senador/-/perfil/${r.senador_id}` : null;
  const who = href ? el("a", { href, textContent: name }) : el("span", { textContent: name });
  return el("span", {}, who, r.partido || r.uf ? el("small", { className: "hint", textContent: ` ${[r.partido, r.uf].filter(Boolean).join("-")}` }) : null);
}
const day = (d) => el("span", { className: "nowrap", textContent: d || "–" });
const monthSpan = (a, b) => (a === b ? a : `${a} – ${b}`);

/** The three boxes every flag opens with: the rule, the baseline, and why it may be innocent. */
function explain(root, { rule, base, innocent }) {
  root.append(el("div", { className: "rule" },
    el("div", { className: "card" }, el("h2", { textContent: L("A regra", "The rule") }), el("p", { textContent: rule })),
    el("div", { className: "card" }, el("h2", { textContent: L("Comparado com", "Measured against") }), el("p", { textContent: base })),
    el("div", { className: "card" }, el("h2", { textContent: L("Explicações inocentes comuns", "Common innocent explanations") }), el("ul", {}, ...innocent.map((t) => el("li", { textContent: t }))))));
}
const byParty = (rows, value) => {
  const m = new Map();
  for (const r of rows) { const k = r.partido || L("sem partido", "no party"); m.set(k, (m.get(k) || 0) + value(r)); }
  return [...m].sort((a, b) => b[1] - a[1]).slice(0, 15).map(([label, v]) => ({ label, value: v, color: css("--accent") }));
};

// ------------------------------------------------------------ overview

const FLAGS = [
  { tab: "barred", title: L("Emendas pagas a empresas impedidas", "Amendments paid to barred companies"), key: "emendas_impedidas",
    text: (x) => L(`${plural(x.empresas, "empresa", "empresas")} receberam dinheiro de emendas enquanto uma sanção as impedia de contratar com o poder público.`,
      `${plural(x.empresas, "company", "companies")} received amendment money while a sanction barred them from public contracts.`) },
  { tab: "contracts", title: L("Contratos com empresas impedidas", "Contracts with barred companies"), key: "contratos_impedidas",
    text: (x) => L(`contratos assinados por órgãos que a sanção alcançava, com ${plural(x.empresas, "empresa impedida", "empresas impedidas")} na data (${fmt(x.dias_lidos)} dias do PNCP lidos).`,
      `contracts signed by bodies the sanction covered, with ${plural(x.empresas, "company", "companies")} barred on the day (${fmt(x.dias_lidos)} PNCP days read).`) },
  { tab: "campaign", title: L("Fornecedor de campanha pago com emendas do parlamentar", "Campaign supplier paid from the member's amendments"), key: "campanha_emendas",
    text: (x) => L(`empresas e entidades privadas que trabalharam na campanha de um deputado e depois receberam dinheiro das emendas desse mesmo deputado.`,
      `companies and private bodies that worked for a deputy's campaign and later received money from that same deputy's amendments.`) },
  { tab: "concentration", title: L("Emendas concentradas em uma entidade privada", "Amendments concentrated on one private recipient"), key: "concentracao",
    text: (x) => L(`parlamentares que mandaram 25% ou mais do dinheiro das suas emendas para uma só entidade ou empresa privada (o parlamentar típico manda ${pct(x.base?.mediana_maior_share, 1)}).`,
      `members who sent 25% or more of their amendment money to a single private body or company (the typical member sends ${pct(x.base?.mediana_maior_share, 1)}).`) },
  { tab: "dominant", title: L("Órgão dominado por um fornecedor", "Buyer dominated by one supplier"), key: "fornecedor_dominante",
    text: (x) => L(`órgãos públicos em que um único fornecedor levou 80% ou mais do valor dos grandes contratos (a mediana é ${pct(x.mediana_maior_share)}).`,
      `public buyers where one supplier took 80% or more of their large contracts' value (the median is ${pct(x.mediana_maior_share)}).`) },
  { tab: "leniency", title: L("Contratos após acordo de leniência", "Contracts after a leniency agreement"), key: "leniencia_contratos",
    text: (x) => L(`grandes contratos assinados por ${plural(x.empresas, "empresa", "empresas")} depois de admitir irregularidades em acordo de leniência.`,
      `large contracts signed by ${plural(x.empresas, "company", "companies")} after admitting wrongdoing in a leniency agreement.`) },
];

async function overview(root, go) {
  const r = await R();
  root.append(el("div", { className: "flags" }, ...FLAGS.map((f) => {
    const x = r[f.key] || {};
    const money = x.valor ? el("small", { textContent: brl(x.valor) }) : null;
    return el("button", { type: "button", className: "flag-card", on: { click: () => go(f.tab) } },
      el("h3", { textContent: f.title }), el("span", { className: "big" }, fmt(x.casos || 0), money), el("p", { textContent: f.text(x) }),
      el("span", { className: "go", textContent: L("Ver a lista →", "See the list →") }));
  })));
  const c = r.cruzamentos || {};
  root.append(el("p", { className: "about", style: "margin-top:18px" },
    L(`${plural(c.entidades || 0, "empresa ou entidade aparece", "empresas ou entidades aparecem")} em duas listas ou mais, e ${plural(c.parlamentares || 0, "parlamentar", "parlamentares")} também. `,
      `${plural(c.entidades || 0, "company or body appears", "companies or bodies appear")} on two lists or more, and so ${(c.parlamentares || 0) === 1 ? "does" : "do"} ${plural(c.parlamentares || 0, "member of Congress", "members of Congress")}. `),
    el("a", { href: "?tab=cross", textContent: L("Ver quem →", "See who →"), on: { click: (e) => { e.preventDefault(); go("cross"); } } })));
}

// ------------------------------------------------------------ 1. amendments paid while barred

const REACH = { sim: L("alcança verbas federais", "covers federal money"), possivel: L("pode alcançar", "may cover") };
async function barred(root) {
  const r = (await R()).emendas_impedidas, rows = await data("site/alertas/emendas_impedidas.csv");
  explain(root, {
    rule: L("Um pagamento de emenda a uma empresa (CNPJ) num mês em que ela estava no CEIS ou no CNEP com uma sanção que impede contratar — impedimento, inidoneidade ou suspensão — e cujo alcance cobre, ou pode cobrir, dinheiro federal.",
      "An amendment payment to a company (CNPJ) in a month when it was on CEIS or CNEP under a sanction that bars contracting (ban, unfitness or suspension) whose reach covers, or may cover, federal money."),
    base: L(`Todos os pagamentos de emendas desde 2014. Outros ${fmt(r.fora_do_alcance?.casos)} casos (${brl(r.fora_do_alcance?.valor)}) foram a empresas impedidas só na esfera de um estado ou município, o que não impede receber dinheiro federal; esses ficam de fora.`,
      `Every amendment payment since 2014. Another ${fmt(r.fora_do_alcance?.casos)} cases (${brl(r.fora_do_alcance?.valor)}) went to companies barred only within one state's or town's sphere, which does not stop federal money; those are left out.`),
    innocent: [L("O pagamento quita um contrato assinado antes da sanção, o que a lei permite.", "The payment settles a contract signed before the sanction, which the law allows."),
      L("O parlamentar indica o destino da emenda, não a empresa: quem contrata é o órgão que a executa.", "The member chooses where the amendment goes, not the company: the executing body does the hiring."),
      L("A sanção pode ter sido suspensa na Justiça sem que a lista fosse atualizada.", "The sanction may have been suspended in court without the list being updated.")],
  });
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Pago a empresas impedidas", "Paid to barred companies"), value: brl(r.valor), sub: L(`${fmt(r.casos)} pares de empresa e autor`, `${fmt(r.casos)} company–author pairs`) },
    { label: L("Sanção alcança verbas federais", "Sanction covers federal money"), value: brl(r.sim?.valor), sub: L(`${plural(r.sim?.empresas || 0, "empresa", "empresas")}`, `${plural(r.sim?.empresas || 0, "company", "companies")}`) },
    { label: L("Empresas", "Companies"), value: fmt(r.empresas), sub: L("com ao menos um pagamento", "with at least one payment") },
    { label: L("Autores das emendas", "Amendment authors"), value: fmt(r.autores), sub: L("parlamentares, bancadas e comissões", "members, state benches and committees") },
  ]);
  const c1 = chart(), c2 = chart();
  root.append(grid(card(L("Por partido do autor", "By the author's party"), L("Valor pago a empresas impedidas por emendas individuais, pelo partido do autor no ano da emenda.", "Paid to barred companies through individual amendments, by the author's party in the amendment's year."), c1),
    card(L("Quem mais mandou", "Who sent the most"), L("Os autores com mais dinheiro pago a empresas impedidas.", "The authors with the most paid to barred companies."), c2)));
  const indiv = rows.filter((x) => x.tipo === "individual" || x.tipo === "especial");
  later(() => C.bars(c1, { rows: byParty(indiv, (x) => +x.valor), format: (v) => brl(v, 0) }));
  const byAuthor = new Map();
  for (const x of rows) byAuthor.set(x.autor, (byAuthor.get(x.autor) || 0) + +x.valor);
  later(() => C.bars(c2, { rows: [...byAuthor].sort((a, b) => b[1] - a[1]).slice(0, 15).map(([label, value]) => ({ label, value, color: css("--accent") })), format: (v) => brl(v, 0) }));
  const tb = el("div");
  root.append(card(L("Todos os pagamentos", "Every payment"), L("Um par de empresa e autor por linha. Clique na empresa para ver suas sanções.", "One company–author pair per row. Click a company to see its sanctions."), tb));
  table(tb, rows.map((x) => ({ ...x, valor: +x.valor, pagamentos: +x.pagamentos })), [
    { key: "nome", label: L("Empresa", "Company"), text: true, wrap: true, fmt: (v, x) => company(x, { sanctioned: true }) },
    { key: "autor", label: L("Autor da emenda", "Amendment author"), text: true, wrap: true, fmt: (v, x) => member(x) },
    { key: "barrado", label: L("Alcance da sanção", "Sanction's reach"), text: true, fmt: (v) => el("span", { className: `tag${v === "sim" ? " hot" : ""}`, textContent: REACH[v] || v }) },
    { key: "primeiro", label: L("Meses", "Months"), text: true, fmt: (v, x) => monthSpan(x.primeiro, x.ultimo) },
    { key: "pagamentos", label: L("Pagamentos", "Payments"), fmt: (v) => fmt(v) },
    { key: "valor", label: L("Pago", "Paid"), fmt: (v) => brl(v) }], { sortBy: "valor", pageSize: 15, name: "amendments-to-barred-companies" });
}

// ------------------------------------------------------------ 2. contracts with barred companies

const SPH = { F: L("Federal", "Federal"), E: L("Estadual", "State"), M: L("Municipal", "Municipal"), D: L("Distrital", "Federal District"), N: L("Outra", "Other") };
async function contracts(root) {
  const r = (await R()).contratos_impedidas, rows = await data("site/alertas/contratos_impedidas.csv");
  explain(root, {
    rule: L("Um contrato publicado no PNCP e assinado num dia em que o fornecedor estava no CEIS ou no CNEP com uma sanção que impede contratar e cujo alcance cobre o órgão que contratou (a mesma esfera, ou todas).",
      "A contract published on the PNCP and signed on a day when the supplier was on CEIS or CNEP under a sanction that bars contracting and whose reach covers the buying body (its sphere, or every sphere)."),
    base: L(`Os contratos lidos do PNCP até agora: ${fmt(r.dias_lidos)} dias do histórico desde 2021. Contratos com valores impossíveis (erros de digitação) ficam de fora.`,
      `The PNCP contracts read so far: ${fmt(r.dias_lidos)} days of the history since 2021. Contracts with impossible values (typos) are left out.`),
    innocent: [L("O contrato é um aditivo ou a continuação de um contrato assinado antes da sanção.", "The contract amends or continues one signed before the sanction."),
      L("A sanção foi suspensa por decisão judicial que a lista ainda não reflete.", "The sanction was suspended by a court order the list does not yet show."),
      L("Erro de cadastro: a data de assinatura publicada no PNCP pode estar errada.", "A data-entry error: the signing date published on the PNCP may be wrong.")],
  });
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Contratos", "Contracts"), value: fmt(r.casos), sub: L(`${plural(r.empresas, "empresa", "empresas")}`, `${plural(r.empresas, "company", "companies")}`) },
    { label: L("Valor", "Value"), value: brl(r.valor), sub: L("valor global, como publicado", "global value, as published") },
    { label: L("Histórico lido", "History read"), value: fmt(r.dias_lidos), sub: L("dias do PNCP", "PNCP days") },
  ]);
  const by = new Map();
  for (const x of rows) by.set(x.esfera, (by.get(x.esfera) || 0) + +x.valor);
  const c1 = chart();
  root.append(card(L("Por esfera do órgão que contratou", "By the buying body's sphere"), null, c1));
  later(() => C.bars(c1, { rows: [...by].sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: SPH[k] || k, value: v, color: css("--accent") })), format: (v) => brl(v, 0) }));
  const tb = el("div");
  root.append(card(L("Todos os contratos", "Every contract"), null, tb));
  table(tb, rows.map((x) => ({ ...x, valor: +x.valor })), [
    { key: "assinatura", label: L("Assinado", "Signed"), text: true, fmt: day },
    { key: "orgao", label: L("Órgão", "Buyer"), text: true, wrap: true }, { key: "uf", label: "UF", text: true },
    { key: "nome", label: L("Fornecedor", "Supplier"), text: true, wrap: true, fmt: (v, x) => company(x, { sanctioned: true }) },
    { key: "categoria_sancao", label: L("Sanção", "Sanction"), text: true, wrap: true, fmt: (v, x) => el("span", {}, v, el("br"), el("small", { className: "hint", textContent: `${x.sancao_inicio} – ${x.sancao_fim || L("sem prazo", "no end")}` })) },
    { key: "objeto", label: L("Objeto", "Object"), text: true, wrap: true },
    { key: "valor", label: L("Valor", "Value"), fmt: (v) => brl(v) }], { sortBy: "valor", pageSize: 12, name: "contracts-with-barred-companies" });
}

// ------------------------------------------------------------ 3. campaign supplier, then the member's amendments

async function campaign(root) {
  const r = (await R()).campanha_emendas, rows = await data("site/alertas/campanha_emendas.csv");
  explain(root, {
    rule: L(`Uma empresa ou entidade privada (CNPJ) contratada pela campanha de um deputado federal em 2018 ou 2022 que, a partir de outubro daquele ano, recebeu ao menos ${brl(10000, 0)} das emendas desse mesmo deputado.`,
      `A company or private body (CNPJ) a federal deputy's 2018 or 2022 campaign contracted that, from October of that year, received at least ${brl(10000, 0)} from that same deputy's amendments.`),
    base: L(`${fmt(r.pares_campanha)} pares de campanha e fornecedor nas eleições de 2018 e 2022 (deputados federais e senadores). Bancos, estatais, governos e concessionárias de serviços públicos (energia, água, telefonia) ficam de fora: campanhas e órgãos públicos pagam a todos eles.`,
      `${fmt(r.pares_campanha)} campaign–supplier pairs in the 2018 and 2022 elections (federal deputies and senators). Banks, state companies, governments and public-service concessionaires (power, water, telephone) are left out: campaigns and public bodies all pay them.`),
    innocent: [L("Entidades locais (associações, clubes, grupos culturais) trabalham em campanhas e recebem verbas públicas para projetos legítimos.", "Local bodies (associations, clubs, cultural groups) work in campaigns and receive public money for legitimate projects."),
      L("Um pagamento de campanha pequeno (aluguel de espaço, um serviço) não indica vínculo.", "A small campaign payment (a venue, a service) does not show a tie."),
      L("O órgão que executa a emenda escolhe o fornecedor, não o parlamentar.", "The body that executes the amendment chooses the supplier, not the member.")],
  });
  const tb = el("div");
  root.append(card(L("Os casos", "The cases"), L("O valor contratado pela campanha e o que as emendas do mesmo deputado pagaram depois à mesma entidade.", "What the campaign contracted, and what the same deputy's amendments later paid the same body."), tb));
  table(tb, rows.map((x) => ({ ...x, campanha: +x.campanha, emendas: +x.emendas, pagamentos: +x.pagamentos })), [
    { key: "deputado", label: L("Deputado", "Deputy"), text: true, wrap: true, fmt: (v, x) => member(x) },
    { key: "nome", label: L("Empresa ou entidade", "Company or body"), text: true, wrap: true, fmt: (v, x) => company(x) },
    { key: "eleicao", label: L("Eleição", "Election"), text: true },
    { key: "campanha", label: L("Contratado pela campanha", "Contracted by the campaign"), fmt: (v) => brl(v) },
    { key: "emendas", label: L("Pago pelas emendas", "Paid by the amendments"), fmt: (v) => brl(v) },
    { key: "primeiro", label: L("Meses", "Months"), text: true, fmt: (v, x) => monthSpan(x.primeiro, x.ultimo) }], { sortBy: "emendas", pageSize: 15, search: false, name: "campaign-supplier-then-amendments" });
}

// ------------------------------------------------------------ 4. concentration

const KIND = { fundacao_apoio: L("Fundação de apoio à pesquisa", "Research support foundation"), saude: L("Saúde ou filantropia", "Health or charity"),
  entidade: L("Associação ou entidade", "Association or body"), empresa: L("Empresa", "Company") };
async function concentration(root) {
  const r = (await R()).concentracao, rules = (await R()).rules, rows = await data("site/alertas/concentracao.csv");
  explain(root, {
    rule: L(`Uma única entidade ou empresa privada recebeu ao menos ${brl(rules.conc_min, 0)} e ${pct(rules.conc_share)} ou mais de todo o dinheiro pago pelas emendas de um parlamentar desde fevereiro de 2019.`,
      `A single private body or company received at least ${brl(rules.conc_min, 0)} and ${pct(rules.conc_share)} or more of all the money a member's amendments paid since February 2019.`),
    base: L(`Entre ${fmt(r.base?.deputados)} parlamentares, a maior parcela que vai a uma só entidade privada é de ${pct(r.base?.mediana_maior_share, 1)} na mediana; 90% ficam abaixo de ${pct(r.base?.p90_maior_share, 1)}.`,
      `Across ${fmt(r.base?.deputados)} members, the largest share going to a single private recipient is ${pct(r.base?.mediana_maior_share, 1)} at the median; 90% stay below ${pct(r.base?.p90_maior_share, 1)}.`),
    innocent: [L("Fundações de apoio de universidades e da Fiocruz executam emendas para pesquisa e saúde: é o caminho previsto para esse dinheiro.", "Support foundations of universities and Fiocruz execute amendments for research and health: that is how such money is meant to flow."),
      L("Hospitais filantrópicos (Santas Casas) recebem emendas de saúde por desenho do SUS.", "Charity hospitals (Santas Casas) receive health amendments by the design of the public health system."),
      L("Um parlamentar com poucas emendas pagas concentra mais por aritmética.", "A member with few amendments paid concentrates more by arithmetic.")],
  });
  const tb = el("div");
  root.append(card(L("Os casos", "The cases"), L("O tipo de entidade vem do nome e da natureza jurídica, para separar fundações de apoio e hospitais dos demais.", "The kind of recipient comes from its name and legal nature, to tell support foundations and hospitals from the rest."), tb));
  table(tb, rows.map((x) => ({ ...x, valor: +x.valor, share: +x.share, total_deputado: +x.total_deputado })), [
    { key: "deputado", label: L("Parlamentar", "Member"), text: true, wrap: true, fmt: (v, x) => member(x) },
    { key: "nome", label: L("Entidade ou empresa", "Body or company"), text: true, wrap: true, fmt: (v, x) => company(x) },
    { key: "tipo", label: L("Tipo", "Kind"), text: true, fmt: (v) => el("span", { className: "tag", textContent: KIND[v] || v }) },
    { key: "valor", label: L("Recebeu", "Received"), fmt: (v) => brl(v) },
    { key: "share", label: L("Parcela", "Share"), fmt: (v) => pct(v) },
    { key: "total_deputado", label: L("Total pago pelas emendas", "All their amendments paid"), fmt: (v) => brl(v) }], { sortBy: "share", pageSize: 15, search: false, name: "concentrated-amendments" });
}

// ------------------------------------------------------------ 5. dominant supplier

async function dominant(root) {
  const r = (await R()).fornecedor_dominante, rules = (await R()).rules, rows = await data("site/alertas/fornecedor_dominante.csv");
  explain(root, {
    rule: L(`Um órgão com ao menos ${rules.dom_contracts} grandes contratos (R$ 1 milhão ou mais) somando ${brl(rules.dom_value, 0)} ou mais, em que um só fornecedor levou ${pct(rules.dom_share)} ou mais do valor.`,
      `A buyer with at least ${rules.dom_contracts} large contracts (R$ 1 million or more) adding up to ${brl(rules.dom_value, 0)} or more, where one supplier took ${pct(rules.dom_share)} or more of the value.`),
    base: L(`Entre os ${fmt(r.orgaos_com_5)} órgãos com cinco grandes contratos ou mais nos ${fmt(r.dias_lidos)} dias lidos do PNCP, o maior fornecedor leva ${pct(r.mediana_maior_share)} do valor na mediana.`,
      `Among the ${fmt(r.orgaos_com_5)} buyers with five or more large contracts in the ${fmt(r.dias_lidos)} PNCP days read, the largest supplier takes ${pct(r.mediana_maior_share)} of the value at the median.`),
    innocent: [L("Alguns serviços têm um só prestador possível: a fundação que administra o hospital do município, a única empresa que opera certo equipamento.", "Some services have a single possible provider: the foundation running the town's hospital, the only firm operating some equipment."),
      L("Poucos dias de histórico lidos tornam a concentração mais provável por acaso.", "With few days of history read, concentration is likelier by chance.")],
  });
  const tb = el("div");
  root.append(card(L("Os casos", "The cases"), null, tb));
  table(tb, rows.map((x) => ({ ...x, valor: +x.valor, maior_share: +x.maior_share, contratos: +x.contratos })), [
    { key: "orgao", label: L("Órgão", "Buyer"), text: true, wrap: true }, { key: "uf", label: "UF", text: true },
    { key: "nome", label: L("Fornecedor dominante", "Dominant supplier"), text: true, wrap: true, fmt: (v, x) => company(x) },
    { key: "maior_share", label: L("Parcela do valor", "Share of value"), fmt: (v) => pct(v) },
    { key: "contratos", label: L("Grandes contratos", "Large contracts"), fmt: (v) => fmt(v) },
    { key: "valor", label: L("Valor total", "Total value"), fmt: (v) => brl(v) }], { sortBy: "valor", pageSize: 15, search: false, name: "dominant-suppliers" });
}

// ------------------------------------------------------------ 6. leniency

async function leniency(root) {
  const r = (await R()).leniencia_contratos, rows = await data("site/alertas/leniencia_contratos.csv");
  explain(root, {
    rule: L("Um grande contrato (R$ 1 milhão ou mais) publicado no PNCP e assinado por uma empresa depois da data de início do seu acordo de leniência com a CGU, em que ela admitiu irregularidades.",
      "A large contract (R$ 1 million or more) published on the PNCP and signed by a company after the start of its leniency agreement with the CGU, in which it admitted wrongdoing."),
    base: L(`${fmt(r.acordos)} acordos de leniência com CNPJ; os contratos são os dos ${fmt(r.dias_lidos)} dias lidos do PNCP.`, `${fmt(r.acordos)} leniency agreements with a CNPJ; the contracts are those of the ${fmt(r.dias_lidos)} PNCP days read.`),
    innocent: [L("O acordo de leniência existe justamente para que a empresa possa voltar a contratar, cumprindo o que prometeu.", "A leniency agreement exists precisely so the company can contract again, on the terms it promised."),
      L("A empresa pode ter mudado de controle desde o acordo.", "The company may have changed hands since the agreement.")],
  });
  const tb = el("div");
  root.append(card(L("Os contratos", "The contracts"), null, tb));
  table(tb, rows.map((x) => ({ ...x, valor: +x.valor })), [
    { key: "assinatura", label: L("Assinado", "Signed"), text: true, fmt: day },
    { key: "nome", label: L("Empresa", "Company"), text: true, wrap: true, fmt: (v, x) => company(x, { sanctioned: true }) },
    { key: "acordo", label: L("Acordo desde", "Agreement since"), text: true, fmt: day },
    { key: "orgao", label: L("Órgão", "Buyer"), text: true, wrap: true }, { key: "uf", label: "UF", text: true },
    { key: "objeto", label: L("Objeto", "Object"), text: true, wrap: true },
    { key: "valor", label: L("Valor", "Value"), fmt: (v) => brl(v) }], { sortBy: "valor", pageSize: 12, name: "contracts-after-leniency" });
}

// ------------------------------------------------------------ on several lists

const LIST = { emendas_impedidas: L("emendas a impedidas", "amendments to barred firms"), contratos_impedidas: L("contratos com impedidas", "contracts with barred firms"),
  campanha_emendas: L("fornecedor de campanha", "campaign supplier"), concentracao: L("emendas concentradas", "concentrated amendments"),
  fornecedor_dominante: L("fornecedor dominante", "dominant supplier"), leniencia_contratos: L("após leniência", "after leniency") };
const tags = (v) => el("span", {}, ...v.split(";").map((k) => el("span", { className: "tag", textContent: LIST[k] || k, style: "margin:0 4px 4px 0" })));
async function cross(root) {
  const [ent, par] = await Promise.all([data("site/alertas/entidades.csv"), data("site/alertas/parlamentares.csv")]);
  root.append(el("p", { className: "about" }, L("Aparecer em mais de uma lista não soma culpa: muitas vezes é o mesmo fato visto duas vezes (uma empresa impedida que recebe emendas e também assina contratos). Mas são os primeiros casos a olhar.",
    "Appearing on more than one list does not add up guilt: often it is the same fact seen twice (a barred company that receives amendments and also signs contracts). But these are the first cases to look at.")));
  const t1 = el("div"), t2 = el("div");
  root.append(grid(card(L("Empresas e entidades", "Companies and bodies"), null, t1), card(L("Parlamentares", "Members of Congress"), null, t2)));
  table(t1, ent.map((x) => ({ ...x, n: +x.n })), [{ key: "nome", label: L("Empresa ou entidade", "Company or body"), text: true, wrap: true, fmt: (v, x) => company(x, { sanctioned: x.listas.includes("impedidas") }) },
    { key: "listas", label: L("Listas", "Lists"), text: true, wrap: true, fmt: tags }, { key: "n", label: "N" }], { sortBy: "n", pageSize: 12, name: "companies-on-several-lists" });
  table(t2, par.map((x) => ({ ...x, n: +x.n })), [{ key: "deputado", label: L("Parlamentar", "Member"), text: true, wrap: true, fmt: (v, x) => member(x) },
    { key: "listas", label: L("Listas", "Lists"), text: true, wrap: true, fmt: tags }, { key: "n", label: "N" }], { sortBy: "n", pageSize: 12, search: false, name: "members-on-several-lists" });
}

// ------------------------------------------------------------ tabs

const show = tabs((name) => {
  const box = $(`#tab-${name}`);
  const f = { overview: (b) => overview(b, (t) => { show(t); window.scrollTo({ top: $("nav.tabs").offsetTop - 70, behavior: "smooth" }); }),
    barred, contracts, campaign, concentration, dominant, leniency, cross }[name];
  guard(box, () => f(box));
});
