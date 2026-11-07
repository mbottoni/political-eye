"""Turn the day's sanctions snapshots into tidy tables under ``data/sancoes/``.

    data/sancoes/ceis.csv, cnep.csv, cepim.csv   every sanction listed, one row each
    data/sancoes/leniencia.csv                   leniency agreements, one row per company and agreement
    data/sancoes/leniencia_efeitos.csv           what each agreement required
    data/sancoes/changes.csv                     when each sanction or agreement entered and left the lists
    data/sancoes/ref/fundamentacoes.csv          the legal grounds, by id (long texts, few distinct)

Columns keep the published names, in snake_case without accents. Dates are
ISO, money has a ``.`` decimal point. Every CPF is masked the way CGU masks
it (``***.462.240-**``), in the document column and in every text. See
``methodology/sancoes.md``.
"""

from __future__ import annotations

import base64
import hashlib
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

from ..io import write_csv

# Each list's key; the changes log names a row by the key's last part.
LISTS = {"ceis": ["codigo_da_sancao"], "cnep": ["codigo_da_sancao"], "cepim": ["cnpj_entidade", "numero_convenio"]}
CHANGES = ["data", "lista", "codigo", "mudanca", "tipo_de_pessoa", "documento", "nome"]
DOC = "cpf_ou_cnpj_do_sancionado"
PROCESS = "numero_do_processo"
LONG = "fundamentacao_legal"
# A CPF, formatted (with a mistyped check part, too) or as a bare run of 11
# digits, but not part of a longer number such as a CNPJ, a process number or
# a date: a separator only joins numbers when a digit follows it, so a CPF
# that ends a sentence is still found.
_EDGE_L, _EDGE_R = r"(?<!\d)(?<!\d[./-])", r"(?!\d)(?![./-]\d)"
CPF = re.compile(_EDGE_L + r"(\d{3})\.?(\d{3})\.?(\d{3})(?:-\d{2,3}|\d{2})" + _EDGE_R)
CPF_FORMATTED = re.compile(_EDGE_L + r"(\d{3})\.(\d{3})\.(\d{3})-\d{2,3}" + _EDGE_R)


def _log(msg: str) -> None:
    print(f"[build] {msg}", file=sys.stderr)


