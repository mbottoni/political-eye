"""What changed: one short change log per source, the Atom feeds and the "what changed" page.

The repository's history records every change, but only git can read it. Each source's job keeps a log of what
changed in the last WINDOW days, in one shape for every source, so a page, a feed reader and an email can follow it:

    data/site/mudancas/<fonte>.csv          one row per change: data, fonte, tipo, chave, titulo, pf, detalhe,
                                            detalhe_en, valor, n, link
    data/site/mudancas/<fonte>.json         the rule behind the log, since when it runs, coverage, the label of each
                                            kind of change, and one summary per day (pt and en)
    data/site/mudancas/estado/<fonte>.json  for the logs that compare two builds: what the last build held
    docs/feeds/<fonte>.xml, todas.xml       Atom, one entry per source and day, in Portuguese
    docs/feeds/en/<fonte>.xml, all.xml      the same in English

Two kinds of log:

- dated by the source, rebuilt from the data every time: ``sancoes`` (the snapshot that first showed an entry or an
  exit, data/sancoes/changes.csv), ``pncp`` (the day a contract was published), ``camara`` and ``senado`` (the day of
  a month's first roll call);
- found by comparing two builds, dated by the data the build read: ``alertas`` (the red-flag lists, dated by the
  sanctions snapshot) and ``emendas`` (payments over PAY_MIN, dated by the amendments file's Last-Modified). The
  first build only records what is there.

Each log keeps the WINDOW days up to its own latest date, never up to today, and no file carries the time of the run:
a run with nothing new rewrites every file byte for byte. People are never named (sanctioned people are counted per
day; individual firms named after a person keep their CNPJ, not their name). See methodology/mudancas.md.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from html import escape
from pathlib import Path

import pandas as pd

from .common import csv, write_json

WINDOW = 90                # days each log keeps, up to its own latest date
PAY_MIN = 5_000_000        # an amendment payment (one amendment, one recipient, one month) worth listing
CONTRACT_MIN = 100_000_000  # a contract worth listing, at the value the contracts page counts it at
FEED_ENTRIES = 30          # entries (source-days) in each source's feed
FEED_ALL = 60              # entries in the feed of every source
FEED_ITEMS = 20            # changes listed in one entry; the rest are on the page
SITE = "https://mbottoni.github.io/political-eye/"
TAG = "tag:mbottoni.github.io,2026:political-eye"
COLS = ["data", "fonte", "tipo", "chave", "titulo", "pf", "detalhe", "detalhe_en", "valor", "n", "link"]

FONTES = {
    "sancoes": {"pt": "Sanções", "en": "Sanctions", "pagina": "sancoes/"},
    "alertas": {"pt": "Sinais de alerta", "en": "Red flags", "pagina": "alertas/"},
    "emendas": {"pt": "Emendas parlamentares", "en": "Parliamentary amendments", "pagina": "emendas/"},
    "pncp": {"pt": "Contratos públicos", "en": "Public contracts", "pagina": "pncp/"},
    "camara": {"pt": "Câmara dos Deputados", "en": "Câmara dos Deputados", "pagina": "camara/"},
    "senado": {"pt": "Senado Federal", "en": "Senado Federal", "pagina": "senado/"},
}
COMBINED = {"pt": "todas", "en": "all"}

_LISTS = {"ceis": "CEIS", "cnep": "CNEP", "cepim": "CEPIM"}
TIPOS = {
    "sancoes": {
        **{f"{k}_entrou": (f"Entrou no {v}", f"Entered {v}") for k, v in _LISTS.items()},
        **{f"{k}_saiu": (f"Saiu do {v}", f"Left {v}") for k, v in _LISTS.items()},
        **{f"{k}_entrou_pessoas": (f"Pessoas que entraram no {v}", f"People who entered {v}") for k, v in _LISTS.items()},
        **{f"{k}_saiu_pessoas": (f"Pessoas que saíram do {v}", f"People who left {v}") for k, v in _LISTS.items()},
        "leniencia_entrou": ("Novo acordo de leniência", "New leniency agreement"),
        "leniencia_saiu": ("Saiu da lista de acordos de leniência", "Left the leniency agreements list"),
    },
    "alertas": {
        "emendas_impedidas": ("Emenda paga a empresa impedida", "Amendment paid to a barred company"),
        "contratos_impedidas": ("Contrato com empresa impedida na data", "Contract with a company barred on the day"),
        "contratos_impedidas_historico": ("Contratos antigos com empresa impedida", "Older contracts with a barred company"),
        "campanha_emendas": ("Fornecedor de campanha pago com emendas do mesmo parlamentar", "Campaign supplier paid from the same member's amendments"),
        "concentracao": ("Emendas concentradas em um favorecido privado", "Amendments concentrated on one private recipient"),
        "fornecedor_dominante": ("Órgão dominado por um fornecedor", "Buyer dominated by one supplier"),
        "leniencia_contratos": ("Contrato após acordo de leniência", "Contract after a leniency agreement"),
        "leniencia_contratos_historico": ("Contratos antigos após acordo de leniência", "Older contracts after a leniency agreement"),
    },
    "emendas": {"pagamento": ("Pagamento de emenda de R$ 5 mi ou mais", "Amendment payment of R$ 5 M or more")},
    "pncp": {"contrato": ("Contrato de R$ 100 mi ou mais", "Contract of R$ 100 M or more")},
    "camara": {"mes": ("Mês com votações nominais", "Month with roll calls")},
    "senado": {"mes": ("Mês com votações nominais", "Month with roll calls")},
}

REGRAS = {
    "sancoes": ("Empresas e entidades que entraram ou saíram do CEIS, do CNEP, do CEPIM ou da lista de acordos de leniência, "
                "na data do retrato da CGU que mostrou a mudança. Pessoas são contadas por dia, nunca nomeadas; empresas "
                "individuais com nome de pessoa aparecem só com o CNPJ.",
                "Companies and organisations that entered or left CEIS, CNEP, CEPIM or the leniency agreements list, on the "
                "date of the CGU snapshot that showed the change. People are counted per day, never named; individual firms "
                "named after a person appear with their CNPJ only."),
    "alertas": ("Sinais que não estavam na construção anterior da página de sinais de alerta, datados pelo retrato das sanções "
                "que a construção leu. Contratos assinados antes da janela, quase todos vindos do histórico do PNCP que ainda "
                "está sendo lido, são contados por dia, não listados. Um sinal não é prova de irregularidade.",
                "Flags that were not in the previous build of the red-flags page, dated by the sanctions snapshot that build "
                "read. Contracts signed before the window, nearly all from the PNCP history still being read, are counted per "
                "day, not listed. A flag is not evidence of an irregularity."),
    "emendas": ("Pagamentos de emenda (uma emenda, um favorecido, um mês) que chegaram a R$ 5 milhões desde a construção "
                "anterior, datados pelo arquivo do Portal da Transparência. Em 2025 e 2026, pagamentos desse tamanho são 0,8% "
                "das linhas e 20% do dinheiro, uns 70 por mês.",
                "Amendment payments (one amendment, one recipient, one month) that reached R$ 5 million since the previous "
                "build, dated by the Transparency Portal's file. In 2025 and 2026 payments that large are 0.8% of the rows and "
                "20% of the money, about 70 a month."),
    "pncp": ("Contratos publicados no PNCP que contam R$ 100 milhões ou mais pelas regras da página de contratos (valores "
             "implausíveis corrigidos ou deixados de fora), na data de publicação. São 1,3% dos contratos de R$ 1 milhão ou "
             "mais e 44% do valor deles, uns 2 ou 3 por dia.",
             "Contracts published on the PNCP that count R$ 100 million or more under the contracts page's rules (implausible "
             "values fixed or left out), on the day they were published. They are 1.3% of contracts of R$ 1 million or more "
             "and 44% of their value, two or three a day."),
    "camara": ("Cada mês que ganhou suas primeiras votações nominais no Plenário, na data da primeira; o número cresce a cada "
               "semana até o mês acabar.",
               "Each month that got its first roll calls in the plenary, on the day of the first; the count grows each week "
               "until the month ends."),
    "senado": ("Cada mês que ganhou suas primeiras votações nominais no Plenário, na data da primeira; o número cresce a cada "
               "semana até o mês acabar.",
               "Each month that got its first roll calls in the plenary, on the day of the first; the count grows each week "
               "until the month ends."),
}
NOTAS = {
    "sancoes": ("Pessoas punidas são contadas, nunca nomeadas.", "Sanctioned people are counted, never named."),
    "alertas": ("Um sinal não é prova de irregularidade: é um padrão nos dados oficiais que pode ter explicação legítima.",
                "A flag is not evidence of an irregularity: it is a pattern in official data that may have a legitimate explanation."),
}

# ------------------------------------------------------------------ formats (the pages' own, in Python)

_MONTHS = {"pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"],
           "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]}


def num(x: float, lang: str, digits: int = 0) -> str:
    s = f"{x:,.{digits}f}"
    return s.translate(str.maketrans(",.", ".,")) if lang == "pt" else s


def brl(x: float, lang: str) -> str:
    """R$ with a scale word, as on the pages: R$ 6,2 mi / R$ 6.2 M."""
    a = abs(float(x))
    units = [" tri", " bi", " mi", " mil"] if lang == "pt" else [" tn", " bn", " M", " k"]
    for d, u in zip((1e12, 1e9, 1e6, 1e3), units):
        if a >= d * 0.9995:
            n = a / d
            return f"R$ {num(n, lang, 0 if round(n, 1) >= 100 else 1)}{u}"
    return f"R$ {num(a, lang)}"


def day(iso: str, lang: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso or ""):
        return iso or ""
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}" if lang == "pt" else f"{int(d)} {_MONTHS['en'][int(m) - 1][:3]} {y}"


def month(ym: str, lang: str, short: bool = False) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}", ym or ""):
        return ym or ""
    if short:
        return f"{ym[5:7]}/{ym[:4]}" if lang == "pt" else f"{_MONTHS['en'][int(ym[5:7]) - 1][:3]} {ym[:4]}"
    m = _MONTHS[lang][int(ym[5:7]) - 1]
    return f"{m} de {ym[:4]}" if lang == "pt" else f"{m} {ym[:4]}"


def pct(x: float, lang: str) -> str:
    return f"{num(100 * float(x), lang)}%"


def cnpj(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if re.fullmatch(r"\d{14}", c or "") else (c or "")


def withheld(lang: str) -> str:
    return "Empresa individual (nome omitido)" if lang == "pt" else "Individual firm (name withheld)"


def _both(f):
    """Render a detail in both languages: f(lang) -> text."""
    return f("pt"), f("en")


# ------------------------------------------------------------------ helpers

def _read(p: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(p, dtype=str, keep_default_na=False, **kw) if p.exists() else pd.DataFrame()


def _money(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _cut(anchor: str) -> str:
    """The day before the window: a log keeps the rows dated after it."""
    return (date.fromisoformat(anchor) - timedelta(days=WINDOW)).isoformat()


def _row(**kw) -> dict:
    r = {c: "" for c in COLS} | {"pf": 0, "valor": None, "n": None}
    r.update(kw)
    return r


def _frame(rows) -> pd.DataFrame:
    if isinstance(rows, pd.DataFrame) and rows.empty:
        return pd.DataFrame(columns=COLS)
    t = pd.DataFrame(rows, columns=COLS) if not isinstance(rows, pd.DataFrame) else rows[COLS].copy()
    if t.empty:
        return pd.DataFrame(columns=COLS)
    t["valor"] = pd.to_numeric(t.valor, errors="coerce").round(2)
    t["n"] = pd.to_numeric(t.n, errors="coerce").astype("Int64")
    t["pf"] = pd.to_numeric(t.pf, errors="coerce").fillna(0).astype(int)
    for c in ("data", "fonte", "tipo", "chave", "titulo", "detalhe", "detalhe_en", "link"):
        t[c] = t[c].fillna("").astype(str)
    t = t.drop_duplicates(["data", "fonte", "tipo", "chave"], keep="last")
    t = t.assign(_v=t.valor.fillna(-1)).sort_values(["data", "tipo", "_v", "chave"], ascending=[False, True, False, True])
    return t.drop(columns="_v").reset_index(drop=True)


def _state(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _write_state(path: Path, since: str, keys) -> None:
    """What a build held, one key per line so its git diff reads as the change itself."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"desde": since, "chaves": sorted(set(keys))}, ensure_ascii=False, indent=0) + "\n")


