"""Turn one year of raw API responses into tidy monthly tables under ``data/senado/``.

Output per month ``YYYY-MM`` (CSV, sorted, ``\\n`` line endings, so a rebuild
that changes nothing produces no git diff):

    data/senado/votacoes/YYYY-MM.csv   Plenário roll calls (one row per vote)
    data/senado/votes/YYYY-MM.csv      each senator's recorded vote, party and UF then
    data/senado/orientations/YYYY-MM.csv how party and government leaders oriented each roll call
    data/senado/authorship/YYYY-MM.csv senators' signatures on matérias presented
    data/senado/senators/YYYY-MM.csv   everyone in either table, with party and UF

``methodology/senado.md`` explains every rule.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

from ..io import write_csv
from .fetch import legislaturas, senators_listed

VOTACOES = ["id", "data", "sessao", "sequencial", "tipo_sessao", "processo_id", "materia", "sigla", "secreta", "resultado",
            "votos_sim", "votos_nao", "votos_abstencao", "descricao"]
VOTES = ["votacao_id", "senador_id", "voto", "partido", "uf"]
ORIENTATIONS = ["votacao_id", "bancada", "orientacao"]
AUTHORSHIP = ["processo_id", "sigla_tipo", "materia", "data_apresentacao", "senador_id", "partido", "lider"]
SENATORS = ["senador_id", "nome", "partido", "uf", "n_votes", "n_authored"]
NO_PARTY = {"", "Sem registro"}
NOT_SENATE = {"Revisora", "Substitutivo"}   # a Câmara bill under review, or the Câmara's substitute
# The authors' text spells some parties differently from the votes, whose labels we keep.
PARTY_IN_TEXT = {"PODEMOS": "PODE"}



def party_in_text(autoria: str, nome: str) -> tuple[str, bool]:
    """A senator's party in a matéria's authors text, and whether they signed as a leader.

    Authors are written ``Senador Flávio Bolsonaro (PL/RJ)``, ``Senadora
    Teresa Leitão (PT/PE)`` or, for party and bloc leaders, ``Líder do PSD
    Omar Aziz (PSD/AM)``: the name, then ``(party/UF)``. ``("", False)`` when
    the text leaves the senator out.
    """
    pat = re.compile(rf"(?:^|\s){re.escape(nome)}\s*\(([^/()]+)/[A-Z]{{2}}\)")
    for seg in autoria.split(","):
        m = pat.search(seg)
        if m:
            party = m[1].strip()
            return PARTY_IN_TEXT.get(party, party), seg.strip().startswith("Líder")
    return "", False


def _log(msg: str) -> None:
    print(f"[build] {msg}", file=sys.stderr)


def _s(x) -> str:
    return "" if x is None else str(x).strip()


def load_votes(raw: Path, year: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Roll calls of ``year`` and every senator's recorded vote in them."""
    recs = json.loads((raw / f"votacao-{year}.json").read_text())
    report = {"votacoes_misdated": 0, "votacoes_without_votes": 0, "votacoes_off_year": 0, "votes_duplicate": 0}
    vt, vv = [], []
    seen = set()
    for r in recs:
        day = _s(r.get("dataSessao"))[:10]
        if day[:4] != str(year):
            report["votacoes_off_year"] += 1
            continue
        # Votes from 1998-1999 are filed under 2015-2017 session dates (a
        # session-code collision); their legislative record keeps the real date.
        informed = _s((r.get("informeLegislativo") or {}).get("data"))[:4]
        if informed and informed != day[:4]:
            report["votacoes_misdated"] += 1
            continue
        votos = r.get("votos") or []
        if not votos:
            report["votacoes_without_votes"] += 1
            continue
        vid = str(r["codigoSessaoVotacao"])
        secret = _s(r.get("votacaoSecreta")) == "S"
        rows = {}
        for x in votos:
            sid = _s(x.get("codigoParlamentar"))
            if not sid:
                continue
            if sid in rows:
                report["votes_duplicate"] += 1
            rows[sid] = (vid, sid, _s(x.get("siglaVotoParlamentar")), _s(x.get("siglaPartidoParlamentar")),
                         _s(x.get("siglaUFParlamentar")), _s(x.get("nomeParlamentar")))
        if vid in seen:
            report["votes_duplicate"] += len(rows)
            continue
        seen.add(vid)
        cast = [v[2] for v in rows.values()]
        total = (lambda k, w: _s(r.get(k)) if secret else str(cast.count(w)))
        vt.append({
            "id": vid, "data": day, "sessao": _s(r.get("codigoSessao")), "sequencial": _s(r.get("sequencialVotacao")),
            "tipo_sessao": _s(r.get("siglaTipoSessao")),
            "processo_id": _s(r.get("idProcesso")), "materia": _s(r.get("identificacao")), "sigla": _s(r.get("sigla")),
            "secreta": int(secret), "resultado": _s(r.get("resultadoVotacao")),
            "votos_sim": total("totalVotosSim", "Sim"), "votos_nao": total("totalVotosNao", "Não"),
            "votos_abstencao": total("totalVotosAbstencao", "Abstenção"),
            "descricao": " ".join(_s(r.get("descricaoVotacao")).split()),
        })
        vv.extend(rows.values())
    vt = pd.DataFrame(vt, columns=VOTACOES)
    vv = pd.DataFrame(vv, columns=[*VOTES, "nome"])
    return vt, vv, report


