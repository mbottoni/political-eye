// political-eye: what changed. Each source's job keeps a log of its last 90 days (data/site/mudancas/<fonte>.csv)
// and one summary per day (<fonte>.json), written by politicaleye/site/mudancas.py; this page shows them by day,
// filtered by source and period, and links the Atom feeds built from the same logs.
import { setupPage } from "../lib/page.js";
import { $, brl, data, el, fmt, guard, params, plural, setParam, tiles } from "../lib/ui.js";
import { L, date, lang, month } from "../lib/i18n.js";

setupPage();

const FONTES = ["sancoes", "alertas", "emendas", "pncp", "camara", "senado"];
const COLOR = { sancoes: "--s8", alertas: "--s4", emendas: "--s3", pncp: "--s2", camara: "--s1", senado: "--s7" };
const PERIODS = [7, 30, 90];
const SHOW = 8;        // items per source and day before "show all"
const DAYS = 10;       // days drawn before "earlier days"
const en = () => lang() === "en";
const feed = (f) => `../feeds/${en() ? "en/" : ""}${f}.xml`;
const ALL = () => (en() ? "all" : "todas");
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const since = (days) => { const d = new Date(); d.setDate(d.getDate() - (days - 1)); return iso(d); };
const WITHHELD = () => L("Empresa individual (nome omitido)", "Individual firm (name withheld)");

const ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1.6" fill="currentColor"/></svg>';

let logs = [], fonte = FONTES.includes(params.get("fonte")) ? params.get("fonte") : "", dias = PERIODS.includes(+params.get("dias")) ? +params.get("dias") : 30;
const target = /^\d{4}-\d{2}-\d{2}$/.test(params.get("dia") || "") ? params.get("dia") : null;
if (target && target < since(dias)) dias = PERIODS.find((p) => target >= since(p)) || 90;

// ------------------------------------------------------------ pieces

function subscribe() {
  const box = $("#subscribe");
  const a = el("a", { className: "feed", href: feed(ALL()), title: L("Feed Atom: cole o endereço no seu leitor de feeds", "Atom feed: paste the address into your feed reader") });
  a.innerHTML = ICON;
  a.append(L("Feed de todas as fontes", "Feed of every source"));
  const per = FONTES.flatMap((f, i) => {
    const m = logs.find((x) => x.f === f)?.meta;
    return [i ? " · " : "", el("a", { href: feed(f), textContent: m ? m.nome[lang()] : f })];
  });
  box.replaceChildren(a, el("span", {}, L("ou por fonte: ", "or by source: "), ...per),
    el("span", { className: "hint", textContent: L("Atom: cole o endereço no seu leitor de feeds.", "Atom: paste the address into your feed reader.") }));
}

function inPeriod(rows) {
  const from = since(dias);
  return rows.filter((r) => r.data >= from);
}

function drawTiles() {
  const get = (f) => inPeriod(logs.find((x) => x.f === f)?.rows || []);
  const sa = get("sancoes"), al = get("alertas"), em = get("emendas"), pn = get("pncp");
  const who = (rows, end) => new Set(rows.filter((r) => r.tipo.endsWith(end)).map((r) => r.chave.split(":").pop())).size;
  const people = (rows, part) => rows.filter((r) => r.tipo.includes(part) && r.tipo.endsWith("_pessoas")).reduce((s, r) => s + +r.n, 0);
  const flags = al.filter((r) => !r.tipo.endsWith("_historico")), old = al.filter((r) => r.tipo.endsWith("_historico")).reduce((s, r) => s + +r.n, 0);
  const sum = (rows) => rows.reduce((s, r) => s + (+r.valor || 0), 0);
  const cov = logs.find((x) => x.f === "pncp")?.meta?.cobertura;
  tiles($("#tiles"), [
    { label: L("Empresas que entraram em listas de sanções", "Companies that entered a sanctions list"), value: fmt(who(sa, "_entrou")),
      sub: L(`${fmt(who(sa, "_saiu"))} saíram; ${plural(people(sa, "_entrou_"), "pessoa entrou", "pessoas entraram")}, contadas e nunca nomeadas`,
        `${fmt(who(sa, "_saiu"))} left; ${plural(people(sa, "_entrou_"), "person", "people")} entered, counted and never named`) },
    { label: L("Sinais de alerta novos", "New red flags"), value: fmt(flags.length),
      sub: old ? L(`e ${fmt(old)} contratos antigos achados no histórico do PNCP`, `and ${fmt(old)} older contracts found in the PNCP history`)
        : L("um sinal não é prova de irregularidade", "a flag is not evidence of an irregularity") },
    { label: L("Grandes pagamentos de emendas", "Large amendment payments"), value: brl(sum(em), 1),
      sub: L(`${plural(em.length, "pagamento", "pagamentos")} de R$ 5 mi ou mais`, `${plural(em.length, "payment")} of R$ 5 M or more`) },
    { label: L("Grandes contratos publicados", "Large contracts published"), value: brl(sum(pn), 1),
      sub: L(`${plural(pn.length, "contrato", "contratos")} de R$ 100 mi ou mais`, `${plural(pn.length, "contract")} of R$ 100 M or more`)
        + (cov ? L(`; PNCP lido em ${fmt(cov.dias_lidos)} de ${fmt(cov.dias)} dias`, `; PNCP read on ${fmt(cov.dias_lidos)} of ${fmt(cov.dias)} days`) : "") },
  ]);
  $("#tiles").querySelectorAll(".tile").forEach((t, i) => t.style.setProperty("--accent", `var(${COLOR[["sancoes", "alertas", "emendas", "pncp"][i]]})`));
}

