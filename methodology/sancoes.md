# Sanções: methodology

The federal lists of companies, organisations and people barred from public
contracts or punished for corruption, and the leniency agreements companies
signed. CGU publishes each list only as today's snapshot and keeps no
history: an entry that expires or is lifted simply disappears. This source
records every snapshot, so `data/sancoes/changes.csv` says when each entry
appeared and when it left.

## Source

The Portal da Transparência's downloads (CGU), one zip per list:

| list | download page | what it is |
|---|---|---|
| CEIS | `/download-de-dados/ceis` | Cadastro de Empresas Inidôneas e Suspensas: companies and people any federal, state or municipal body has barred from contracting (suspension, inidoneidade, impediment) |
| CNEP | `/download-de-dados/cnep` | Cadastro Nacional de Empresas Punidas: penalties under the Anti-Corruption Law (Lei 12.846/2013), mostly fines |
| CEPIM | `/download-de-dados/cepim` | Cadastro de Entidades Privadas Sem Fins Lucrativos Impedidas: non-profits barred from federal agreements, one row per agreement |
| Acordos de leniência | `/download-de-dados/acordos-leniencia` | leniency agreements under Lei 12.846, with what each required |

Each page names the date of the snapshot it offers in its script
(`arquivos.push({"ano" : "2026", "mes" : "11", "dia" : "06", ...})`); the
file is
`dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/<list>/<YYYYMMDD>_<NAME>.zip`.
Only the latest date can be downloaded (older dates answer 403). CEIS, CNEP
and the leniency file are published daily for the previous day; CEPIM less
often. The files are cp1252 (their headers use its en dash), `;`-separated.
`data/sancoes/sources.json` records each zip's URL, size, ETag,
`Last-Modified` and snapshot date.

The download server sits behind a bot check (AWS WAF): a burst of requests
from one address gets a "Human Verification" page (HTTP 405) instead of the
file for a while. The daily job makes five requests.

## Tables

