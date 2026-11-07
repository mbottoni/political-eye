import datetime as dt

import pandas as pd

from politicaleye.siconfi import build as b


def a1(conta, coluna, valor):
    return {"anexo": "RGF-Anexo 01", "cod_conta": conta, "conta": conta, "coluna": coluna, "valor": valor}


def a5(conta, cod, valor):
    return {"anexo": "RGF-Anexo 05", "cod_conta": cod, "conta": conta, "coluna": "x", "valor": valor}


ITEMS = [
    a1("ReceitaCorrenteLiquidaLimiteLegal", "Valor", 100.0), a1("ReceitaCorrenteLiquidaAjustada", "Valor", 98.0),
    a1("DespesaComPessoalTotal", "Valor", 50.0), a1("DespesaComPessoalTotal", "% sobre a RCL Ajustada", 51.02),
    a1("DespesaComPessoalTotal", "<MR-11>", 4.0),
    a1("LimiteMaximoDespesaComPessoalTotal", "% sobre a RCL Ajustada", 54),
    a1("LimitePrudencialDespesaComPessoalTotal", "% sobre a RCL Ajustada", 51.3),
    a1("LimiteDeAlertaDespesaComPessoalTotal", "% sobre a RCL Ajustada", 48.6),
    a5("TOTAL DOS RECURSOS NÃO VINCULADOS (I)", "DisponibilidadeDeCaixaBruta", 10.0),
    a5("TOTAL DOS RECURSOS NÃO VINCULADOS (I)", "DisponibilidadeDeCaixaLiquidaAposRP", -2.5),
    a5("TOTAL DOS RECURSOS VINCULADOS AO RPPS (III)", "DisponibilidadeDeCaixaBruta", 99.0),
    a5("TOTAL (IV) = (I + II + III)", "DisponibilidadeDeCaixaBruta", 30.0),
    a5("TOTAL (IV) = (I + II + III)", "DisponibilidadeDeCaixaLiquidaAposRP", 12.0),
]


def test_parse():
    p = b.parse_pessoal(ITEMS)
    assert (p["rcl"], p["rcl_ajustada"], p["dtp"], p["dtp_pct"]) == (100.0, 98.0, 50.0, 51.02)
    assert (p["limite_maximo_pct"], p["limite_prudencial_pct"], p["limite_alerta_pct"]) == (54.0, 51.3, 48.6)
    assert p["situacao"] == "acima_alerta"
    assert b.parse_caixa(ITEMS) == {"bruta_livre": 10.0, "liquida_livre": -2.5, "bruta_total": 30.0, "liquida_total": 12.0}
    assert b.parse_caixa(ITEMS[:8]) is None                 # Anexo 05 only comes with the year's last report
    old = b.parse_caixa([a5("Total dos Recursos", "DisponibilidadeDeCaixaBruta", 7.0)])   # the 2015 label
    assert old["bruta_total"] == 7.0


def test_situacao_and_2015_layout():
    p = b.parse_pessoal([a1("DespesaComPessoalTotal", "% sobre a RCL", 55.0), a1("LimiteMaximoDespesaComPessoalTotal", "% sobre a RCL", 54)])
    assert p["situacao"] == "acima_maximo" and p["rcl_ajustada"] == ""


def test_candidates():
    nov = dt.date(2026, 11, 7)
    assert b.candidates(2024, nov) == [("Q", 3), ("S", 2)]
    assert b.candidates(2026, nov) == [("Q", 2), ("S", 1), ("Q", 1)]
    assert b.candidates(2026, dt.date(2026, 7, 1)) == [("Q", 1)]
    assert b.candidates(2025, dt.date(2026, 1, 15)) == [("Q", 3), ("S", 2), ("Q", 2), ("S", 1)]


def test_update_queue_and_resume(monkeypatch, tmp_path):
    ents = [{"cod_ibge": c, "ente": n, "uf": "SP", "regiao": "SE", "populacao": p, "cnpj": "1", "capital": "0  ",
             "esfera": "M"} for c, n, p in ((3550308, "São Paulo", 12000000), (3509502, "Campinas", 1100000))]
    ents.append({"cod_ibge": 35, "ente": "SP", "uf": "SP", "regiao": "SE", "populacao": 1, "cnpj": "1", "capital": "1",
                 "esfera": "E"})
    calls = []

    def rgf(ibge, ano, per, n):
        calls.append((ibge, ano, per, n))
        if ibge == "3509502" and per == "Q":   # Campinas reports by semester
            return []
        return ITEMS
    monkeypatch.setattr(b.fetch, "entes", lambda: ents)
    monkeypatch.setattr(b.fetch, "rgf", rgf)
    nov = dt.date(2026, 11, 7)
    r = b.update(tmp_path, today=nov, years=[2026, 2024], limit=3)
    assert calls[0][:2] == ("3550308", 2026)                # the biggest first, the year in progress first
    assert r == {"read": 3, "queued": 3, "left": 0, "with_report": 3, "stopped": ""}
    q = pd.read_csv(tmp_path / "consultas.csv", dtype=str)
    assert q[["cod_ibge", "ano", "periodicidade"]].values.tolist() == [   # sorted by year, then town
        ["3550308", "2024", "Q"], ["3509502", "2026", "S"], ["3550308", "2026", "Q"]]
    calls.clear()
    r = b.update(tmp_path, today=nov, years=[2026, 2024])
    assert r["queued"] == 1 and calls == [("3509502", 2024, "S", 2)]   # resumes; asks Campinas by semester first
    assert pd.read_csv(tmp_path / "entes.csv", dtype=str).cod_ibge.tolist() == ["3509502", "3550308"]
    pes = pd.read_csv(tmp_path / "pessoal" / "2024.csv", dtype=str)
    assert pes.columns.tolist() == b.PESSOAL and pes.periodicidade.tolist() == ["S", "Q"]
    assert (tmp_path / "caixa" / "2024.csv").exists()


def test_network_failures_are_retried_later(monkeypatch, tmp_path):
    ents = [{"cod_ibge": c, "ente": "x", "uf": "SP", "regiao": "SE", "populacao": 10 - c, "cnpj": "1", "capital": "0",
             "esfera": "M"} for c in range(1, 8)]
    monkeypatch.setattr(b.fetch, "entes", lambda: ents)

    def rgf(ibge, ano, per, n):
        if ibge == "1":
            return ITEMS
        raise RuntimeError("nodename nor servname provided")
    monkeypatch.setattr(b.fetch, "rgf", rgf)
    r = b.update(tmp_path, today=dt.date(2026, 11, 7), years=[2024])
    assert r["read"] == 1 and r["stopped"].startswith("5 failures in a row")
    q = pd.read_csv(tmp_path / "consultas.csv", dtype=str)
    assert q.cod_ibge.tolist() == ["1"]                       # the failed ones stay in the queue