def _modified(sources: Path, name: str) -> str:
    """The Last-Modified day of a bulk file, from a source's sources.json."""
    s = json.loads(sources.read_text()) if sources.exists() else {}
    lm = s.get(name, {}).get("last_modified", "")
    try:
        return parsedate_to_datetime(lm).date().isoformat() if lm else ""
    except (TypeError, ValueError):
        return ""


def _snapshot(data: Path) -> str:
    s = json.loads((data / "sancoes" / "sources.json").read_text()) if (data / "sancoes" / "sources.json").exists() else {}
    return s.get("ceis", {}).get("date", "")


def _people(data: Path, cache: dict) -> set[str]:
    if "people" not in cache:
        from .sancoes import name_tokens
        cache["people"] = name_tokens(data)
    return cache["people"]


def _person_firm(names: pd.Series, people: set[str]) -> pd.Series:
    from .sancoes import individual_firm
    return individual_firm(names, people)


# ------------------------------------------------------------------ sanctions: from the lists' own change log

_SPHERE = {"FEDERAL": ("federal", "federal"), "ESTADUAL": ("estadual", "state"), "MUNICIPAL": ("municipal", "municipal")}
# The CGU's categories as the sanctions page labels them (docs/sancoes/app.js, CAT).
_CAT = {
    "Impedimento/proibição de contratar com prazo determinado": ("Impedimento, com prazo", "Contracting ban, fixed term"),
    "Impedimento/proibição de contratar sem prazo determinado": ("Impedimento, sem prazo", "Contracting ban, no end date"),
    "Suspensão": ("Suspensão de licitar", "Suspended from tenders"),
    "Declaração de Inidoneidade sem prazo determinado": ("Inidoneidade, sem prazo", "Declared unfit, no end date"),
    "Declaração de Inidoneidade com prazo determinado": ("Inidoneidade, com prazo", "Declared unfit, fixed term"),
    "Demissão": ("Demissão (servidor público)", "Dismissed (civil servant)"),
    "Suspensão/Interdição das atividades sem prazo determinado": ("Interdição, sem prazo", "Activity halt, no end date"),
    "Suspensão/Interdição das atividades com prazo determinado": ("Interdição, com prazo", "Activity halt, fixed term"),
    "Multa": ("Multa", "Fine"),
    "Advertência": ("Advertência", "Warning"),
    "Publicação extraordinária da decisão condenatória": ("Publicação da condenação", "Ruling published at its cost"),
    "Proibição de receber incentivos, subsídios, subvenções, doações ou empréstimos": ("Proibição de receber subsídios", "No subsidies or public loans"),
    "Dissolução compulsória da PJ": ("Dissolução compulsória", "Compulsory dissolution"),
    "Perdimento de bens": ("Perdimento de bens", "Assets forfeited"),
}


