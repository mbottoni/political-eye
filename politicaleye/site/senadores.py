"""Summaries for the senators page: ``data/site/senadores/``.

The deputies page's files (``deputados.py``), for the Senate, keyed by ``senador_id``:

    senadores_<leg>.csv   one row per senator of the legislature: the cross-source view
                          (data/views/senadores_<leg>.csv) plus position on the first voting dimension and
                          network centrality (the Senado page's twelve-month windows, averaged over the
                          legislature's months), cross-party ties, the share of their amendment money paid in
                          their own state and nationally, their Senate race's large donors, amendment money paid
                          to barred companies, money to towns their party runs, roll-call participation and
                          the matérias they signed
    vizinhos_<leg>.csv    closest and furthest co-voters over the legislature (pairs with 30 contested roll
                          calls in common: the Senate votes far less often than the Câmara)
    emendas_<leg>.csv, destinos_<leg>.csv, doadores_<leg>.csv
                          amendments by year and type, where their payments landed, their race's large donors
    atividade_<leg>.csv   senator and month: roll calls held while in office (those they presided left out),
                          votes cast, roll calls presided, matérias signed (all, and bills) and co-signed
    propostas_<leg>.csv   senator and kind of matéria (bills, requests, other): signed, and co-signed
    coautores_<leg>.csv   each senator's most frequent co-signers (matérias with at most 20 senator signers)
    partidos_<leg>.csv    each senator's parties over the legislature
    campanhas_<leg>.csv   person: every candidacy of theirs in 2018, 2022 and 2026 that the crosswalk links
                          (Senate races as senator or suplente, and federal-deputy races), with its money; a
                          suplente's row names the slate's senator candidate and what that campaign raised

The Senado records no signing order, so a senator "signed" a matéria whether they wrote it or joined it.
Signature drives (more than 20 senator signers; every PEC has 27 or more) are left out of what they signed
and counted as co-signed; signatures as party or bloc leader, on behalf of the bench, are left out.

See methodology/views.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..senado import graphs as sg
from ..views.senadores import campaigns
from .common import csv
from .deputados import COAUTHORS, _covoting, _mayors, _network, amendments, donors, party_in, sanctions

LEGS = (56, 57)
MIN_SHARED = 30    # contested roll calls two senators must both have voted on to be ranked as co-voters
MAX_SIGNERS = sg.MAX_AUTHORS   # more senator signers than this is a signature drive, not authorship
# Kinds of matéria, from the Senado's type codes; PLS and PDS were the Senate's bills before 2019.
KINDS = {"projetos": {"PL", "PLS", "PLP", "PEC", "PDL", "PDS", "PRS"}, "requerimentos": {"RQS", "REQ", "INS"}}
KIND_OF = {t: k for k, ts in KINDS.items() for t in ts}
CAST = {"Sim", "Não", "Abstenção", "Votou", "P-OD"}   # a vote cast (Votou: a secret vote); anything else is not
PRESIDING = "Presidente (art. 51 RISF)"
NO_PARTY = {"S/PARTIDO", "SEMREGISTRO"}


def _activity(data: Path, leg: int, ids: list[str]) -> dict[str, pd.DataFrame]:
    """Participation, matérias signed, co-signers and parties over the legislature, from the Senado's monthly tables."""
    root, keep = data / "senado", set(ids)
    act, signs, party = [], [], []
    for m in sg.months(root):
        if sg.legislatura(m) != leg:
            continue
        vp, sp, ap = (root / sub / f"{m}.csv" for sub in ("votes", "senators", "authorship"))
        if vp.exists():
            v = pd.read_csv(vp, dtype=str, keep_default_na=False, usecols=["votacao_id", "senador_id", "voto"])
            v = v[v.senador_id.isin(keep)].drop_duplicates(["votacao_id", "senador_id"])
            # Every roll call lists the 81 senators then in office; one they presided is not one they could vote in.
            pres = v.voto == PRESIDING
            a = v.assign(votacoes=~pres, votos=v.voto.isin(CAST), presidiu=pres).groupby("senador_id")[["votacoes", "votos", "presidiu"]].sum()
            act.append(a.assign(month=m).reset_index())
        if sp.exists():
            s = pd.read_csv(sp, dtype=str, keep_default_na=False, usecols=["senador_id", "partido"])
            party.append(s[s.senador_id.isin(keep)].assign(month=m))
        if ap.exists():
            a = pd.read_csv(ap, dtype=str, keep_default_na=False, usecols=["processo_id", "sigla_tipo", "senador_id", "lider"])
            signs.append(a[a.lider != "1"].assign(month=m))   # a leader signing for the bench is not their own matéria
    ac = ["senador_id", "votacoes", "votos", "presidiu", "month"]
    act = pd.concat(act, ignore_index=True) if act else pd.DataFrame(columns=ac)
    s = pd.concat(signs, ignore_index=True) if signs else pd.DataFrame(columns=["processo_id", "sigla_tipo", "senador_id", "lider", "month"])
    s = s.drop_duplicates(["processo_id", "senador_id"])
    size = s.groupby("processo_id").senador_id.transform("size")
    s = s.assign(autor=size <= MAX_SIGNERS, coautor=size >= 2, tipo=s.sigla_tipo.map(KIND_OF).fillna("outros"))
    mine = s[s.senador_id.isin(keep)]

    # Month by month.
    sm = mine.assign(projeto=mine.autor & (mine.tipo == "projetos")).groupby(["senador_id", "month"]).agg(
        autor=("autor", "sum"), projetos=("projeto", "sum"), coautor=("coautor", "sum"))
    mo = act.set_index(["senador_id", "month"])[["votacoes", "votos", "presidiu"]].join(sm, how="outer").fillna(0)
    mo = mo.astype(int).reset_index().sort_values(["senador_id", "month"])

    # Kinds of matéria, and the senators they share the most matérias with.
    kinds = mine.groupby(["senador_id", "tipo"]).agg(autor=("autor", "sum"), coautor=("coautor", "sum"))
    kinds = kinds.astype(int).reset_index().sort_values(["senador_id", "tipo"])
    small = s.loc[(size >= 2) & (size <= MAX_SIGNERS), ["processo_id", "senador_id"]]
    pairs = small[small.senador_id.isin(keep)].merge(small, on="processo_id", suffixes=("", "_outro"))
    pairs = pairs[pairs.senador_id != pairs.senador_id_outro].groupby(["senador_id", "senador_id_outro"]).size().rename("n").reset_index()
    co = (pairs.sort_values(["senador_id", "n", "senador_id_outro"], ascending=[True, False, True]).groupby("senador_id").head(COAUTHORS)
          .rename(columns={"senador_id_outro": "outro_id"}))

    # Parties: one row per stretch under the same party, spellings unified and mergers counted from their year.
    p = pd.concat(party, ignore_index=True) if party else pd.DataFrame(columns=["senador_id", "partido", "month"])
    p = p.assign(partido=[party_in(x, int(m[:4])) if x else "" for x, m in zip(p.partido, p.month)])
    p.loc[p.partido.isin(NO_PARTY), "partido"] = "S.PART."   # as the Câmara writes it
    p = p[p.partido != ""].sort_values(["senador_id", "month"])
    run = (p.partido != p.groupby("senador_id").partido.shift()).cumsum().rename("trecho")
    parties = (p.groupby(["senador_id", run]).agg(partido=("partido", "first"), de=("month", "first"), ate=("month", "last"))
               .reset_index().drop(columns="trecho"))

    tot = mo.groupby("senador_id")[["votacoes", "votos", "presidiu", "autor", "projetos", "coautor"]].sum()
    per = pd.DataFrame({
        "presenca": (tot.votos / tot.votacoes).where(tot.votacoes > 0).round(4), "votacoes_mandato": tot.votacoes,
        "presidiu": tot.presidiu, "propostas_autor": tot.autor, "projetos_autor": tot.projetos, "propostas_coautor": tot.coautor,
        "partidos": parties.groupby("senador_id").partido.nunique().reindex(tot.index).fillna(0).astype(int)})
    month_party = {(i, m): x for i, m, x in zip(p.senador_id, p.month, p.partido)}
    return {"per": per.rename_axis("senador_id").reset_index(), "mo": mo, "kinds": kinds, "co": co, "parties": parties,
            "month_party": month_party}


