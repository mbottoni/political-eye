"""The change logs and feeds on a tiny world: a few sanctions, two builds of the red flags and of the amendment
payments, a week of contracts and a month of roll calls."""

import json
import xml.etree.ElementTree as ET

import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import mudancas as m

from .test_sancoes import CEIS_COLS, sanction

ATOM = {"a": "http://www.w3.org/2005/Atom"}
CO, GONE, MEI, BIG = "11111111000111", "22222222000122", "44444444000144", "55555555000155"
PERSON_NAME, MEI_NAME = "FULANO DE TAL", "12.345.678 JOAO SILVA"


def world(tmp_path):
    d = tmp_path / "data"
    sc = d / "sancoes"
    write_csv(pd.DataFrame([
        sanction("1", "J", CO, "BARRED LTDA", "Impedimento/proibição de contratar com prazo determinado", "2026-11-01", "2027-11-01",
                 "Todas as Esferas em todos os Poderes", "MUNICIPAL", uf="SP"),
        sanction("3", "F", "***.462.240-**", PERSON_NAME, "Suspensão", "2026-11-01", "", "", "ESTADUAL"),
        sanction("4", "J", MEI, MEI_NAME, "Suspensão", "2026-11-01", "", "", "ESTADUAL"),
    ]), sc / "ceis.csv")
    write_csv(pd.DataFrame(columns=[*CEIS_COLS, "valor_da_multa"]), sc / "cnep.csv")
    write_csv(pd.DataFrame([
        {"data": "2026-11-12", "lista": "ceis", "codigo": "1", "mudanca": "entrou", "tipo_de_pessoa": "J", "documento": CO, "nome": "BARRED LTDA"},
        {"data": "2026-11-12", "lista": "ceis", "codigo": "3", "mudanca": "entrou", "tipo_de_pessoa": "F", "documento": "***.462.240-**", "nome": PERSON_NAME},
        {"data": "2026-11-13", "lista": "ceis", "codigo": "4", "mudanca": "entrou", "tipo_de_pessoa": "J", "documento": MEI, "nome": MEI_NAME},
        {"data": "2026-11-13", "lista": "cnep", "codigo": "9", "mudanca": "saiu", "tipo_de_pessoa": "J", "documento": GONE, "nome": "GONE SA"},
        {"data": "2026-07-01", "lista": "ceis", "codigo": "8", "mudanca": "saiu", "tipo_de_pessoa": "J", "documento": GONE, "nome": "GONE SA"},   # outside the window
    ]), sc / "changes.csv")
    (sc / "sources.json").write_text(json.dumps({"ceis": {"date": "2026-11-13"}}))

    # Red flags as the red-flags page wrote them on its first build.
    al = d / "site" / "alertas"
    (al / "resumo.json").parent.mkdir(parents=True)
    (al / "resumo.json").write_text("{}")
    write_csv(pd.DataFrame([contract("c-1", "2026-10-01", 50_000.0)]), al / "contratos_impedidas.csv")
    write_csv(pd.DataFrame([barred(CO, "BARRED LTDA", "0")]), al / "emendas_impedidas.csv")

    # Amendment payments as the amendments file had them on Nov 12.
    em = d / "emendas"
    write_csv(pd.DataFrame([
        {"codigo": "E1", "autor_codigo": "901", "autor": "BANCADA DO ACRE", "tipo": "bancada"},
    ]), em / "emendas" / "2026.csv")
    write_csv(pd.DataFrame({"favorecido": [CO, BIG], "nome": ["BARRED LTDA", "FUNDO ESTADUAL DE SAUDE"], "natureza_juridica": ["Sociedade Empresária Limitada", "Fundo Público"],
                            "tipo": "Pessoa Jurídica"}), em / "favorecidos.csv")
    write_csv(pd.DataFrame([payment("E1", "2026-10", BIG, 6_000_000.0)]), em / "pagamentos" / "2026.csv")
    (em / "sources.json").write_text(json.dumps({"EmendasParlamentares": {"last_modified": "Thu, 12 Nov 2026 19:00:00 GMT"}}))

    # A week of contracts: one large, one smaller, one typo, all published in the window.
    write_csv(pd.DataFrame([
        pncp("k-1", "2026-11-05", 150e6, 150e6, BIG, "OBRAS SA"),
        pncp("k-2", "2026-11-05", 50e6, 50e6, CO, "BARRED LTDA"),
        pncp("k-3", "2026-11-06", 20e9, 20e9, CO, "BARRED LTDA"),   # over R$ 10 bn: a typo, left out
    ]), d / "pncp" / "contratos" / "2026-11.csv")
    write_csv(pd.DataFrame({"dia": ["2026-11-05", "2026-11-06"], "publicados": ["10", "12"], "atualizados": ["", ""]}), d / "pncp" / "dias.csv")

    write_csv(pd.DataFrame({"id": ["a", "b"], "data": ["2026-11-03", "2026-11-04"]}), d / "camara" / "votacoes" / "2026-11.csv")
    return d