def slug(name: str) -> str:
    """``"CÓDIGO DA SANÇÃO"`` -> ``"codigo_da_sancao"``."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def mask_cpf(doc: str) -> str:
    """``"86246224091"`` -> ``"***.462.240-**"``, as CGU shows a CPF."""
    d = re.sub(r"\D", "", doc)
    return f"***.{d[3:6]}.{d[6:9]}-**" if len(d) == 11 else "*" * len(doc)


def mask_text(s: pd.Series, pattern: re.Pattern = CPF) -> pd.Series:
    return s.str.replace(pattern, lambda m: f"***.{m[2]}.{m[3]}-**", regex=True)


def _ref_id(text: str) -> str:
    # base32, so an id never looks like a CPF to anyone scanning the tables
    return base64.b32encode(hashlib.sha256(text.encode()).digest()).decode().lower()[:12] if text else ""


def _read(zip_path: Path) -> dict[str, pd.DataFrame]:
    out = {}
    with zipfile.ZipFile(zip_path) as z:
        for n in z.namelist():
            raw = z.read(n)
            try:
                text = raw.decode("cp1252")    # the headers use cp1252's en dash
            except UnicodeDecodeError:
                text = raw.decode("latin1")
            from io import StringIO
            df = pd.read_csv(StringIO(text), sep=";", dtype=str, keep_default_na=False)
            out[n] = df.rename(columns=slug)
    return out


def _tidy(df: pd.DataFrame, refs: dict[str, str]) -> pd.DataFrame:
    df = df.apply(lambda c: c.str.strip())
    for c in df.columns:
        if c.startswith("data") and df[c].str.fullmatch(r"(\d{2}/\d{2}/\d{4})?").all():
            df[c] = df[c].str.replace(r"(\d{2})/(\d{2})/(\d{4})", r"\3-\2-\1", regex=True)
        elif c.startswith("valor") and df[c].str.fullmatch(r"-?[\d.]*(,\d+)?").all():
            df[c] = df[c].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    if DOC in df:
        company = df[DOC].str.fullmatch(r"\d{14}")   # no CPF has 14 digits
        foreign = df[DOC].str.startswith("EX")
        df[DOC] = df[DOC].where(company | foreign, df[DOC].map(mask_cpf))
    for c in df.columns:
        if c == DOC:
            continue
        df[c] = mask_text(df[c], CPF_FORMATTED if c == PROCESS else CPF)
    if LONG in df:
        ids = df[LONG].map(_ref_id)
        refs.update(dict(zip(ids, df[LONG])))
        df[LONG] = ids
    return df


def _code_order(df: pd.DataFrame, key: str) -> pd.DataFrame:
    k = pd.to_numeric(df[key], errors="coerce")
    return df.assign(_k=k).sort_values(["_k", key, *df.columns.drop(key).tolist()], kind="stable").drop(columns="_k")


def _changes(old: pd.DataFrame | None, new: pd.DataFrame, key: str, lista: str, day: str, name_col: str) -> pd.DataFrame:
    """Rows for every key that appeared in or left the list since the last snapshot."""
    if old is None:   # the first snapshot: a baseline, not a change
        return pd.DataFrame(columns=CHANGES)
    o, n = set(old[key]), set(new[key])

    def rows(df: pd.DataFrame, keys: set, what: str) -> pd.DataFrame:
        d = df[df[key].isin(keys)]
        return pd.DataFrame({
            "data": day, "lista": lista, "codigo": d[key], "mudanca": what,
            "tipo_de_pessoa": d["tipo_de_pessoa"] if "tipo_de_pessoa" in d else "J",
            "documento": next((d[c] for c in (DOC, "cnpj_entidade", "cnpj_do_sancionado") if c in d), ""),
            "nome": d[name_col],
        })

    return pd.concat([rows(new, n - o, "entrou"), rows(old, o - n, "saiu")], ignore_index=True)


def build(raw: Path, data: Path, dates: dict[str, str]) -> dict:
    """Rebuild the tables from the zips in ``raw``; ``dates`` gives each list's snapshot date."""
    refs: dict[str, str] = {}
    old_ref = data / "ref" / "fundamentacoes.csv"
    if old_ref.exists():
        refs.update(pd.read_csv(old_ref, dtype=str, keep_default_na=False).set_index("id").texto.to_dict())
    changes = []
    report = {}

    def previous(name: str) -> pd.DataFrame | None:
        p = data / f"{name}.csv"
        return pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else None

    for lista, keys in LISTS.items():
        z = raw / f"{lista}.zip"
        if not z.exists():
            continue
        (df,) = _read(z).values()
        df = _tidy(df, refs)
        dup = int(df.duplicated(keys).sum())
        df = df.drop_duplicates()
        df = df.assign(_key=df[keys].agg(":".join, axis=1))
        df = _code_order(df, keys[0]) if len(keys) == 1 else df.sort_values(["_key", *df.columns.drop("_key")])
        name_col = next(c for c in ("nome_do_sancionado", "nome_entidade") if c in df)
        prev = previous(lista)
        if prev is not None:
            prev = prev.assign(_key=prev[keys].agg(":".join, axis=1))
        ch = _changes(prev, df, "_key", lista, dates.get(lista, ""), name_col)
        ch["codigo"] = ch.codigo.str.split(":").str[-1]
        if "cnpj_entidade" in df:
            ch["documento"] = ch.documento.where(ch.documento != "", None)
        changes.append(ch)
        write_csv(df.drop(columns="_key"), data / f"{lista}.csv")
        report[lista] = len(df)
        report[f"{lista}_duplicate_keys"] = dup
        if DOC in df:
            report[f"{lista}_people"] = int((~df[DOC].str.fullmatch(r"\d{14}")).sum())

    z = raw / "acordos-leniencia.zip"
    if z.exists():
        parts = _read(z)
        acordos = next(v for k, v in parts.items() if "Acordos" in k)
        efeitos = next(v for k, v in parts.items() if "Efeitos" in k)
        acordos = _tidy(acordos, refs).drop_duplicates()
        acordos = acordos.assign(_k=pd.to_numeric(acordos.id_do_acordo, errors="coerce")).sort_values(
            ["_k", *acordos.columns]).drop(columns="_k")
        efeitos = _tidy(efeitos, refs).drop_duplicates()
        efeitos = efeitos.assign(_k=pd.to_numeric(efeitos.id_do_acordo, errors="coerce")).sort_values(
            ["_k", *efeitos.columns]).drop(columns="_k")
        acordos["_key"] = acordos.id_do_acordo + ":" + acordos.cnpj_do_sancionado
        prev = previous("leniencia")
        if prev is not None:
            prev["_key"] = prev.id_do_acordo + ":" + prev.cnpj_do_sancionado
        name = next(c for c in acordos.columns if c.startswith("razao_social"))
        ch = _changes(prev, acordos.assign(cnpj=acordos.cnpj_do_sancionado), "_key", "leniencia",
                      dates.get("acordos-leniencia", ""), name)
        ch["documento"] = ch.codigo.str.split(":").str[1]
        ch["codigo"] = ch.codigo.str.split(":").str[0]
        changes.append(ch)
        write_csv(acordos.drop(columns="_key"), data / "leniencia.csv")
        write_csv(efeitos, data / "leniencia_efeitos.csv")
        report["leniencia"] = len(acordos)

    log_path = data / "changes.csv"
    old = pd.read_csv(log_path, dtype=str, keep_default_na=False) if log_path.exists() else pd.DataFrame(columns=CHANGES)
    new = pd.concat([old, *[c[CHANGES] for c in changes if len(c)]], ignore_index=True).drop_duplicates()
    new = new.assign(_k=pd.to_numeric(new.codigo, errors="coerce")).sort_values(
        ["data", "lista", "mudanca", "_k", "codigo"]).drop(columns="_k")
    write_csv(new[CHANGES], log_path)
    report["changes_today"] = len(new) - len(old)

    used = set()
    for name in ("ceis", "cnep", "cepim"):
        p = data / f"{name}.csv"
        if p.exists():
            t = pd.read_csv(p, dtype=str, keep_default_na=False)
            if LONG in t:
                used |= set(t[LONG])
    ref = pd.DataFrame(sorted((k, v) for k, v in refs.items() if k in used), columns=["id", "texto"])
    write_csv(ref, data / "ref" / "fundamentacoes.csv")
    _log(" ".join(f"{k}={v}" for k, v in report.items()))
    return report