def _campaigns(data: Path, view: pd.DataFrame) -> pd.DataFrame:
    """Every linked candidacy of the senators in 2018, 2022 and 2026; suplentes with their slate's senator candidate."""
    x = pd.read_csv(data / "ref" / "politicians.csv", dtype=str, keep_default_na=False)
    c = campaigns(data, x[x.pessoa.isin(set(view.pessoa))], (2018, 2022, 2026), cargos=None)
    if c.empty:
        return c.assign(titular="", titular_total="")
    # A Senate slate is one number in one state: the suplentes share their senator candidate's number.
    heads = []
    for y in c.ano.unique():
        d = data / "tse" / str(y)
        k = pd.read_csv(d / "candidatos.csv", dtype=str, keep_default_na=False, usecols=["sq_candidato", "cargo", "uf", "numero", "nome_urna"])
        k = k[k.cargo == "Senador"].drop_duplicates(["uf", "numero"], keep=False)
        t = pd.read_csv(d / "receitas_por_candidato.csv", dtype=str, keep_default_na=False, usecols=["sq_candidato", "total"])
        heads.append(k.merge(t, on="sq_candidato", how="left").assign(ano=y)[["ano", "uf", "numero", "nome_urna", "total"]])
    h = pd.concat(heads, ignore_index=True).rename(columns={"nome_urna": "titular", "total": "titular_total"})
    c = c.merge(h, on=["ano", "uf", "numero"], how="left")
    sup = c.cargo.str.contains("Suplente")
    c.loc[~sup, ["titular", "titular_total"]] = ""
    return c.fillna("")


