"""Public contracts from the PNCP: ``data/pncp/``.

    data/pncp/contratos/YYYY-MM.csv     contracts worth VALOR_MIN or more, by month of publication
    data/pncp/sancionados/YYYY-MM.csv   contracts of any value signed with a company the sanctions
                                        lists (data/sancoes/) had barred on the signing date, by month
                                        of publication
    data/pncp/resumo_dia.csv            every contract published, counted and summed by day,
                                        government sphere and kind of supplier
    data/pncp/dias.csv                  the days read so far

The whole stream is over 2 million contracts a year, too much to commit, so
only these are. A daily run reads yesterday's publications and updates, then
fills the history, newest day first, until its time budget runs out.
``methodology/pncp.md`` explains every rule.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
import time
from pathlib import Path

import pandas as pd

from ..io import write_csv
from ..sancoes.build import CPF, mask_cpf, mask_text
from . import fetch

FIRST_DAY = "2021-09-01"
VALOR_MIN = 1_000_000
OBJETO_MAX = 200
MAX_FAILURES = 5     # consecutive failed days before a run stops (and saves)
CONTRATOS = ["controle", "compra", "publicacao", "assinatura", "vigencia_inicio", "vigencia_fim", "orgao_cnpj", "orgao",
             "esfera", "poder", "uf", "municipio_ibge", "tipo", "categoria", "fornecedor_tipo", "fornecedor",
             "fornecedor_nome", "objeto", "valor_inicial", "valor_global", "retificacao"]
SANCIONADOS = CONTRATOS + ["lista", "codigo_sancao", "categoria_sancao", "sancao_inicio", "sancao_fim", "abrangencia",
                           "orgao_sancionador", "esfera_sancionador", "uf_sancionador", "cobre"]
SANC_DIR = "sancionados"
LEGACY_SANC = "contratos_sancionados.csv"   # one file until Nov 2026, when it outgrew GitHub's 100 MB limit
# Sanctions that bar a company from contracting; fines and the like do not.
BARS = re.compile(r"^(Impedimento|Declaração de Inidoneidade|Suspensão$)")
ESFERA = {"FEDERAL": "F", "ESTADUAL": "E", "MUNICIPAL": "M"}
RESUMO = ["dia", "esfera", "fornecedor_tipo", "contratos", "valor_global"]
DIAS = ["dia", "publicados", "atualizados"]


def _log(msg: str) -> None:
    print(f"[pncp] {msg}", file=sys.stderr, flush=True)


def _s(x) -> str:
    return "" if x is None else str(x).strip()


def _money(x) -> str:
    try:
        return f"{float(x):.2f}"
    except (TypeError, ValueError):
        return ""


def tidy(r: dict) -> dict:
    """One contract as a row; a person's CPF is masked wherever it appears."""
    org, uni = r.get("orgaoEntidade") or {}, r.get("unidadeOrgao") or {}
    kind = _s(r.get("tipoPessoa"))
    ni = re.sub(r"\D", "", _s(r.get("niFornecedor")))
    if kind == "PF" or len(ni) == 11:
        ni = mask_cpf(ni)
    objeto = " ".join(_s(r.get("objetoContrato")).split())
    if len(objeto) > OBJETO_MAX:
        objeto = objeto[:OBJETO_MAX - 1].rstrip() + "…"
    text = pd.Series([_s(r.get("nomeRazaoSocialFornecedor")), objeto])
    nome, objeto = mask_text(text, CPF).tolist()
    return {
        "controle": _s(r.get("numeroControlePNCP")), "compra": _s(r.get("numeroControlePncpCompra")),
        "publicacao": _s(r.get("dataPublicacaoPncp"))[:10], "assinatura": _s(r.get("dataAssinatura"))[:10],
        "vigencia_inicio": _s(r.get("dataVigenciaInicio"))[:10], "vigencia_fim": _s(r.get("dataVigenciaFim"))[:10],
        "orgao_cnpj": _s(org.get("cnpj")), "orgao": _s(org.get("razaoSocial")), "esfera": _s(org.get("esferaId")),
        "poder": _s(org.get("poderId")), "uf": _s(uni.get("ufSigla")), "municipio_ibge": _s(uni.get("codigoIbge")),
        "tipo": _s((r.get("tipoContrato") or {}).get("nome")), "categoria": _s((r.get("categoriaProcesso") or {}).get("nome")),
        "fornecedor_tipo": kind, "fornecedor": ni, "fornecedor_nome": nome, "objeto": objeto,
        "valor_inicial": _money(r.get("valorInicial")), "valor_global": _money(r.get("valorGlobal")),
        "retificacao": _s(r.get("numeroRetificacao")),
    }