def log_sancoes(data: Path, cache: dict) -> tuple[pd.DataFrame, dict]:
    from .sancoes import COMPANY, sanctions
    src = data / "sancoes"
    ch = _read(src / "changes.csv")
    meta = {"desde": ch.data.min() if len(ch) else "", "ate": ch.data.max() if len(ch) else ""}
    if ch.empty:
        return _frame([]), meta
    anchor = ch.data.max()
    ch = ch[ch.data > _cut(anchor)]
    company = ch.documento.str.fullmatch(COMPANY) & (ch.tipo_de_pessoa != "F")
    rows = []
    # People: one count per day, list and direction. Never a name, never a document.
    for (d, lista, m), n in ch[~company].groupby(["data", "lista", "mudanca"]).size().items():
        rows.append(_row(data=d, fonte="sancoes", tipo=f"{lista}_{m}_pessoas", chave=f"{lista}:{m}:pessoas", n=int(n), link="../sancoes/?tab=changes"))
    co = ch[company].copy()
    if len(co):
        s = sanctions(src)
        s = s.assign(lista=s.lista.str.lower())[["lista", "codigo", "categoria", "orgao", "esfera", "uf", "fim", "multa"]]
        co = co.merge(s, how="left", on=["lista", "codigo"])
        cep = _read(src / "cepim.csv")
        if len(cep):
            org = cep.drop_duplicates("cnpj_entidade").set_index("cnpj_entidade").orgao_concedente
            is_cep = co.lista == "cepim"
            co.loc[is_cep, "orgao"] = co.loc[is_cep, "documento"].map(org)
        co[["categoria", "orgao", "esfera", "uf", "fim"]] = co[["categoria", "orgao", "esfera", "uf", "fim"]].fillna("")
        co["multa"] = co.multa.fillna(0.0)
        g = co.groupby(["data", "lista", "mudanca", "documento"], as_index=False).agg(
            nome=("nome", "first"), n=("codigo", "size"), categoria=("categoria", "first"), orgao=("orgao", "first"),
            esfera=("esfera", "first"), uf=("uf", "first"), fim=("fim", "max"), multa=("multa", "sum"))
        emp = _read(data / "site" / "sancoes" / "empresas.csv")
        known = set(emp.cnpj) if len(emp) else set()
        hidden = set(emp.cnpj[emp.pf == "1"]) if len(emp) else set()
        g["pf"] = (_person_firm(g.nome, _people(data, cache)) | g.documento.isin(hidden)).astype(int)
        for r in g.itertuples(index=False):
            def detail(lang, r=r):
                parts = [cnpj(r.documento)]
                if r.mudanca == "entrou":
                    if r.categoria:
                        parts.append(_CAT.get(r.categoria, (r.categoria, r.categoria))[0 if lang == "pt" else 1])
                    if r.orgao:
                        sph = _SPHERE.get(r.esfera.upper(), ("", ""))[0 if lang == "pt" else 1]
                        where = ", ".join(x for x in (sph, r.uf) if x)
                        parts.append(f"{r.orgao} ({where})" if where else r.orgao)
                    if r.lista in ("ceis", "cnep") and r.fim:
                        parts.append(f"até {day(r.fim, lang)}" if lang == "pt" else f"until {day(r.fim, lang)}")
                if r.n > 1:
                    parts.append(f"{r.n} sanções" if lang == "pt" else f"{r.n} sanctions")
                return " · ".join(parts)
            pt, en = _both(detail)
            rows.append(_row(data=r.data, fonte="sancoes", tipo=f"{r.lista}_{r.mudanca}", chave=f"{r.lista}:{r.mudanca}:{r.documento}",
                             titulo="" if r.pf else r.nome, pf=r.pf, detalhe=pt, detalhe_en=en,
                             valor=r.multa if r.multa > 0 else None, n=int(r.n),
                             link=f"../sancoes/?tab=company&cnpj={r.documento}" if r.documento in known else "../sancoes/?tab=changes"))
    return _frame(rows), meta


