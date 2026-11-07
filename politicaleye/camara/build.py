"""Turn one year of raw bulk files into tidy monthly tables under ``data/``.

Output per month ``YYYY-MM`` (all CSV, sorted, ``\\n`` line endings, so a
rebuild that changes nothing produces no git diff):

    data/camara/votacoes/YYYY-MM.csv     Plenário roll-call votes (one row per vote)
    data/camara/votes/YYYY-MM.csv        how each deputy voted in each of them
    data/camara/authorship/YYYY-MM.csv   deputy signatures on proposições presented
    data/camara/deputies/YYYY-MM.csv     everyone in either table, with party and UF

Each month is built from that year's files only. Rows whose date falls in a
different year than the file they came from are dropped and counted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from ..io import read_raw as _read
from ..io import write_csv as _write

PLENARIO = "PLEN"


def _log(msg: str) -> None:
    print(f"[build] {msg}", file=sys.stderr)


def _as_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(-1).astype("int64")


def load_votes(raw: Path, year: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Plenário votações that have per-deputy votes, and those votes."""
    vt = _read(raw / f"votacoes-{year}.csv", [
        "id", "data", "dataHoraRegistro", "siglaOrgao", "aprovacao",
        "votosSim", "votosNao", "votosOutros", "descricao",
    ])
    vv = _read(raw / f"votacoesVotos-{year}.csv", [
        "idVotacao", "dataHoraVoto", "voto", "deputado_id", "deputado_nome",
        "deputado_siglaPartido", "deputado_siglaUf",
    ])
    report = {}
    vt = vt[vt.siglaOrgao == PLENARIO].drop_duplicates("id", keep="last")
    vv = vv[vv.idVotacao.isin(vt.id) & (vv.deputado_id != "")]
    vt = vt[vt.id.isin(vv.idVotacao)]
    off_year = vt.data.str[:4] != str(year)
    report["votacoes_off_year"] = int(off_year.sum())
    vt = vt[~off_year]
    vv = vv[vv.idVotacao.isin(vt.id)]
    n = len(vv)
    vv = vv.sort_values("dataHoraVoto").drop_duplicates(["idVotacao", "deputado_id"], keep="last")
    report["votes_duplicate"] = n - len(vv)
    return vt, vv, report


def load_authorship(raw: Path, year: int) -> tuple[pd.DataFrame, dict]:
    """Deputy signatures on proposições presented in ``year``."""
    pr = _read(raw / f"proposicoes-{year}.csv", ["id", "siglaTipo", "dataApresentacao"])
    au = _read(raw / f"proposicoesAutores-{year}.csv", [
        "idProposicao", "idDeputadoAutor", "nomeAutor", "siglaPartidoAutor",
        "siglaUFAutor", "ordemAssinatura", "proponente",
    ])
    report = {}
    au = au[au.idDeputadoAutor != ""]
    au = au.merge(pr.drop_duplicates("id"), left_on="idProposicao", right_on="id", how="left")
    missing = au.dataApresentacao.isna() | (au.dataApresentacao == "")
    report["authorship_no_proposicao"] = int(missing.sum())
    au = au[~missing]
    off_year = au.dataApresentacao.str[:4] != str(year)
    report["authorship_off_year"] = int(off_year.sum())
    au = au[~off_year]
    n = len(au)
    au = au.drop_duplicates(["idProposicao", "idDeputadoAutor"], keep="first")
    report["authorship_duplicate"] = n - len(au)
    return au, report