function chip(label, count, on, color, click) {
  return el("button", { type: "button", className: "chip", "aria-pressed": String(on), style: color ? `--src: var(${color})` : "", on: { click } },
    color ? el("i") : null, label, count != null ? el("b", { textContent: fmt(count) }) : null);
}

function drawControls() {
  const counts = Object.fromEntries(logs.map((x) => [x.f, inPeriod(x.rows).length]));
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const src = el("div", { className: "chips", role: "group", "aria-label": L("Fonte", "Source") },
    chip(L("Todas", "All"), total, !fonte, null, () => set({ fonte: "" })),
    ...logs.map((x) => chip(x.meta.nome[lang()], counts[x.f], fonte === x.f, COLOR[x.f], () => set({ fonte: x.f }))));
  const per = el("div", { className: "chips", role: "group", "aria-label": L("Período", "Period") },
    ...PERIODS.map((p) => chip(L(`${p} dias`, `${p} days`), null, dias === p, null, () => set({ dias: p }))));
  $("#controls").replaceChildren(el("div", { className: "ctl" }, el("span", { textContent: L("Fonte", "Source") }), src),
    el("div", { className: "ctl" }, el("span", { textContent: L("Período", "Period") }), per));
}

function drawRule() {
  const box = $("#rule");
  if (!fonte) {
    box.replaceChildren(el("p", { textContent: L(
      "Cada mudança leva a data do dado que a mostrou: o retrato da CGU para as sanções, o dia da publicação para os contratos, o arquivo do Portal da Transparência para as emendas, o retrato das sanções para os sinais de alerta e o dia da primeira votação para os meses. Escolha uma fonte para ver a regra de cada registro.",
      "Each change carries the date of the data that showed it: the CGU snapshot for sanctions, the publication day for contracts, the Transparency Portal's file for amendments, the sanctions snapshot for red flags and the day of the first roll call for months. Pick a source to see each log's rule.") }));
    return;
  }
  const m = logs.find((x) => x.f === fonte).meta, k = lang();
  const lines = [el("p", { textContent: m.regra[k] })];
  const span = m.desde ? L(`Registro desde ${date(m.desde)}; dado mais recente: ${date(m.ate)}.`, `Log since ${date(m.desde)}; latest data: ${date(m.ate)}.`) : "";
  const cov = m.cobertura ? L(` Nos 90 dias até ${date(m.ate)}, o PNCP foi lido em ${fmt(m.cobertura.dias_lidos)} dias de ${fmt(m.cobertura.dias)}; ${plural(m.cobertura.implausiveis, "contrato com valor implausível ficou", "contratos com valor implausível ficaram")} de fora.`,
    ` In the 90 days to ${date(m.ate)}, the PNCP was read on ${fmt(m.cobertura.dias_lidos)} of ${fmt(m.cobertura.dias)} days; ${plural(m.cobertura.implausiveis, "contract")} with an implausible value left out.`) : "";
  if (span || cov) lines.push(el("p", { textContent: span + cov }));
  if (m.nota) lines.push(el("p", { textContent: m.nota[k] }));
  lines.push(el("p", {}, el("a", { href: m.pagina, textContent: L(`Abrir a página: ${m.nome.pt}`, `Open the page: ${m.nome.en}`) }), " · ",
    el("a", { href: feed(fonte), textContent: L("feed Atom desta fonte", "this source's Atom feed") })));
  box.replaceChildren(...lines);
}

function item(r, tipos) {
  const kind = tipos[r.tipo]?.[lang()] || r.tipo;
  const go = () => el("a", { className: "go", href: r.link, textContent: L("ver →", "see →") });
  let name, link = false;
  if (r.titulo) { name = el("a", { className: "name", href: r.link, textContent: r.titulo }); link = true; }
  else if (+r.pf) name = el("span", { className: "name withheld", textContent: WITHHELD() });
  else if (r.tipo === "mes") name = el("span", { className: "name", textContent: month(r.chave) });
  else if (r.tipo.endsWith("_pessoas")) name = el("span", { className: "name", textContent: plural(+r.n, L("pessoa", "person"), L("pessoas", "people")) });
  else if (r.tipo.endsWith("_historico")) name = el("span", { className: "name", textContent: plural(+r.n, L("contrato", "contract"), L("contratos", "contracts")) });
  else name = el("span", { className: "name", textContent: "–" });
  const detail = en() ? r.detalhe_en || r.detalhe : r.detalhe;
  return el("li", {},
    el("div", { className: "what" }, el("span", { className: "kind", textContent: kind }), name, link ? null : el("span", {}, " ", go()),
      detail ? el("span", { className: "detail", textContent: detail }) : null),
    el("span", { className: "val", textContent: r.valor !== "" && +r.valor ? brl(+r.valor, 1) : "" }));
}