def _pair(a: int, b: int, lang: str, noun: tuple[str, str]) -> str:
    """'41 empresas entraram e 34 saíram' / '41 companies entered and 34 left'."""
    one, many = noun
    if lang == "pt":
        came = lambda n: "entrou" if n == 1 else "entraram"
        went = lambda n: "saiu" if n == 1 else "saíram"
        if a and b:
            return f"{num(a, lang)} {one if a == 1 else many} {came(a)} e {num(b, lang)} {went(b)}"
        return f"{num(a, lang)} {one if a == 1 else many} {came(a)}" if a else f"{num(b, lang)} {one if b == 1 else many} {went(b)}"
    if a and b:
        return f"{num(a, lang)} {one if a == 1 else many} entered and {num(b, lang)} left"
    return f"{num(a, lang)} {one if a == 1 else many} entered" if a else f"{num(b, lang)} {one if b == 1 else many} left"


def _sum_sancoes(t: pd.DataFrame, lang: str) -> str:
    ppl = t.tipo.str.endswith("_pessoas")
    co = t[~ppl]
    who = co.chave.str.split(":").str[-1]
    a, b = who[co.tipo.str.endswith("_entrou")].nunique(), who[co.tipo.str.endswith("_saiu")].nunique()
    pe = t[ppl]
    pa, pb = int(pe.n[pe.tipo.str.contains("_entrou_")].sum()), int(pe.n[pe.tipo.str.contains("_saiu_")].sum())
    parts = []
    if a or b:
        parts.append(_pair(a, b, lang, ("empresa", "empresas") if lang == "pt" else ("company", "companies")))
    if pa or pb:
        parts.append(_pair(pa, pb, lang, ("pessoa", "pessoas") if lang == "pt" else ("person", "people")))
    order = [*_LISTS, "leniencia"]
    lists = sorted({x.split("_")[0] for x in t.tipo}, key=order.index)
    names = [_LISTS.get(x, "leniência" if lang == "pt" else "leniency") for x in lists]
    head = (" e ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else names[0]) if lang == "pt" else \
        (" and ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else names[0])
    return f"{head}: {'; '.join(parts)}"


# ------------------------------------------------------------------ red flags: against the previous build

# flag: (tab on the red-flags page, short nouns for the day's summary pt/en, the column that dates the case)
FLAGS = {
    "emendas_impedidas": ("barred", ("emenda paga a empresa impedida", "emendas pagas a empresas impedidas"),
                          ("amendment paid to a barred company", "amendments paid to barred companies"), None),
    "contratos_impedidas": ("contracts", ("contrato com empresa impedida", "contratos com empresas impedidas"),
                            ("contract with a barred company", "contracts with barred companies"), "assinatura"),
    "campanha_emendas": ("campaign", ("fornecedor de campanha pago com emendas", "fornecedores de campanha pagos com emendas"),
                         ("campaign supplier paid from amendments", "campaign suppliers paid from amendments"), None),
    "concentracao": ("concentration", ("caso de emendas concentradas", "casos de emendas concentradas"),
                     ("case of concentrated amendments", "cases of concentrated amendments"), None),
    "fornecedor_dominante": ("dominant", ("órgão dominado por um fornecedor", "órgãos dominados por um fornecedor"),
                             ("buyer dominated by one supplier", "buyers dominated by one supplier"), None),
    "leniencia_contratos": ("leniency", ("contrato após leniência", "contratos após leniência"),
                            ("contract after a leniency agreement", "contracts after a leniency agreement"), "assinatura"),
}


def flag_keys(flag: str, t: pd.DataFrame) -> pd.Series:
    """A red flag's identity, kept stable across builds: the case, not its amounts."""
    if flag == "emendas_impedidas":
        return flag + ":" + t.cnpj + "|" + t.pessoa.where(t.pessoa != "", t.autor)
    if flag in ("contratos_impedidas", "leniencia_contratos"):
        return flag + ":" + t.controle
    if flag == "fornecedor_dominante":
        return flag + ":" + t.orgao_cnpj + "|" + t.cnpj
    return flag + ":" + t.cnpj + "|" + t.pessoa


def _party(r) -> str:
    p = "-".join(x for x in (getattr(r, "partido", ""), getattr(r, "uf", "")) if x)
    return f" ({p})" if p else ""


def _flag_detail(flag: str, r, lang: str) -> str:
    pt = lang == "pt"
    obj = (r.objeto[:120] + "…") if len(getattr(r, "objeto", "")) > 120 else getattr(r, "objeto", "")
    if flag == "emendas_impedidas":
        reach = ("alcance certo" if r.barrado == "sim" else "alcance possível") if pt else ("certain reach" if r.barrado == "sim" else "possible reach")
        span = f"{month(r.primeiro, lang, True)}–{month(r.ultimo, lang, True)}" if r.primeiro != r.ultimo else month(r.ultimo, lang, True)
        n = int(float(r.pagamentos or 0))
        pays = (f"{num(n, lang)} {'pagamento' if n == 1 else 'pagamentos'}" if pt else f"{num(n, lang)} {'payment' if n == 1 else 'payments'}")
        who = f"{'emendas de' if pt else 'amendments by'} {r.autor}{_party(r)}"
        return " · ".join([cnpj(r.cnpj), who, f"{pays}, {span}", reach])
    if flag == "contratos_impedidas":
        end = day(r.sancao_fim, lang) or ("sem fim" if pt else "open-ended")
        return " · ".join(x for x in [cnpj(r.cnpj), f"{r.orgao} ({r.uf})",
                                      f"{'assinado em' if pt else 'signed on'} {day(r.assinatura, lang)}",
                                      f"{_CAT.get(r.categoria_sancao, (r.categoria_sancao,) * 2)[0 if pt else 1]}, {day(r.sancao_inicio, lang)}–{end}"
                                      + (f" ({r.orgao_sancionador})" if r.orgao_sancionador else ""),
                                      obj] if x)
    if flag == "campanha_emendas":
        return " · ".join([cnpj(r.cnpj),
                           (f"campanha de {r.deputado}{_party(r)} em {r.eleicao}: {brl(float(r.campanha), lang)}; depois, {brl(float(r.emendas), lang)} das emendas do mesmo parlamentar"
                            if pt else f"{r.deputado}{_party(r)}'s {r.eleicao} campaign paid it {brl(float(r.campanha), lang)}; then {brl(float(r.emendas), lang)} came from the same member's amendments")])
    if flag == "concentracao":
        return " · ".join([cnpj(r.cnpj),
                           (f"{pct(r.share, lang)} do que as emendas de {r.deputado}{_party(r)} pagaram desde 2019" if pt
                            else f"{pct(r.share, lang)} of what {r.deputado}{_party(r)}'s amendments paid since 2019")])
    if flag == "fornecedor_dominante":
        who = withheld(lang) if str(r.pf) == "1" else r.nome
        n = int(float(r.contratos or 0))
        return (f"{who} ({cnpj(r.cnpj)}) ficou com {pct(r.maior_share, lang)} de {num(n, lang)} contratos grandes" if pt
                else f"{who} ({cnpj(r.cnpj)}) took {pct(r.maior_share, lang)} of {num(n, lang)} large contracts")
    if flag == "leniencia_contratos":
        return " · ".join(x for x in [cnpj(r.cnpj), f"{r.orgao} ({r.uf})",
                                      (f"assinado em {day(r.assinatura, lang)}, acordo desde {day(r.acordo, lang)}" if pt
                                       else f"signed on {day(r.assinatura, lang)}, agreement since {day(r.acordo, lang)}"), obj] if x)
    return ""


