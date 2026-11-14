"""One politician across sources: ``data/ref/politicians.csv``.

Each source names people its own way: the Câmara by deputy id, the Senado by
``CodigoParlamentar``, TSE by candidacy (``sq_candidato``, one per election),
the Portal da Transparência by an amendment-author code. This table maps
every one of those ids to one ``pessoa``, with the method that linked it, so
a deputy's votes, amendments and campaign money can be read together.

No CPF is used or committed: the Câmara no longer publishes deputies' CPFs and
TSE stopped publishing candidates'. Matching is on names, birth dates, states
and terms; see ``methodology/ref.md``.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

from ..fetch import download, get_bytes
from ..io import read_raw, write_csv

DEPUTADOS = "https://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv"
SENADORES = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/{leg}.json?exercicio=S"
TSE = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{year}.zip"
FIRST_LEG = 54            # 2011-2015: authors of the 2014 amendments
ELECTIONS = (2018, 2022, 2026)
COLS = ["pessoa", "fonte", "id", "nome", "metodo"]


def _log(msg: str) -> None:
    print(f"[ref] {msg}", file=sys.stderr)


def norm(s: str) -> str:
    """``"Acácio da Silva Favacho Neto"`` -> ``"ACACIO DA SILVA FAVACHO NETO"``."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return " ".join(re.sub(r"[^A-Z ]+", " ", s).split())


def leg_years(leg: int) -> range:
    """Calendar years a legislature touches (it runs 1 February to 31 January)."""
    start = 1795 + 4 * leg
    return range(start, start + 5)


# ------------------------------------------------------------------ inputs

def fetch(raw: Path, legs: list[int]) -> None:
    download(DEPUTADOS, raw / "deputados.csv")
    for leg in legs:
        body = get_bytes(SENADORES.format(leg=leg), headers={"Accept": "application/json"}, check=json.loads)
        (raw / f"senadores-{leg}.json").write_bytes(body)
    for y in ELECTIONS:
        download(TSE.format(year=y), raw / f"consulta_cand_{y}.zip", timeout=300)


def deputies(raw: Path) -> pd.DataFrame:
    d = read_raw(raw / "deputados.csv", ["uri", "nome", "idLegislaturaInicial", "idLegislaturaFinal", "nomeCivil",
                                          "dataNascimento", "ufNascimento"])
    d["id"] = d.uri.str.rsplit("/", n=1).str[-1]
    d["leg_fim"] = pd.to_numeric(d.idLegislaturaFinal, errors="coerce")
    d["leg_ini"] = pd.to_numeric(d.idLegislaturaInicial, errors="coerce")
    d = d[d.leg_fim >= FIRST_LEG].copy()
    d["civil"] = d.nomeCivil.map(norm)
    d["parl"] = d.nome.map(norm)
    d["nasc"] = d.dataNascimento.str[:10]
    return d[["id", "nome", "civil", "parl", "nasc", "leg_ini", "leg_fim"]]


def senators(raw: Path, legs: list[int]) -> pd.DataFrame:
    rows = []
    for leg in legs:
        p = raw / f"senadores-{leg}.json"
        if not p.exists():
            continue
        ps = json.loads(p.read_text())["ListaParlamentarLegislatura"]["Parlamentares"]["Parlamentar"]
        for x in ps if isinstance(ps, list) else [ps]:
            i = x["IdentificacaoParlamentar"]
            rows.append((i["CodigoParlamentar"], i["NomeParlamentar"].strip(), norm(i.get("NomeCompletoParlamentar", "")),
                         norm(i["NomeParlamentar"]), (i.get("UfParlamentar") or "").strip(), leg))
    s = pd.DataFrame(rows, columns=["id", "nome", "civil", "parl", "uf", "leg"])
    return s.groupby(["id", "nome", "civil", "parl", "uf"], as_index=False).leg.agg(lambda v: sorted(set(v)))


def candidates(raw: Path) -> pd.DataFrame:
    out = []
    for y in ELECTIONS:
        p = raw / f"consulta_cand_{y}.zip"
        if not p.exists():
            continue
        with zipfile.ZipFile(p) as z:
            name = next(n for n in z.namelist() if n.endswith("_BRASIL.csv"))
            c = pd.read_csv(z.open(name), sep=";", encoding="latin1", dtype=str, keep_default_na=False,
                            usecols=["SQ_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "DS_CARGO", "SG_UF",
                                     "DT_NASCIMENTO"])
        c = c.drop_duplicates("SQ_CANDIDATO")
        d = c.DT_NASCIMENTO.str.strip()
        out.append(pd.DataFrame({
            "id": c.SQ_CANDIDATO, "nome": c.NM_URNA_CANDIDATO.str.strip(), "civil": c.NM_CANDIDATO.map(norm),
            "cargo": c.DS_CARGO.str.upper().str.strip(), "uf": c.SG_UF, "ano": y,
            "nasc": d.str[6:10] + "-" + d.str[3:5] + "-" + d.str[0:2],
        }))
    t = pd.concat(out, ignore_index=True)
    t.loc[~t.nasc.str.fullmatch(r"\d{4}-\d{2}-\d{2}"), "nasc"] = ""
    return t


