"""The town profiles on a tiny world: two towns in SP and one in RJ, two deputies, a bench, a fund, a bank,
a barred supplier and a person's firm."""

import json

import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import municipios as m

ALDEIA, BAIRRO, COSTA = "3500105", "3500204", "3300100"
FUND, ASSOC, BANK, FIRM, PERSON_FIRM = "55555555000155", "66666666000166", "00000000000191", "77777777000177", "88888888000188"
CONTRACT = {"compra": "", "vigencia_inicio": "", "vigencia_fim": "", "poder": "E", "uf": "SP", "tipo": "Contrato", "categoria": "Obras",
            "fornecedor_tipo": "PJ", "objeto": "OBRA", "retificacao": "0"}


def world(tmp_path):
    d = tmp_path / "data"
    write_csv(pd.DataFrame([
        {"cod_ibge": ALDEIA, "ente": "Aldeia", "uf": "SP", "regiao": "SE", "populacao": "10000", "cnpj": "11111111000111", "capital": "0"},
        {"cod_ibge": BAIRRO, "ente": "Bairro", "uf": "SP", "regiao": "SE", "populacao": "200000", "cnpj": "22222222000122", "capital": "0"},
        {"cod_ibge": COSTA, "ente": "Costa", "uf": "RJ", "regiao": "SE", "populacao": "15000", "cnpj": "33333333000133", "capital": "0"}]),
        d / "siconfi" / "entes.csv")
    # Two deputies (PT and PL), each with an amendment author code.
    write_csv(pd.DataFrame({"pessoa": ["camara:1", "camara:1", "camara:2", "camara:2"], "fonte": ["camara", "emendas", "camara", "emendas"],
                            "id": ["1", "901", "2", "902"], "nome": ["Ana Lima", "ANA LIMA", "Beto Souza", "BETO SOUZA"], "metodo": ""}), d / "ref" / "politicians.csv")
    for month in ("2025-05", "2025-06"):
        write_csv(pd.DataFrame({"deputado_id": ["1", "2"], "nome": ["Ana Lima", "Beto Souza"], "partido": ["PT", "PL"], "uf": ["SP", "SP"],
                                "n_votes": "1", "n_authored": "0"}), d / "camara" / "deputies" / f"{month}.csv")
    write_csv(pd.DataFrame({"pessoa": ["camara:1"], "deputado_id": ["1"], "nome": ["Ana Lima"], "partido": ["PT"], "uf": ["SP"]}), d / "views" / "deputados_57.csv")
    write_csv(pd.DataFrame([{"codigo": c, "ano": "2025", "tipo": t, "autor_codigo": a, "autor": n}
                            for c, t, a, n in (("P1", "especial", "901", "ANA LIMA"), ("I1", "individual", "901", "ANA LIMA"),
                                               ("I2", "individual", "902", "BETO SOUZA"), ("B1", "bancada", "", "BANCADA DE SAO PAULO"))]),
              d / "emendas" / "emendas" / "2025.csv")
    pay = lambda code, month, who, town, value: {"codigo_emenda": code, "ano_mes": month, "favorecido": who, "tipo_favorecido": "Pessoa Jurídica",
                                                 "uf": "SP" if town != "BRASÍLIA" else "DF", "municipio": town, "n_favorecidos": "1", "valor": value}
    write_csv(pd.DataFrame([
        pay("P1", "2025-05", "11111111000111", "ALDEIA", "50000.00"),    # Pix to the town's own CNPJ (Ana, PT)
        pay("I1", "2025-06", FUND, "ALDEIA", "30000.00"),                # its health fund (Ana, PT)
        pay("I2", "2025-06", "11111111000111", "ALDEIA", "20000.00"),    # Beto, PL
        pay("", "2025-06", "11111111000111", "ALDEIA", "1000.00"),       # no amendment code
        pay("I1", "2025-06", ASSOC, "ALDEIA", "7000.00"),                # a private association based there: apart
        pay("I1", "2025-06", BANK, "BRASÍLIA", "99999.00"),              # the bank in Brasília: left out
        pay("B1", "2025-06", "22222222000122", "BAIRRO", "100000.00"),   # the state bench, no party
        pay("I2", "2025-06", "22222222000122", "BAIRRO", "80000.00")]),  # Beto, PL
        d / "emendas" / "pagamentos" / "2025.csv")
    write_csv(pd.DataFrame([pay("I2", "2026-02", "22222222000122", "BAIRRO", "10.00")]), d / "emendas" / "pagamentos" / "2026.csv")
    write_csv(pd.DataFrame({"favorecido": [FUND, ASSOC, BANK], "nome": ["FUNDO MUNICIPAL DE SAUDE DE ALDEIA", "ASSOCIACAO X", "BANCO DO BRASIL SA"],
                            "natureza_juridica": ["Fundo Público da Administração Direta Municipal", "Associação Privada", "Sociedade de Economia Mista"],
                            "tipo": "Pessoa Jurídica"}), d / "emendas" / "favorecidos.csv")
    write_csv(pd.DataFrame([{"ano": "2024", "cod_ibge": c, "municipio": c, "uf": u, "sg_ue": "", "eleicao": "Eleições Municipais 2024", "data_eleicao": "2024-10-06",
                             "suplementar": "0", "turno": "1", "sq_candidato": c, "nome_urna": f"PREFEITO {c}", "partido": p, "genero": "", "cor_raca": ""}
                            for c, u, p in ((ALDEIA, "SP", "PT"), (BAIRRO, "SP", "DEM"), (COSTA, "RJ", "PL"))]), d / "ref" / "prefeitos.csv")
    write_csv(pd.DataFrame({"nome": ["JOAO DA SILVA"]}), d / "tse" / "2022" / "candidatos.csv")

    lim = {"limite_maximo_pct": "54.0", "limite_prudencial_pct": "51.3", "limite_alerta_pct": "48.6"}
    write_csv(pd.DataFrame([{"cod_ibge": c, "ano": "2025", "periodicidade": "Q", "periodo": "3", "rcl": r, "rcl_ajustada": r, "dtp": "1", "dtp_pct": p, **lim, "situacao": s}
                            for c, r, p, s in ((ALDEIA, "50000000", "44.00", ""), (BAIRRO, "900000000", "55.00", "acima_maximo"))]),
              d / "siconfi" / "pessoal" / "2025.csv")
    write_csv(pd.DataFrame([{"cod_ibge": ALDEIA, "ano": "2025", "periodicidade": "Q", "periodo": "3", "bruta_livre": "0", "liquida_livre": "-20000",
                             "bruta_total": "0", "liquida_total": "0"}]), d / "siconfi" / "caixa" / "2025.csv")
    write_csv(pd.DataFrame([{"cod_ibge": c, "ano": "2025", "periodicidade": "Q", "periodo": "3", "linhas": n, "consultado_em": "2026-11-07"}
                            for c, n in ((ALDEIA, "10"), (BAIRRO, "10"), (COSTA, "0"))]), d / "siconfi" / "consultas.csv")

    c = lambda ctl, who, name, value, esfera="M": {"controle": ctl, "publicacao": "2025-10-01", "assinatura": "2025-09-30", "orgao_cnpj": "11111111000111",
                                                   "orgao": "MUNICIPIO DE ALDEIA", "esfera": esfera, "municipio_ibge": ALDEIA, "fornecedor": who,
                                                   "fornecedor_nome": name, "valor_inicial": value, "valor_global": value, **CONTRACT}
    write_csv(pd.DataFrame([c("C1", FIRM, "CONSTRUTORA X LTDA", "2000000.00"), c("C2", PERSON_FIRM, "JOAO DA SILVA ME", "1500000.00"),
                            c("C3", FIRM, "CONSTRUTORA X LTDA", "50000000000.00"),          # a typo: left out
                            c("C4", FIRM, "CONSTRUTORA X LTDA", "9000000.00", esfera="E")]),  # a state body in town: not the town's
              d / "pncp" / "contratos" / "2025-10.csv")
    sanc = {"lista": "ceis", "categoria_sancao": "Impedimento/proibição de contratar com prazo determinado", "sancao_inicio": "2025-01-01",
            "sancao_fim": "2027-01-01", "abrangencia": "", "orgao_sancionador": "PREFEITURA DE ALDEIA", "esfera_sancionador": "MUNICIPAL", "uf_sancionador": "SP"}
    write_csv(pd.DataFrame([{**c("C1", FIRM, "CONSTRUTORA X LTDA", "2000000.00"), **sanc, "codigo_sancao": "1", "cobre": "sim"},
                            {**c("C5", FIRM, "CONSTRUTORA X LTDA", "5000.00"), **sanc, "codigo_sancao": "2", "cobre": "nao"}]),
              d / "pncp" / "contratos_sancionados.csv")
    write_csv(pd.DataFrame({"dia": ["2025-10-01"], "publicados": ["10"], "atualizados": [""]}), d / "pncp" / "dias.csv")
    return d