def log_alertas(data: Path, out: Path, cache: dict) -> tuple[pd.DataFrame, dict] | None:
    src = data / "site" / "alertas"
    if not (src / "resumo.json").exists():
        return None   # the red-flags page was never built here: nothing to compare
    stamp = _snapshot(data) or date.today().isoformat()
    cur = {}
    for flag in FLAGS:
        t = _read(src / f"{flag}.csv")
        if len(t):
            t = t.assign(k=flag_keys(flag, t)).drop_duplicates("k")
        cur[flag] = t
    keys = [k for t in cur.values() if len(t) for k in t.k]
    path = out / "estado" / "alertas.json"
    state = _state(path)
    since = state["desde"] if state else stamp
    new = set(keys) - set(state["chaves"]) if state else set()
    _write_state(path, since, keys)

    rows = []
    cut = _cut(stamp)
    for flag, (tab, *_x, when) in FLAGS.items():
        t = cur[flag]
        if not len(t):
            continue
        t = t[t.k.isin(new)]
        link = f"../alertas/?tab={tab}"
        if when:
            old = t[t[when] <= cut]
            t = t[t[when] > cut]
            if len(old):
                rows.append(_row(data=stamp, fonte="alertas", tipo=f"{flag}_historico", chave=f"{flag}_historico", n=len(old),
                                 valor=float(_money(old.valor).sum()), link=link,
                                 detalhe=f"assinados até {day(cut, 'pt')}; quase todos vêm do histórico do PNCP, lido do mais novo para o mais antigo",
                                 detalhe_en=f"signed by {day(cut, 'en')}; nearly all come from the PNCP history, read newest first"))
        if not len(t):
            continue
        # The red-flags page withholds individual firms' names; the rule is applied again here, so a log never
        # carries a name an earlier build of that page let through.
        named = t.nome.fillna("")
        flagged = pd.to_numeric(t["pf"], errors="coerce").fillna(0).astype(bool) if "pf" in t else pd.Series(False, index=t.index)
        t = t.assign(pf=(flagged | _person_firm(named, _people(data, cache))).astype(int))
        for r in t.itertuples(index=False):
            pf = int(r.pf) if flag != "fornecedor_dominante" else 0   # the flag names the buyer; its supplier is in the detail
            title = r.orgao if flag == "fornecedor_dominante" else ("" if pf else r.nome)
            pt, en = _both(lambda lang, r=r: _flag_detail(flag, r, lang))
            value = r.emendas if flag == "campanha_emendas" else r.valor
            rows.append(_row(data=stamp, fonte="alertas", tipo=flag, chave=r.k.split(":", 1)[1], titulo=title, pf=pf,
                             detalhe=pt, detalhe_en=en, valor=float(value or 0), link=link))
    old = _read(out / "alertas.csv")
    t = pd.concat([_frame(old), _frame(rows)], ignore_index=True)
    # Two builds on the same day (the daily job, then a rebuild after a code change) add up their older contracts.
    hist = t.tipo.str.endswith("_historico")
    if hist.any():
        h = t[hist].groupby(["data", "fonte", "tipo", "chave"], as_index=False).agg(
            {"titulo": "first", "pf": "first", "detalhe": "first", "detalhe_en": "first", "valor": "sum", "n": "sum", "link": "first"})
        t = pd.concat([t[~hist], h], ignore_index=True)
    t = _frame(t)
    if len(t):
        t = t[t.data > _cut(max(t.data.max(), stamp))]
    return _frame(t), {"desde": since, "ate": stamp}


def _sum_alertas(t: pd.DataFrame, lang: str) -> str:
    pt = lang == "pt"
    parts = []
    for flag, (_tab, nouns_pt, nouns_en, _w) in FLAGS.items():
        n = int((t.tipo == flag).sum())
        if n:
            one, many = nouns_pt if pt else nouns_en
            parts.append(f"{num(n, lang)} {one if n == 1 else many}")
    old = t[t.tipo.str.endswith("_historico")]
    k = int(old.n.sum()) if len(old) else 0
    join = (lambda xs: " e ".join([", ".join(xs[:-1]), xs[-1]]) if len(xs) > 1 else xs[0]) if pt else \
        (lambda xs: " and ".join([", ".join(xs[:-1]), xs[-1]]) if len(xs) > 1 else xs[0])
    head = ("Novos na lista: " if pt else "Newly listed: ") + join(parts) if parts else ""
    tail = ((f"{num(k, lang)} {'contrato antigo achado' if k == 1 else 'contratos antigos achados'} no histórico do PNCP" if pt
             else f"{num(k, lang)} older {'contract' if k == 1 else 'contracts'} found in the PNCP history") if k else "")
    if head and tail:
        return f"{head}; {'e' if pt else 'and'} {tail}"
    return head or (tail[0].upper() + tail[1:] if tail else "")


