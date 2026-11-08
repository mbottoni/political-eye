"""The ranking's table: allowance per month in office against the state, red flags beside it."""

import pandas as pd

from politicaleye.io import write_csv
from politicaleye.site import ranking as rk


def test_build(tmp_path):
    d = tmp_path / "data"
    write_csv(pd.DataFrame({"pessoa": ["camara:1", "camara:2"], "deputado_id": ["1", "2"], "nome": ["Ana", "Bia"], "partido": ["PA", "PB"], "uf": ["SP", "SP"],
                            "meses": ["20", "3"], "presenca": ["0.9", "0.5"], "votacoes_mandato": ["100", "20"], "projetos_autor": ["5", "0"],
                            "propostas_autor": ["9", "1"], "relatorias": ["2", "0"], "propostas_coautor": ["4", "1"], "cross_share": ["0.3", "0.1"],
                            "with_gov": ["0.5", "0.5"], "emendas_pago": ["0", "0"]}), d / "site" / "deputados" / "deputados_57.csv")
    write_csv(pd.DataFrame({"deputado_id": [1, 1, 2], "mes": [3, 4, 3], "subcota": [1, 5, 1], "valor": [1000.0, 1000.0, 600.0], "documentos": [1, 1, 1]}),
              d / "camara" / "cota" / "2024.csv")
    write_csv(pd.DataFrame({"deputado_id": [1], "mes": [1], "subcota": [1], "valor": [5000.0], "documentos": [1]}), d / "camara" / "cota" / "2023.csv")  # 56th
    write_csv(pd.DataFrame({"subcota": ["1", "5"], "descricao": ["ESCRITÓRIO", "DIVULGAÇÃO"]}), d / "camara" / "cota" / "subcotas.csv")
    write_csv(pd.DataFrame({"pessoa": ["camara:1"], "cnpj": ["1"]}), d / "site" / "alertas" / "campanha_emendas.csv")
    rk.build(d)
    r = pd.read_csv(d / "site" / "ranking" / "deputados_57.csv", dtype={"deputado_id": str}, keep_default_na=False).set_index("deputado_id")
    # January 2023 belongs to the 56th legislature, so Ana's 57th spending is 2,000 over 20 months.
    assert r.loc["1", "cota_total"] == 2000.0 and r.loc["1", "cota_mes"] == 100.0 and r.loc["1", "cota_divulgacao"] == 0.5
    assert r.loc["1", "cota_mes_uf"] == 100.0   # the state's median counts deputies with 12 months or more only
    assert r.loc["1", "alertas"] == "campanha_emendas" and r.loc["2", "alertas"] == ""