def sanctions(sancoes: Path) -> pd.DataFrame:
    """Companies (14-digit CNPJ) barred from contracting by CEIS or CNEP, with each sanction's dates and scope."""
    rows = []
    for lista in ("ceis", "cnep"):
        p = sancoes / f"{lista}.csv"
        if not p.exists():
            continue
        t = pd.read_csv(p, dtype=str, keep_default_na=False)
        t = t[t.cpf_ou_cnpj_do_sancionado.str.fullmatch(r"\d{14}") & t.categoria_da_sancao.str.match(BARS)]
        rows.append(pd.DataFrame({
            "fornecedor": t.cpf_ou_cnpj_do_sancionado, "lista": lista, "codigo_sancao": t.codigo_da_sancao,
            "categoria_sancao": t.categoria_da_sancao, "sancao_inicio": t.data_inicio_sancao,
            "sancao_fim": t.data_final_sancao, "abrangencia": t.abragencia_da_sancao,
            "orgao_sancionador": t.orgao_sancionador, "esfera_sancionador": t.esfera_orgao_sancionador,
            "uf_sancionador": t.uf_orgao_sancionador}))
    cols = ["fornecedor", "lista", "codigo_sancao", "categoria_sancao", "sancao_inicio", "sancao_fim", "abrangencia",
            "orgao_sancionador", "esfera_sancionador", "uf_sancionador"]
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=cols)


_GENERIC = {"MUNICIPIO", "MUNICIPAL", "PREFEITURA", "CAMARA", "FUNDO", "SECRETARIA", "ESTADO", "ESTADUAL", "GOVERNO",
            "FEDERAL", "NACIONAL", "MINISTERIO", "INSTITUTO", "UNIVERSIDADE", "SAUDE", "EDUCACAO", "DESENVOLVIMENTO",
            "ADMINISTRACAO", "SERVICOS", "EMPRESA", "BRASILEIRA", "BRASIL", "PUBLICA", "PUBLICO", "SOCIAL", "GERAL",
            "DIRETA", "INDIRETA", "AUTARQUIA", "FUNDACAO", "ASSISTENCIA", "TRIBUNAL", "JUSTICA", "UNIDADES", "VINCULO"}


def _tokens(name: str) -> set[str]:
    from ..ref.politicians import norm
    return {t for t in norm(name).split() if len(t) >= 4 and t not in _GENERIC}


def covers(m: pd.DataFrame) -> pd.Series:
    """Whether a sanction's scope reaches the contracting body: ``sim``, ``nao`` or ``possivel``.

    - for every sphere (``Todas as Esferas``): every contract, ``sim``;
    - another sphere, or for a state or municipal sanction another state: ``nao``;
    - for its whole sphere (``Em todos os Poderes da Esfera``): every federal
      body, or every body of that state, ``sim``; for a municipality, only
      bodies of that municipality;
    - only the sanctioning body, or a municipality's sphere: bodies whose names
      share a distinctive word with the sanctioner's (the town's name, say) are
      ``possivel``, the others ``nao``. Names are written too differently to say
      ``sim``.
    """
    everywhere = m.abrangencia.str.startswith("Todas as Esferas")
    sphere = m.abrangencia.str.startswith("Em todos os Poderes da Esfera")
    esf = m.esfera_sancionador.map(ESFERA)
    other = esf.notna() & (esf != m.esfera)
    other |= esf.isin(["E", "M"]) & (m.uf_sancionador != "") & (m.uf_sancionador != m.uf)
    shared = pd.Series([bool(_tokens(a) & _tokens(b)) for a, b in zip(m.orgao, m.orgao_sancionador)], index=m.index)
    narrow = m.abrangencia.str.startswith("No órgão") | (sphere & (esf == "M")) | m.abrangencia.str.startswith("Na Esfera")
    out = pd.Series("possivel", index=m.index)
    out = out.mask(narrow & ~shared, "nao")
    out = out.mask(sphere & esf.isin(["F", "E"]), "sim")
    return out.mask(other, "nao").mask(everywhere, "sim")


