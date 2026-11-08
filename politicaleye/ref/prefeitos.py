"""Every municipality's elected mayor and party, from TSE's municipal-election candidate files.

    data/ref/prefeitos.csv   one row per municipality and election won: the regular elections of 2016, 2020
                             and 2024, plus the supplementary elections held during those terms

TSE names a municipality by its own code (``SG_UE``) and name, not IBGE's, so
each is matched to an IBGE code by state and normalised name, with a short
list of spellings that differ. ``mayor_by_year`` says who governed each town
in each calendar year. See methodology/ref.md#mayors.
"""

from __future__ import annotations

import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

from ..fetch import download_zip
from ..io import write_csv

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{year}.zip"
ELECTIONS = (2016, 2020, 2024)
COLS = ["ano", "cod_ibge", "municipio", "uf", "sg_ue", "eleicao", "data_eleicao", "suplementar", "turno", "sq_candidato",
        "nome_urna", "partido", "genero", "cor_raca"]
# TSE spelling -> IBGE spelling, after normalisation, where the two registries differ.
SPELLING = {
    ("SP", "EMBU"): "EMBU DAS ARTES", ("RJ", "PARATI"): "PARATY", ("SP", "FLORINEA"): "FLORINIA",
    ("BA", "MUQUEM DO SAO FRANCISCO"): "MUQUEM DE SAO FRANCISCO", ("MG", "DONA EUSEBIA"): "DONA EUZEBIA",
    ("RO", "ALVORADA DO OESTE"): "ALVORADA DOESTE", ("RO", "ESPIGAO DO OESTE"): "ESPIGAO DOESTE", ("RN", "AREZ"): "ARES",
    ("BA", "SANTA TEREZINHA"): "SANTA TERESINHA", ("PA", "SANTA ISABEL DO PARA"): "SANTA IZABEL DO PARA",
    ("BA", "CAMACA"): "CAMACAN", ("SE", "GRACCHO CARDOSO"): "GRACHO CARDOSO", ("PA", "ELDORADO DOS CARAJAS"): "ELDORADO DO CARAJAS",
    ("MG", "SAO THOME DAS LETRAS"): "SAO TOME DAS LETRAS", ("RN", "ASSU"): "ACU",
}


def _log(msg: str) -> None:
    print(f"[prefeitos] {msg}", file=sys.stderr)


def norm(s: str) -> str:
    """``"Santa Bárbara d'Oeste"`` -> ``"SANTA BARBARA DOESTE"``: no accents, apostrophes or hyphens."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    s = s.replace("'", "").replace("`", "").replace("-", " ")
    return " ".join(re.sub(r"[^A-Z ]+", " ", s).split())


def fetch(raw: Path) -> None:
    for y in ELECTIONS:
        if download_zip(CDN.format(year=y), raw / f"consulta_cand_{y}.zip", attempts=8, timeout=300) is None:
            raise RuntimeError(f"consulta_cand_{y}: 404")


def _read(path: Path) -> pd.DataFrame:
    want = ["NR_TURNO", "SG_UF", "SG_UE", "NM_UE", "DS_CARGO", "DS_SIT_TOT_TURNO", "SG_PARTIDO", "NM_URNA_CANDIDATO",
            "SQ_CANDIDATO", "DS_GENERO", "DS_COR_RACA", "CD_ELEICAO", "DS_ELEICAO", "DT_ELEICAO", "CD_TIPO_ELEICAO"]
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith("_BRASIL.csv"))
        with z.open(name) as f:
            have = [c.strip().strip('"') for c in f.readline().decode("latin1").strip().split(";")]
        return pd.read_csv(z.open(name), sep=";", encoding="latin1", dtype=str, keep_default_na=False,
                           usecols=[c for c in want if c in have])


def elected(raw: Path, year: int) -> pd.DataFrame:
    """Elected mayors of one year's file: the regular election and any supplementary ones in it."""
    c = _read(raw / f"consulta_cand_{year}.zip")
    c = c[(c.DS_CARGO.str.upper().str.strip() == "PREFEITO") & (c.DS_SIT_TOT_TURNO.str.strip() == "ELEITO")].copy()
    d = c.DT_ELEICAO.str.strip()
    c["data"] = d.str[6:10] + "-" + d.str[3:5] + "-" + d.str[0:2]
    c["sup"] = ~c.DS_ELEICAO.str.contains(r"^Elei[çc][õo]es Municipais", case=False, regex=True)
    return pd.DataFrame({
        "ano": str(year), "uf": c.SG_UF, "sg_ue": c.SG_UE, "municipio": c.NM_UE.str.strip(), "eleicao": c.DS_ELEICAO.str.strip(),
        "data_eleicao": c.data, "suplementar": c.sup.map({True: "1", False: "0"}), "turno": c.NR_TURNO,
        "sq_candidato": c.SQ_CANDIDATO, "nome_urna": c.NM_URNA_CANDIDATO.str.strip(), "partido": c.SG_PARTIDO.str.strip(),
        "genero": c.DS_GENERO.str.strip(), "cor_raca": c.get("DS_COR_RACA", pd.Series("", index=c.index)).str.strip(),
    })