| table | one row per |
|---|---|
| `data/sancoes/ceis.csv` | sanction (`codigo_da_sancao`) |
| `data/sancoes/cnep.csv` | sanction (`codigo_da_sancao`), with `valor_da_multa` |
| `data/sancoes/cepim.csv` | barred entity and agreement (`cnpj_entidade`, `numero_convenio`) |
| `data/sancoes/leniencia.csv` | agreement and company (`id_do_acordo`, `cnpj_do_sancionado`): one agreement can cover several companies |
| `data/sancoes/leniencia_efeitos.csv` | agreement and effect (integrity programme, fine, and so on) |
| `data/sancoes/changes.csv` | entry that appeared in or left a list: `data` (the snapshot's date), `lista`, `codigo`, `mudanca` (`entrou`, `saiu`), `tipo_de_pessoa`, `documento`, `nome` |
| `data/sancoes/ref/fundamentacoes.csv` | legal ground (`id`, `texto`): CEIS and CNEP repeat a few hundred long texts, so the lists carry an id |

Columns keep the published names in snake_case without accents (`CÓDIGO DA
SANÇÃO` is `codigo_da_sancao`). Dates are ISO; money uses a `.` decimal point.

**History starts on 2026-11-06** (CEPIM: 2026-10-28), the first snapshot
recorded. Entries listed then have no `entrou` row; their sanction dates
(`data_inicio_sancao`, `data_publicacao`) say how old they are. A change is
dated by the snapshot that first shows it, not by the day the job ran.

## People's data

CEIS and CNEP list people as well as companies (about 9,200 of 23,746 CEIS
entries are people), and CGU publishes their full CPF. Following the repo's
rule ([METHODOLOGY.md](../METHODOLOGY.md#peoples-data)), the name of a
sanctioned person is kept and **their CPF is masked the way CGU masks it
elsewhere**: `***.462.240-**`, the middle six digits only. Specifically:

- the document column (`cpf_ou_cnpj_do_sancionado`) keeps a 14-digit CNPJ or
  a foreign code (`EX...`) and masks anything else;
- every text column is scanned for CPFs, which turn up in business names (a
  sole proprietor's company name often ends with the owner's CPF), in
  observations ("…Fábio … (CPF nº 018.714.277-70)…") and in publication
  details. A CPF formatted `000.000.000-00` (or mistyped with three check
  digits) or written as a bare run of 11 digits is masked, unless it is part
  of a longer number such as a CNPJ, a date or a process number;
- in `numero_do_processo` only formatted CPFs are masked, since bare 11-digit
  process numbers are common there.

The build counts people per list (`ceis_people`), and the tests check that
no full CPF from the fixtures reaches any table.

## Size

About 14 MB, almost all CEIS. The lists grow by a few thousand entries a year
(CEIS sanctions starting in 2025: 6,071), and `changes.csv` by one row per
entry or exit.

## The explorer page

[`docs/sancoes/`](https://mbottoni.github.io/political-eye/sancoes/) draws
on summaries that `python -m politicaleye site build sancoes`
(`politicaleye/site/sancoes.py`) writes to `data/site/sancoes/`. The daily
job rebuilds them after each update, so the cross-source numbers below run
at most a day behind the other sources.

**People are counted, never named.** Every table on the page that names
someone holds only companies and organisations (a 14-digit CNPJ or a foreign
code). Sanctions on people enter the counts and charts only. An individual
firm (*empresário individual*, MEI) has a CNPJ but carries its owner's name,
so its name is withheld too ("Individual firm (name withheld)"). A company
name counts as a person's when it is an MEI name (`12.345.678 JOAO SILVA`),
carries a CPF, or is two or more words that all occur in real people's names
(the TSE candidate files and the politician crosswalk), leaving out `ME`,
`EPP`, `EIRELI` and connectors (`VAGNER BORGES DIAS`, `JOAO DA SILVA ME`). A
name with `LTDA` never counts. On 2026-11-06 this withheld 700 of 12,471
names.

**In force.** A sanction is in force on a day when it started on or before
that day and has no end date or ends on or after it. The page's "in force"
counts use the snapshot's date. "Past their end date, still listed" counts
entries whose end date is before the snapshot: CGU removes them with a delay.

**What bars contracting.** The same rule as the PNCP matching
([pncp.md](pncp.md#contracts-with-sanctioned-companies)): impediment,
*inidoneidade* and suspension. Fines, warnings and the rest do not.

**Amendments paid while barred.** An amendment payment (by month, from
`data/emendas/pagamentos/`) to a CNPJ counts as paid while barred when a
barring sanction of that CNPJ overlaps the payment's month. A company paid
straight from an amendment is paid by a federal body, so each match is
classed by whether the sanction binds federal bodies:

- `sim`: a sanction for every sphere and power, or a federal sanction for its
  whole sphere (or its sphere and power);
- `possivel`: a federal sanction limited to its own body, or with no scope
  recorded: the paying body may be the sanctioner;
- `nao`: a state or municipal sanction that does not cover every sphere.

As for contracts, only sanctions still listed can be matched: a sanction that
expired and left the list before November 2026 leaves no trace.

**Authors and parties.** Each payment's amendment code gives its author
(`data/emendas/emendas/`). Individual authors are linked to a deputy or
senator through the crosswalk ([ref](../METHODOLOGY.md)), and their party is
the one the chamber tables record for the month nearest to July of the
amendment's year (the latest month on or before it, else the first after),
under one name per party as it stood that year: renamed parties under their
new name (PMDB is MDB, PR is PL, PRB is Republicanos), merged ones under the
successor from the year of the merger (DEM is União from 2022). "No party"
is not a party, and is left out of the party table.
Benches, committees and the rapporteur-general have no party. A party's share
is the money its members' individual amendments paid to companies while
barred, over everything those amendments paid to anyone. Payments with no
amendment code (8% of rows) have no author and are left out of the author
and party tables.

**Campaign suppliers** (TSE `fornecedores.csv`) are matched on election day
(7 October 2018, 2 October 2022, 4 October 2026). Campaign spending is not
public contracting; the match is context.

**CEPIM** records no dates, so amendment money to an organisation now on
CEPIM may have been paid before it was barred.

**Leniency amounts** are read from each agreement's terms: the first "valor
total de R$ …" (or in euros or dollars) and "dos quais R$ … correspondem a
multa". Agreements whose terms state no total have none. An agreement is
named after its group when the terms name one ("grupo OAS"), otherwise after
its first company.

**How long and how late.** A sanction's length runs from its start to its
end date. Its delay is the days from its start to the date its record was
created (`data_origem_informacao`).
