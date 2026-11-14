// Companies across sources: one profile per CNPJ, joining sanctions, PNCP contracts, amendment payments,
// campaign sales and red flags. The search index loads on first use; each profile is one small shard.
import { $, brl, css, data, el, fmt, guard, onResize, params, pct, plural, setParam, table, tabs, tiles } from "../lib/ui.js";
import * as C from "../lib/charts.js";
import { L } from "../lib/i18n.js";
import { setupPage } from "../lib/page.js";

setupPage();

// ------------------------------------------------------------ helpers

const R = () => data("site/empresas/resumo.json");
const card = (title, note, ...kids) => el("div", { className: "card wide" }, el("h2", { textContent: title }), note ? el("p", { className: "note", textContent: note }) : null, ...kids);
const chart = () => el("div", { className: "chart" });
const n = (v) => (v === "" || v == null ? 0 : +v);
const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const cnpjFmt = (c) => (/^\d{14}$/.test(c) ? `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}` : c);
const day = (v) => el("span", { className: "nowrap", textContent: v ?? "" });
const redraws = [];
const WITHHELD = L("Empresa individual (nome omitido)", "Individual firm (name withheld)");
const SRC = { S: L("Sanções", "Sanctions"), H: L("Sanção passada", "Past sanction"), C: L("Contratos", "Contracts"), E: L("Emendas", "Amendments"),
  T: L("Campanhas", "Campaigns"), A: L("Sinais de alerta", "Red flags") };
const srcPills = (f) => el("span", { className: "src" }, ...[...String(f || "")].map((k) => el("i", { className: k, textContent: SRC[k] || k })));
const BARS = /^(Impedimento|Declaração de Inidoneidade|Suspensão$)/;

// The CGU's wording -> labels in the page's language (the same as the sanctions page).
const CAT = {
  "Impedimento/proibição de contratar com prazo determinado": L("Impedimento, com prazo", "Contracting ban, fixed term"),
  "Impedimento/proibição de contratar sem prazo determinado": L("Impedimento, sem prazo", "Contracting ban, no end date"),
  "Suspensão": L("Suspensão de licitar", "Suspended from tenders"),
  "Declaração de Inidoneidade sem prazo determinado": L("Inidoneidade, sem prazo", "Declared unfit, no end date"),
  "Declaração de Inidoneidade com prazo determinado": L("Inidoneidade, com prazo", "Declared unfit, fixed term"),
  "Suspensão/Interdição das atividades sem prazo determinado": L("Interdição, sem prazo", "Activity halt, no end date"),
  "Suspensão/Interdição das atividades com prazo determinado": L("Interdição, com prazo", "Activity halt, fixed term"),
  "Multa": L("Multa", "Fine"), "Advertência": L("Advertência", "Warning"),
  "Publicação extraordinária da decisão condenatória": L("Publicação da condenação", "Ruling published at its cost"),
  "Proibição de receber incentivos, subsídios, subvenções, doações ou empréstimos": L("Proibição de receber subsídios", "No subsidies or public loans"),
  "Dissolução compulsória da PJ": L("Dissolução compulsória", "Compulsory dissolution"), "Perdimento de bens": L("Perdimento de bens", "Assets forfeited"),
};
const NOT_STATED = L("Não informada", "Not stated");
const SCOPE = {
  "Todas as Esferas em todos os Poderes": L("Todas as esferas e Poderes", "Every sphere and power"),
  "Em todos os Poderes da Esfera do órgão sancionador": L("Toda a esfera do sancionador", "The sanctioner's whole sphere"),
  "Na Esfera e no Poder do órgão sancionador": L("Esfera e Poder do sancionador", "The sanctioner's sphere and power"),
  "No órgão sancionador": L("Só o órgão sancionador", "Only the sanctioning body"), "Sem Informação": NOT_STATED, "Em outro órgão": L("Outro órgão", "Another body"),
};
const SPHERE = { F: "Federal", E: L("Estadual", "State"), M: "Municipal" };
const STATUS = { v: L("Vigente", "In force"), e: L("Encerrada, ainda listada", "Ended, still listed"), f: L("Ainda não começou", "Not started yet") };
const COBRE = { sim: L("Sim, alcança o comprador", "Yes, reaches the buyer"), possivel: L("Sim, pode alcançar o comprador", "Yes, may reach the buyer"),
  nao: L("Sim, mas não alcança o comprador", "Yes, but it does not reach the buyer") };
const FED = { sim: L("vale para órgãos federais", "binds federal bodies"), possivel: L("pode valer para o pagador", "may bind the payer"), nao: L("só em outra esfera", "another sphere only") };
const OFFICE = { DF: L("Deputado federal", "Federal deputy"), SN: L("Senador", "Senator"), S1: L("1º suplente", "1st substitute"), S2: L("2º suplente", "2nd substitute") };
const RESULT = { e: L("eleito", "elected"), s: L("suplente", "substitute"), n: L("não eleito", "not elected") };
const AUTHOR = { parlamentar: L("Parlamentar", "Member of Congress"), individual: L("Individual", "Individual"), especial: L("Individual (Pix)", "Individual (Pix)"),
  bancada: L("Bancada estadual", "State bench"), comissao: L("Comissão", "Committee"), relator: L("Relator-geral", "Rapporteur-general") };
const LEN_STATUS = { "Em Execução": L("Em execução", "In progress"), "Cumprido": L("Cumprido", "Fulfilled") };

/** A member of Congress, linked to their profile here (deputies of the 56th and 57th legislatures) or on the Senate's site. */
function memberHref(link) {
  const d = /^d(\d+):(\d+)$/.exec(link || "");
  if (d) return `../deputados/?tab=profile&leg=${d[1]}&dep=${d[2]}`;
  const s = /^s:(\d+)$/.exec(link || "");
  return s ? `https://www25.senado.leg.br/web/senadores/senador/-/perfil/${s[1]}` : null;
}
const member = (name, link) => { const h = memberHref(link); return h ? el("a", { href: h, textContent: name }) : name; };
/** The contract's page on the PNCP, from its control number (orgão-tipo-sequencial/ano). */
function pncpHref(controle) {
  const m = /^(\d{14})-\d+-(\d+)\/(\d{4})$/.exec(controle || "");
  return m ? `https://pncp.gov.br/app/contratos/${m[1]}/${m[3]}/${+m[2]}` : null;
}

let authorsP = null;
const authors = () => (authorsP ??= data("site/empresas/autores.csv").then((rows) => new Map(rows.map((r) => [r.autor_codigo, r]))));

// ------------------------------------------------------------ search

