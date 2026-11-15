# Town profiles ("Meu município"): methodology

One page per municipality, [`docs/municipios/`](https://mbottoni.github.io/political-eye/municipios/),
searchable from the front page. It joins four sources that each cover all 5,570 towns: the mayors elected
([ref.md](ref.md#mayors-prefeitoscsv)), the amendment money paid ([emendas.md](emendas.md)), the contracts
published on the PNCP ([pncp.md](pncp.md)) and the fiscal reports filed on Siconfi ([siconfi.md](siconfi.md)).
It holds no new data. `python -m politicaleye site build municipios` (`politicaleye/site/municipios.py`)
writes `data/site/municipios/`; the daily `sancoes` job rebuilds it after the other cross-source pages, so
each source is at most a day behind.

| file | what it holds |
|---|---|
| `index.csv` | every municipality: IBGE code, name, state, population (the search box) |
| `resumo.json` | what each source covers, amendment money to town governments by year, and the medians of similar towns |
| `perfil/<NNNN>.json` | the profiles of the towns whose IBGE code starts with `NNNN`: about a dozen towns and 40 kB a file, so a profile loads one small file rather than the whole country (19 MB) |

The module's docstring lists every field.

## Mayors

Every mayor elected in 2016, 2020 and 2024, and in any supplementary election, from `data/ref/prefeitos.csv`.
A year is attributed to the mayor in office as `ref.prefeitos.mayor_by_year` does: the regular winner of the
election before the term, replaced by a supplementary winner from the year after their election. The 2012
election is not loaded, so mayors start in 2017. Brasília and Fernando de Noronha elect none.

## Amendments received

**What counts.** Payments (`data/emendas/pagamentos/`) to the town government, found by who was paid, not by
where the amendment says it applies: `data/emendas/por_municipio.csv` counts only amendments applied to one
municipality and misses most "Pix" transfers, which are recorded as `MÚLTIPLO`. A payment is the town's when
its recipient is:

- the municipality's own CNPJ (`data/siconfi/entes.csv`), where Pix transfers land: R$ 63.0 billion since 2014;
- or one of its funds, autarchies, foundations or other bodies, by legal nature (`Município`, or a nature
  ending in `Municipal` in `data/emendas/favorecidos.csv`) and by the recipient's town (name and state, as
  on the amendments page): R$ 49.6 billion, nearly all of it municipal health funds.

Payments to associations, foundations and companies based in the town (R$ 38.7 billion in all) are shown
apart and are not in the town's total: they reach the town, but not its government. Payments to state and
federal bodies, state companies and the banks that carry transfers are left out: they sit in one town (most
in Brasília) but spend for a wider area.

**Health money before 2025.** Until 2024 the Portal da Transparência recorded most health transfers "fundo a
fundo" as paid to Banco do Brasil in Brasília (CNPJ `00000000000191`), with no destination town: R$ 14.5
billion in 2023 and R$ 19.3 billion in 2024, against R$ 0.15 billion in 2025. From 2025 they appear paid to
each town's health fund. Only about 5% of the earlier payments belong to an amendment applied to a single
town, so the rest cannot be placed. A town's amendment money therefore jumps in 2025, mostly as a change in
the record: town governments got R$ 13.6 billion in 2024 and R$ 32.6 billion in 2025, R$ 21.9 billion of
which went to municipal funds. Comparisons between towns in the same year are not affected; comparisons
across years before and after 2025 are, and the page says so.

**Types.** From the amendment's code: Pix (`especial`), individual, state bench, committee, rapporteur, or no
code (payments the source does not tie to an amendment, mostly before 2019).

**Authors and parties.** A payment's amendment gives its author. Individual and Pix amendments are linked to
a member of Congress through `data/ref/politicians.csv`; benches, committees and the budget rapporteur
are not people and have no party. A member's party is the one they had in the month of the payment, from the
Câmara's and the Senado's monthly tables, or the latest before it (payments go on after a member leaves
office), or the first after it. The author table shows each member's party at their latest payment to the
town, and the party chart sums by party, both under today's name (PMDB is MDB, DEM and PSL are União, PTB and
Patriota are PRD).

**From the mayor's party.** For each payment since 2017 whose author's party and the town's mayor are both
known, whether the author was of the mayor's party that year, with parties compared as they stood that year
(`deputados.party_in`: DEM and PSL count as União only from 2022). The town's share is the money from the
mayor's party over that money. **By the state's mix** is what the share would be if the town got money from
each party in the same proportion as all of its state's town governments did that year, weighted by the
town's money each year. Across all towns, 24.8% of R$ 68.4 billion came from the mayor's party, against 12.0%
by the state mix (2026-11-14). That is an association, not proof of favour: mayors may ask more of their own
party, and parties that elect many mayors also elect many members of Congress.

## Contracts

The PNCP contracts of the town's bodies: municipal sphere (`esfera` `M`) and the town's IBGE code. Values go
through `pncp.plausible()`, as on the contracts page: a global value over 15 times the initial one counts at
the initial value, and a contract over R$ 10 billion or over three years of the town's revenue is left out
(the profile says how many were).

- **Large contracts** are those of R$ 1 million or more (`data/pncp/contratos/`).
- **Contracts with barred companies** are every contract, of any value, signed with a company under a
  sanction that bars contracting on the signing day (`data/pncp/sancionados/`). A contract matched to several sanctions counts once, at the widest
  reach (`cobre`): the sanction reached the buyer (`sim`), may have (`possivel`) or came from another town or
  sphere and does not bar this contract (`nao`). The profile lists those that did or may have, and counts the
  rest.
- A supplier among the largest is flagged when it signed any contract with the town's bodies while barred.

**Coverage.** The PNCP history is read newest first; every contract figure covers only the days read (408 of
1,894 days since September 2021 on 2026-11-14, from 2025-09-26 on), and the page states it. Days read are a
sample of the calendar, not of towns, so comparisons between towns are fair, only noisy.

**Names.** A supplier that is a private individual (masked CPF), an individual firm by legal nature, or whose
name is made only of words of people's names and initials (`"P R C DUARTE"`, `"JOAO DA SILVA ME"`; the words
come from TSE's candidate lists and the politicians crosswalk, as on the sanctions page) is shown as "name
withheld", and its contract's object is left out with it. A corporation (`S.A.`) is not. On 2026-11-14, 1,510 of the 23,640 suppliers of
town bodies were.

## Accounts

Payroll as a share of net current revenue, the status against the three limits of the Fiscal Responsibility
Law, revenue and unrestricted free cash at year end, from each year's last report read, exactly as on the
[Siconfi page](siconfi.md#the-explorer-page). Years for which Siconfi was consulted and the town filed no
report are listed.

## Similar towns

Each number is set against two groups: the towns of the same state, and the towns of the same population band
nationwide (under 5,000; 5,000–20,000; 20,000–100,000; 100,000–500,000; 500,000 or more, by Siconfi's
population figure). For each group the page shows the median and the town's position: the share of the
group's towns below it, ties counted half.

| measure | year | towns compared |
|---|---|---|
| amendment money to the town government per inhabitant | the last full year of payments (2025 on 2026-11-14) | all, with zero for none |
| large contracts per inhabitant | the days read | all, with zero for none |
| payroll share of revenue | the town's latest year read | the towns read that year |
| free cash per inhabitant | the town's latest year read | the towns read that year |

Per inhabitant uses today's population for every year.