def build_leg(data: Path, leg: int) -> dict:
    out = data / "site" / "senadores"
    view = pd.read_csv(data / "views" / f"senadores_{leg}.csv", dtype=str, keep_default_na=False)
    by, de, shares, pg = amendments(data, leg, view, out)
    camp = view.rename(columns={"campanha_ano": "ano", "campanha_sq_candidato": "sq_candidato"})[["pessoa", "ano", "sq_candidato"]]
    dd, donated = donors(data, camp, out / f"doadores_{leg}.csv")
    sanc = sanctions(data, set(view.pessoa))
    cp = _campaigns(data, view)
    csv(cp.drop(columns=["numero"]).sort_values(["pessoa", "ano", "sq_candidato"]), out / f"campanhas_{leg}.csv")

    work = _activity(data, leg, view.senador_id.tolist())
    csv(work["mo"], out / f"atividade_{leg}.csv")
    csv(work["kinds"], out / f"propostas_{leg}.csv")
    csv(work["co"], out / f"coautores_{leg}.csv")
    csv(work["parties"].sort_values(["senador_id", "de"]), out / f"partidos_{leg}.csv")

    mayors = _mayors(data, pg, view, month_party=work["month_party"], member="senador_id")
    v = (view.merge(_network(data, leg, chamber="senado", member="senador_id"), on="senador_id", how="left")
         .merge(work["per"], on="senador_id", how="left"))
    v = v.join(shares, on="pessoa").join(donated, on="pessoa").join(sanc, on="pessoa").join(mayors, on="pessoa")
    for c in ("grandes_doadores", "grandes_doadores_valor", "sancoes_pago_sancionadas", "sancoes_pago_total", "sancoes_empresas"):
        v[c] = v[c].fillna(0)
    v["grandes_doadores"] = v.grandes_doadores.astype(int)
    v["sancoes_empresas"] = v.sancoes_empresas.astype(int)
    for c in ("votacoes_mandato", "presidiu", "propostas_autor", "projetos_autor", "propostas_coautor", "partidos"):
        v[c] = v[c].astype("Int64")
    v = v.round({"grandes_doadores_valor": 2, "sancoes_pago_total": 2, "sancoes_pago_sancionadas": 2})
    csv(v, out / f"senadores_{leg}.csv")

    nb = _covoting(data, leg, view.senador_id.tolist(), chamber="senado", member="senador_id", min_shared=MIN_SHARED)
    csv(nb, out / f"vizinhos_{leg}.csv")
    return {"senators": len(v), "with_network": int(v.pc1.notna().sum()), "amendment_rows": len(by),
            "signed": int(work["kinds"].autor.sum()), "attendance_median": float(work["per"].presenca.median()) if len(work["per"]) else None,
            "places": len(de), "donations": len(dd), "campaigns": len(cp), "neighbour_rows": len(nb)}


def build(data: Path) -> dict:
    legs = [leg for leg in LEGS if (data / "views" / f"senadores_{leg}.csv").exists()]
    out = {leg: build_leg(data, leg) for leg in legs}
    csv(pd.DataFrame({"legislatura": legs}), data / "site" / "senadores" / "legislaturas.csv")
    return out
