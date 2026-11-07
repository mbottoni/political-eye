import csv
import io
import json
import zipfile

import pandas as pd

from politicaleye.ref import politicians as P


def write_inputs(root):
    raw, data = root / "raw", root / "data" / "ref"
    raw.mkdir(parents=True)
    rows = [  # uri, nome, legIni, legFim, nomeCivil, cpf, sexo, rede, site, nascimento, falecimento, ufNasc, munNasc
        ["https://x/deputados/1", "Esperidião Amin", "55", "55", "ESPERIDIÃO AMIN HELOU FILHO", "", "M", "", "", "1947-12-21", "", "SC", ""],
        ["https://x/deputados/2", "Ana Paula", "56", "57", "ANA PAULA SOUZA", "", "F", "", "", "1980-01-01", "", "SP", ""],
        ["https://x/deputados/3", "Ana Paula", "57", "57", "ANA PAULA LIMA", "", "F", "", "", "1975-05-05", "", "SC", ""],
        ["https://x/deputados/4", "Velho", "50", "53", "VELHO DEPUTADO", "", "M", "", "", "1940-01-01", "", "RJ", ""],
    ]
    s = io.StringIO()
    w = csv.writer(s, delimiter=";", quoting=csv.QUOTE_ALL)
    w.writerow(["uri", "nome", "idLegislaturaInicial", "idLegislaturaFinal", "nomeCivil", "cpf", "siglaSexo",
                "urlRedeSocial", "urlWebsite", "dataNascimento", "dataFalecimento", "ufNascimento", "municipioNascimento"])
    w.writerows(rows)
    (raw / "deputados.csv").write_text(s.getvalue(), encoding="utf-8-sig")
    sen = {"ListaParlamentarLegislatura": {"Parlamentares": {"Parlamentar": [
        {"IdentificacaoParlamentar": {"CodigoParlamentar": "22", "NomeParlamentar": "Esperidião Amin",
                                      "NomeCompletoParlamentar": "Esperidião Amin Helou Filho", "UfParlamentar": "SC"}}]}}}
    (raw / "senadores-56.json").write_text(json.dumps(sen))
    head = ["SQ_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "DS_CARGO", "SG_UF", "DT_NASCIMENTO"]
    for year, cand in {
        2018: [["901", "ANA PAULA SOUZA", "ANA PAULA", "DEPUTADO FEDERAL", "SP", "01/01/1980"],
               ["902", "ESPERIDIÃO AMIN HELOU FILHO", "AMIN", "SENADOR", "SC", "21/12/1947"]],
        2022: [["903", "ANA PAULA SOUZA", "ANA PAULA", "DEPUTADO FEDERAL", "SP", "01/01/1980"],   # runs again
               ["904", "ANA PAULA LIMA", "ANA PAULA", "DEPUTADO FEDERAL", "SC", ""]],             # no birth date
        2026: [["905", "ANA PAULA SOUSA MACHADO", "ANA PAULA", "DEPUTADO FEDERAL", "SP", "01/01/1980"]],  # respelled
    }.items():
        t = io.StringIO()
        w = csv.writer(t, delimiter=";", quoting=csv.QUOTE_ALL)
        w.writerow(head)
        w.writerows(cand)
        with zipfile.ZipFile(raw / f"consulta_cand_{year}.zip", "w") as z:
            z.writestr(f"consulta_cand_{year}_BRASIL.csv", t.getvalue().encode("latin1"))
    (root / "data" / "camara" / "deputies").mkdir(parents=True)
    pd.DataFrame({"deputado_id": ["2", "3"], "nome": ["Ana Paula"] * 2, "partido": ["PT", "PL"], "uf": ["SP", "SC"],
                  "n_votes": [1, 1], "n_authored": [0, 0]}).to_csv(root / "data" / "camara" / "deputies" / "2025-03.csv", index=False)
    (root / "data" / "emendas").mkdir(parents=True)
    pd.DataFrame({"autor_codigo": ["2210", "2850", "5000", "7121"],
                  "autor": ["ESPERIDIAO AMIN", "ESPERIDIAO AMIN", "ANA PAULA", "BANCADA DO RIO GRANDE DO NORTE"],
                  "ano": ["2020", "2017", "2024", "2024"], "tipo": "individual", "emendas": 1, "empenhado": "1.00",
                  "liquidado": "0.00", "pago": "0.00"}).to_csv(root / "data" / "emendas" / "por_autor.csv", index=False)
    return raw, data


def test_crosswalk(tmp_path):
    raw, data = write_inputs(tmp_path)
    r = P.build(raw, data)
    x = pd.read_csv(data / "politicians.csv", dtype=str, keep_default_na=False)
    assert x.columns.tolist() == P.COLS
    who = x.set_index(["fonte", "id"]).pessoa
    amin = who[("camara", "1")]
    assert amin == "camara:1"
    assert who[("senado", "22")] == who[("tse", "902")] == amin               # deputy, then senator
    assert who[("emendas", "2210")] == who[("emendas", "2850")] == amin       # one code per mandate
    assert who[("tse", "901")] == who[("tse", "903")] == "camara:2"          # the same person, two elections
    assert who[("tse", "904")] == "camara:3"                                   # no birth date: name + state
    assert who[("tse", "905")] == "camara:2"                                   # birth date, first name, state
    assert ("emendas", "5000") not in who.index                                # two deputies called Ana Paula
    assert ("emendas", "7121") not in who.index                                # a bench, not a person
    assert ("camara", "4") not in who.index                                    # left before 2011
    m = x.set_index(["fonte", "id"]).metodo
    assert m[("tse", "901")] == "nome_civil+nascimento" and m[("tse", "904")] == "nome_civil+uf"
    assert m[("camara", "1")] == ""
    assert r["autores_ligados"] == 2


def test_overrides(tmp_path):
    raw, data = write_inputs(tmp_path)
    ov = tmp_path / "overrides.csv"
    ov.write_text("fonte,id,pessoa\nemendas,5000,camara:3\n")
    P.build(raw, data, ov)
    x = pd.read_csv(data / "politicians.csv", dtype=str, keep_default_na=False).set_index(["fonte", "id"])
    assert x.loc[("emendas", "5000")].tolist() == ["camara:3", "ANA PAULA", "manual"]   # added by hand


def test_norm_and_years():
    assert P.norm("Acácio da Silva  Favacho-Neto") == "ACACIO DA SILVA FAVACHO NETO"
    assert list(P.leg_years(57)) == [2023, 2024, 2025, 2026, 2027]