def authors(emendas: Path) -> pd.DataFrame:
    a = pd.read_csv(emendas / "por_autor.csv", dtype=str, keep_default_na=False)
    a = a[a.autor_codigo != ""]
    return a.groupby(["autor_codigo", "autor"], as_index=False).ano.agg(lambda v: sorted({int(x) for x in v}))


# ---------------------------------------------------------------- matching

def _unique(left: pd.DataFrame, right: pd.DataFrame, on: list[str]) -> pd.DataFrame:
    """Pairs where the key is unique on both sides and every key part is filled."""
    lk = left[(left[on] != "").all(axis=1)]
    rk = right[(right[on] != "").all(axis=1)]
    lk = lk[~lk.duplicated(on, keep=False)]
    rk = rk[~rk.duplicated(on, keep=False)]
    return lk.merge(rk, on=on, suffixes=("_l", "_r"))


PARTICLES = {"DA", "DE", "DO", "DAS", "DOS", "E"}


def _share_a_word(a: str, b: str) -> bool:
    """Whether two normalised names have a word in common besides the first (particles left out)."""
    words = lambda s: {w for w in s.split()[1:] if len(w) > 2 and w not in PARTICLES}   # noqa: E731
    return bool(words(a) & words(b))


def build(raw: Path, data: Path, overrides: Path | None = None) -> dict:
    legs = list(range(FIRST_LEG, 59))
    dep, sen, cand = deputies(raw), senators(raw, legs), candidates(raw)
    links: list[tuple[str, str, str, str, str]] = []   # (fonte_a, id_a, fonte_b, id_b, metodo)
    report = {"deputados": len(dep), "senadores": len(sen), "candidaturas": len(cand)}

    # Câmara <-> TSE (federal deputy candidacies), one election at a time, since
    # the same person runs again: civil name + birth date, then civil name + state.
    uf = _deputy_uf(data)   # deputies' state is not in the Câmara's file; take it from our vote records
    dep_uf = dep.assign(uf=dep.id.map(uf).fillna(""))
    for y in ELECTIONS:
        fed = cand[(cand.cargo == "DEPUTADO FEDERAL") & (cand.ano == y)]
        m1 = _unique(dep, fed, ["civil", "nasc"])
        links += [("camara", a, "tse", b, "nome_civil+nascimento") for a, b in zip(m1.id_l, m1.id_r)]
        m2 = _unique(dep_uf, fed[~fed.id.isin(set(m1.id_r))], ["civil", "uf"])
        links += [("camara", a, "tse", b, "nome_civil+uf") for a, b in zip(m2.id_l, m2.id_r)]
        # Spelling differs between the two registries (SOUZA / SOUSA, an added
        # JUNIOR or married name): birth date, first name and state.
        done = set(m1.id_r) | set(m2.id_r)
        linked = set(m1.id_l) | set(m2.id_l)
        m3 = _unique(dep_uf[~dep_uf.id.isin(linked)].assign(first=lambda t: t.civil.str.split().str[0].fillna("")),
                     fed[~fed.id.isin(done)].assign(first=lambda t: t.civil.str.split().str[0].fillna("")),
                     ["nasc", "first", "uf"])
        links += [("camara", a, "tse", b, "nascimento+primeiro_nome+uf") for a, b in zip(m3.id_l, m3.id_r)]
        linked |= set(m3.id_l)

        # Senado <-> TSE (senator and suplente candidacies): full name + state.
        st = cand[cand.cargo.isin(["SENADOR", "1º SUPLENTE", "2º SUPLENTE"]) & (cand.ano == y)]
        m3 = _unique(sen, st, ["civil", "uf"])
        links += [("senado", a, "tse", b, "nome_civil+uf") for a, b in zip(m3.id_l, m3.id_r)]

        # Câmara <-> TSE, every other office (senator and their substitutes, governor, state deputy,
        # president and the running mates): deputies who ran for something else, or switched to it
        # after registering for the Câmara. Only keys with the birth date, so a namesake (a son with the
        # same civil name) is never taken for the deputy. The looser key (birth date, first name, state)
        # also needs another word of the name in common: two Franciscos born the same day in the same
        # state are two people.
        first = lambda t: t.civil.str.split().str[0].fillna("")   # noqa: E731
        other = cand[(cand.cargo != "DEPUTADO FEDERAL") & (cand.ano == y)].assign(first=first)
        m5 = _unique(dep_uf, other, ["civil", "nasc"])
        links += [("camara", a, "tse", b, "outro_cargo:nome_civil+nascimento") for a, b in zip(m5.id_l, m5.id_r)]
        m6 = _unique(dep_uf[~dep_uf.id.isin(set(m5.id_l))].assign(first=first), other[~other.id.isin(set(m5.id_r))],
                     ["nasc", "first", "uf"])
        m6 = m6[pd.Series([_share_a_word(a, b) for a, b in zip(m6.civil_l, m6.civil_r)], index=m6.index, dtype=bool)]
        links += [("camara", a, "tse", b, "outro_cargo:nascimento+primeiro_nome+uf") for a, b in zip(m6.id_l, m6.id_r)]

    # Senado <-> Câmara (senators who were deputies): full civil name.
    m4 = _unique(sen, dep, ["civil"])
    links += [("senado", a, "camara", b, "nome_civil") for a, b in zip(m4.id_l, m4.id_r)]

    # Amendment authors <-> legislators in office in an amendment's year or the year before.
    au = authors(data.parent / "emendas")
    in_office = []
    for r in dep.itertuples():
        yrs = {y for leg in range(int(r.leg_ini), int(r.leg_fim) + 1) for y in leg_years(leg)}
        in_office.append(("camara", r.id, r.parl, yrs))
    for r in sen.itertuples():
        in_office.append(("senado", r.id, r.parl, {y for leg in r.leg for y in leg_years(leg)}))
    by_name: dict[str, list] = {}
    for f, i, n, yrs in in_office:
        by_name.setdefault(n, []).append((f, i, yrs))
    # A name can hit one person's Câmara and Senado ids (deputy, then senator):
    # that is still one person, so hits are compared as people.
    person = _components(links)
    matched = 0
    for r in au.itertuples():
        want = {y for a in r.ano for y in (a - 1, a)}
        hits = sorted({(f, i) for f, i, yrs in by_name.get(norm(r.autor), []) if yrs & want})
        if hits and len({person(h) for h in hits}) == 1:
            f, i = hits[0]
            links.append(("emendas", r.autor_codigo, f, i, "nome_parlamentar+mandato"))
            matched += 1
    report.update(autores=len(au), autores_ligados=matched)

    names = {("camara", r.id): r.nome for r in dep.itertuples()}
    names |= {("senado", r.id): r.nome for r in sen.itertuples()}
    names |= {("tse", r.id): r.nome for r in cand.itertuples()}
    names |= {("emendas", r.autor_codigo): r.autor for r in au.itertuples()}
    nodes = [("camara", i) for i in dep.id] + [("senado", i) for i in sen.id]
    out = _people(links, names, overrides, nodes)
    write_csv(out, data / "politicians.csv")
    report.update({f"ids_{k}": int(v) for k, v in out.fonte.value_counts().items()},
                  pessoas=int(out.pessoa.nunique()))
    report["metodos"] = out.metodo.value_counts().to_dict()
    _log(" ".join(f"{k}={v}" for k, v in report.items()))
    return report


