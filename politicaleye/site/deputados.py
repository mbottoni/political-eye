"""Summaries for the deputies page: ``data/site/deputados/``.

    deputados_<leg>.csv   one row per deputy of the legislature: the cross-source view
                          (data/views/deputados_<leg>.csv) plus their mean position on the first voting
                          dimension (pc1) and network centrality over the legislature's months, the share
                          of their co-voting ties that cross party lines, the share of their amendment money
                          paid in their own state and nationally, the large donors of their campaign, and
                          the amendment money paid to companies while under a barring sanction (every
                          budget since 2015, from data/site/sancoes/autores.csv)
    vizinhos_<leg>.csv    each deputy's closest and furthest co-voters over the legislature: contested roll
                          calls both voted on, and the share where they voted the same way
    emendas_<leg>.csv     person, budget year and type: amendments, committed, paid
    destinos_<leg>.csv    person, recipient's state and municipality (IBGE code; empty when the payment
                          names no town that matches IBGE's list): paid so far on the amendments they authored
                          for the legislature's budgets, from the payments table
    doadores_<leg>.csv    person: the donors of R$50,000 or more to their campaign (CPF masked), amount
    atividade_<leg>.csv   deputy and month: roll calls held, votes they cast, proposals they presented as
                          first signer (all, and bills) and co-signed
    propostas_<leg>.csv   deputy and kind of proposal (bills, rapporteur opinions, amendments, oversight,
                          requests, other): as first signer and as co-signer, over the legislature
    coautores_<leg>.csv   each deputy's most frequent co-signers (proposals with at most 50 signers)
    partidos_<leg>.csv    each deputy's parties over the legislature, from the month they first and last
                          appear under each

Attendance (``presenca``) is the votes a deputy cast over the roll calls held in the months they appear
in the Câmara's tables (voting or signing). A month they missed entirely does not count against them.

Mayors' parties (data/ref/prefeitos.csv): ``prefeito_mesmo_partido`` is the share of a deputy's
amendment money paid to a town in a year when that town's mayor was of the deputy's party (their party
that month); ``prefeito_base`` is what the share would be by chance: the share of their own state's
towns that party ran, averaged over the same payments. Parties are compared under today's name only
from the year they merged (DEM and PSL count as UNIÃO from 2022, not before).

See methodology/views.md.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..camara import graphs as g
from ..views.deputados import budget_years, election_of
from .common import csv
from .emendas import UF, town_codes

LEGS = (56, 57)
# Kinds of proposal, from the Câmara's type codes (siglaTipo). Signing order 1 is the first signer.
KINDS = {"projetos": {"PL", "PLP", "PEC", "PDL", "PRC"},
         "relatorias": {"PRL", "PRLP", "PRLE", "PPP", "PEP", "PSS", "SBT", "SBR", "EMR", "CVO", "VTS", "RDF"},
         "emendas": {"EMC", "EMP", "ESB", "EMS", "EMA", "EML", "EMO", "SOR", "SLD"},
         "fiscalizacao": {"RIC", "PFC", "SIT"},
         "requerimentos": {"REQ", "RPD", "RPDR", "DTQ", "INC"}}
KIND_OF = {t: k for k, ts in KINDS.items() for t in ts}
COAUTHORS = 8   # co-signers kept per deputy
RENAMED_PARTIES = {"PTDOB": "AVANTE", "PSDC": "DC", "PRB": "REPUBLICANOS", "PTN": "PODE", "PODEMOS": "PODE", "PEN": "PATRIOTA",
                   "PTC": "AGIR", "SD": "SOLIDARIEDADE", "UNIAO": "UNIÃO"}
MERGED = {"PHS": ("PODE", 2019), "PRP": ("PATRIOTA", 2019), "PPL": ("PCDOB", 2019), "DEM": ("UNIÃO", 2022), "PSL": ("UNIÃO", 2022),
          "PROS": ("SOLIDARIEDADE", 2023), "PSC": ("PODE", 2023), "PTB": ("PRD", 2024), "PATRIOTA": ("PRD", 2024)}


def party_in(label: str, year: int) -> str:
    """One name per party as it stood in ``year``: Câmara and TSE spellings alike, mergers from the year they happened."""
    from ..camara.orientations import party_key
    k = party_key(label).replace(" ", "").upper()
    k = RENAMED_PARTIES.get(k, k)
    m = MERGED.get(k)
    return m[0] if m and year >= m[1] else k
NEIGHBOURS = 8
MIN_SHARED = 50   # contested roll calls two deputies must both have voted on to be ranked as co-voters


def _cents(s: pd.Series) -> pd.Series:
    return (pd.to_numeric(s, errors="coerce").fillna(0) * 100).round().astype("int64")


def wilson(k: np.ndarray, n: np.ndarray, z: float = 1.96) -> tuple[np.ndarray, np.ndarray]:
    """Wilson score interval for k successes in n trials (elementwise)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        p = k / n
        mid = (p + z * z / (2 * n)) / (1 + z * z / n)
        half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return mid - half, mid + half