def test_helpers():
    assert m.today("PMDB") == "MDB" and m.today("PRP") == "PRD" and m.today("DEM") == "UNIÃO" and m.today("S.PART.") == ""
    v = pd.Series([1.0, 2.0, 2.0, None, 5.0])
    assert m.percentile(v, [pd.Series(["a", "a", "a", "a", "b"])]).round(4).tolist()[:3] == [0.1667, 0.6667, 0.6667]
    names = pd.Series(["P R C DUARTE", "JOAO DA SILVA ME", "CONSTRUTORA X LTDA", "J A COMERCIO", "DUARTE S.A.", "JOAO DE SA", "FULANO"])
    hide = m.is_personal(pd.Series(["1", "2", "3", "4", "5", "6", "***.123.456-**"]), names, pd.Series(["PJ", "PJ", "PJ", "PJ", "PJ", "PJ", "PF"]),
                         pd.Series("", index=names.index), {"DUARTE", "JOAO", "SILVA", "SA", "S", "A"})
    assert hide.tolist() == [True, True, False, False, False, True, True]


def test_build(tmp_path):
    d = world(tmp_path)
    m.build(d)
    out = d / "site" / "municipios"
    a = json.loads((out / "perfil" / "3500.json").read_text())
    town, bairro = a[ALDEIA], a[BAIRRO]
    assert town["n"] == "Aldeia" and town["k"] == "5k–20k" and town["m"][0][2:4] == [f"PREFEITO {ALDEIA}", "PT"]
    # Pix, the fund and the no-code payment count; the association is apart; the bank is left out.
    y = dict(zip(["ano", "total", *m.TIPOS, "municipal", "privado", "mesmo", "conhecido"], town["a"]["y"][0]))
    assert y["ano"] == 2025 and y["total"] == 101000 and y["especial"] == 50000 and y["individual"] == 50000 and y[""] == 1000
    assert y["municipal"] == 30000 and y["privado"] == 7000
    # The mayor is PT: Ana's 80,000 of the 100,000 whose author's party is known; the state's mix gives PT 80 of 180.
    assert y["mesmo"] == 80000 and y["conhecido"] == 100000
    share, base, known = town["a"]["mp"]
    assert share == 0.8 and abs(base - 80 / 180) < 1e-4 and known == 100000
    au = town["a"]["au"]
    assert au[0][:6] == ["p", "Ana Lima", "PT", "camara", 80000, 50000] and au[0][8] == "57:1"
    assert au[1][:3] == ["p", "Beto Souza", "PL"] and au[-1][0] == "n"
    assert town["a"]["pa"] == [["PT", 80000], ["PL", 20000]]
    # Bairro's mayor is DEM, counted as UNIÃO in 2025: no member of that party sent it money (80,000 in 2025, 10 in 2026).
    assert bairro["a"]["au"][0][:2] == ["c", "Bancada de Sao Paulo"] and bairro["a"]["mp"] == [0.0, 0.0, 80010]
    # Contracts: the typo and the state body's contract are out; the barred supplier is flagged; the person's firm unnamed.
    c = town["c"]
    assert c["n"] == 2 and c["v"] == 3500000 and c["x"] == 1
    assert c["f"][0] == [FIRM, "CONSTRUTORA X LTDA", 1, 2000000, "sim"] and c["f"][1][1] == "" and c["f"][1][4] == ""
    assert c["s"] == {"nao": [1, 5000], "sim": [1, 2000000]} and len(c["sl"]) == 1 and c["sl"][0][6] == "sim"
    assert all(row[3] == "" for row in c["t"] if row[2] == "")   # no object for an unnamed supplier
    # Siconfi, the ranks among the state's towns, and a town that filed no report.
    assert town["f"]["y"] == [[2025, 44.0, "abaixo", 50000000, 1, -20000]]
    assert town["r"]["dtp_pct"] == [2025, 44.0, 0.25, 0.5] and bairro["r"]["dtp_pct"][2] == 0.75
    assert town["r"]["emendas_hab"][:3] == [2025, 10.1, 0.75] and town["r"]["caixa_hab"][1] == -2.0
    costa = json.loads((out / "perfil" / "3300.json").read_text())[COSTA]
    assert costa["f"] == {"nf": [2025], "y": []} and costa["a"]["y"] == [] and costa["r"]["contratos_hab"][1] == 0
    r = json.loads((out / "resumo.json").read_text())
    assert r["ano_ref"] == 2025 and r["pncp"]["days_read"] == 1 and r["pncp"]["sancionados"]["sim"] == 1
    assert r["peers"]["emendas_hab"]["2025"]["SP"] == (10.1 + 0.9) / 2 and r["peers"]["dtp_pct"]["2025"]["SP"] == 49.5
    assert pd.read_csv(out / "index.csv", dtype=str).cod_ibge.tolist() == [COSTA, ALDEIA, BAIRRO]
    for p in out.rglob("*.*"):
        assert "JOAO DA SILVA" not in p.read_text(), p.name


def test_build_is_deterministic(tmp_path):
    d = world(tmp_path)
    m.build(d)
    first = {p: p.read_bytes() for p in (d / "site").rglob("*") if p.is_file()}
    m.build(d)
    assert first == {p: p.read_bytes() for p in (d / "site").rglob("*") if p.is_file()}


def test_reads_sanctions_by_month(tmp_path):
    """The same contracts from data/pncp/sancionados/YYYY-MM.csv, the layout that replaces the single file."""
    d = world(tmp_path)
    (d / "pncp" / "sancionados").mkdir()
    (d / "pncp" / "contratos_sancionados.csv").rename(d / "pncp" / "sancionados" / "2025-10.csv")
    m.build(d)
    town = json.loads((d / "site" / "municipios" / "perfil" / "3500.json").read_text())[ALDEIA]
    assert town["c"]["s"] == {"nao": [1, 5000], "sim": [1, 2000000]} and town["c"]["f"][0][4] == "sim"