def match_sanctions(contracts: pd.DataFrame, sanc: pd.DataFrame) -> pd.DataFrame:
    """Contracts whose supplier was barred, by a sanction then in force, on the day it was signed."""
    m = contracts.merge(sanc, on="fornecedor")
    on = (m.sancao_inicio != "") & (m.sancao_inicio <= m.assinatura) & (
        (m.sancao_fim == "") | (m.assinatura <= m.sancao_fim))
    m = m[on & (m.assinatura != "")].copy()
    m["cobre"] = covers(m)
    return m[SANCIONADOS]


def read_sanctioned(data: Path) -> pd.DataFrame:
    """Every contract signed with a barred company (``data/pncp/sancionados/``, and the legacy single file if present)."""
    files = sorted((data / SANC_DIR).glob("*.csv")) + [p for p in [data / LEGACY_SANC] if p.exists()]
    parts = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in files]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=SANCIONADOS)


def write_by_month(t: pd.DataFrame, folder: Path, sort: list[str]) -> None:
    """One file per month of publication; months no longer present are removed."""
    keep = set()
    for month, part in t.assign(_m=t.publicacao.str[:7]).groupby("_m"):
        p = folder / f"{month}.csv"
        write_csv(part.drop(columns="_m").sort_values(sort), p)
        keep.add(p)
    for p in folder.glob("*.csv"):
        if p not in keep:
            p.unlink()


class Store:
    """The committed tables, loaded once per run and written after each batch."""

    def __init__(self, data: Path):
        self.data = data
        self.big = self._read_dir(data / "contratos", CONTRATOS)
        self.sanc = read_sanctioned(data)[SANCIONADOS]
        self.resumo = self._read(data / "resumo_dia.csv", RESUMO)
        self.dias = self._read(data / "dias.csv", DIAS)
        self.new_big, self.new_sanc, self.new_resumo = [], [], []

    @staticmethod
    def _read(p: Path, cols: list[str]) -> pd.DataFrame:
        return pd.read_csv(p, dtype=str, keep_default_na=False)[cols] if p.exists() else pd.DataFrame(columns=cols)

    def _read_dir(self, folder: Path, cols: list[str]) -> pd.DataFrame:
        parts = [self._read(p, cols) for p in sorted(folder.glob("*.csv"))]
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)

    def add(self, records: list[dict], sanc: pd.DataFrame, day: str | None, *, updated: bool) -> int:
        rows = pd.DataFrame([tidy(r) for r in records], columns=CONTRATOS)
        if not updated and day is not None:
            v = pd.to_numeric(rows.valor_global, errors="coerce").fillna(0)
            res = rows.assign(_v=(v * 100).round().astype("int64")).groupby(
                ["esfera", "fornecedor_tipo"], as_index=False).agg(contratos=("controle", "size"), _v=("_v", "sum"))
            res["dia"] = day
            res["valor_global"] = res._v.map(lambda c: f"{c // 100}.{c % 100:02d}")
            self.new_resumo.append(res[RESUMO])
        big = rows[pd.to_numeric(rows.valor_global, errors="coerce").fillna(0) >= VALOR_MIN]
        self.new_big.append(big)
        if updated:   # a contract updated below the threshold leaves the table
            small = set(rows.controle) - set(big.controle)
            self.big = self.big[~self.big.controle.isin(small)]
        self.new_sanc.append(match_sanctions(rows, sanc))
        return len(rows)

    def mark(self, day: str, publicados: int | None = None, atualizados: int | None = None) -> None:
        d = self.dias.set_index("dia")
        row = d.loc[day].to_dict() if day in d.index else {"publicados": "", "atualizados": ""}
        if publicados is not None:
            row["publicados"] = str(publicados)
        if atualizados is not None:
            row["atualizados"] = str(atualizados)
        d.loc[day] = row
        self.dias = d.reset_index()[DIAS]

    def save(self) -> None:
        big = pd.concat([self.big, *self.new_big], ignore_index=True).drop_duplicates("controle", keep="last")
        sanc = pd.concat([self.sanc, *self.new_sanc], ignore_index=True)
        sanc = sanc.drop_duplicates(["controle", "lista", "codigo_sancao"], keep="last")
        res = pd.concat([self.resumo, *self.new_resumo], ignore_index=True).drop_duplicates(
            ["dia", "esfera", "fornecedor_tipo"], keep="last")
        self.big, self.sanc, self.resumo = big, sanc, res
        self.new_big, self.new_sanc, self.new_resumo = [], [], []
        write_by_month(big, self.data / "contratos", ["publicacao", "controle"])
        write_by_month(sanc, self.data / SANC_DIR, ["assinatura", "controle", "lista", "codigo_sancao"])
        (self.data / LEGACY_SANC).unlink(missing_ok=True)
        write_csv(res.sort_values(["dia", "esfera", "fornecedor_tipo"]), self.data / "resumo_dia.csv")
        write_csv(self.dias.sort_values("dia"), self.data / "dias.csv")