function group(f, day, rows) {
  const x = logs.find((y) => y.f === f), m = x.meta;
  const sum = m.dias.find((d) => d.data === day);
  const list = el("ul", { className: "items" }), extra = rows.length - SHOW;
  const fill = (all) => list.replaceChildren(...(all ? rows : rows.slice(0, SHOW)).map((r) => item(r, m.tipos)));
  fill(false);
  const box = el("article", { className: "group", style: `--src: var(${COLOR[f]})` },
    el("header", {}, el("span", { className: "badge", textContent: m.nome[lang()] }),
      el("p", { className: "sum", textContent: sum ? (en() ? sum.resumo_en : sum.resumo) : "" }),
      el("a", { className: "more-link", href: m.pagina, textContent: L("abrir a página →", "open the page →") })),
    list);
  if (extra > 0) {
    const t = el("button", { type: "button", className: "toggle", textContent: L(`Mostrar todos os ${fmt(rows.length)}`, `Show all ${fmt(rows.length)}`) });
    let open = false;
    t.addEventListener("click", () => { open = !open; fill(open); t.textContent = open ? L("Mostrar menos", "Show fewer") : L(`Mostrar todos os ${fmt(rows.length)}`, `Show all ${fmt(rows.length)}`); });
    box.append(t);
  }
  if (m.nota) box.append(el("p", { className: "note", textContent: m.nota[lang()] }));
  return box;
}

function drawTimeline() {
  const box = $("#timeline");
  const rows = logs.filter((x) => !fonte || x.f === fonte).flatMap((x) => inPeriod(x.rows));
  const days = [...new Set(rows.map((r) => r.data))].sort().reverse();
  if (!days.length) {
    const latest = logs.filter((x) => !fonte || x.f === fonte).flatMap((x) => x.rows.map((r) => r.data)).sort().pop();
    box.replaceChildren(el("p", { className: "empty", textContent: latest
      ? L(`Nenhuma mudança registrada nos últimos ${dias} dias. A mais recente é de ${date(latest)}.`, `No change recorded in the last ${dias} days. The latest is from ${date(latest)}.`)
      : L("Nenhuma mudança registrada ainda nesta fonte: o registro começa na primeira construção e mostra o que aparecer depois.",
        "No change recorded yet for this source: the log starts at its first build and shows what appears after it.") }));
    return;
  }
  let shown = Math.max(DAYS, target ? days.indexOf(target) + 1 : 0);
  const quiet = (FONTES.filter((f) => !fonte || f === fonte)).filter((f) => !rows.some((r) => r.fonte === f));
  const draw = () => {
    const parts = days.slice(0, shown).map((d) => {
      const sec = el("section", { className: `day${d === target ? " hit" : ""}`, id: `d-${d}` });
      const here = rows.filter((r) => r.data === d);
      sec.append(el("h2", {}, date(d), el("small", { textContent: plural(here.length, L("mudança", "change"), L("mudanças", "changes")) })));
      for (const f of FONTES) {
        const g = here.filter((r) => r.fonte === f);
        if (g.length) sec.append(group(f, d, g));
      }
      return sec;
    });
    if (quiet.length && !fonte) {
      parts.push(el("p", { className: "quiet", textContent: L(`Sem mudanças no período: ${quiet.map((f) => logs.find((x) => x.f === f).meta.nome.pt).join(", ")}.`,
        `No changes in the period: ${quiet.map((f) => logs.find((x) => x.f === f).meta.nome.en).join(", ")}.`) }));
    }
    if (shown < days.length) {
      const b = el("button", { type: "button", className: "toggle", textContent: L(`Dias anteriores (${fmt(days.length - shown)})`, `Earlier days (${fmt(days.length - shown)})`) });
      b.addEventListener("click", () => { shown += DAYS; draw(); });
      parts.push(el("div", { className: "later" }, b));
    }
    box.replaceChildren(...parts);
  };
  draw();
}

function set(change) {
  if ("fonte" in change) { fonte = change.fonte; setParam("fonte", fonte, ""); }
  if ("dias" in change) { dias = change.dias; setParam("dias", String(dias), "30"); }
  render();
}

function render() {
  drawTiles();
  drawControls();
  drawRule();
  drawTimeline();
}

// ------------------------------------------------------------ boot

guard($("#timeline"), async () => {
  const got = await Promise.all(FONTES.map(async (f) => {
    try {
      const [meta, rows] = await Promise.all([data(`site/mudancas/${f}.json`), data(`site/mudancas/${f}.csv`)]);
      return { f, meta, rows };
    } catch (e) { console.warn(`mudancas ${f}:`, e); return null; }   // a source whose log was never built is left out
  }));
  logs = got.filter(Boolean);
  if (!logs.length) throw new Error(L("nenhum registro de mudanças encontrado", "no change log found"));
  if (fonte && !logs.some((x) => x.f === fonte)) fonte = "";
  subscribe();
  render();
  if (target) document.getElementById(`d-${target}`)?.scrollIntoView({ block: "start" });
});