# ------------------------------------------------------------------ amendment payments: against the previous build

_EMENDA_TIPO = {"individual": ("individual", "individual"), "especial": ("Pix", "“Pix”"), "bancada": ("de bancada", "state bench"),
                "comissao": ("de comissão", "committee"), "relator": ("de relator", "rapporteur")}


def log_emendas(data: Path, out: Path, cache: dict) -> tuple[pd.DataFrame, dict] | None:
    src = data / "emendas"
    files = sorted((src / "pagamentos").glob("*.csv"))
    if not files:
        return None
    stamp = _modified(src / "sources.json", "EmendasParlamentares") or date.today().isoformat()
    parts = []
    for p in files:
        t = pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["codigo_emenda", "ano_mes", "favorecido", "uf", "municipio", "valor"])
        parts.append(t[t.favorecido != ""].assign(valor=lambda x: _money(x.valor)))
    pay = pd.concat(parts, ignore_index=True)
    g = pay.groupby(["codigo_emenda", "ano_mes", "favorecido"], as_index=False).agg(valor=("valor", "sum"), uf=("uf", "first"), municipio=("municipio", "first"))
    big = g[g.valor >= PAY_MIN].copy()
    big["k"] = big.codigo_emenda + "|" + big.ano_mes + "|" + big.favorecido
    path = out / "estado" / "emendas.json"
    state = _state(path)
    since = state["desde"] if state else stamp
    new = big[~big.k.isin(set(state["chaves"]))] if state else big.iloc[:0]
    _write_state(path, since, big.k)

    rows = []
    if len(new):
        from .alertas import deputies, display, members
        em = pd.concat([pd.read_csv(p, dtype=str, keep_default_na=False, usecols=["codigo", "autor_codigo", "autor", "tipo"])
                        for p in sorted((src / "emendas").glob("*.csv"))], ignore_index=True).drop_duplicates("codigo").set_index("codigo")
        x = _read(data / "ref" / "politicians.csv")
        who = x[x.fonte == "emendas"].drop_duplicates("id").set_index("id").pessoa if len(x) else pd.Series(dtype=str)
        dep = members(data, deputies(data))
        fav = _read(src / "favorecidos.csv")
        fav = fav.drop_duplicates("favorecido").set_index("favorecido") if len(fav) else pd.DataFrame(columns=["nome", "natureza_juridica"])
        from .alertas import INDIVIDUAL
        new = new.assign(nome=new.favorecido.map(fav.nome).fillna(""), natureza=new.favorecido.map(fav.natureza_juridica).fillna(""))
        new["pf"] = (_person_firm(new.nome, _people(data, cache)) | new.natureza.isin(INDIVIDUAL) | new.favorecido.str.contains(r"\*")).astype(int)
        for r in new.itertuples(index=False):
            a = em.loc[r.codigo_emenda] if r.codigo_emenda in em.index else None
            pessoa = who.get(a.autor_codigo) if a is not None else None
            d = dep.loc[pessoa] if pessoa is not None and pessoa in dep.index else None
            author = (d.nome + (f" ({d.partido}-{d.uf})" if d.partido else "")) if d is not None else (display(a.autor) if a is not None else "")
            kind = _EMENDA_TIPO.get(a.tipo, ("", "")) if a is not None else ("", "")

            def detail(lang, r=r, author=author, kind=kind):
                pt = lang == "pt"
                k = kind[0 if pt else 1]
                if author and kind[0] in ("individual", "Pix"):
                    what = f"emenda {k} de {author}" if pt else f"{k} amendment by {author}"
                elif author:   # a bench, a committee or the rapporteur-general: the name says which
                    what = f"emenda de {author}" if pt else f"amendment by {author}"
                else:
                    what = "sem código de emenda" if pt else "no amendment code"
                where = f"{r.municipio} ({r.uf})" if r.municipio else r.uf
                return " · ".join(x for x in [cnpj(r.favorecido), what, f"{'pago em' if pt else 'paid in'} {month(r.ano_mes, lang, True)}", where] if x)
            pt_, en_ = _both(detail)
            link = (f"../deputados/?tab=profile&leg={d.leg}&dep={d.deputado_id}" if d is not None and d.casa == "camara" and d.deputado_id and d.leg in (56, 57)
                    else "../emendas/?tab=authors")
            rows.append(_row(data=stamp, fonte="emendas", tipo="pagamento", chave=r.k, titulo="" if r.pf else r.nome, pf=r.pf,
                             detalhe=pt_, detalhe_en=en_, valor=r.valor, link=link))
    old = _read(out / "emendas.csv")
    t = _frame(pd.concat([old, _frame(rows)], ignore_index=True) if len(old) else rows)
    if len(t):
        t = t[t.data > _cut(max(t.data.max(), stamp))]
    return _frame(t), {"desde": since, "ate": stamp}


def _sum_emendas(t: pd.DataFrame, lang: str) -> str:
    n, v = len(t), float(t.valor.sum())
    if lang == "pt":
        return f"{num(n, lang)} {'pagamento' if n == 1 else 'pagamentos'} de emenda de R$ 5 mi ou mais, {'somando ' if n > 1 else ''}{brl(v, lang)}"
    return f"{num(n, lang)} amendment {'payment' if n == 1 else 'payments'} of R$ 5 M or more, {brl(v, lang)}{' in all' if n > 1 else ''}"


# ------------------------------------------------------------------ large contracts: by the day they were published

_ESFERA = {"F": ("federal", "federal"), "E": ("estadual", "state"), "M": ("municipal", "municipal"), "D": ("distrital", "Federal District"), "N": ("", "")}