def load_orientations(raw: Path, year: int, vt: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Leaders' orientations for the year's roll calls, joined on ``sequencialVotacao``.

    The orientation endpoint names roll calls by the electronic panel's
    sequence number, which ``/votacao`` also carries (from 2019; empty before).
    A leader who changed orientation keeps the last one given.
    """
    path = raw / f"orientacao-{year}.json"
    if not path.exists():
        return pd.DataFrame(columns=ORIENTATIONS), {}
    by_seq = dict(zip(vt.sequencial, vt.id))
    by_seq.pop("", None)
    rows, report = [], {"orientacoes_votacoes": 0, "orientacoes_sem_votacao": 0}
    for x in json.loads(path.read_text()).get("votacoes") or []:
        given = x.get("orientacoesLideranca") or []
        if not given:
            continue
        report["orientacoes_votacoes"] += 1
        vid = by_seq.get(_s(x.get("sequencialVotacao")))
        if vid is None:
            report["orientacoes_sem_votacao"] += 1
            continue
        for o in sorted(given, key=lambda o: _s(o.get("dataHora"))):
            rows.append((vid, _s(o.get("partido")), _s(o.get("voto"))))
    o = pd.DataFrame(rows, columns=ORIENTATIONS).drop_duplicates(["votacao_id", "bancada"], keep="last")
    return o, report


def load_authorship(raw: Path, year: int) -> tuple[pd.DataFrame, dict]:
    """Senators' signatures on matérias presented in ``year``, from each senator's list."""
    people = senators_listed(raw, legislaturas(year))
    report = {"authorship_off_year": 0, "authorship_not_senate": 0, "authorship_party_unparsed": 0}
    rows = []
    for p in people:
        path = raw / "autoria" / str(year) / f"{p['codigo']}.json"
        for it in json.loads(path.read_text()) or []:
            day = _s(it.get("dataApresentacao"))[:10]
            if day[:4] != str(year):
                report["authorship_off_year"] += 1
                continue
            # Congresso items (vetoes, credited to the Senate's president;
            # joint committees) and Câmara bills under review (credited to
            # senators who wrote them as deputies) are not Senate authorship.
            if _s(it.get("casaIdentificadora")) != "SF" or _s(it.get("objetivo")) in NOT_SENATE:
                report["authorship_not_senate"] += 1
                continue
            materia = _s(it.get("identificacao"))
            # The party at the time is only in the authors' text.
            party, lider = party_in_text(_s(it.get("autoria")), p["nome"])
            if not party:
                report["authorship_party_unparsed"] += 1
            rows.append((_s(it.get("id")), materia.split(" ")[0], materia, day, p["codigo"], party, int(lider)))
    au = pd.DataFrame(rows, columns=AUTHORSHIP).drop_duplicates(["processo_id", "senador_id"])
    report["authorship_rows"] = len(au)
    return au, report


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(-1).astype("int64")


def _senators(vv: pd.DataFrame, au: pd.DataFrame, listed: pd.DataFrame) -> pd.DataFrame:
    """One row per senator seen this month; party and UF from the latest vote, else the latest signature."""
    from_votes = vv.groupby("senador_id").agg(nome=("nome", "last"), partido=("partido", "last"), uf=("uf", "last"),
                                              n_votes=("votacao_id", "nunique"))
    from_auth = au.sort_values("data_apresentacao").groupby("senador_id").agg(
        partido=("partido", "last"), n_authored=("processo_id", "nunique"))
    ids = from_votes.index.union(from_auth.index)
    lst = listed.set_index("codigo").reindex(ids)
    df = pd.DataFrame(index=ids)

    def pick(*cols):
        out = pd.Series("", index=ids)
        for c in reversed(cols):
            c = c.reindex(ids).fillna("")
            out = c.where(~c.isin(NO_PARTY), out)
        return out

    df["nome"] = pick(from_votes.nome, lst.nome)
    df["partido"] = pick(from_votes.partido, from_auth.partido)
    df["uf"] = pick(from_votes.uf, lst.uf)
    df["n_votes"] = from_votes.n_votes.reindex(ids).fillna(0).astype("int64")
    df["n_authored"] = from_auth.n_authored.reindex(ids).fillna(0).astype("int64")
    df.index.name = "senador_id"
    df = df.reset_index()
    return df.assign(_k=_num(df.senador_id)).sort_values("_k").drop(columns="_k")[SENATORS]


def build_year(year: int, raw: Path, data_dir: Path) -> dict:
    """Rebuild every month of ``year``. Returns counts of what was dropped."""
    vt, vv, r1 = load_votes(raw, year)
    au, r2 = load_authorship(raw, year)
    vo, r3 = load_orientations(raw, year, vt)
    listed = pd.DataFrame(senators_listed(raw, legislaturas(year)), columns=["codigo", "nome", "uf"])
    # A few senators are missing from their own legislature's list (Wilder Morais, 2016-2018, is only in the
    # 57th's), so a UF still missing comes from any other cached list.
    cached = sorted(int(f.stem.split("-")[1]) for f in raw.glob("senadores-*.json"))
    anywhere = pd.DataFrame(senators_listed(raw, cached), columns=["codigo", "nome", "uf"])
    listed = listed.merge(anywhere[["codigo", "uf"]].rename(columns={"uf": "uf_any"}), on="codigo", how="outer")
    listed["uf"] = listed.uf.where(listed.uf.fillna("") != "", listed.uf_any).fillna("")
    listed = listed.drop(columns="uf_any")
    report = {"year": year, **r1, **r3, **r2}

    vt = vt.assign(month=vt.data.str[:7], _s=_num(vt.sessao), _i=_num(vt.id)).sort_values(["data", "_s", "_i"])
    order = {v: i for i, v in enumerate(vt.id)}
    vv = vv.assign(month=vv.votacao_id.map(dict(zip(vt.id, vt.month))), _o=vv.votacao_id.map(order),
                   _k=_num(vv.senador_id)).sort_values(["_o", "_k"])
    au = au.assign(month=au.data_apresentacao.str[:7], _p=_num(au.processo_id), _k=_num(au.senador_id)).sort_values(
        ["data_apresentacao", "_p", "_k"])
    months = sorted(set(vt.month) | set(au.month))

    vo = vo.assign(_o=vo.votacao_id.map(order)).sort_values(["_o", "bancada"])
    stale = {p for sub in ("votacoes", "votes", "orientations", "authorship", "senators")
             for p in (data_dir / sub).glob(f"{year}-*.csv")}
    for month in months:
        mvv, mau = vv[vv.month == month], au[au.month == month]
        out = {
            "votacoes": vt[vt.month == month][VOTACOES],
            "votes": mvv[VOTES],
            "orientations": vo[vo.votacao_id.isin(set(mvv.votacao_id))][ORIENTATIONS],
            "authorship": mau[AUTHORSHIP],
            "senators": _senators(mvv, mau, listed),
        }
        for sub, df in out.items():
            path = data_dir / sub / f"{month}.csv"
            write_csv(df, path)
            stale.discard(path)
    for p in stale:
        p.unlink()
    report.update(months=len(months), votacoes=len(vt), votes=len(vv))
    _log(" ".join(f"{k}={v}" for k, v in report.items()))
    return report