def update(data: Path, *, hours: float = 5.0, today: dt.date | None = None, days: int | None = None) -> dict:
    """Read yesterday (published and updated), then the history, newest first, until the budget runs out."""
    today = today or dt.datetime.now(dt.UTC).date()
    deadline = time.monotonic() + hours * 3600
    sanc = sanctions(data.parent / "sancoes")
    st = Store(data)
    yesterday = (today - dt.timedelta(days=1)).isoformat()
    done = dict(zip(st.dias.dia, st.dias.publicados))
    updated = dict(zip(st.dias.dia, st.dias.atualizados))
    report = {"dias": 0, "contratos": 0, "atualizados": 0}

    if updated.get(yesterday, "") == "":
        try:
            recs = fetch.contratos(yesterday, updated=True)
            st.add(recs, sanc, None, updated=True)
            st.mark(yesterday, atualizados=len(recs))
            report["atualizados"] = len(recs)
        except RuntimeError as e:   # tried again next run
            _log(f"{yesterday} updates: {e}")

    all_days, d = [], dt.date.fromisoformat(yesterday)
    while d.isoformat() >= FIRST_DAY:
        all_days.append(d.isoformat())
        d -= dt.timedelta(days=1)
    queue = [x for x in all_days if done.get(x, "") == ""]
    if days is not None:
        queue = queue[:days]
    _log(f"{len(queue)} days to read; {len(all_days) - len(queue)} already read")
    failed = 0
    report["stopped"] = ""
    for i, day in enumerate(queue, 1):
        if time.monotonic() > deadline:
            break
        try:
            recs = fetch.contratos(day)
        except RuntimeError as e:   # left unread, so the next run tries again
            failed += 1
            _log(f"{day}: {e}")
            if failed >= MAX_FAILURES:
                report["stopped"] = f"{MAX_FAILURES} failures in a row; last: {e}"
                break
            continue
        failed = 0
        report["contratos"] += st.add(recs, sanc, day, updated=False)
        st.mark(day, publicados=len(recs))
        report["dias"] += 1
        if i % 10 == 0:
            st.save()
            _log(f"{i}/{len(queue)} days read (through {day})")
    st.save()
    report["left"] = len(queue) - report["dias"]
    report["sancionados"] = len(st.sanc)
    _log(" ".join(f"{k}={v}" for k, v in report.items()))
    return report