def _covoting(data: Path, leg: int, ids: list[str]) -> pd.DataFrame:
    """Pooled agreement between every pair of deputies over the legislature's contested roll calls."""
    pos = {d: i for i, d in enumerate(ids)}
    n = len(ids)
    agree, both = np.zeros((n, n), dtype=np.int64), np.zeros((n, n), dtype=np.int64)
    for m in g.months(data / "camara"):
        if g.legislatura(m) != leg:
            continue
        who, _, M = g.vote_matrix(g.load_month(m, data / "camara").votes)
        keep = [k for k, d in enumerate(who) if str(d) in pos]
        if not keep:
            continue
        idx = np.array([pos[str(who[k])] for k in keep])
        M = M[keep].astype(np.int64)
        Y, N = (M == 1).astype(np.int64), (M == -1).astype(np.int64)
        A = Y + N
        agree[np.ix_(idx, idx)] += Y @ Y.T + N @ N.T
        both[np.ix_(idx, idx)] += A @ A.T
    rows = []
    with np.errstate(invalid="ignore", divide="ignore"):
        rate = agree / both
        lo, hi = wilson(agree, both)
    for i, d in enumerate(ids):
        ok = np.flatnonzero((both[i] >= MIN_SHARED) & (np.arange(n) != i))
        if not len(ok):
            continue
        # Ranked on the Wilson bounds, so a pair that agreed on 50 of 52 votes does not
        # outrank one that agreed on 480 of 500: closest by the lower bound, furthest by the upper.
        near = ok[np.lexsort((ok, -lo[i, ok]))]
        far = ok[np.lexsort((ok, hi[i, ok]))]
        for kind, pick in (("perto", near[:NEIGHBOURS]), ("longe", far[:NEIGHBOURS])):
            for j in pick:
                rows.append({"deputado_id": d, "tipo": kind, "outro_id": ids[j], "n": int(both[i, j]),
                             "concordancia": round(float(rate[i, j]), 4)})
    return pd.DataFrame(rows, columns=["deputado_id", "tipo", "outro_id", "n", "concordancia"])


def _network(data: Path, leg: int) -> pd.DataFrame:
    """Mean ideal point and eigenvector centrality over the legislature's months; cross-party share of ties."""
    files = sorted((data / "site" / "camara" / "members").glob("*.csv"))
    t = pd.concat([pd.read_csv(f, dtype={"id": str}) for f in files], ignore_index=True) if files else pd.DataFrame()
    if t.empty:
        return pd.DataFrame(columns=["deputado_id", "pc1", "eigen", "cross_share"])
    t = t[t.month.map(g.legislatura) == leg]
    out = t.groupby("id").agg(pc1=("pc1", "mean"), eigen=("eigen", "mean"), degree=("degree", "sum"), cross=("cross_degree", "sum"))
    out["cross_share"] = (out.cross / out.degree).where(out.degree > 0)
    return out[["pc1", "eigen", "cross_share"]].round(4).rename_axis("deputado_id").reset_index()