def log_pncp(data: Path, cache: dict) -> tuple[pd.DataFrame, dict]:
    from .pncp import contracts, town_revenue
    src = data / "pncp"
    dias = _read(src / "dias.csv")
    c = contracts(src, town_revenue(data))
    if c.empty:
        return _frame([]), {"desde": "", "ate": "", "cobertura": {"dias": WINDOW, "dias_lidos": 0}}
    anchor = dias.dia.max() if len(dias) else c.publicacao.max()
    cut = _cut(anchor)
    w = c[(c.publicacao > cut) & (c.publicacao <= anchor)]
    big = w[(w.suspeito != 2) & (w.v >= CONTRACT_MIN)].copy()
    out_typos = w[(w.suspeito == 2) & (_money(w.valor_global) >= CONTRACT_MIN)]
    read = sorted(dias.dia[(dias.dia > cut) & (dias.dia <= anchor)]) if len(dias) else []
    every = [(date.fromisoformat(cut) + timedelta(days=i)).isoformat() for i in range(1, WINDOW + 1)]
    meta = {"desde": every[0], "ate": anchor,
            "cobertura": {"dias": WINDOW, "dias_lidos": len(read), "faltam": [d for d in every if d not in set(read)][:31],
                          "implausiveis": len(out_typos)}}
    if big.empty:
        return _frame([]), meta
    big["pf"] = ((big.fornecedor_tipo == "PF") | big.fornecedor.str.contains(r"\*") | _person_firm(big.fornecedor_nome, _people(data, cache))).astype(int)
    rows = []
    for r in big.itertuples(index=False):
        def detail(lang, r=r):
            pt = lang == "pt"
            sph = _ESFERA.get(r.esfera, ("", ""))[0 if pt else 1]
            where = ", ".join(x for x in (sph, r.uf) if x)
            obj = (r.objeto[:140] + "…") if len(r.objeto) > 140 else r.objeto
            parts = [cnpj(r.fornecedor) if not r.pf else "", f"{r.orgao} ({where})" if where else r.orgao, obj]
            if r.assinatura:
                parts.append(f"{'assinado em' if pt else 'signed on'} {day(r.assinatura, lang)}")
            if r.suspeito == 1:
                parts.append(f"contado pelo valor inicial; publicado com {brl(float(r.valor_global), lang)}" if pt
                             else f"counted at its initial value; published at {brl(float(r.valor_global), lang)}")
            return " · ".join(x for x in parts if x)
        pt_, en_ = _both(detail)
        rows.append(_row(data=r.publicacao, fonte="pncp", tipo="contrato", chave=r.controle, titulo="" if r.pf else r.fornecedor_nome,
                         pf=int(r.pf), detalhe=pt_, detalhe_en=en_, valor=float(r.v), link="../pncp/?tab=large"))
    return _frame(rows), meta


def _sum_pncp(t: pd.DataFrame, lang: str) -> str:
    n, v = len(t), float(t.valor.sum())
    if lang == "pt":
        return f"{num(n, lang)} {'contrato' if n == 1 else 'contratos'} de R$ 100 mi ou mais {'publicado' if n == 1 else 'publicados'}, {'somando ' if n > 1 else ''}{brl(v, lang)}"
    return f"{num(n, lang)} {'contract' if n == 1 else 'contracts'} of R$ 100 M or more published, {brl(v, lang)}{' in all' if n > 1 else ''}"


# ------------------------------------------------------------------ roll-call months

def log_votes(data: Path, chamber: str) -> tuple[pd.DataFrame, dict]:
    months = []
    for p in sorted((data / chamber / "votacoes").glob("*.csv")):
        t = _read(p, usecols=["data"])
        t = t[t.data != ""] if len(t) else t
        if len(t):
            months.append((p.stem, t.data.min(), t.data.max(), len(t)))
    if not months:
        return _frame([]), {"desde": "", "ate": ""}
    anchor = max(m[2] for m in months)
    cut = _cut(anchor)
    rows = []
    for m, first, last, n in months:
        if first <= cut:
            continue
        pt = f"{month(m, 'pt')}: {num(n, 'pt')} {'votação nominal' if n == 1 else 'votações nominais'}" + (f", de {day(first, 'pt')} a {day(last, 'pt')}" if first != last else f", em {day(first, 'pt')}")
        en = f"{month(m, 'en')}: {num(n, 'en')} roll {'call' if n == 1 else 'calls'}" + (f", {day(first, 'en')} to {day(last, 'en')}" if first != last else f", on {day(first, 'en')}")
        rows.append(_row(data=first, fonte=chamber, tipo="mes", chave=m, detalhe=pt, detalhe_en=en, n=n, link=f"../{chamber}/?month={m}"))
    return _frame(rows), {"desde": months[0][1], "ate": anchor}


def _sum_votes(t: pd.DataFrame, lang: str) -> str:
    return "; ".join(f"{'Votações nominais de' if lang == 'pt' else 'Roll calls of'} {month(m, lang)}: {num(int(n), lang)}" for m, n in zip(t.chave, t.n))


SUMMARY = {"sancoes": _sum_sancoes, "alertas": _sum_alertas, "emendas": _sum_emendas, "pncp": _sum_pncp, "camara": _sum_votes, "senado": _sum_votes}


# ------------------------------------------------------------------ write

def write_log(out: Path, fonte: str, t: pd.DataFrame, meta: dict) -> pd.DataFrame:
    t = _frame(t)
    csv(t, out / f"{fonte}.csv")
    days = []
    for d, g in t.groupby("data", sort=True):
        days.append({"data": d, "n": int(len(g)), "resumo": SUMMARY[fonte](g, "pt"), "resumo_en": SUMMARY[fonte](g, "en")})
    info = FONTES[fonte]
    write_json({"fonte": fonte, "nome": {"pt": info["pt"], "en": info["en"]}, "pagina": f"../{info['pagina']}", "janela": WINDOW,
                "regra": dict(zip(("pt", "en"), REGRAS[fonte])), "nota": dict(zip(("pt", "en"), NOTAS[fonte])) if fonte in NOTAS else None,
                "tipos": {k: {"pt": v[0], "en": v[1]} for k, v in TIPOS[fonte].items()},
                **meta, "dias": days[::-1]}, out / f"{fonte}.json", digits=4)
    return t


def update(data: Path, fontes=None) -> dict:
    """Update the change logs of the given sources (default: all). Feeds are separate: see feeds()."""
    out = data / "site" / "mudancas"
    cache: dict = {}
    report = {}
    for f in fontes or FONTES:
        if f == "sancoes":
            r = log_sancoes(data, cache)
        elif f == "alertas":
            r = log_alertas(data, out, cache)
        elif f == "emendas":
            r = log_emendas(data, out, cache)
        elif f == "pncp":
            r = log_pncp(data, cache)
        elif f in ("camara", "senado"):
            r = log_votes(data, f)
        else:
            raise ValueError(f"unknown source {f!r}; known: {list(FONTES)}")
        if r is None:
            report[f] = "skipped (nothing to compare)"
            continue
        report[f] = len(write_log(out, f, *r))
    return report