let indexP = null;
/** Every company with a profile: name (blank when withheld), sources, money received (R$ thousand). Loaded on first use. */
function index() {
  indexP ??= data("site/empresas/indice.csv").then((rows) => rows.map((r) => ({ cnpj: r.cnpj, nome: r.nome, pf: r.pf === "1", fontes: r.fontes, valor: n(r.valor) * 1000, key: norm(r.nome) })));
  return indexP;
}
function rank(all, q) {
  const digits = q.replace(/[\s./-]/g, "");
  if (/^\d{2,}$/.test(digits)) return all.filter((x) => x.cnpj.startsWith(digits)).sort((a, b) => b.valor - a.valor).slice(0, 8);
  const words = norm(q).split(/\s+/).filter(Boolean);
  if (words.join("").length < 2) return [];
  const whole = words.join(" ");
  const score = (x) => (x.key.startsWith(whole) ? 0 : x.key.split(/[\s.,/-]+/).some((w) => w.startsWith(words[0])) ? 1 : 2);
  return all.filter((x) => x.key && words.every((w) => x.key.includes(w))).map((x) => [score(x), x])
    .sort((a, b) => a[0] - b[0] || b[1].valor - a[1].valor).slice(0, 8).map(([, x]) => x);
}

/** A combobox over the index: a name (any words of it) or a CNPJ (its first digits, or all 14). */
function companySearch(onPick) {
  const input = el("input", { type: "search", placeholder: L("Nome da empresa ou CNPJ…", "Company name or CNPJ…"), autocomplete: "off", spellcheck: false, role: "combobox",
    "aria-label": L("Buscar empresa", "Find a company"), "aria-autocomplete": "list", "aria-expanded": "false", "aria-controls": "cs-list" });
  const list = el("ul", { id: "cs-list", className: "options", role: "listbox", hidden: true });
  const box = el("div", { className: "dsearch wide-search" }, el("span", { className: "icon", "aria-hidden": "true" }), input, list);
  let hits = [], active = -1;
  const close = () => { list.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; input.removeAttribute("aria-activedescendant"); };
  const pick = (cnpj) => { if (!cnpj) return; close(); input.value = ""; onPick(cnpj); };
  const paint = (empty) => {
    list.replaceChildren(...(hits.length ? hits.map((x, i) => {
      const li = el("li", { id: `cs-o${i}`, role: "option", className: "option", "aria-selected": String(i === active) },
        el("span", { className: "who", style: "grid-column: 1 / 3" }, el("b", { textContent: x.nome || WITHHELD }), el("span", { textContent: `${cnpjFmt(x.cnpj)} · ${[...x.fontes].map((k) => SRC[k]).join(", ")}` })),
        x.valor ? el("span", { className: "leg", textContent: brl(x.valor, 1) }) : el("span"));
      li.addEventListener("mousedown", (e) => { e.preventDefault(); pick(x.cnpj); });
      li.addEventListener("mousemove", () => { if (active !== i) { active = i; paint(); } });
      return li;
    }) : [el("li", { className: "none", textContent: empty || L("Nenhuma empresa encontrada.", "No company found.") })]));
    list.hidden = false; input.setAttribute("aria-expanded", "true");
    if (active >= 0) input.setAttribute("aria-activedescendant", `cs-o${active}`); else input.removeAttribute("aria-activedescendant");
  };
  const update = async () => {
    const q = input.value.trim();
    if (!q) { hits = []; close(); return; }
    if (!list.hidden || !hits.length) { hits = []; paint(L("Carregando o índice…", "Loading the index…")); }
    const all = await index();
    if (input.value.trim() !== q) return;   // typed on meanwhile
    hits = rank(all, q); active = hits.length ? 0 : -1;
    const digits = q.replace(/[\s./-]/g, "");
    paint(/^\d{14}$/.test(digits) ? L("Este CNPJ não tem ficha: não aparece em nenhuma das fontes desta página.", "This CNPJ has no profile: it appears in none of this page's sources.")
      : /^\d+$/.test(digits) || q.length > 1 ? null : L("Digite mais letras.", "Type a few more letters."));
  };
  input.addEventListener("input", update);
  input.addEventListener("focus", () => { index(); if (input.value.trim()) update(); });
  input.addEventListener("blur", () => setTimeout(close, 100));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!hits.length) return;
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + hits.length) % hits.length; paint();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const digits = input.value.replace(/[\s./-]/g, "");
      pick(hits[Math.max(0, active)]?.cnpj || (/^\d{14}$/.test(digits) ? digits : null));
    } else if (e.key === "Escape") close();
  });
  return box;
}

// ------------------------------------------------------------ one company

let showCompany = null, showTab = () => {};
function openCompany(cnpj) {
  setParam("cnpj", cnpj);
  showTab("profile");
  if (showCompany) showCompany(cnpj);
  window.scrollTo({ top: $("nav.tabs").offsetTop - 8, behavior: "smooth" });
}
const companyLink = (name, cnpj) => el("button", { className: "linkish", type: "button", textContent: name || WITHHELD, title: cnpjFmt(cnpj), on: { click: () => openCompany(cnpj) } });