def _mayors(data: Path, pg: pd.DataFrame, view: pd.DataFrame) -> pd.DataFrame:
    """Per person: share of town payments to towns their party governed that year, and the chance level."""
    cols = ["prefeito_mesmo_partido", "prefeito_base"]
    ref = data / "ref" / "prefeitos.csv"
    t = pg[pg.municipio_ibge != ""].copy()
    if not ref.exists() or t.empty:
        return pd.DataFrame(columns=cols)
    from ..ref.prefeitos import mayor_by_year
    t["ano"] = t.ano_mes.str[:4].astype(int)
    may = mayor_by_year(pd.read_csv(ref, dtype=str, keep_default_na=False), sorted(t.ano.unique()))
    may["exercicio"] = may.exercicio.astype(int)
    may["p"] = [party_in(x, y) for x, y in zip(may.partido, may.exercicio)]
    may["uf2"] = may.cod_ibge.str[:2]
    t = t.merge(may[["exercicio", "cod_ibge", "p"]], left_on=["ano", "municipio_ibge"], right_on=["exercicio", "cod_ibge"], how="inner")

    # The deputy's party in the month of the payment (their latest one after they left).
    month_party = {}
    for f in sorted((data / "camara" / "deputies").glob("*.csv")):
        if f.stem[:4] >= str(t.ano.min()):
            d = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=["deputado_id", "partido"])
            month_party.update({(i, f.stem): p for i, p in zip(d.deputado_id, d.partido)})
    who = view.set_index("pessoa")
    dep = t.pessoa.map(who.deputado_id)
    label = [month_party.get((i, m), who.partido.get(pe, "")) for i, m, pe in zip(dep, t.ano_mes, t.pessoa)]
    t["mine"] = [party_in(x, y) for x, y in zip(label, t.ano)]
    t["same"] = t.mine == t.p

    # Chance level: the share of the deputy's own state's towns their party ran that year.
    home = t.pessoa.map(who.uf).map({v: k for k, v in UF.items()})
    runs = may.groupby(["exercicio", "uf2", "p"]).size() / may.groupby(["exercicio", "uf2"]).size()
    t["base"] = [runs.get((y, u, p), 0.0) for y, u, p in zip(t.ano, home, t.mine)]
    t["w"] = t.valor.astype(float)
    g = t[t.w > 0].groupby("pessoa")
    out = pd.DataFrame({"prefeito_mesmo_partido": g.apply(lambda x: x.w[x.same].sum() / x.w.sum(), include_groups=False),
                        "prefeito_base": g.apply(lambda x: (x.w * x.base).sum() / x.w.sum(), include_groups=False)})
    return out.round(4)


def _activity(data: Path, leg: int, ids: list[str]) -> dict[str, pd.DataFrame]:
    """Attendance, proposals, co-signers and parties over the legislature, from the Câmara's monthly tables."""
    cam, keep = data / "camara", set(ids)
    act, signs = [], []
    for m in g.months(cam):
        if g.legislatura(m) != leg:
            continue
        vp, dp, ap = (cam / sub / f"{m}.csv" for sub in ("votacoes", "deputies", "authorship"))
        held = len(pd.read_csv(vp, usecols=[0])) if vp.exists() else 0
        if dp.exists():
            d = pd.read_csv(dp, dtype={"deputado_id": str, "partido": str}, keep_default_na=False, usecols=["deputado_id", "partido", "n_votes"])
            act.append(d[d.deputado_id.isin(keep)].assign(month=m, votacoes=held))
        if ap.exists():
            a = pd.read_csv(ap, dtype=str, keep_default_na=False, usecols=["proposicao_id", "sigla_tipo", "deputado_id", "ordem_assinatura"])
            signs.append(a.assign(month=m))
    act = pd.concat(act, ignore_index=True) if act else pd.DataFrame(columns=["deputado_id", "partido", "n_votes", "month", "votacoes"])
    s = pd.concat(signs, ignore_index=True) if signs else pd.DataFrame(columns=["proposicao_id", "sigla_tipo", "deputado_id", "ordem_assinatura", "month"])
    s = s.drop_duplicates(["proposicao_id", "deputado_id"])
    s["primeiro"] = s.ordem_assinatura == "1"
    s["tipo"] = s.sigla_tipo.map(KIND_OF).fillna("outros")
    mine = s[s.deputado_id.isin(keep)]

    # Month by month.
    sm = mine.assign(projeto=mine.primeiro & (mine.tipo == "projetos"), coassinou=~mine.primeiro).groupby(["deputado_id", "month"]).agg(
        autor=("primeiro", "sum"), projetos=("projeto", "sum"), coautor=("coassinou", "sum"))
    mo = act.rename(columns={"n_votes": "votos"}).set_index(["deputado_id", "month"])[["votacoes", "votos"]].join(sm, how="outer").fillna(0)
    mo = mo.astype(int).reset_index().sort_values(["deputado_id", "month"])

    # Kinds of proposal, and the co-signers they share the most proposals with.
    kinds = mine.assign(coassinou=~mine.primeiro).groupby(["deputado_id", "tipo"]).agg(autor=("primeiro", "sum"), coautor=("coassinou", "sum"))
    kinds = kinds.astype(int).reset_index().sort_values(["deputado_id", "tipo"])
    size = s.groupby("proposicao_id").deputado_id.transform("size")
    small = s.loc[(size >= 2) & (size <= g.MAX_AUTHORS), ["proposicao_id", "deputado_id"]]
    pairs = small[small.deputado_id.isin(keep)].merge(small, on="proposicao_id", suffixes=("", "_outro"))
    pairs = pairs[pairs.deputado_id != pairs.deputado_id_outro].groupby(["deputado_id", "deputado_id_outro"]).size().rename("n").reset_index()
    co = (pairs.sort_values(["deputado_id", "n", "deputado_id_outro"], ascending=[True, False, True]).groupby("deputado_id").head(COAUTHORS)
          .rename(columns={"deputado_id_outro": "outro_id"}))

    # Parties: one row per stretch under the same party, its spelling unified (the Câmara writes REPUBLIC and
    # REPUBLICANOS for the same party) and mergers counted from their year; months with no party are skipped.
    a = act.assign(partido=[party_in(x, int(m[:4])) if x else "" for x, m in zip(act.partido, act.month)])
    a = a[a.partido != ""].sort_values(["deputado_id", "month"])
    run = (a.partido != a.groupby("deputado_id").partido.shift()).cumsum().rename("trecho")
    parties = (a.groupby(["deputado_id", run]).agg(partido=("partido", "first"), de=("month", "first"), ate=("month", "last"))
               .reset_index().drop(columns="trecho"))

    tot = mo.groupby("deputado_id")[["votacoes", "votos", "autor", "projetos", "coautor"]].sum()
    per = pd.DataFrame({
        "presenca": (tot.votos / tot.votacoes).where(tot.votacoes > 0).round(4), "votacoes_mandato": tot.votacoes,
        "propostas_autor": tot.autor, "projetos_autor": tot.projetos, "propostas_coautor": tot.coautor,
        "relatorias": kinds[kinds.tipo == "relatorias"].set_index("deputado_id").autor.reindex(tot.index).fillna(0).astype(int),
        "partidos": parties.groupby("deputado_id").partido.nunique().reindex(tot.index).fillna(0).astype(int)})
    return {"per": per.rename_axis("deputado_id").reset_index(), "mo": mo, "kinds": kinds, "co": co, "parties": parties}