def contract(controle, signed, value):
    return {"controle": controle, "assinatura": signed, "orgao": "MUNICIPIO X", "esfera": "M", "uf": "SP", "cnpj": CO, "nome": "BARRED LTDA", "pf": "0",
            "objeto": "OBRAS", "valor": value, "categoria_sancao": "Suspensão", "sancao_inicio": "2020-01-01", "sancao_fim": "", "orgao_sancionador": "X"}


def barred(cnpj, nome, pf):
    return {"cnpj": cnpj, "nome": nome, "pf": pf, "pessoa": "", "deputado_id": "", "senador_id": "", "casa": "", "leg": "0", "autor": "BANCADA DO ACRE",
            "tipo": "bancada", "partido": "", "uf": "", "barrado": "sim", "valor": 1000.0, "pagamentos": "1", "primeiro": "2026-11", "ultimo": "2026-11"}


def payment(code, month, fav, value):
    return {"codigo_emenda": code, "ano_mes": month, "favorecido": fav, "tipo_favorecido": "Pessoa Jurídica", "uf": "AC", "municipio": "RIO BRANCO",
            "n_favorecidos": "1", "valor": value}


def pncp(controle, published, initial, glob, supplier, name):
    return {"controle": controle, "compra": "", "publicacao": published, "assinatura": published, "vigencia_inicio": "", "vigencia_fim": "",
            "orgao_cnpj": "99999999000199", "orgao": "ESTADO Y", "esfera": "E", "poder": "E", "uf": "RJ", "municipio_ibge": "3304557",
            "tipo": "Contrato", "categoria": "Obras", "fornecedor_tipo": "PJ", "fornecedor": supplier, "fornecedor_nome": name,
            "objeto": "PONTE", "valor_inicial": initial, "valor_global": glob, "retificacao": "0"}


def log(d, fonte):
    return pd.read_csv(d / "site" / "mudancas" / f"{fonte}.csv", dtype=str, keep_default_na=False)


def every_file(d):
    return {p: p.read_bytes() for root in (d / "site" / "mudancas", d.parent / "docs" / "feeds") for p in sorted(root.rglob("*")) if p.is_file()}


def test_sanctions_name_companies_and_count_people(tmp_path):
    d = world(tmp_path)
    m.build(d)
    t = log(d, "sancoes")
    assert set(t.tipo) == {"ceis_entrou", "ceis_entrou_pessoas", "cnep_saiu"}   # the July exit is outside the 90 days
    co = t[t.chave == f"ceis:entrou:{CO}"].iloc[0]
    assert co.titulo == "BARRED LTDA" and "Impedimento, com prazo" in co.detalhe and "Contracting ban" in co.detalhe_en and "01/11/2027" in co.detalhe
    assert t[t.tipo == "ceis_entrou_pessoas"].n.tolist() == ["1"]
    mei = t[t.chave == f"ceis:entrou:{MEI}"].iloc[0]
    assert mei.titulo == "" and mei.pf == "1"   # an individual firm keeps its CNPJ, not its name
    meta = json.loads((d / "site" / "mudancas" / "sancoes.json").read_text())
    assert [x["data"] for x in meta["dias"]] == ["2026-11-13", "2026-11-12"]
    assert meta["dias"][1]["resumo"] == "CEIS: 1 empresa entrou; 1 pessoa entrou"
    # No person's name, and no individual firm's, in any log or feed.
    for p, b in every_file(d).items():
        text = b.decode()
        assert PERSON_NAME not in text and "JOAO SILVA" not in text, p