// The red-flag lists, as the red-flags page names them, and the tab that explains each.
const FLAGS = {
  emendas_impedidas: { tab: "barred", title: L("Emendas pagas enquanto estava impedida de contratar", "Amendment money paid while it was barred from contracting"),
    text: L("Recebeu pagamentos de emendas num mês em que estava no CEIS ou no CNEP sob uma sanção que impede contratar e que alcança (ou pode alcançar) o dinheiro federal. Explicações inocentes: o pagamento quita um contrato anterior à sanção; a sanção pode ter sido suspensa na Justiça.",
      "It received amendment payments in a month when it was on CEIS or CNEP under a sanction that bars contracting and reaches (or may reach) federal money. Innocent explanations: the payment settles a contract signed before the sanction; the sanction may have been suspended in court.") },
  contratos_impedidas: { tab: "contracts", title: L("Contratos assinados enquanto estava impedida", "Contracts signed while it was barred"),
    text: L("Assinou contratos no PNCP num dia em que uma sanção impeditiva que alcança o comprador estava em vigor. Explicações inocentes: aditivo ou continuação de um contrato anterior; uma decisão judicial que a lista não mostra; data de assinatura errada no PNCP.",
      "It signed PNCP contracts on a day when a barring sanction that reaches the buyer was in force. Innocent explanations: an amendment to or continuation of an earlier contract; a court order the list does not show; a wrong signing date on the PNCP.") },
  campanha_emendas: { tab: "campaign", title: L("Fornecedora de campanha paga depois com emendas do mesmo deputado", "Campaign supplier later paid from the same deputy's amendments"),
    text: L("Trabalhou para a campanha de um deputado e, a partir de outubro daquele ano, recebeu pelo menos R$ 10 mil das emendas desse mesmo deputado. Explicações inocentes: entidades locais trabalham em campanhas e recebem recursos para projetos legítimos; quem escolhe o fornecedor é o órgão que executa a emenda.",
      "It worked for a deputy's campaign and, from October of that year, received at least R$ 10,000 from that same deputy's amendments. Innocent explanations: local organisations work in campaigns and get public money for legitimate projects; the body executing the amendment chooses the supplier.") },
  concentracao: { tab: "concentration", title: L("Concentra o dinheiro de emendas de um parlamentar", "Takes a large share of one member's amendment money"),
    text: L("Recebeu R$ 1 milhão ou mais e pelo menos 25% de tudo o que as emendas de um parlamentar pagaram desde fevereiro de 2019. Explicações inocentes: fundações de apoio e hospitais filantrópicos executam emendas por definição; quem tem poucas emendas pagas concentra mais.",
      "It received R$ 1 million or more and at least 25% of everything a member's amendments paid since February 2019. Innocent explanations: support foundations and charity hospitals execute amendments by design; a member with few amendments paid concentrates more.") },
  fornecedor_dominante: { tab: "dominant", title: L("Fornecedora dominante de um comprador público", "Dominant supplier of a public buyer"),
    text: L("Ficou com 80% ou mais do valor dos grandes contratos de um comprador público (ao menos 5 contratos e R$ 10 milhões). Explicações inocentes: há serviços com um só fornecedor possível; com pouco histórico lido, a concentração aparece mais por acaso.",
      "It took 80% or more of the value of a public buyer's large contracts (at least 5 contracts and R$ 10 million). Innocent explanations: some services have one possible provider; with little history read, concentration shows up more by chance.") },
  leniencia_contratos: { tab: "leniency", title: L("Contratos depois de um acordo de leniência", "Contracts after a leniency agreement"),
    text: L("Assinou grandes contratos depois de firmar um acordo de leniência com a CGU, em que admitiu irregularidades. O acordo existe para que a empresa volte a contratar nas condições que prometeu: é mais contexto do que alerta.",
      "It signed large contracts after a leniency agreement with the CGU, in which it admitted wrongdoing. The agreement exists so the company can contract again on the terms it promised: this is context more than a flag.") },
};

function dossierHead(p, cnpj, r, example) {
  const nat = p.nj != null ? r.naturezas[p.nj] : "", cnae = p.cn != null ? r.cnaes[p.cn] : "";
  const kids = [el("h2", { className: "dname", textContent: p.n || (p.pf ? WITHHELD : L("Sem nome registrado", "No name on record")) }),
    el("p", { className: "dmeta" }, el("span", { className: "doc", textContent: `CNPJ ${cnpjFmt(cnpj)}` }),
      nat ? el("span", { className: "chip", textContent: nat }) : null,
      p.lc ? el("span", { className: "chip soft", textContent: p.lc, title: L("Município onde recebeu a maior parte dos pagamentos de emendas", "Town where it received most of its amendment payments") }) : null,
      cnae ? el("span", { className: "chip soft", textContent: cnae, title: L("Atividade declarada à Justiça Eleitoral", "Activity declared to the electoral court") }) : null)];
  if (example) kids.push(el("p", { className: "about", textContent: L("Exemplo: a empresa que aparece em mais listas de sinais de alerta e em mais fontes. Busque outra acima.",
    "Example: the company on the most red-flag lists and in the most sources. Find another one above.") }));
  if (p.pf) kids.push(el("p", { className: "about", textContent: L("Uma empresa individual leva o nome do dono; por isso esta página mostra o CNPJ e os números, mas não o nome.",
    "An individual firm carries its owner's name, so this page shows its CNPJ and numbers but not the name.") }));
  if (["Empresa Pública", "Sociedade de Economia Mista"].includes(nat)) kids.push(el("p", { className: "about", textContent: L("Empresa estatal. Bancos públicos aparecem como favorecidos de emendas quando operam programas e repasses: o dinheiro passa por eles, não fica com eles.",
    "A state company. Public banks appear as amendment recipients when they run programmes and transfers: the money passes through them rather than staying with them.") }));
  return el("div", { className: "dossier", id: "sec-resumo" }, ...kids);
}

function flagsSection(box, p) {
  const f = p.f || {};
  const keys = Object.keys(FLAGS).filter((k) => f[k]);
  box.append(el("h3", { className: "dsec", id: "sec-alertas", textContent: L("Sinais de alerta", "Red flags") }));
  box.append(el("p", { className: "lead", textContent: L("Um sinal de alerta é um padrão nos dados oficiais que merece um olhar mais atento, não uma prova de irregularidade: muitos têm explicação legítima e os dados podem estar errados. Cada um traz a sua regra, a base de comparação e as explicações inocentes na página de sinais de alerta.",
    "A red flag is a pattern in official data that deserves a closer look, not evidence of an irregularity: many have legitimate explanations, and the data can be wrong. The red-flags page gives each one's rule, baseline and innocent explanations.") }));
  if (!keys.length) { box.append(el("p", { className: "hint", textContent: L("Não aparece em nenhuma das seis listas de sinais de alerta.", "It is on none of the six red-flag lists.") })); return; }
  for (const k of keys) {
    const [count, value, det] = f[k], F = FLAGS[k];
    const items = (det || []).map((d) => {
      if (k === "emendas_impedidas") return el("li", {}, member(d[0], d[3]), d[1] ? ` (${d[1]}-${d[2]})` : "", `: ${brl(d[5])}, ${FED[d[4]] || ""}`);
      if (k === "campanha_emendas") return el("li", {}, member(d[0], d[3]), ` (${d[1]}-${d[2]}): ${L(`campanha de ${d[4]} pagou ${brl(d[5])}; emendas pagaram ${brl(d[6])}`, `${d[4]} campaign paid ${brl(d[5])}; amendments paid ${brl(d[6])}`)}`);
      if (k === "concentracao") return el("li", {}, member(d[0], d[3]), ` (${d[1]}-${d[2]}): ${L(`${pct(d[4])} do que suas emendas pagaram (${brl(d[5])})`, `${pct(d[4])} of what their amendments paid (${brl(d[5])})`)}`);
      if (k === "fornecedor_dominante") return el("li", { textContent: `${d[0]}${d[1] ? ` (${d[1]})` : ""}: ${L(`${pct(d[3])} de ${fmt(d[2])} grandes contratos`, `${pct(d[3])} of ${fmt(d[2])} large contracts`)}` });
      return null;
    }).filter(Boolean);
    const summary = k === "emendas_impedidas" ? L(`${brl(value)} de ${plural(count, "autor", "autores")}.`, `${brl(value)} from ${plural(count, "author")}.`)
      : k === "contratos_impedidas" || k === "leniencia_contratos" ? L(`${plural(count, "contrato", "contratos")}, ${brl(value)}. Estão na seção de contratos abaixo.`, `${plural(count, "contract")}, ${brl(value)}. They are in the contracts section below.`)
        : k === "fornecedor_dominante" ? L(`${plural(count, "comprador", "compradores")}.`, `${plural(count, "buyer")}.`) : "";
    box.append(el("div", { className: `flag${k === "leniencia_contratos" ? " soft" : ""}` }, el("h3", { textContent: F.title }), el("p", { textContent: F.text }),
      summary ? el("p", { textContent: summary }) : null, items.length ? el("ul", {}, ...items) : null,
      el("p", {}, el("a", { href: `../alertas/?tab=${F.tab}`, textContent: L("A regra e a lista completa →", "The rule and the full list →") }))));
  }
}