def build_leg(data: Path, leg: int) -> dict:
    out = data / "site" / "deputados"
    view = pd.read_csv(data / "views" / f"deputados_{leg}.csv", dtype=str, keep_default_na=False)
    x = pd.read_csv(data / "ref" / "politicians.csv", dtype=str, keep_default_na=False)
    autor = x[x.fonte == "emendas"].set_index("id").pessoa
    people = set(view.pessoa)

    # Amendments for the budgets the legislature approved.
    files = [data / "emendas" / "emendas" / f"{y}.csv" for y in budget_years(leg)]
    em = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in files if f.exists()], ignore_index=True)
    em["pessoa"] = em.autor_codigo.map(autor)
    em = em[em.pessoa.isin(people)].copy()
    for c in ("empenhado", "pago"):
        em[c] = _cents(em[c])
    em["uf"] = em.uf_ibge.str[:2].map(UF).fillna("")
    by = em.groupby(["pessoa", "ano", "tipo"]).agg(emendas=("codigo", lambda s: s[s != ""].nunique()),
                                                  empenhado=("empenhado", "sum"), pago=("pago", "sum")).reset_index()
    by[["empenhado", "pago"]] = by[["empenhado", "pago"]] / 100
    csv(by.round(2).sort_values(["pessoa", "ano", "tipo"]), out / f"emendas_{leg}.csv")
    # Where the money landed: payments on those amendments, by the recipient's town (as on the amendments page).
    owner = em[em.codigo != ""].drop_duplicates("codigo").set_index("codigo").pessoa
    pfiles = sorted((data / "emendas" / "pagamentos").glob("*.csv"))
    cols = ["codigo_emenda", "ano_mes", "uf", "municipio", "valor"]
    pg = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=cols) for f in pfiles],
                   ignore_index=True) if pfiles else pd.DataFrame(columns=cols)
    pg = pg[pg.codigo_emenda.isin(owner.index)].copy()
    pg["pessoa"] = pg.codigo_emenda.map(owner)
    pg["municipio_ibge"] = town_codes(data, pg) if len(pg) else []
    pg["valor"] = _cents(pg.valor)
    de = pg.groupby(["pessoa", "uf", "municipio_ibge"]).valor.sum().div(100).round(2).rename("pago").reset_index()
    de = de[de.pago != 0]
    csv(de.sort_values(["pessoa", "pago", "municipio_ibge"], ascending=[True, False, True]), out / f"destinos_{leg}.csv")
    home = view.set_index("pessoa").uf
    em["casa"] = em.uf == em.pessoa.map(home)
    tot = em.groupby("pessoa").pago.sum()
    shares = pd.DataFrame({"emendas_pago_estado": em[em.casa].groupby("pessoa").pago.sum() / tot,
                           "emendas_pago_nacional": em[em.uf == ""].groupby("pessoa").pago.sum() / tot}).fillna(0)
    shares = shares.where(tot.reindex(shares.index) > 0).round(4)

    # The large donors of the campaign that elected them.
    y = election_of(leg)
    dd_path = data / "tse" / str(y) / "doacoes_grandes_doadores.csv"
    sq = view[view.campanha_sq_candidato != ""].set_index("campanha_sq_candidato").pessoa
    if dd_path.exists():
        dd = pd.read_csv(dd_path, dtype=str, keep_default_na=False)
        dd = dd[dd.sq_candidato.isin(sq.index)].assign(pessoa=lambda t: t.sq_candidato.map(sq), valor=lambda t: pd.to_numeric(t.valor))
    else:
        dd = pd.DataFrame(columns=["pessoa", "doador", "nome", "valor"])
    csv(dd[["pessoa", "doador", "nome", "valor"]].sort_values(["pessoa", "valor", "doador"], ascending=[True, False, True]),
        out / f"doadores_{leg}.csv")
    donors = dd.groupby("pessoa").agg(grandes_doadores=("doador", "size"), grandes_doadores_valor=("valor", "sum"))

    # Amendment money paid to companies under a barring sanction, every budget (the sanctions page's table).
    sp = data / "site" / "sancoes" / "autores.csv"
    if sp.exists():
        s = pd.read_csv(sp, dtype=str, keep_default_na=False)
        s = s[s.pessoa.isin(people)]
        for c in ("pago_total", "pago_sancionadas", "empresas_sancionadas"):
            s[c] = pd.to_numeric(s[c], errors="coerce").fillna(0)
        sanc = s.groupby("pessoa")[["pago_total", "pago_sancionadas", "empresas_sancionadas"]].sum()
        sanc.columns = ["sancoes_pago_total", "sancoes_pago_sancionadas", "sancoes_empresas"]
    else:
        sanc = pd.DataFrame(columns=["sancoes_pago_total", "sancoes_pago_sancionadas", "sancoes_empresas"])

    work = _activity(data, leg, view.deputado_id.tolist())
    csv(work["mo"], out / f"atividade_{leg}.csv")
    csv(work["kinds"], out / f"propostas_{leg}.csv")
    csv(work["co"], out / f"coautores_{leg}.csv")
    csv(work["parties"].sort_values(["deputado_id", "de"]), out / f"partidos_{leg}.csv")

    v = view.merge(_network(data, leg), on="deputado_id", how="left").merge(work["per"], on="deputado_id", how="left")
    v = v.join(shares, on="pessoa").join(donors, on="pessoa").join(sanc, on="pessoa").join(_mayors(data, pg, view), on="pessoa")
    for c in ("grandes_doadores", "grandes_doadores_valor", "sancoes_pago_sancionadas", "sancoes_pago_total", "sancoes_empresas"):
        v[c] = v[c].fillna(0)
    v["grandes_doadores"] = v.grandes_doadores.astype(int)
    v["sancoes_empresas"] = v.sancoes_empresas.astype(int)
    v = v.round({"grandes_doadores_valor": 2, "sancoes_pago_total": 2, "sancoes_pago_sancionadas": 2})
    csv(v, out / f"deputados_{leg}.csv")

    nb = _covoting(data, leg, view.deputado_id.tolist())
    csv(nb, out / f"vizinhos_{leg}.csv")
    return {"deputies": len(v), "with_network": int(v.pc1.notna().sum()), "amendment_rows": len(by),
            "proposals": int(work["kinds"].autor.sum()), "attendance_median": float(work["per"].presenca.median()) if len(work["per"]) else None,
            "places": len(de), "paid_to_a_town": round(float(de.loc[de.municipio_ibge != "", "pago"].sum() / max(de.pago.sum(), 1)), 4), "donations": len(dd), "neighbour_rows": len(nb)}


def build(data: Path) -> dict:
    legs = [leg for leg in LEGS if (data / "views" / f"deputados_{leg}.csv").exists()]
    out = {leg: build_leg(data, leg) for leg in legs}
    csv(pd.DataFrame({"legislatura": legs}), data / "site" / "deputados" / "legislaturas.csv")
    return out