# ------------------------------------------------------------------ Atom

def _abs(link: str, lang: str) -> str:
    url = SITE + link[3:] if link.startswith("../") else link
    if lang == "en":
        url += ("&" if "?" in url else "?") + "lang=en"
    return url


def entries(data: Path, fonte: str) -> list[dict]:
    """One feed entry per day of a source's log, newest first, with its HTML in both languages."""
    out = data / "site" / "mudancas"
    if not (out / f"{fonte}.json").exists():
        return []
    meta = json.loads((out / f"{fonte}.json").read_text())
    t = _read(out / f"{fonte}.csv")
    tipos = meta.get("tipos", {})
    res = []
    for d in meta.get("dias", []):
        g = t[t.data == d["data"]] if len(t) else t
        e = {"fonte": fonte, "data": d["data"], "n": d["n"]}
        for lang in ("pt", "en"):
            name = meta["nome"][lang]
            summary = d["resumo"] if lang == "pt" else d["resumo_en"]
            page = SITE + f"mudancas/?fonte={fonte}&dia={d['data']}" + ("&lang=en" if lang == "en" else "")
            items = []
            for r in g.head(FEED_ITEMS).itertuples(index=False):
                label = tipos.get(r.tipo, {}).get(lang, r.tipo)
                title = r.titulo or (withheld(lang) if r.pf == "1" else "")
                detail = r.detalhe if lang == "pt" else (r.detalhe_en or r.detalhe)
                bits = [f"<b>{escape(label)}</b>"]
                if title:
                    bits.append(f'<a href="{escape(_abs(r.link, lang))}">{escape(title)}</a>')
                elif r.n and r.tipo.endswith("_pessoas"):
                    bits.append(escape(num(int(r.n), lang)))
                text = ": ".join(bits)
                if detail:
                    text += f" — {escape(detail)}"
                if r.valor:
                    text += f" — {escape(brl(float(r.valor), lang))}"
                if not title:
                    text += f' (<a href="{escape(_abs(r.link, lang))}">{"ver" if lang == "pt" else "see"}</a>)'
                items.append(f"<li>{text}</li>")
            more = len(g) - FEED_ITEMS
            html = f"<p>{escape(summary)}</p><ul>{''.join(items)}</ul>"
            if more > 0:
                html += (f'<p><a href="{escape(page)}">' + (f"Mais {num(more, lang)} na página" if lang == "pt" else f"{num(more, lang)} more on the page") + "</a></p>")
            nota = (meta.get("nota") or {}).get(lang)
            if nota:
                html += f"<p><i>{escape(nota)}</i></p>"
            e[lang] = {"title": f"{name}, {day(d['data'], lang)}: {summary}", "summary": summary, "html": html, "link": page}
        res.append(e)
    return res


def atom(es: list[dict], lang: str, key: str, title: str, subtitle: str, alternate: str) -> str:
    sub = "" if lang == "pt" else "en/"
    updated = max((e["data"] for e in es), default="2026-11-01") + "T12:00:00Z"
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           f'<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="{"pt-BR" if lang == "pt" else "en"}">',
           f"  <title>{escape(title)}</title>",
           f"  <subtitle>{escape(subtitle)}</subtitle>",
           f"  <id>{TAG}/feeds/{sub}{key}</id>",
           f'  <link rel="self" type="application/atom+xml" href="{SITE}feeds/{sub}{key}.xml"/>',
           f'  <link rel="alternate" type="text/html" href="{escape(alternate)}"/>',
           f"  <updated>{updated}</updated>",
           "  <author><name>political-eye</name><uri>https://github.com/mbottoni/political-eye</uri></author>"]
    for e in es:
        x = e[lang]
        when = e["data"] + "T12:00:00Z"
        out += ["  <entry>",
                f"    <id>{TAG}/{'' if lang == 'pt' else 'en/'}{e['fonte']}/{e['data']}</id>",
                f"    <title>{escape(x['title'])}</title>",
                f'    <link rel="alternate" type="text/html" href="{escape(x["link"])}"/>',
                f"    <published>{when}</published>",
                f"    <updated>{when}</updated>",
                f'    <category term="{e["fonte"]}" label="{escape(FONTES[e["fonte"]][lang])}"/>',
                f"    <summary>{escape(x['summary'])}</summary>",
                f'    <content type="html">{escape(x["html"])}</content>',
                "  </entry>"]
    out.append("</feed>")
    return "\n".join(out) + "\n"


def feeds(data: Path, docs: Path | None = None) -> dict:
    """Rebuild every Atom feed from the change logs as they are: cheap, and run again after a rebase so the feed of
    every source never misses what another job pushed meanwhile."""
    docs = docs or data.parent / "docs"
    every = []
    report = {}
    for f in FONTES:
        es = entries(data, f)
        every += es
        for lang in ("pt", "en"):
            name = FONTES[f][lang]
            path = docs / "feeds" / ("" if lang == "pt" else "en") / f"{f}.xml"
            path.parent.mkdir(parents=True, exist_ok=True)
            title = f"political-eye: {name}" + (" — o que mudou" if lang == "pt" else " — what changed")
            sub = REGRAS[f][0 if lang == "pt" else 1]
            path.write_text(atom(es[:FEED_ENTRIES], lang, f, title, sub, _abs(f"../mudancas/?fonte={f}", lang)))
        report[f] = len(es)
    order = list(FONTES)
    every.sort(key=lambda e: (e["data"], -order.index(e["fonte"])), reverse=True)
    for lang in ("pt", "en"):
        path = docs / "feeds" / ("" if lang == "pt" else "en") / f"{COMBINED[lang]}.xml"
        title = "political-eye: o que mudou" if lang == "pt" else "political-eye: what changed"
        sub = ("O que mudou nos dados abertos que o political-eye acompanha: sanções, sinais de alerta, emendas, contratos e votações."
               if lang == "pt" else "What changed in the open data political-eye follows: sanctions, red flags, amendments, contracts and roll calls.")
        path.write_text(atom(every[:FEED_ALL], lang, COMBINED[lang], title, sub, _abs("../mudancas/", lang)))
    return report


def build(data: Path) -> dict:
    """Every source's log, then the feeds (``site build mudancas``)."""
    r = update(data)
    feeds(data)
    return r