function sanctionsSection(box, p, cnpj, r) {
  box.append(el("h3", { className: "dsec", id: "sec-sancoes", textContent: L("Sanções", "Sanctions") }));
  const S = (p.s || []).map(([lista, codigo, c, inicio, fim, orgao, esf, uf, a, multa, st]) => ({ lista, codigo, categoria: r.categorias[c], inicio, fim, orgao, esf, uf, abrangencia: r.abrangencias[a], multa, st }));
  const H = (p.h || []).map(([dia, lista, codigo, mudanca]) => ({ dia, lista: lista.toUpperCase(), codigo, mudanca }));
  const P = (p.p || []).map(([convenio, orgao, motivo]) => ({ convenio, orgao, motivo }));
  const Le = (p.l || []).map(([id, inicio, fim, situacao, orgao]) => ({ id, inicio, fim, situacao, orgao }));
  const since = r.sancoes.historico_desde;
  if (!S.length && !H.length && !P.length && !Le.length) {
    box.append(el("p", { className: "hint", textContent: L(`Não está em nenhuma lista federal de sanções (CEIS, CNEP, CEPIM, acordos de leniência) na captura de ${r.sancoes.snapshot}, nem entrou ou saiu delas desde ${since}, quando o registro de mudanças começou.`,
      `It is on no federal sanctions list (CEIS, CNEP, CEPIM, leniency agreements) in the ${r.sancoes.snapshot} snapshot, and has not entered or left one since ${since}, when the change log began.`) }));
    return;
  }
  const listed = new Set(S.map((x) => `${x.lista}|${x.codigo}`));
  const removed = H.filter((x) => x.mudanca === "saiu" && !listed.has(`${x.lista}|${x.codigo}`));
  const vig = S.filter((x) => x.st === "v"), bars = vig.filter((x) => BARS.test(x.categoria));
  const parts = [];
  if (S.length) parts.push(L(`${plural(S.length, "sanção listada", "sanções listadas")} no CEIS e no CNEP em ${r.sancoes.snapshot}, ${fmt(vig.length)} em vigor${bars.length ? `, ${fmt(bars.length)} impedindo de contratar` : ""}`,
    `${plural(S.length, "sanction")} listed on CEIS and CNEP on ${r.sancoes.snapshot}, ${fmt(vig.length)} in force${bars.length ? `, ${fmt(bars.length)} barring it from contracting` : ""}`));
  if (removed.length) parts.push(L(`${plural(removed.length, "sanção retirada", "sanções retiradas")} das listas desde ${since}`, `${plural(removed.length, "sanction")} removed from the lists since ${since}`));
  if (P.length) parts.push(L(`${plural(P.length, "convênio", "convênios")} no CEPIM`, `${plural(P.length, "agreement")} on CEPIM`));
  if (Le.length) parts.push(L(`${plural(Le.length, "acordo", "acordos")} de leniência`, `${plural(Le.length, "leniency agreement")}`));
  box.append(el("p", { className: "lead" }, `${parts.join("; ")}. `, el("a", { href: `../sancoes/?tab=company&cnpj=${cnpj}`, textContent: L("Linha do tempo na página de sanções →", "Timeline on the sanctions page →") })));
  if (S.length) {
    const ts = el("div");
    box.append(card(L("Sanções nas listas de hoje", "Sanctions on today's lists"), L("Vermelho na coluna de sanção: categorias que impedem de contratar. Uma sanção limitada a um órgão ou esfera não impede contratos em outros lugares.",
      "The sanction column marks categories that bar contracting. A sanction limited to one body or sphere does not stop contracts elsewhere."), ts));
    table(ts, S, [{ key: "lista", label: L("Lista", "List"), text: true }, { key: "categoria", label: L("Sanção", "Sanction"), text: true, fmt: (v) => el("span", { style: BARS.test(v) ? `color:${css("--critical")};font-weight:600` : "", textContent: CAT[v] || v }) },
      { key: "st", label: L("Situação", "Status"), text: true, fmt: (v) => STATUS[v] || v }, { key: "inicio", label: L("Início", "From"), text: true, fmt: day }, { key: "fim", label: L("Fim", "To"), text: true, fmt: (v) => day(v || L("sem data", "no end date")) },
      { key: "orgao", label: L("Aplicada por", "Imposed by"), text: true, wrap: true }, { key: "esf", label: L("Esfera", "Sphere"), text: true, fmt: (v) => SPHERE[v] || NOT_STATED }, { key: "uf", label: "UF", text: true },
      { key: "abrangencia", label: L("Abrangência", "Scope"), text: true, fmt: (v) => SCOPE[v] || v }, { key: "multa", label: L("Multa", "Fine"), fmt: (v) => (n(v) ? brl(v) : "") }],
    { sortBy: "inicio", pageSize: 10, search: S.length > 10, name: `sancoes-${cnpj}` });
  }
  if (H.length) {
    const th = el("div");
    box.append(card(L("Entradas e saídas registradas", "Entries and exits recorded"), L(`A CGU publica só a lista do dia; o political-eye guarda cada captura desde ${since}. Uma sanção retirada não aparece mais na tabela acima.`,
      `The CGU publishes only the day's list; political-eye keeps every snapshot since ${since}. A removed sanction no longer appears in the table above.`), th));
    table(th, H, [{ key: "dia", label: L("Dia", "Day"), text: true, fmt: day }, { key: "lista", label: L("Lista", "List"), text: true }, { key: "codigo", label: L("Código", "Code"), text: true },
      { key: "mudanca", label: L("Mudança", "Change"), text: true, fmt: (v) => (v === "entrou" ? L("Incluída", "Added") : L("Retirada", "Removed")) }], { sortBy: "dia", search: false, name: `mudancas-${cnpj}` });
  }
  if (P.length) {
    const tp = el("div");
    box.append(card(L("Impedida de firmar convênios federais (CEPIM)", "Barred from federal agreements (CEPIM)"), L("Os convênios por trás do impedimento. O CEPIM não registra datas.", "The agreements behind the bar. CEPIM records no dates."), tp));
    table(tp, P, [{ key: "convenio", label: L("Convênio", "Agreement"), text: true }, { key: "orgao", label: L("Concedente", "Grantor"), text: true, wrap: true }, { key: "motivo", label: L("Motivo", "Reason"), text: true, wrap: true }], { search: false, name: `cepim-${cnpj}` });
  }
  if (Le.length) {
    const tl = el("div");
    box.append(card(L("Acordos de leniência", "Leniency agreements"), L("Acordos com a CGU pela Lei Anticorrupção, em que a empresa admitiu irregularidades e se comprometeu a reparar o dano.", "Agreements with the CGU under the Anti-Corruption Law, in which the company admitted wrongdoing and undertook to repair the damage."), tl));
    table(tl, Le, [{ key: "inicio", label: L("Início", "From"), text: true, fmt: day }, { key: "fim", label: L("Fim", "To"), text: true, fmt: day }, { key: "situacao", label: L("Situação", "Status"), text: true, fmt: (v) => LEN_STATUS[v] || v },
      { key: "orgao", label: L("Órgão", "Body"), text: true, wrap: true }], { search: false, name: `leniencia-${cnpj}` });
  }
}

