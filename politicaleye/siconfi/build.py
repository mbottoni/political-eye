"""Payroll and cash of every municipality, from their fiscal reports: ``data/siconfi/``.

    data/siconfi/entes.csv          every municipality: IBGE code, name, state, population, CNPJ
    data/siconfi/pessoal/YYYY.csv   payroll against the Fiscal Responsibility Law's limits (RGF Anexo 01)
    data/siconfi/caixa/YYYY.csv     cash at the end of the year (RGF Anexo 05)
    data/siconfi/consultas.csv      which report each row came from, and when it was read

One report per municipality and year: the year's last (3rd four-month period,
or 2nd semester for towns that report by semester), or, for the year in
progress, the latest one due. The API allows one call a second, so
:func:`update` works through a queue until a time budget runs out, saving
after every batch; the next run continues where it stopped. The biggest
municipalities come first. ``methodology/siconfi.md`` explains every rule.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
import time
from pathlib import Path

import pandas as pd

from ..io import write_csv
from . import fetch

FIRST_YEAR = 2015
MAX_FAILURES = 5           # consecutive failed municipality-years before a run stops (and saves)
REFRESH_DAYS = 25          # re-read the year in progress after this long (and last year's, January to March)
PESSOAL = ["cod_ibge", "ano", "periodicidade", "periodo", "rcl", "rcl_ajustada", "dtp", "dtp_pct",
           "limite_maximo_pct", "limite_prudencial_pct", "limite_alerta_pct", "situacao"]
CAIXA = ["cod_ibge", "ano", "periodicidade", "periodo", "bruta_livre", "liquida_livre", "bruta_total", "liquida_total"]
CONSULTAS = ["cod_ibge", "ano", "periodicidade", "periodo", "linhas", "consultado_em"]
ENTES = ["cod_ibge", "ente", "uf", "regiao", "populacao", "cnpj", "capital"]


def _log(msg: str) -> None:
    print(f"[siconfi] {msg}", file=sys.stderr, flush=True)


def candidates(ano: int, today: dt.date) -> list[tuple[str, int]]:
    """Reports to try for a year, best first: (periodicidade, periodo)."""
    if ano < today.year - 1 or (ano == today.year - 1 and today.month > 2):
        return [("Q", 3), ("S", 2)]
    if ano == today.year - 1:   # January and February: the year's last report is due on 30 January
        return [("Q", 3), ("S", 2), ("Q", 2), ("S", 1)]
    due = []
    if today.month >= 10:
        due += [("Q", 2), ("S", 1)]
    if today.month >= 6:
        due += [("Q", 1)]
    return due


def parse_pessoal(items: list[dict]) -> dict:
    """RCL, payroll (DTP), payroll as a share of RCL and the three limits, from Anexo 01."""
    a = [i for i in items if i.get("anexo") == "RGF-Anexo 01"]
    val = {(i["cod_conta"], "valor" if i["coluna"] == "Valor" else "pct" if i["coluna"].startswith("%") else "x"): i["valor"]
           for i in a}

    def get(conta: str, kind: str):
        v = val.get((conta, kind))
        return "" if v is None else round(float(v), 2)

    row = {
        "rcl": get("ReceitaCorrenteLiquidaLimiteLegal", "valor"), "rcl_ajustada": get("ReceitaCorrenteLiquidaAjustada", "valor"),
        "dtp": get("DespesaComPessoalTotal", "valor"), "dtp_pct": get("DespesaComPessoalTotal", "pct"),
        "limite_maximo_pct": get("LimiteMaximoDespesaComPessoalTotal", "pct"),
        "limite_prudencial_pct": get("LimitePrudencialDespesaComPessoalTotal", "pct"),
        "limite_alerta_pct": get("LimiteDeAlertaDespesaComPessoalTotal", "pct"),
    }
    row["situacao"] = situacao(row)
    return row


def situacao(r: dict) -> str:
    """Where payroll stands against the law's limits: ``acima_maximo``, ``acima_prudencial``, ``acima_alerta`` or ``""``."""
    p = r["dtp_pct"]
    if p == "":
        return ""
    for name in ("maximo", "prudencial", "alerta"):
        lim = r[f"limite_{name}_pct"]
        if lim != "" and p > lim:
            return f"acima_{name}"
    return ""


_TOTAL = re.compile(r"^(TOTAL \(|TOTAL DOS RECURSOS$)", re.I)
_LIVRE = re.compile(r"^TOTAL DOS RECURSOS N[ÃA]O VINCULADOS", re.I)


def parse_caixa(items: list[dict]) -> dict | None:
    """Gross and net (after carried-over commitments) cash, unrestricted and total, from Anexo 05."""
    a = [i for i in items if i.get("anexo") == "RGF-Anexo 05"]
    if not a:
        return None
    out = {"bruta_livre": "", "liquida_livre": "", "bruta_total": "", "liquida_total": ""}
    for i in a:
        conta = (i.get("conta") or "").strip()
        which = "livre" if _LIVRE.match(conta) else "total" if _TOTAL.match(conta) else None
        if which is None:
            continue
        if i["cod_conta"] == "DisponibilidadeDeCaixaBruta":
            out[f"bruta_{which}"] = round(float(i["valor"]), 2)
        elif i["cod_conta"] == "DisponibilidadeDeCaixaLiquidaAposRP":
            out[f"liquida_{which}"] = round(float(i["valor"]), 2)
    return out


def _read(path: Path, cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_csv(path, dtype=str, keep_default_na=False)[cols]


def _read_years(folder: Path, cols: list[str]) -> pd.DataFrame:
    parts = [_read(p, cols) for p in sorted(folder.glob("*.csv"))]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)


