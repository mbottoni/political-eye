# Companies across sources: methodology

The [companies page](https://mbottoni.github.io/political-eye/empresas/) has one profile per company or
organisation (CNPJ), searchable by name or CNPJ: its sanctions, current and past; the public contracts it
signed; the amendment money paid to it and whose amendments paid it; the election campaigns it sold to and
which candidates; and the red-flag lists it is on. **A match between sources is not by itself an
irregularity**, and a red flag is a pattern worth a closer look, not evidence.

Built by `python -m politicaleye site build empresas` (`politicaleye/site/empresas.py`) in the daily `sancoes`
workflow, after the red-flags page, from tables other sources already commit: the sanctions lists and their change
log ([sancoes.md](sancoes.md)), PNCP contracts ([pncp.md](pncp.md)), amendment payments ([emendas.md](emendas.md)),
campaign suppliers ([tse.md](tse.md)), the red-flag lists ([alertas.md](alertas.md)) and the politician
crosswalk ([ref.md](ref.md)). It runs at most a day behind each of them.

## Who has a profile

Every CNPJ (14 digits) that is:

- on CEIS or CNEP as a company or organisation, on CEPIM, in a leniency agreement, or in the sanctions change log
  (`data/sancoes/changes.csv`);
- the supplier of a PNCP contract of R$ 1 million or more (a contract left out as a typo brings no one in), or of a contract of any value signed while a barring
  sanction reached or may have reached the buyer (`cobre` `sim` or `possivel`);
- the recipient (*favorecido*) of amendment payments adding up to more than zero (refunds can cancel them out);
- on any of the red-flag lists.

**Left out:** public bodies, by their legal nature in `data/emendas/favorecidos.csv` (towns, states, their funds,
ministries and other *órgãos*, autarchies, public foundations and public consortia): they receive money by design.
State companies stay, labelled; public banks receive amendment money as the agents of programmes and transfers, and
the profile says so. A PNCP supplier the amendments table does not know has no recorded legal nature and stays.
Campaign suppliers come in only with another source: a company that only sold to campaigns is on the
[campaign finance page](https://mbottoni.github.io/political-eye/tse/?tab=suppliers). Foreign codes (`EX…`) and
people are never profiles.

On 2026-11-14: 84,657 profiles. Sanctions bring 12,429 companies, contracts 35,059, amendments 44,878, the red-flag
lists 609; 11,383 are in two sources or more.

## Names, and people

A company is named by the first source that has a name for it: the Receita's registered name on the sanctions
lists, then the amendments table, CEPIM, the leniency agreements, the PNCP (latest contract), the TSE and the
change log.

**Individual firms named after a person have the name withheld**: the profile keeps the CNPJ and every number,
and shows "Individual firm (name withheld)". A firm is withheld when its legal nature is an individual's
(*Empresário (Individual)*, EIRELI, rural producer, one-lawyer firm) or when any of its names, from any source,
reads as a person's by the sanctions page's rule ([sancoes.md](sancoes.md#the-explorer-page): an MEI name, a name
carrying a CPF, or two or more words that all occur in real people's names; a name with `LTDA` never counts). On
2026-11-14: 6,130 of 84,657. A withheld firm's name is also taken out of its contracts' objects, which sometimes
repeat it. Sanctioned people are never shown: they have no CNPJ, and the change log's people are skipped.

Members of Congress and candidates are public figures and are named, linked to their profile on this site
(deputies of the 56th and 57th legislatures) or on the Senate's site.

## Sanctions

- **On the lists today**: every CEIS and CNEP entry for the CNPJ in the latest snapshot, with its status on the
  snapshot's date: *in force* (started, and no end date or one on or after the snapshot), *ended, still listed*
  (end date passed; the CGU removes entries with a delay) or *not started yet*. The categories that bar
  contracting are the same as everywhere (impediment, *inidoneidade*, suspension).
- **Entries and exits**: the change log since its first recorded change (2026-11-09; the first snapshot is from
  2026-11-06). A sanction that left the list shows only there, with its list, code and day. Sanctions that left
  before the log began leave no trace.
- **CEPIM** agreements (no dates are recorded) and **leniency agreements**.

The sanctions page's company tab draws the same sanctions on a timeline; each profile links to it.

## Contracts

The PNCP's contracts of R$ 1 million or more (`data/pncp/contratos/`), plus any contract signed while a barring
sanction reached or may have reached the buyer (`data/pncp/sancionados/`, or the single file it replaced). Values
follow the contracts page's rules ([pncp.md](pncp.md#the-explorer-page)): a global value over 15 times the initial
counts at the initial (marked `*`), and a contract over R$ 10 billion, or over three years of the buying town's
revenue, is left out and counted apart. Each contract's "while barred" column is the widest reach of a sanction
matched to it (`cobre`), `nao` included: the sanction existed but bound another sphere or body.

**Coverage.** The PNCP history is read newest first, so a profile has only the contracts of the days read so far;
every profile says how many (408 of 1,894 days since 2021-09-01 on 2026-11-14).

A profile lists the 10 largest contracts and up to 15 signed while barred; when that is not all of them, it adds
the totals by year and the 8 largest buyers. A contract's object is shortened: its boilerplate opening goes
("Contratação de empresa especializada para…", "O objeto do presente instrumento é…", "[LICITANET] -") and it is
cut at 70 characters. Each contract links to its page on the PNCP, which has the rest.

## Amendments

Amendment payments made **directly** to the CNPJ, by month, since 2014 (`data/emendas/pagamentos/`). Money that
reaches a company through a town hall or an agreement is not here: the recipient is then the town or the partner
organisation.

**While barred** is the sanctions page's rule: a payment in a month that overlaps a barring sanction of the CNPJ,
whatever the sanction's reach (the red-flag list keeps only reaches that cover federal money).

**Whose amendments.** Each payment's amendment code gives its author. Deputies and senators are linked through the
crosswalk and shown with their latest party and state (as on the red-flags page); state benches, committees and
the rapporteur-general have no party. For the 2020–2022 rapporteur amendments (RP 9) the members who chose the
destination were not published. A profile lists the 15 authors who paid most and sums the rest; payments with no
amendment code are a line of their own.

## Campaigns

- **What every candidate paid it**: `data/tse/<year>/fornecedores.csv`, companies paid R$ 50,000 or more by
  candidates for any office in an election, with how many candidates.
- **Which candidates**: `fornecedores_candidatos.csv`, every company that federal deputy and senator candidates
  contracted, at any value. A profile lists the 10 who paid most per election, with party, state, office and result,
  and sums the rest.
- **On election day** the profile says when the company was under a barring sanction (same rule as the sanctions
  page; a campaign is not public contracting, so this is context).

**Donors.** Companies may not donate to campaigns since 2015 (STF, ADI 4.650), so in the TSE's data a company is
only ever a supplier. Its owners may donate as individuals; the open data do not link a donor's CPF to a company,
and this page does not try.

## Red flags

The six lists of the red-flags page ([alertas.md](alertas.md)), read as committed: the profile says which lists the
CNPJ is on, with the rule, the innocent explanations and the members or buyers involved, and links to the full
list. The dominant-supplier list is built from the contracts page's buyer summary and follows it.

## Files and size

`data/site/empresas/`:

| file | what |
|---|---|
| `resumo.json` | counts per source, each source's coverage, the caps above, and the lists of legal natures, activities, sanction categories and scopes that profiles refer to by position |
| `indice.csv` | one row per profile for the search box: `cnpj`, `nome` (blank when withheld), `pf`, `fontes` (S sanctions now, H only a past sanction, C contracts, E amendments, T campaigns, A red flags), `valor` (contracts and amendments, R$ thousand) |
| `destaques.csv` | the 400 companies on the most red-flag lists, then in the most sources, then with the most public money |
| `autores.csv` | the amendment authors the profiles cite: name, kind, party, state, link |
| `perfis/<nnn>.json` | the profiles, one file per first three digits of the CNPJ |

A profile loads one shard (median 20 KB, largest 126 KB); the search index (4.7 MB, 1.7 MB compressed) loads the
first time the reader types in the search box. In profiles, amounts of R$ 100 or more are in whole reais. All
together about 32 MB on 2026-11-14 (10 MB compressed), growing with the PNCP history and the amendment payments.