/** Columns of value by year; a second series (red) for what was paid or signed while barred. */
function byYear(box, rows, barredName) {
  const ys = rows.map((x) => +x[0]), lo = Math.min(...ys), hi = Math.max(...ys);
  if (!rows.length || hi === lo) return false;
  const at = new Map(rows.map((x) => [+x[0], x]));
  const years = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
  const draw = () => C.stack(box, { x: years.map(String), height: 180, format: (v) => brl(v, 0), series: [
    { name: barredName, color: css("--critical"), values: years.map((y) => n(at.get(y)?.[2])) },
    { name: L("Demais", "Other"), color: css("--line"), values: years.map((y) => n(at.get(y)?.[1]) - n(at.get(y)?.[2])) }] });
  draw(); redraws.push(draw);
  return true;
}

function contractsSection(box, p, cnpj, r) {
  box.append(el("h3", { className: "dsec", id: "sec-contratos", textContent: L("Contratos públicos", "Public contracts") }));
  const c = p.c, k = r.pncp;
  const cover = L(`O PNCP é lido do dia mais recente para o mais antigo: ${fmt(k.days_read)} dos ${fmt(k.span_days)} dias desde ${k.since} foram lidos até agora (${k.first} a ${k.last}). Contratos de outros dias ainda não aparecem.`,
    `The PNCP is read from the newest day back: ${fmt(k.days_read)} of the ${fmt(k.span_days)} days since ${k.since} have been read so far (${k.first} to ${k.last}). Contracts from other days do not show yet.`);
  const typos = c?.x ? L(` ${plural(c.x, "contrato ficou", "contratos ficaram")} de fora: o valor publicado é implausível (acima de R$ 10 bilhões, ou de três anos da receita do município comprador), como na página de contratos.`,
    ` ${plural(c.x, "contract was", "contracts were")} left out: the published value is implausible (over R$ 10 billion, or three years of the buying town's revenue), as on the contracts page.`) : "";
  if (!c?.n) { box.append(el("p", { className: "hint", textContent: `${L("Nenhum contrato de R$ 1 milhão ou mais, nem contrato assinado durante um impedimento, nos dias lidos do PNCP.", "No contract of R$ 1 million or more, and no contract signed while barred, in the PNCP days read.")} ${cover}${typos}` })); return; }
  const T = (c.t || []).map(([assinatura, orgao, uf, objeto, v, cobre, controle, fixed]) => ({ assinatura, orgao, uf, objeto, v, cobre, controle, fixed }));
  const b = c.b || [0, 0];
  const shown = T.length < c.n ? L(` A tabela mostra os ${fmt(Math.min(10, T.length))} maiores e os assinados durante um impedimento.`, ` The table shows the ${fmt(Math.min(10, T.length))} largest and those signed while barred.`) : "";
  box.append(el("p", { className: "lead", textContent: L(`${plural(c.n, "contrato", "contratos")}, ${brl(c.v)}${b[0] ? `, dos quais ${fmt(b[0])} (${brl(b[1])}) assinados enquanto uma sanção impeditiva alcançava ou podia alcançar o comprador` : ""}.${shown}`,
    `${plural(c.n, "contract")}, ${brl(c.v)}${b[0] ? `, of which ${fmt(b[0])} (${brl(b[1])}) signed while a barring sanction reached or may have reached the buyer` : ""}.${shown}`) }));
  // By year, and who bought: from the summary when the table is cut, else from the table itself.
  const years = c.y || Object.values(T.reduce((a, x) => { const y = (x.assinatura || "").slice(0, 4); if (y) { a[y] ??= [y, 0, 0]; a[y][1]++; a[y][2] += n(x.v); } return a; }, {}));
  const barredYear = T.reduce((a, x) => { const y = (x.assinatura || "").slice(0, 4); if (["sim", "possivel"].includes(x.cobre)) a[y] = (a[y] || 0) + n(x.v); return a; }, {});
  const cy = chart();
  const yrows = years.map(([y, , v]) => [y, v, barredYear[y] || 0]);
  const tc = el("div");
  box.append(card(L("Os contratos", "The contracts"), `${L("Contratos de R$ 1 milhão ou mais e qualquer contrato assinado enquanto a empresa estava impedida. Valores com * foram corrigidos: o valor global publicado passava de 15 vezes o inicial, e conta o inicial.", "Contracts of R$ 1 million or more, and any contract signed while the company was barred. Values marked * were corrected: the published global value was over 15 times the initial one, which is counted instead.")} ${cover}`, tc));
  table(tc, T, [{ key: "assinatura", label: L("Assinatura", "Signed"), text: true, fmt: day }, { key: "orgao", label: L("Comprador", "Buyer"), text: true, wrap: true }, { key: "uf", label: "UF", text: true },
    { key: "objeto", label: L("Objeto", "Object"), text: true, wrap: true }, { key: "v", label: L("Valor", "Value"), fmt: (v, x) => `${brl(v)}${x.fixed ? " *" : ""}` },
    { key: "cobre", label: L("Durante impedimento", "While barred"), text: true, wrap: true, fmt: (v) => COBRE[v] || "" },
    { key: "controle", label: "PNCP", text: true, fmt: (v) => { const h = pncpHref(v); return h ? el("a", { href: h, textContent: L("ver", "view"), title: v, rel: "noopener" }) : v; } }],
  { sortBy: "v", pageSize: 10, search: T.length > 10, name: `contratos-${cnpj}` });
  if (typos) box.append(el("p", { className: "about", textContent: typos.trim() }));
  const extra = [];
  if (yrows.length > 1) extra.push(card(L("Valor por ano de assinatura", "Value by year signed"), L("Vermelho: assinados enquanto uma sanção impeditiva alcançava ou podia alcançar o comprador.", "Red: signed while a barring sanction reached or may have reached the buyer."), cy));
  if (c.o && c.o.length) {
    const tb = el("div");
    extra.push(card(L("Maiores compradores", "Largest buyers"), L(`Entre os ${fmt(c.no)} órgãos que contrataram a empresa.`, `Among the ${fmt(c.no)} bodies that contracted it.`), tb));
    table(tb, c.o.map(([orgao, uf, k2, v]) => ({ orgao, uf, k: k2, v })), [{ key: "orgao", label: L("Comprador", "Buyer"), text: true, wrap: true }, { key: "uf", label: "UF", text: true },
      { key: "k", label: L("Contratos", "Contracts") }, { key: "v", label: L("Valor", "Value"), fmt: (v) => brl(v) }], { sortBy: "v", search: false, name: `compradores-${cnpj}` });
  }
  if (extra.length) box.append(extra.length > 1 ? el("div", { className: "grid2" }, ...extra.map((x) => { x.classList.remove("wide"); return x; })) : extra[0]);
  if (yrows.length > 1) byYear(cy, yrows, L("Durante impedimento", "While barred"));
}