def match_ibge(m: pd.DataFrame, entes: pd.DataFrame) -> pd.Series:
    """IBGE code for each (uf, municipio) row, by normalised name within the state."""
    key = entes.assign(k=entes.ente.map(norm)).drop_duplicates(["uf", "k"]).set_index(["uf", "k"]).cod_ibge
    k = [SPELLING.get((uf, norm(n)), norm(n)) for uf, n in zip(m.uf, m.municipio)]
    return pd.Series([key.get((uf, x), "") for uf, x in zip(m.uf, k)], index=m.index)


def build(raw: Path, data: Path, entes: Path) -> dict:
    e = pd.read_csv(entes, dtype=str, keep_default_na=False)
    rows = [elected(raw, y) for y in ELECTIONS if (raw / f"consulta_cand_{y}.zip").exists()]
    m = pd.concat(rows, ignore_index=True)
    m["cod_ibge"] = match_ibge(m, e)
    miss = m[m.cod_ibge == ""].drop_duplicates(["uf", "municipio"])
    if len(miss):
        _log(f"{len(miss)} municipalities not matched to IBGE: {miss[['uf', 'municipio']].values.tolist()[:20]}")
    m = m[m.cod_ibge != ""]
    m = m.sort_values(["ano", "cod_ibge", "data_eleicao", "turno", "sq_candidato"]).drop_duplicates(["ano", "cod_ibge", "data_eleicao"], keep="last")
    write_csv(m[COLS], data / "prefeitos.csv")
    regular = m[m.suplementar == "0"]
    out = {str(y): int((regular.ano == str(y)).sum()) for y in ELECTIONS}
    out["suplementares"] = int((m.suplementar == "1").sum())
    out["unmatched"] = int(len(miss))
    _log(str(out))
    return out


def mayor_by_year(prefeitos: pd.DataFrame, years) -> pd.DataFrame:
    """Who governed each municipality in each calendar year: the regular winner of the election before the
    term (2017–2020: 2016, and so on), replaced by a supplementary winner from the year after their election."""
    p = prefeitos.copy()
    p["inicio"] = p.ano.astype(int) + 1
    p.loc[p.suplementar == "1", "inicio"] = p.data_eleicao.str[:4].astype(int).where(p.suplementar == "1") + 1
    out = []
    for y in years:
        cand = p[(p.ano.astype(int) + 1 <= y) & (y <= p.ano.astype(int) + 4) & (p.inicio <= y)]
        last = cand.sort_values(["cod_ibge", "inicio", "data_eleicao"]).drop_duplicates("cod_ibge", keep="last")
        out.append(last.assign(exercicio=y))
    cols = ["exercicio", "cod_ibge", "partido", "nome_urna", "genero", "cor_raca", "ano", "suplementar"]
    return pd.concat(out, ignore_index=True)[cols] if out else pd.DataFrame(columns=cols)
