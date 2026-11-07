# Emendas: methodology

Parliamentary amendments (*emendas parlamentares*) are the slices of the
federal budget that deputies, senators, state benches and committees direct
to places and projects of their choosing. This source records each one,
how much of it has been committed, settled and paid, and who received the
money.

## Source

One zip from the Portal da Transparência (CGU), regenerated every night,
with every amendment since 2014:

`https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO`
(redirects to `dadosabertos-download.cgu.gov.br/.../EmendasParlamentares.zip`,
about 32 MB; three latin-1, `;`-separated CSVs)

| file | what it gives us |
|---|---|
| `EmendasParlamentares.csv` | each amendment by place of application and budget line (function, subfunction, program, action, budget plan), with the amounts committed (*empenhado*), settled (*liquidado*) and paid, and the carried-over balances (*restos a pagar*) |
| `EmendasParlamentares_PorFavorecido.csv` | who received the money, month by month |
| `EmendasParlamentares_Convenios.csv` | the agreements (*convênios*) that carry the money to states, towns and organisations |

The amounts are cumulative as of the file's date: the daily job rebuilds
every table, and each commit's diff is what was committed or paid that day.
`data/emendas/sources.json` records the zip's URL, size, ETag and
`Last-Modified`.

## Tables

| table | one row per |
|---|---|
| `data/emendas/emendas/YYYY.csv` | amendment of year `YYYY`, place and budget line: `codigo`, `ano`, `tipo`, `autor_codigo`, `autor`, `numero`, `localidade`, `municipio_ibge`, `uf_ibge`, the budget-line codes `funcao`, `subfuncao`, `programa`, `acao`, `plano`, and `empenhado`, `liquidado`, `pago`, `rap_inscritos`, `rap_cancelados`, `rap_pagos` |
| `data/emendas/pagamentos/YYYY.csv` | payment month (`ano_mes`), amendment and recipient: `favorecido` (a code, see below), `tipo_favorecido`, the recipient's `uf` and `municipio`, `n_favorecidos`, `valor` |
| `data/emendas/convenios/YYYY.csv` | agreement, by the amendment's year: `numero`, `data_publicacao`, `convenente`, `objeto`, `valor`, `localidade`, `funcao`, `subfuncao` |
| `data/emendas/favorecidos.csv` | named recipient: `favorecido`, `nome`, `natureza_juridica`, `tipo` |
| `data/emendas/por_autor.csv` | author, year and type: `emendas` (distinct codes), `empenhado`, `liquidado`, `pago` |
| `data/emendas/por_municipio.csv` | municipality (IBGE code), year and type: the same totals, for amendments applied to one municipality |
| `data/emendas/ref/*.csv` | names of the codes: functions, subfunctions, programs, actions, budget plans (by action), municipalities |

Money is in reais with two decimals, summed in integer centavos so totals
are exact. Budget-line names live in `ref/` rather than on every row, which
keeps the main table under a third of its published size.

**Types** (`tipo`), from the published text:

| `tipo` | published as | what it is |
|---|---|---|
| `individual` | Emenda Individual - Transferências com Finalidade Definida | a deputy's or senator's own amendment, for a defined purpose |
| `especial` | Emenda Individual - Transferências Especiais | the "Pix" amendments (from 2020): money sent straight to a state or town's account, with no defined purpose |
| `bancada` | Emenda de Bancada | a state's bench of deputies and senators |
| `comissao` | Emenda de Comissão | a committee |
| `relator` | Emenda de Relator | the budget rapporteur's; in 2020–2022 (RP 9) the "secret budget", whose real sponsors were not published |

## What is missing from the source

- **No code or author** for 17,810 of 94,827 rows: all of 2014, plus some
  bench, committee and rapporteur lines in 2016–2020 that the budget marks
  as amendments but the file does not attribute. They are kept with an empty
  `codigo` and `autor`; their money is real and counts in every total.
- **Rapporteur amendments name no sponsor.** Their author is `RELATOR GERAL`;
  the deputies and senators who chose where the money went are not in this
  file.
- **Payments without an amendment code**: 54,371 payment rows, mostly
  2014–2019.
- **Authors are identified by the Portal's own code** (`autor_codigo`, e.g.
  1246 for Júlio César), not by their Câmara or Senado id. Matching them is
  planned as a shared crosswalk (`data/ref/politicians.csv`).

## Recipients, and private individuals

Recipients are named (`favorecido` is their code, `favorecidos.csv` gives the
name) when they are:

- a legal entity with a 14-digit CNPJ (`Pessoa Jurídica`): towns, municipal
  funds, companies, associations, banks;
- a government unit with a 6-digit UG code (`Unidade Gestora`);
- a generic bank or payroll account (`RB...`, such as Caixa as operator of
  Bolsa Família, R$9.4 billion);
- a foreign recipient (`EX...`) whose name carries a company or institution
  form (LTDA, INC, GMBH, B.V., CORPORATION, UNIVERSITY, the UN agencies and
  so on): Embraer, Saab's Gripen project, laboratory suppliers.

Everyone else is summed, unnamed, into one row per amendment, month, town and
recipient type, with `n_favorecidos` saying how many were summed. That
covers private individuals (`Pessoa Fisica`, already shown by CGU with a
masked CPF), and also codes that could hide one: 21 `Sem informação` rows
with 11-digit codes (a CPF's length), `PF...` generic codes, invalid codes,
and foreign codes without a company form. This follows the repo's rule
([METHODOLOGY.md](../METHODOLOGY.md#peoples-data)): a private person's name
next to a sum of public money is not needed to follow the money, and their
CPF is never committed. Of R$281 billion paid, R$0.94 billion (0.33%) is in
unnamed rows, R$0.67 billion of it to private individuals.

A recipient's name and legal nature can vary between rows (`HOSPITAL X`,
`HOSPITAL X LTDA`); `favorecidos.csv` keeps the most frequent, ties broken
alphabetically.

## Size

About 86 MB in all: payments 50 MB, agreements 16 MB, amendments 13 MB,
recipients 6 MB. A year adds about 8 MB, most of it payments.
