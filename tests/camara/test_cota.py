"""The office-allowance (CEAP) tables from a tiny copy of the Câmara's yearly file."""

import zipfile

import pandas as pd

from politicaleye.camara import cota

HEAD = ['txNomeParlamentar', 'cpf', 'ideCadastro', 'nuCarteiraParlamentar', 'nuLegislatura', 'sgUF', 'sgPartido', 'codLegislatura', 'numSubCota',
        'txtDescricao', 'numEspecificacaoSubCota', 'txtDescricaoEspecificacao', 'txtFornecedor', 'txtCNPJCPF', 'txtNumero', 'indTipoDocumento',
        'datEmissao', 'vlrDocumento', 'vlrGlosa', 'vlrLiquido', 'numMes', 'numAno', 'numParcela', 'txtPassageiro', 'txtTrecho', 'numLote',
        'numRessarcimento', 'datPagamentoRestituicao', 'vlrRestituicao', 'nuDeputadoId', 'ideDocumento', 'urlDocumento']


def row(ide, sub, desc, value, mes, ano, who="DEP A", cpf="12345678900", supplier="JOAO DA SILVA", doc="***.123.456-**"):
    r = dict.fromkeys(HEAD, "")
    r.update(txNomeParlamentar=who, cpf=cpf, ideCadastro=ide, numSubCota=sub, txtDescricao=desc, txtFornecedor=supplier, txtCNPJCPF=doc,
             vlrLiquido=value, numMes=mes, numAno=ano, txtPassageiro="FULANO DE TAL")
    return r


def test_build_year(tmp_path):
    raw, data = tmp_path / "raw", tmp_path / "data"
    raw.mkdir()
    rows = [row("", "1", "MANUTENÇÃO DE ESCRITÓRIO", "500", "2", "2024", who="LIDERANÇA DO PT"),   # a leadership office: dropped
            row("10", "1", "MANUTENÇÃO DE ESCRITÓRIO", "100.5", "2", "2024"), row("10", "1", "MANUTENÇÃO DE ESCRITÓRIO", "-20", "2", "2024"),
            row("10", "5", "DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR.", "300", "3", "2024"),
            row("10", "5", "DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR.", "999", "12", "2023")]                 # another year's receipt: dropped
    text = "﻿" + ";".join(f'"{h}"' for h in HEAD) + "\n" + "\n".join(";".join(f'"{r[h]}"' for h in HEAD) for r in rows) + "\n"
    with zipfile.ZipFile(raw / "Ano-2024.csv.zip", "w") as z:
        z.writestr("Ano-2024.csv", text)
    rep = cota.build_year(2024, raw, data)
    t = pd.read_csv(data / "cota" / "2024.csv")
    assert t.values.tolist() == [[10, 2, 1, 80.5, 2], [10, 3, 5, 300.0, 1]] and rep["deputies"] == 1
    assert pd.read_csv(data / "cota" / "subcotas.csv").subcota.tolist() == [1, 5]
    # Only sums: no CPF, supplier or passenger reaches the repository.
    for p in (data / "cota").glob("*.csv"):
        text = p.read_text()
        assert "12345678900" not in text and "SILVA" not in text and "FULANO" not in text