def _deputies(vv: pd.DataFrame, au: pd.DataFrame) -> pd.DataFrame:
    """One row per deputy seen this month; party/UF from their latest appearance."""
    from_votes = vv.sort_values("dataHoraVoto").groupby("deputado_id").agg(
        nome=("deputado_nome", "last"),
        partido=("deputado_siglaPartido", "last"),
        uf=("deputado_siglaUf", "last"),
        n_votes=("idVotacao", "nunique"),
    )
    from_auth = au.sort_values("dataApresentacao").groupby("idDeputadoAutor").agg(
        nome=("nomeAutor", "last"),
        partido=("siglaPartidoAutor", "last"),
        uf=("siglaUFAutor", "last"),
        n_authored=("idProposicao", "nunique"),
    )
    from_auth.index.name = "deputado_id"
    ids = from_votes.index.union(from_auth.index)
    df = pd.DataFrame(index=ids)
    for col in ["nome", "partido", "uf"]:
        # Prefer what the vote record says: it is stamped at vote time.
        df[col] = from_votes[col].reindex(ids).where(
            from_votes[col].reindex(ids).fillna("") != "", from_auth[col].reindex(ids)
        ).fillna("")
    df["n_votes"] = from_votes.n_votes.reindex(ids).fillna(0).astype("int64")
    df["n_authored"] = from_auth.n_authored.reindex(ids).fillna(0).astype("int64")
    df.index.name = "deputado_id"
    df = df.reset_index()
    return df.assign(_k=_as_int(df.deputado_id)).sort_values("_k").drop(columns="_k")


def build_year(year: int, raw: Path, data_dir: Path) -> dict:
    """Rebuild every month of ``year``. Returns counts of what was dropped."""
    vt, vv, r1 = load_votes(raw, year)
    au, r2 = load_authorship(raw, year)
    report = {"year": year, **r1, **r2}

    vt = vt.assign(month=vt.data.str[:7])
    vv = vv.merge(vt[["id", "month", "dataHoraRegistro"]], left_on="idVotacao", right_on="id")
    au = au.assign(month=au.dataApresentacao.str[:7], data_apresentacao=au.dataApresentacao.str[:10])
    months = sorted(set(vt.month) | set(au.month))

    stale = {
        p for sub in ("votacoes", "votes", "authorship", "deputies")
        for p in (data_dir / sub).glob(f"{year}-*.csv")
    }
    for month in months:
        mvt = vt[vt.month == month].sort_values(["dataHoraRegistro", "id"])
        mvv = vv[vv.month == month]
        mau = au[au.month == month]

        votacoes = mvt.rename(columns={
            "dataHoraRegistro": "hora_registro", "votosSim": "votos_sim",
            "votosNao": "votos_nao", "votosOutros": "votos_outros",
        })[["id", "data", "hora_registro", "aprovacao", "votos_sim", "votos_nao", "votos_outros", "descricao"]]

        order = {vid: i for i, vid in enumerate(mvt.id)}
        votes = (
            mvv.assign(_o=mvv.idVotacao.map(order), _k=_as_int(mvv.deputado_id))
            .sort_values(["_o", "_k"])
            .rename(columns={"idVotacao": "votacao_id"})[["votacao_id", "deputado_id", "voto"]]
        )

        authorship = (
            mau.assign(_p=_as_int(mau.idProposicao), _s=_as_int(mau.ordemAssinatura), _k=_as_int(mau.idDeputadoAutor))
            .sort_values(["data_apresentacao", "_p", "_s", "_k"])
            .rename(columns={
                "idProposicao": "proposicao_id", "siglaTipo": "sigla_tipo",
                "idDeputadoAutor": "deputado_id", "ordemAssinatura": "ordem_assinatura",
            })[["proposicao_id", "sigla_tipo", "data_apresentacao", "deputado_id", "ordem_assinatura", "proponente"]]
        )

        out = {
            "votacoes": votacoes,
            "votes": votes,
            "authorship": authorship,
            "deputies": _deputies(mvv, mau),
        }
        for sub, df in out.items():
            path = data_dir / sub / f"{month}.csv"
            _write(df, path)
            stale.discard(path)

    for p in stale:
        p.unlink()
    report["months"] = len(months)
    report["votacoes"] = int(len(vt))
    report["votes"] = int(len(vv))
    report["authorship_rows"] = int(len(au))
    _log(" ".join(f"{k}={v}" for k, v in report.items()))
    return report
