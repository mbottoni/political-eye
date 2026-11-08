# PNCP: methodology

Public contracts from the Portal Nacional de Contratações Públicas (PNCP),
where every federal, state and municipal body must publish its contracts
under the 2021 procurement law (Lei 14.133). Since September 2021 that is
over 5 million contracts, about 2 million a year, too many to commit (about
1 GB a year), so this source commits three derived tables.

## Source

The PNCP's consultation API, `https://pncp.gov.br/api/consulta/v1`:

| endpoint | used for |
|---|---|
| `/contratos?dataInicial=D&dataFinal=D&pagina=N&tamanhoPagina=500` | every contract published on day D, in its current version |
| `/contratos/atualizacao?…` (same parameters) | every contract changed on day D (amendments, rectifications), including ones published long before |

Dates are `yyyyMMdd`; a day with nothing is HTTP 204 with an empty body; a
page holds at most 500 contracts. Past about 20 requests a minute the API
answers 429 with an HTML page and no `Retry-After`, clearing within a minute,
so requests are spaced 4 seconds apart and a 429 waits 75 seconds. A day
whose pages do not add up to the `totalRegistros` the API reports is not
recorded, and is read again next run.

**Runs.** Each daily run reads yesterday's updates, then the days not read
yet, newest first, for up to five hours, saving every ten days
(`data/pncp/dias.csv` records what has been read). The history, about 11,000
pages, takes a few runs; after that a run takes about four minutes.

## Tables

| table | one row per |
|---|---|
| `data/pncp/contratos/YYYY-MM.csv` | contract worth R$1,000,000 or more (`valor_global`), by month of publication: `controle` (`numeroControlePNCP`), `compra`, `publicacao`, `assinatura`, `vigencia_inicio`, `vigencia_fim`, the contracting body (`orgao_cnpj`, `orgao`, `esfera` F/E/M/N, `poder`, `uf`, `municipio_ibge`), `tipo`, `categoria`, the supplier (`fornecedor_tipo` PJ/PF/PE, `fornecedor`, `fornecedor_nome`), `objeto` (cut at 200 characters), `valor_inicial`, `valor_global`, `retificacao` |
| `data/pncp/contratos_sancionados.csv` | contract of any value and sanction: the same columns plus the sanction (`lista`, `codigo_sancao`, `categoria_sancao`, `sancao_inicio`, `sancao_fim`, `abrangencia`, `orgao_sancionador`, `esfera_sancionador`, `uf_sancionador`) and `cobre` |
| `data/pncp/resumo_dia.csv` | publication day, sphere and kind of supplier: `contratos` and `valor_global`, for every contract published |
| `data/pncp/dias.csv` | day read: contracts published, contracts updated |

**Why R$1 million.** On a sample day (5 November 2026, 8,654 contracts),
contracts of R$1 million or more were 3.2% of contracts and 84% of the money;
R$100,000 or more, 12.8% and 97%. The threshold keeps the table to an
estimated 75 MB for the whole history while covering most of the money. `resumo_dia.csv`
counts everything. A contract updated below the threshold leaves the table.

**Updates.** A contract can change after publication (amendments raise its
value, rectifications fix fields). `contratos/` and `contratos_sancionados.csv`
always hold the latest version read; `resumo_dia.csv` counts each day's
contracts as they were when that day was read.

## Contracts with sanctioned companies

`contratos_sancionados.csv` lists every contract whose supplier (by CNPJ) was
under a sanction that bars contracting on the day the contract was signed:
on CEIS or CNEP ([sancoes.md](sancoes.md)), in a category that bars
contracting (impediment, *inidoneidade*, suspension; fines do not), with a
start date on or before the signing date and an end date on or after it, or
none.

**A match is not an irregular contract.** Most sanctions bind only part of
the State: the body that imposed it, or its sphere (one municipality, one
state, the federal government). `cobre` says whether the sanction's scope
(`abrangencia`) reaches the contracting body:

- `sim`: a sanction for every sphere and power, or for the whole federal or
  state sphere and a body of that sphere and state;
- `nao`: a body of another sphere or, for a state or municipal sanction,
  another state; or, for a sanction limited to its own body or
  municipality, a body whose name shares no distinctive word with the
  sanctioner's;
- `possivel`: the rest. Bodies' names are written too differently between
  the two registries to confirm the same body or town.

On the first day read (6 November 2026: 7,242 contracts published, 10,666
updated), 965 contract-sanction pairs matched; `cobre` was `sim` for 6,
`possivel` for 3 and `nao` for 956.

**Limits.** Only companies are matched: CEIS lists sanctioned people with the
CPF masked ([sancoes.md](sancoes.md#peoples-data)), so they cannot be matched.
And the sanctions lists hold only sanctions still listed: a contract signed
in 2023 under a sanction that has since expired and left the list is not
found. The history in `data/sancoes/changes.csv`, recorded from November
2026, closes that gap from now on.

## People's data

About 3% of contracts have a private individual as supplier (`PF`), whom the
PNCP lists with their full CPF. Their CPF is masked the CGU way
(`***.462.240-**`), and every CPF in a supplier's name (a sole proprietor's
business name often carries the owner's) or in the contract's object is
masked too ([METHODOLOGY.md](../METHODOLOGY.md#peoples-data)). Their name is
kept, as for sanctioned people.

## The explorer page

[`docs/pncp/`](https://mbottoni.github.io/political-eye/pncp/) draws on
summaries that `python -m politicaleye site build pncp`
(`politicaleye/site/pncp.py`) writes to `data/site/pncp/`. The daily job
rebuilds them after each run.

**Coverage.** Every total says how many days of the history it covers
(`dias.csv`, out of every day since 1 September 2021). The history is read
newest first. Days read are a sample of the calendar, not of buyers, so
comparisons between parties, states or buyers are not biased by it, only
noisy while few days are read.

**Implausible values.** Some contracts are published with a global value
thousands of times their initial value (R$ 7.8 million initial, R$ 45.6
billion global). Amendments and renewals can raise a contract's value, but
not by that much: a continuous service renewed to its ten-year limit, with
price adjustments, stays around ten to thirteen times its first year. A
contract whose global value is more than 15 times its initial value is
counted at its initial value and marked "fixed". On the first day read, 15
contracts were, publishing R$ 66.7 billion that count as R$ 96.6 million.
The sanctions page uses the same rule for the contracts it shows.

**Suppliers and buyers.** A supplier is a CNPJ (or a masked CPF). A buyer is
a contracting body's CNPJ. Concentration among suppliers is the Gini
coefficient of their totals, and the share the top 1% and 10% hold. A
buyer's concentration is the Herfindahl index of its large-contract value
across its suppliers (the sum of the squared shares), for buyers with five
or more large contracts. The supplier table adds: whether the CNPJ is on CEIS
or CNEP, contracts signed while barred
([below](#contracts-with-sanctioned-companies)), amendment payments made to
it directly (`data/emendas/pagamentos/`), and what election campaigns paid it
(TSE `fornecedores.csv`, 2018–2026).

**Places.** Per inhabitant uses the municipal populations in
`data/siconfi/entes.csv`, summed by state. The municipal map counts only
contracts of municipal bodies (`esfera` M) located in the town.

**Mayors' parties.** A municipal body's contract is attributed to the mayor
in office in the year it was signed (publication year when the signing date
is missing), from [`data/ref/prefeitos.csv`](ref.md#mayors-prefeitoscsv),
with merged and renamed parties under today's name. A party's value per
inhabitant-year is its towns' large-contract value over the sum, year by
year, of the population those mayors governed. These are associations:
parties govern different kinds of towns.
