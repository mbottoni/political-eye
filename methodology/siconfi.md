# Siconfi: methodology

Whether each of Brazil's 5,570 municipalities keeps its payroll within the
Fiscal Responsibility Law (LRF, Lei Complementar 101/2000), and how much cash
it holds at the end of the year, from the fiscal reports municipalities file
with the Tesouro Nacional.

## Source

The Siconfi API, `https://apidatalake.tesouro.gov.br/ords/siconfi/tt/`:

| endpoint | used for |
|---|---|
| `/entes` | every municipality: IBGE code, name, state, population, CNPJ (one call) |
| `/rgf?an_exercicio=Y&in_periodicidade=P&nr_periodo=N&co_tipo_demonstrativo=T&co_poder=E&id_ente=IBGE` | the Executive's Relatório de Gestão Fiscal for one municipality and period, every annex in one call |

Municipalities report every four months (`Q`, `RGF`) or, if small, every
semester (`S`, `RGF Simplificado`), and some switch between the two from year
to year. The annexes used are the same in both.

**Silent errors.** A wrong parameter, a periodicity the town does not use or
a report not yet filed all return an empty list, not an error. A report is
looked for in the town's last known rhythm first, then in the other.

**Pace.** The API allows one request a second and answers one municipality
and period per call: a full history is about 67,000 municipality-years and
somewhat more calls. Each run (twice a day while the history is read) works
through a queue for up to five hours, biggest municipalities first, saving
every 200, and the next run continues. `data/siconfi/consultas.csv` records
which report each row came from and when it was read (or that none was
found); it is committed with the data, but a change to it alone does not
make a commit.

## Which report

One report per municipality and year:

- **completed years**: the year's last, the 3rd four-month period (`Q3`) or the
  2nd semester (`S2`), which covers the twelve months to December;
- **the year in progress**: the latest one due (from October, `Q2` or `S1`;
  from June, `Q1`), re-read every 25 days, and the previous year's last
  report re-read from January to March, while it is being filed.

Every report gives the last twelve months, so a `Q2` row covers July of the
year before to June.

## Tables

| table | one row per |
|---|---|
| `data/siconfi/entes.csv` | municipality: `cod_ibge`, `ente`, `uf`, `regiao`, `populacao`, `cnpj`, `capital` |
| `data/siconfi/pessoal/YYYY.csv` | municipality and year (RGF Anexo 01): `periodicidade`, `periodo`, `rcl` (net current revenue), `rcl_ajustada` (the base of the payroll limits, from 2017), `dtp` (total payroll), `dtp_pct` (payroll as a share of the base), the three limits in % (`limite_maximo_pct` 54, `limite_prudencial_pct` 51.3, `limite_alerta_pct` 48.6), and `situacao` |
| `data/siconfi/caixa/YYYY.csv` | municipality and year, from the year's last report only (RGF Anexo 05): gross and net cash (after commitments carried over, *restos a pagar*), unrestricted (`*_livre`, *recursos não vinculados*) and in all (`*_total`) |
| `data/siconfi/consultas.csv` | municipality and year read: the report found (`periodicidade`, `periodo`), `linhas`, `consultado_em` |

`situacao` is `acima_maximo` when payroll is above the 54% limit,
`acima_prudencial` above 51.3% (the town may not hire or give raises),
`acima_alerta` above 48.6%, and empty below.

**Rows in the API.** Annex 01's rows are named by `cod_conta`
(`ReceitaCorrenteLiquidaLimiteLegal`, `ReceitaCorrenteLiquidaAjustada`,
`DespesaComPessoalTotal`, `Limite{Maximo,Prudencial,DeAlerta}DespesaComPessoalTotal`)
and `coluna` (`Valor`, or a percentage column: `% sobre a RCL` in 2015–2016,
`% sobre a RCL Ajustada` from 2017). In Annex 05 the columns are named by
`cod_conta` (`DisponibilidadeDeCaixaBruta`, `DisponibilidadeDeCaixaLiquidaAposRP`)
and the rows by `conta`; the total row was `Total dos Recursos` in 2015, then
`TOTAL (III) = (I + II)`, then `TOTAL (IV) = (I + II + III)` once pension funds
(RPPS) were split out, so the unrestricted row (`TOTAL DOS RECURSOS NÃO
VINCULADOS (I)`) is the most comparable across years.

## Coverage

Reports start in 2015; coverage is thinner before 2018 (in a sample of 15
municipalities, 10 had a report for 2015, all 15 for 2018). Some
municipalities never file a given year: they appear in `consultas.csv` with
`linhas = 0`. Values are as the municipality declared them; the API flags
none as wrong (Pinhão, PR, declared payroll at 87% of revenue in 2025).