function amendmentsSection(box, p, cnpj, A, r) {
  box.append(el("h3", { className: "dsec", id: "sec-emendas", textContent: L("Emendas parlamentares", "Parliamentary amendments") }));
  const e = p.e;
  const what = L("Pagamentos de emendas feitos diretamente a este CNPJ, como favorecido, desde 2014. O dinheiro que chega à empresa por meio de uma prefeitura ou de um convênio não aparece aqui: nesse caso o favorecido é a prefeitura ou a entidade conveniada.",
    "Amendment payments made directly to this CNPJ, as the recipient, since 2014. Money that reaches the company through a town hall or an agreement does not show here: the recipient is then the town or the partner organisation.");
  if (!e) { box.append(el("p", { className: "hint", textContent: `${L("Nenhum pagamento direto de emenda.", "No direct amendment payment.")} ${what}` })); return; }
  const Y = e.y || [], barred = sum(Y.map((x) => n(x[2])));
  box.append(el("p", { className: "lead", textContent: L(`${brl(e.v)} pagos de ${Y[0]?.[0]} a ${Y[Y.length - 1]?.[0]}${barred ? `, dos quais ${brl(barred)} num mês em que estava sob uma sanção que impede contratar` : ""}.`,
    `${brl(e.v)} paid from ${Y[0]?.[0]} to ${Y[Y.length - 1]?.[0]}${barred ? `, of which ${brl(barred)} in a month when it was under a sanction barring contracts` : ""}.`) }));
  const ce = chart(), ta = el("div");
  const Au = (e.a || []).map(([code, v, vb]) => { const a = A.get(code) || {}; return { nome: a.nome || code, tipo: a.tipo || "", partido: a.partido || "", uf: a.uf || "", link: a.link || "", v, vb: vb || 0 }; });
  if (e.r) Au.push({ nome: L(`Outros ${fmt(e.r[0])} autores`, `${fmt(e.r[0])} other authors`), tipo: "", partido: "", uf: "", link: "", v: e.r[1], vb: 0 });
  if (e.u) Au.push({ nome: L("Sem emenda identificada", "No amendment code"), tipo: "", partido: "", uf: "", link: "", v: e.u, vb: 0 });
  const authorsCard = card(L("De quem eram as emendas", "Whose amendments paid it"), L("Os autores das emendas por trás dos pagamentos: deputados e senadores pelo nome, partido e estado mais recentes; bancadas, comissões e o relator-geral, que não têm partido. Nas emendas de relator de 2020 a 2022 (o \"orçamento secreto\"), quem escolheu o destino não foi publicado.",
    "The authors of the amendments behind the payments: deputies and senators by name and latest party and state; benches, committees and the rapporteur-general, which have no party. For the 2020–2022 rapporteur amendments (the \"secret budget\"), who chose the destination was not published."), ta);
  if (Y.length > 1) {
    box.append(el("div", { className: "grid2" }, card(L("Pago por ano", "Paid by year"), what, ce), authorsCard));
    for (const x of box.querySelectorAll(".grid2 > .card")) x.classList.remove("wide");
    byYear(ce, Y.map(([y, v, vb]) => [y, v, vb || 0]), L("Durante impedimento", "While barred"));
  } else {
    box.append(authorsCard);
    authorsCard.querySelector(".note").textContent += ` ${what}`;
  }
  table(ta, Au, [{ key: "nome", label: L("Autor", "Author"), text: true, wrap: true, fmt: (v, x) => member(v, x.link) }, { key: "tipo", label: L("Tipo", "Kind"), text: true, fmt: (v) => AUTHOR[v] || "" },
    { key: "partido", label: L("Partido", "Party"), text: true }, { key: "uf", label: "UF", text: true }, { key: "v", label: L("Pago", "Paid"), fmt: (v) => brl(v) },
    { key: "vb", label: L("Durante impedimento", "While barred"), fmt: (v) => (n(v) ? brl(v) : "") }], { sortBy: "v", pageSize: 8, search: false, name: `autores-${cnpj}` });
}