def _save(data: Path, ent: pd.DataFrame, pes: pd.DataFrame, cai: pd.DataFrame, con: pd.DataFrame) -> None:
    def order(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
        return df.assign(_c=pd.to_numeric(df.cod_ibge), _a=pd.to_numeric(df.ano)).sort_values(["_a", "_c", *by]).drop(
            columns=["_c", "_a"])

    for name, df, cols in (("pessoal", pes, PESSOAL), ("caixa", cai, CAIXA)):
        folder = data / name
        df = order(df.drop_duplicates(["cod_ibge", "ano"], keep="last"), [])[cols]
        for ano, part in df.groupby("ano"):
            write_csv(part, folder / f"{ano}.csv")
    write_csv(order(con.drop_duplicates(["cod_ibge", "ano"], keep="last"), [])[CONSULTAS], data / "consultas.csv")


def update(data: Path, *, hours: float = 5.0, today: dt.date | None = None, years: list[int] | None = None,
           limit: int | None = None) -> dict:
    """Work through the queue for ``hours`` (or ``limit`` municipality-years), saving as it goes."""
    today = today or dt.datetime.now(dt.UTC).date()
    deadline = time.monotonic() + hours * 3600
    e = pd.DataFrame(fetch.entes())
    e = e[e.esfera == "M"]
    ent = pd.DataFrame({"cod_ibge": e.cod_ibge.astype(str), "ente": e.ente.str.strip(), "uf": e.uf.str.strip(),
                        "regiao": e.regiao.str.strip(), "populacao": e.populacao.astype(str),
                        "cnpj": e.cnpj.astype(str).str.zfill(14), "capital": e.capital.astype(str).str.strip()})
    ent = ent.assign(_c=pd.to_numeric(ent.cod_ibge)).sort_values("_c").drop(columns="_c")[ENTES]
    write_csv(ent, data / "entes.csv")

    pes, cai = _read_years(data / "pessoal", PESSOAL), _read_years(data / "caixa", CAIXA)
    con = _read(data / "consultas.csv", CONSULTAS)
    seen = {(r.cod_ibge, r.ano): r.consultado_em for r in con.itertuples()}
    stale = (today - dt.timedelta(days=REFRESH_DAYS)).isoformat()
    by_pop = ent.assign(_p=pd.to_numeric(ent.populacao, errors="coerce").fillna(0)).sort_values(
        ["_p", "cod_ibge"], ascending=[False, True]).cod_ibge.tolist()
    all_years = years or list(range(today.year, FIRST_YEAR - 1, -1))
    recent = {today.year} | ({today.year - 1} if today.month <= 3 else set())
    queue = []
    for y in all_years:                       # refresh the recent years first, then fill the history, newest first
        if y in recent:
            queue += [(c, y) for c in by_pop if seen.get((c, str(y)), "") < stale]
    for y in all_years:
        if y not in recent:
            queue += [(c, y) for c in by_pop if (c, str(y)) not in seen]
    # A town reports by semester or by four-month period; ask in its last known rhythm first.
    rhythm = {r.cod_ibge: r.periodicidade for r in con.sort_values("ano").itertuples() if r.periodicidade}
    if limit is not None:
        queue = queue[:limit]
    _log(f"{len(queue)} municipality-years queued; {len(seen)} already read")

    new_p, new_c, new_q, done, failed, stopped = [], [], [], 0, 0, ""
    for cod, ano in queue:
        if time.monotonic() > deadline:
            break
        got = None
        tries = sorted(candidates(ano, today), key=lambda pn: pn[0] != rhythm.get(cod, "Q"))
        try:
            for per, n in tries:
                items = fetch.rgf(cod, ano, per, n)
                if items:
                    got = (per, n, items)
                    break
        except RuntimeError as e:   # left unrecorded, so the next run asks again
            failed += 1
            _log(f"{cod} {ano}: {e}")
            if failed >= MAX_FAILURES:
                stopped = f"{MAX_FAILURES} failures in a row; last: {e}"
                break
            continue
        failed = 0
        stamp = {"cod_ibge": cod, "ano": str(ano), "consultado_em": today.isoformat()}
        if got is None:
            new_q.append({**stamp, "periodicidade": "", "periodo": "", "linhas": "0"})
        else:
            per, n, items = got
            rhythm[cod] = per
            key = {"cod_ibge": cod, "ano": str(ano), "periodicidade": per, "periodo": str(n)}
            new_q.append({**stamp, **key, "linhas": str(len(items))})
            new_p.append({**key, **{k: str(v) for k, v in parse_pessoal(items).items()}})
            c = parse_caixa(items)
            if c:
                new_c.append({**key, **{k: str(v) for k, v in c.items()}})
        done += 1
        if done % 200 == 0:
            _save(data, ent, pd.concat([pes, pd.DataFrame(new_p, columns=PESSOAL)]),
                  pd.concat([cai, pd.DataFrame(new_c, columns=CAIXA)]), pd.concat([con, pd.DataFrame(new_q, columns=CONSULTAS)]))
            _log(f"{done}/{len(queue)} read")
    pes = pd.concat([pes, pd.DataFrame(new_p, columns=PESSOAL)], ignore_index=True)
    cai = pd.concat([cai, pd.DataFrame(new_c, columns=CAIXA)], ignore_index=True)
    con = pd.concat([con, pd.DataFrame(new_q, columns=CONSULTAS)], ignore_index=True)
    _save(data, ent, pes, cai, con)
    report = {"read": done, "queued": len(queue), "left": len(queue) - done,
              "with_report": sum(q["linhas"] != "0" for q in new_q), "stopped": stopped}
    _log(" ".join(f"{k}={v}" for k, v in report.items()))
    return report
