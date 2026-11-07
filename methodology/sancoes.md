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