def test_compared_logs_start_quiet_then_list_what_is_new(tmp_path):
    d = world(tmp_path)
    m.build(d)
    assert log(d, "alertas").empty and log(d, "emendas").empty   # the first build only records what is there
    # The next day: a recent contract, an old one (history being read), an individual firm the page let through.
    al = d / "site" / "alertas"
    write_csv(pd.DataFrame([contract("c-1", "2026-10-01", 50_000.0), contract("c-2", "2026-11-10", 70_000.0), contract("c-3", "2024-03-01", 9_000.0)]),
              al / "contratos_impedidas.csv")
    write_csv(pd.DataFrame([barred(CO, "BARRED LTDA", "0"), barred(MEI, MEI_NAME, "0")]), al / "emendas_impedidas.csv")
    (d / "sancoes" / "sources.json").write_text(json.dumps({"ceis": {"date": "2026-11-14"}}))
    write_csv(pd.DataFrame([payment("E1", "2026-10", BIG, 6_000_000.0), payment("E1", "2026-11", BIG, 7_500_000.0), payment("E1", "2026-11", CO, 4_000_000.0)]),
              d / "emendas" / "pagamentos" / "2026.csv")
    (d / "emendas" / "sources.json").write_text(json.dumps({"EmendasParlamentares": {"last_modified": "Fri, 13 Nov 2026 19:00:00 GMT"}}))
    m.build(d)
    a = log(d, "alertas")
    assert set(a.data) == {"2026-11-14"}
    assert a[a.tipo == "contratos_impedidas"].chave.tolist() == ["c-2"]
    old = a[a.tipo == "contratos_impedidas_historico"].iloc[0]
    assert old.n == "1" and float(old.valor) == 9000.0
    firm = a[a.tipo == "emendas_impedidas"].iloc[0]
    assert firm.titulo == "" and firm.pf == "1" and "BANCADA DO ACRE" in firm.detalhe
    e = log(d, "emendas")
    assert e.chave.tolist() == [f"E1|2026-11|{BIG}"] and e.data.tolist() == ["2026-11-13"]   # under R$ 5 M is not listed
    assert "emenda de Bancada do Acre" in e.detalhe[0] and float(e.valor[0]) == 7_500_000.0
    # A third build with nothing new rewrites nothing, byte for byte.
    first = every_file(d)
    m.build(d)
    assert every_file(d) == first
    # Another build on the same day that reads one more old contract adds it to the day's count.
    write_csv(pd.DataFrame([contract("c-1", "2026-10-01", 50_000.0), contract("c-2", "2026-11-10", 70_000.0), contract("c-3", "2024-03-01", 9_000.0),
                            contract("c-4", "2024-02-01", 1_000.0)]), al / "contratos_impedidas.csv")
    m.build(d)
    old = log(d, "alertas").query("tipo == 'contratos_impedidas_historico'").iloc[0]
    assert old.n == "2" and float(old.valor) == 10_000.0


def test_contracts_use_the_contracts_page_rules(tmp_path):
    d = world(tmp_path)
    m.build(d)
    t = log(d, "pncp")
    assert t.chave.tolist() == ["k-1"] and t.data.tolist() == ["2026-11-05"]   # R$ 50 M is under the line; R$ 20 bn is a typo
    meta = json.loads((d / "site" / "mudancas" / "pncp.json").read_text())
    assert meta["cobertura"]["dias_lidos"] == 2 and meta["cobertura"]["dias"] == m.WINDOW and meta["cobertura"]["implausiveis"] == 1
    c = log(d, "camara")
    assert c.chave.tolist() == ["2026-11"] and c.data.tolist() == ["2026-11-03"] and c.n.tolist() == ["2"]


def test_feeds(tmp_path):
    d = world(tmp_path)
    m.build(d)
    docs = d.parent / "docs" / "feeds"
    pt = ET.parse(docs / "todas.xml").getroot()
    es = pt.findall("a:entry", ATOM)
    ids = [e.find("a:id", ATOM).text for e in es]
    assert len(ids) == len(set(ids))
    assert "tag:mbottoni.github.io,2026:political-eye/sancoes/2026-11-13" in ids
    assert {e.find("a:category", ATOM).get("term") for e in es} == {"sancoes", "pncp", "camara"}
    # The feed is as new as its newest entry, never as the run.
    assert pt.find("a:updated", ATOM).text == max(e.find("a:updated", ATOM).text for e in es) == "2026-11-13T12:00:00Z"
    en = ET.parse(docs / "en" / "all.xml").getroot()
    assert en.get("{http://www.w3.org/XML/1998/namespace}lang") == "en"
    first = en.find("a:entry", ATOM)
    assert first.find("a:title", ATOM).text.startswith("Sanctions, 13 Nov 2026:") and first.find("a:id", ATOM).text.endswith("/en/sancoes/2026-11-13")
    assert "lang=en" in first.find("a:link", ATOM).get("href")
    for f in m.FONTES:
        assert ET.parse(docs / f"{f}.xml").getroot().find("a:title", ATOM) is not None


def test_formats():
    assert m.brl(7_500_000, "pt") == "R$ 7,5 mi" and m.brl(7_500_000, "en") == "R$ 7.5 M" and m.brl(1.9e9, "pt") == "R$ 1,9 bi"
    assert m.brl(150e6, "en") == "R$ 150 M" and m.brl(999_999_999, "pt") == "R$ 1,0 bi"
    assert m.day("2026-11-05", "pt") == "05/11/2026" and m.day("2026-11-05", "en") == "5 Nov 2026"
    assert m.cnpj(CO) == "11.111.111/0001-11" and m.month("2026-11", "en", short=True) == "Nov 2026"