function campaignsSection(box, p, cnpj) {
  box.append(el("h3", { className: "dsec", id: "sec-campanhas", textContent: L("Campanhas eleitorais", "Election campaigns") }));
  const donors = L("Desde 2015 empresas não podem doar a campanhas (STF, ADI 4.650): nos dados do TSE uma empresa aparece só como fornecedora. Seus sócios podem doar como pessoas físicas, mas os dados abertos não ligam o CPF de um doador ao CNPJ de uma empresa.",
    "Since 2015 companies may not donate to campaigns (STF, ADI 4.650): in the TSE's data a company appears only as a supplier. Its owners may donate as individuals, but the open data do not link a donor's CPF to a company's CNPJ.");
  const T = p.t || [];
  if (!T.length) {
    box.append(el("p", { className: "hint", textContent: `${L("Não aparece como fornecedora de campanhas em 2018, 2022 ou 2026: nem com R$ 50 mil ou mais pagos por candidatos de qualquer cargo, nem em vendas a candidatos a deputado federal ou senador.",
      "It does not appear as a campaign supplier in 2018, 2022 or 2026: neither with R$ 50,000 or more paid by candidates for any office, nor in sales to federal deputy or senator candidates.")} ${donors}` }));
    return;
  }
  box.append(el("p", { className: "lead", textContent: donors }));
  for (const [ano, total, ncand, barred, cands, nRest, vRest, nFed, vFed] of T) {
    const bits = [];
    if (total != null) bits.push(L(`Candidatos de todos os cargos lhe pagaram ${brl(total)} (${plural(ncand, "candidato", "candidatos")}).`, `Candidates for every office paid it ${brl(total)} (${plural(ncand, "candidate")}).`));
    if (nFed) bits.push(L(`Vendeu a ${plural(nFed, "candidato", "candidatos")} a deputado federal ou senador, por ${brl(vFed)}.`, `It sold to ${plural(nFed, "federal deputy or senator candidate")}, for ${brl(vFed)}.`));
    if (barred) bits.push(L("No dia da eleição, estava sob uma sanção que impede contratar com o poder público (campanha não é contratação pública; o cruzamento é contexto).",
      "On election day it was under a sanction barring public contracts (a campaign is not public contracting; the match is context)."));
    const tb = el("div");
    box.append(card(L(`Eleição de ${ano}`, `${ano} election`), bits.join(" "), cands ? tb : null));
    if (cands) {
      const rows = cands.map(([nome, partido, uf, cargo, res, link, v]) => ({ nome, partido, uf, cargo, res, link, v }));
      if (nRest) rows.push({ nome: L(`Outros ${fmt(nRest)} candidatos`, `${fmt(nRest)} other candidates`), partido: "", uf: "", cargo: "", res: "", link: "", v: vRest });
      table(tb, rows, [{ key: "nome", label: L("Candidato", "Candidate"), text: true, wrap: true, fmt: (v, x) => member(v, x.link) }, { key: "partido", label: L("Partido", "Party"), text: true },
        { key: "uf", label: "UF", text: true }, { key: "cargo", label: L("Cargo", "Office"), text: true, fmt: (v) => OFFICE[v] || "" }, { key: "res", label: L("Resultado", "Result"), text: true, fmt: (v) => RESULT[v] || "" },
        { key: "v", label: L("Contratado", "Contracted"), fmt: (v) => brl(v) }], { sortBy: "v", pageSize: 10, search: false, name: `campanha-${ano}-${cnpj}` });
    }
  }
}

async function profile(root) {
  const r = await R();
  const out = el("div");
  const feat = await data("site/empresas/destaques.csv");
  const examples = feat.filter((x) => x.nome).slice(0, 4);
  root.append(el("div", { className: "controls" }, el("label", { style: "flex:1 1 420px" }, L("Busque uma empresa ou entidade pelo nome ou CNPJ", "Find a company or organisation by name or CNPJ"), companySearch(openCompany))),
    el("p", { className: "examples" }, L("Exemplos: ", "Examples: "), ...examples.map((x) => el("button", { type: "button", textContent: x.nome, on: { click: () => openCompany(x.cnpj) } }))), out);
  let token = 0;
  const show = async (cnpj, example = false) => {
    const mine = ++token;
    redraws.length = 0;
    const [shard, A] = await Promise.all([data(`site/empresas/perfis/${cnpj.slice(0, 3)}.json`).catch(() => ({})), authors()]);
    if (mine !== token) return;
    const p = shard[cnpj];
    if (!p) {
      out.replaceChildren(el("p", { className: "empty", textContent: L(`O CNPJ ${cnpjFmt(cnpj)} não tem ficha: não está nas listas de sanções, não tem contrato lido no PNCP, não recebeu emenda diretamente e não está em nenhuma lista de sinais de alerta. Órgãos públicos não têm ficha.`,
        `CNPJ ${cnpjFmt(cnpj)} has no profile: it is on no sanctions list, has no PNCP contract read, received no amendment directly and is on no red-flag list. Public bodies have no profile.`) }));
      return;
    }
    const box = el("div");
    out.replaceChildren(box);
    box.append(dossierHead(p, cnpj, r, example));
    const S = p.s || [], vig = S.filter((x) => x[10] === "v").length, T = p.t || [];
    const camp = sum(T.map((x) => (x[1] != null ? x[1] : n(x[8]))));
    const nflags = Object.keys(p.f || {}).length;
    const SECTIONS = [["sec-alertas", L("Sinais de alerta", "Red flags"), nflags], ["sec-sancoes", L("Sanções", "Sanctions"), S.length + (p.p || []).length + (p.l || []).length],
      ["sec-contratos", L("Contratos", "Contracts"), p.c?.n || 0], ["sec-emendas", L("Emendas", "Amendments"), (p.e?.y || []).length ? "" : 0], ["sec-campanhas", L("Campanhas", "Campaigns"), T.length]];
    box.append(el("nav", { className: "jump", "aria-label": L("Seções da ficha", "Profile sections") }, ...SECTIONS.map(([k, t, c]) => el("a", { href: `#${k}`,
      on: { click: (ev) => { ev.preventDefault(); document.getElementById(k)?.scrollIntoView({ behavior: "smooth", block: "start" }); } } }, t, c === "" ? null : el("span", { className: "n", textContent: fmt(c) })))));
    tiles(box.appendChild(el("section", { className: "tiles" })), [
      { label: L("Sanções em vigor", "Sanctions in force"), value: fmt(vig), sub: S.length ? L(`de ${plural(S.length, "listada", "listadas")} no CEIS e no CNEP`, `of ${fmt(S.length)} listed on CEIS and CNEP`)
        : (p.p || p.l || p.h) ? L("no CEIS e no CNEP; veja CEPIM, leniência e mudanças abaixo", "on CEIS and CNEP; see CEPIM, leniency and changes below") : L("nenhuma sanção registrada", "no sanction on record") },
      { label: L("Contratos no PNCP", "Contracts on the PNCP"), value: fmt(p.c?.n || 0), sub: p.c?.n ? `${brl(p.c.v)} · ${L(`${fmt(r.pncp.days_read)} de ${fmt(r.pncp.span_days)} dias lidos`, `${fmt(r.pncp.days_read)} of ${fmt(r.pncp.span_days)} days read`)}`
        : L(`nenhum nos ${fmt(r.pncp.days_read)} dias lidos`, `none in the ${fmt(r.pncp.days_read)} days read`) },
      { label: L("Emendas recebidas", "Amendment money received"), value: brl(p.e?.v || 0), sub: p.e ? L(`pagas diretamente, ${p.e.y[0][0]}–${p.e.y[p.e.y.length - 1][0]}`, `paid directly, ${p.e.y[0][0]}–${p.e.y[p.e.y.length - 1][0]}`) : L("nenhum pagamento direto desde 2014", "no direct payment since 2014") },
      { label: L("Vendas a campanhas", "Sales to campaigns"), value: brl(camp), sub: T.length ? L(`eleições de ${T.map((x) => x[0]).join(", ")}`, `${T.map((x) => x[0]).join(", ")} elections`) : L("nenhuma em 2018, 2022 ou 2026", "none in 2018, 2022 or 2026") },
    ]);
    flagsSection(box, p);
    sanctionsSection(box, p, cnpj, r);
    contractsSection(box, p, cnpj, r);
    amendmentsSection(box, p, cnpj, A, r);
    campaignsSection(box, p, cnpj);
  };
  showCompany = (cnpj) => show(cnpj, false);
  const asked = (params.get("cnpj") || "").replace(/\D/g, "");
  const start = asked || examples[0]?.cnpj;
  if (start) await show(start, !asked);
}