def _deputy_uf(data: Path) -> pd.Series:
    files = sorted((data.parent / "camara" / "deputies").glob("*.csv"))
    if not files:
        return pd.Series(dtype=str)
    d = pd.concat(pd.read_csv(f, dtype=str, keep_default_na=False, usecols=["deputado_id", "uf"]) for f in files)
    return d[d.uf != ""].groupby("deputado_id").uf.last()


PRIORITY = {"camara": 0, "senado": 1, "emendas": 2, "tse": 3}


def _components(links):
    """``node -> representative`` for the people the links form so far."""
    parent: dict[tuple, tuple] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for fa, a, fb, b, _ in links:
        parent[find((fa, a))] = find((fb, b))
    return find


def _people(links, names, overrides: Path | None, nodes=()) -> pd.DataFrame:
    """Connected components of the links; a person is named by their Câmara id, else Senado, else author code."""
    parent: dict[tuple, tuple] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for n in nodes:
        find(n)
    method: dict[tuple, str] = {}   # how each id was first linked
    for fa, a, fb, b, how in links:
        x, y = (fa, a), (fb, b)
        parent[find(x)] = find(y)
        method.setdefault(x, how)
        method.setdefault(y, how)
    groups: dict[tuple, list] = {}
    for node in parent:
        groups.setdefault(find(node), []).append(node)
    rows = []
    for members in groups.values():
        head = min(members, key=lambda n: (PRIORITY[n[0]], int(n[1]) if n[1].isdigit() else 0, n[1]))
        for f, i in members:
            rows.append((f"{head[0]}:{head[1]}", f, i, names.get((f, i), ""), "" if (f, i) == head else method.get((f, i), "")))
    out = pd.DataFrame(rows, columns=COLS)
    if overrides is not None and overrides.exists():   # manual links: move an id, or add one
        ov = pd.read_csv(overrides, dtype=str, keep_default_na=False)
        for r in ov.itertuples():
            hit = (out.fonte == r.fonte) & (out.id == r.id)
            if hit.any():
                out.loc[hit, ["pessoa", "metodo"]] = [r.pessoa, "manual"]
            else:
                out.loc[len(out)] = [r.pessoa, r.fonte, r.id, names.get((r.fonte, r.id), ""), "manual"]
    out["_f"] = out.fonte.map(PRIORITY)
    out["_i"] = pd.to_numeric(out.id, errors="coerce")
    return out.sort_values(["pessoa", "_f", "_i", "id"]).drop(columns=["_f", "_i"])[COLS]