// ------------------------------------------------------------ companies in several sources

async function list(root) {
  const r = await R(), rows = await data("site/empresas/destaques.csv"), k = r.por_fonte;
  tiles(root.appendChild(el("section", { className: "tiles" })), [
    { label: L("Empresas e entidades com ficha", "Companies and organisations profiled"), value: fmt(r.empresas), sub: L(`${fmt(r.nomes_omitidos)} empresas individuais, com o nome omitido`, `${fmt(r.nomes_omitidos)} individual firms, name withheld`) },
    { label: L("Em duas fontes ou mais", "In two sources or more"), value: fmt(r.em_varias), sub: L(`${pct(r.em_varias / r.empresas, 1)} das fichas`, `${pct(r.em_varias / r.empresas, 1)} of profiles`) },
    { label: L("Com sanção em vigor", "Under a sanction in force"), value: fmt(r.sancoes.vigentes), sub: L(`${fmt(r.sancoes.impedidas)} impedidas de contratar em ${r.sancoes.snapshot}`, `${fmt(r.sancoes.impedidas)} barred from contracting on ${r.sancoes.snapshot}`) },
    { label: L("Em listas de sinais de alerta", "On red-flag lists"), value: fmt(k.alertas), sub: L("padrões que merecem um olhar mais atento, não provas", "patterns worth a closer look, not evidence") },
  ]);
  const cover = el("div");
  root.append(card(L("O que cada fonte traz", "What each source brings"), L("Quantas empresas cada fonte põe na página, e até onde cada fonte vai. Uma empresa entra quando aparece em pelo menos uma das quatro primeiras; as campanhas aparecem na ficha de quem já entrou.",
    "How many companies each source brings to the page, and how far each source reaches. A company is in when it appears in at least one of the first four; campaigns show in the profile of those already in."), cover));
  const P = r.pncp;
  table(cover, [
    { fonte: L("Listas de sanções (CEIS, CNEP, CEPIM, leniência)", "Sanctions lists (CEIS, CNEP, CEPIM, leniency)"), n: k.sancoes, alcance: L(`captura de ${r.sancoes.snapshot}; entradas e saídas desde ${r.sancoes.historico_desde}`, `snapshot of ${r.sancoes.snapshot}; entries and exits since ${r.sancoes.historico_desde}`) },
    { fonte: L("Contratos no PNCP", "Contracts on the PNCP"), n: k.contratos, alcance: L(`${fmt(P.days_read)} de ${fmt(P.span_days)} dias lidos (${P.first} a ${P.last}); R$ 1 milhão ou mais, ou assinados durante um impedimento`, `${fmt(P.days_read)} of ${fmt(P.span_days)} days read (${P.first} to ${P.last}); R$ 1 million or more, or signed while barred`) },
    { fonte: L("Pagamentos de emendas, direto ao favorecido", "Amendment payments, straight to the recipient"), n: k.emendas, alcance: L(`${r.emendas.first} a ${r.emendas.last}; só favorecidos privados e estatais`, `${r.emendas.first} to ${r.emendas.last}; private and state-owned recipients only`) },
    { fonte: L("Listas de sinais de alerta", "Red-flag lists"), n: k.alertas, alcance: L("as seis listas da página de sinais de alerta", "the six lists on the red-flags page") },
    { fonte: L("Fornecedores de campanha (TSE)", "Campaign suppliers (TSE)"), n: k.campanhas, alcance: L(`eleições de ${r.tse.eleicoes.join(", ")}`, `${r.tse.eleicoes.join(", ")} elections`) },
  ], [{ key: "fonte", label: L("Fonte", "Source"), text: true, wrap: true }, { key: "n", label: L("Empresas", "Companies"), fmt: (v) => fmt(v) }, { key: "alcance", label: L("Alcance", "Coverage"), text: true, wrap: true }],
  { search: false, sortBy: null, name: "fontes" });
  const tb = el("div");
  root.append(card(L("Empresas em mais listas de alerta e mais fontes", "Companies on the most red-flag lists and in the most sources"),
    L(`As ${fmt(rows.length)} primeiras, ordenadas pelo número de listas de sinais de alerta, depois de fontes, depois pelo dinheiro público recebido (contratos e emendas). Aparecer em várias fontes não é suspeito por si só: é o que acontece com quem contrata muito com o Estado. Clique num nome para abrir a ficha.`,
      `The first ${fmt(rows.length)}, ordered by the number of red-flag lists, then of sources, then by the public money received (contracts and amendments). Being in several sources is not suspicious in itself: it is what happens to anyone who contracts a lot with the State. Click a name to open the profile.`), tb));
  for (const x of rows) for (const c of ["vigentes", "contratos", "contratos_valor", "emendas", "campanhas", "alertas"]) x[c] = n(x[c]);
  table(tb, rows, [{ key: "nome", label: L("Empresa", "Company"), text: true, wrap: true, fmt: (v, x) => companyLink(v, x.cnpj) },
    { key: "fontes", label: L("Fontes", "Sources"), text: true, wrap: true, fmt: (v) => srcPills(v), sort: (x) => x.fontes.replace("H", "").length },
    { key: "alertas", label: L("Alertas", "Flags") }, { key: "vigentes", label: L("Sanções vigentes", "Sanctions in force") },
    { key: "contratos_valor", label: L("Contratos", "Contracts"), fmt: (v) => (v ? brl(v) : "") }, { key: "emendas", label: L("Emendas", "Amendments"), fmt: (v) => (v ? brl(v) : "") },
    { key: "campanhas", label: L("Campanhas", "Campaigns"), fmt: (v) => (v ? brl(v) : "") }], { pageSize: 25, name: "empresas" });
}

// ------------------------------------------------------------ boot

const SECTIONS = { profile, list };
showTab = tabs((name) => { const box = $(`#tab-${name}`); guard(box, () => SECTIONS[name](box)); });
onResize(() => redraws.forEach((f) => f()));
