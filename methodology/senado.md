# Senado: methodology

The same two graphs as the Câmara's ([camara.md](camara.md)), for the
Senate: who votes together and who signs together. Every choice below
changes the graphs. Each one is a parameter of
`politicaleye.senado.graph()`, and the defaults are what
`data/senado/index.csv` uses.

## Source

The Senado's open-data API, `https://legis.senado.leg.br/dadosabertos/`,
one calendar year per call (the API's limit):

| endpoint | what it gives us |
|---|---|
| `/votacao?dataInicio=Y-01-01&dataFim=Y-12-31` | every Plenário roll call, with each senator's recorded vote and their party and UF at that moment |
| `/senador/lista/legislatura/L.json?exercicio=S` | everyone who took office in legislature `L`, suplentes included |
| `/processo?codigoParlamentarAutor=C&dataInicioApresentacao=…&dataFimApresentacao=…` | every matéria (processo) senator `C` signed in the year |

The API's by-date listing of matérias names authors only as text, cut short
for long lists, so co-authors are found from each senator's side: one call
per senator per year. A full backfill is about 2,000 calls; the weekly job
rebuilds the previous and current year in about 260. Endpoints the API marks
as deprecated (`/plenario/...`, `/materia/...`, `/senador/{c}/votacoes`,
`/senador/{c}/autorias`) are not used; they were due to be switched off in
February 2026. `data/senado/sources.json` records the URL, size and SHA-256
of every response a build used (one combined record per year for the
per-senator authorship calls).

## Votes

**The gap: February 2015 to March 2017.** The API has no individual votes
for these two years except the six of the 2016 impeachment trial (DEN
1/2016). What it lists under 2015–2017 session dates are mostly 1998–1999
votes filed under the wrong session (a session-code collision): the vote on
`2015-04-01`, for one, is the 1998 nomination of Adylson Motta, cast by
senators such as Abdias Nascimento. Every deprecated endpoint shows the same
gap. A record is dropped as misdated when the year of its legislative record
(`informeLegislativo.data`) differs from its session's year: 17 records in
2015, 7 in 2016, 9 in 2017, none since. Co-voting graphs therefore start in
2017.

**Only the Senado's own roll calls.** `/votacao` lists Plenário votes of the
Senate. Joint sessions of the Congresso Nacional (veto votes, for one) are
published elsewhere, without senator codes, and are not included.

**Secret votes** (authority nominations, ambassadors, some vetoes) are
`secreta = 1` in `data/senado/votacoes/`. Each senator's row says only
whether they voted (`Votou`), so they never enter the co-voting graph; the
totals come from `totalVotos*`. For open votes the totals are counted from
the individual rows, since the API leaves `totalVotos*` empty.

**Coding.** `Sim` is +1 and `Não` is −1. Every other value is not a vote:
`Abstenção`, `Votou` (secret), `P-NRV` (present, did not register a vote),
`Presidente (art. 51 RISF)` (presiding), `P-OD` (present, declared
obstruction; 7 times in all), and the absence codes (`AP` parliamentary
activity, `LS` health leave, `MIS` official mission, `NCom` did not attend,
and so on; the full list is at `/plenario/lista/tiposComparecimento`). The
Câmara counts `Obstrução` as a `Não` because obstruction there is a quorum
tactic with its own vote code; in the Senate it is too rare to matter.

**Lopsided votes** (minority side under 2.5%, `lop`) are dropped, as in the
Câmara: most Senate roll calls pass with one or two votes against.

**Parties** are as each vote record states them, so a senator who changed
parties appears under the right one on each date. `S/Partido` (no party) is
kept as published; an empty party or `Sem registro` is left empty.

**UF.** Vote records before 2017 mostly leave the senator's UF empty, so it
comes from the legislature list. That list gives the UF in the identification
block only for senators in office today, so it is read from the mandate that
covers the legislature. One senator missing from his own legislature's list
(Wilder Morais, absent from the 55th's and the 56th's) takes it from any other
cached list. Every senator-month has a UF.

## Twelve-month windows

The Senate rarely splits. Contested roll calls per year (open votes with
both sides above 2.5%):

| 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|
| 35 | 15 | 29 | 57 | 75 | 46 | 33 | 41 | 30 |

Half or more of all roll calls are secret, and most open ones pass with one
or two votes against. A month alone would give an empty or
noisy co-voting graph, so a graph pools the `window` months ending at the
month named (`window=12`; `window=1` is a single month). A window never
reaches back before its legislature began (1 February 2019, 2023, 2027),
since a new legislature brings a renewed Senate and usually a new
government; the first months of a legislature therefore have short windows.
`window_start` is a column of `data/senado/index.csv` and an attribute of
every graph, and every count in the index is over the window.

A co-voting graph needs senators with 10 contested votes in common, so it
first has nodes in May 2017 (the 55th legislature, after the gap), June
2019 (the 56th) and September 2023 (the 57th). Co-authorship graphs exist
for every month from February 2015.

Co-authorship uses the same window, so the two graphs of
`politicaleye.senado.aligned()` describe the same months.

**Co-voting.** An edge joins two senators who agreed on at least 80% (`tau`)
of the contested votes they both cast, given at least 10 in common
(`min_shared`). Nodes are senators with at least 10 contested votes in the
window.

## Authorship

**Signers.** A senator signed a matéria when it appears in their
`/processo?codigoParlamentarAutor=` list. Checked against the per-matéria
endpoint (`/processo/{id}`, `autoriaIniciativa`), which names authors with
their codes: for a random 40 matérias of 2024–2026 the senators were the
same in all 40. PEC 20/2026 lists 28 senators there, while its authors' text
names only the first. The order of signatures is not recorded.

**Leaders.** Party and bloc leaders sign some requerimentos (mostly
urgency requests) on behalf of their bench, written `Líder do PSD Omar
Aziz (PSD/AM)`. They count as signers, as in the Câmara, and `lider = 1`
marks them in `data/senado/authorship/` so they can be left out.

**Only Senate matérias.** The same lists also credit:

- presidential vetoes (`VET`) and joint-committee requests, identified in
  the Congresso (`casaIdentificadora = CN`), to the Senate's president or the
  requesting senator;
- bills from the Câmara under review (`objetivo` `Revisora` or
  `Substitutivo`) to senators who wrote them as deputies.

Neither is Senate co-authorship, so both are dropped (about 130–150 rows a
year; the build log counts them as `authorship_not_senate`).

**Party** in `data/senado/authorship/` is the one the authors' text gives
for the senator at the time (`Senador Flávio Bolsonaro (PL/RJ)`, `Líder do
PSD Omar Aziz (PSD/AM)`). It is empty when the text leaves the senator out,
naming only the first author (`Senador Reguffe (PDT/DF) e outros.`): 63% of
2015 signatures, 38% of 2016's, under 7% each year since. Who signed is
unaffected; only this label is missing. The text writes Podemos as `PODEMOS`
and the votes as `PODE`; signatures are stored as `PODE`, so a senator seen
only through signatures (as in January, without votes) keeps one party label.

**Types.** Requerimentos dominate: plenário (`RQS`) and committee (`REQ`,
written `REQ n/ano - CAS` and so on; before 2019, one code per committee,
such as `RDH` or `RCE`) requests are about 70% of matérias. All
types are kept (`exclude=()`), as in the Câmara, where `REQ` is kept too.
PLS, PLC and PDS were replaced by PL and PDL in 2019.

**Signature drives are dropped.** Matérias with more than 20 senator signers
are left out (`max_authors=20`). A PEC needs 27 signatures, a third of the
Senate, and all 636 PECs since 2015 have at least 26 senator signers. Collecting them is a
petition, not collaboration, as with the Câmara's cap of 50 below its
threshold of 171.

**Edges and weights** are the Câmara's: an edge if two senators co-signed at
least one matéria (`min_items`), `n_items` and Newman's weight
`sum(1 / (k - 1))`.

## Party orientations

**Source.** `/plenario/votacao/orientacaoBancada/Y0101/Y1231`, one call per
year from 2018: for each roll call on the electronic panel, how party leaders,
the Government, the Majority, the Minority, the Opposition and the women's
caucus (`Banc Fem`) oriented (`SIM`, `NÃO`, `LIVRE`, `OBSTRUÇÃO`). Kept as
published in `data/senado/orientations/` (`votacao_id, bancada, orientacao`);
a leader who changed orientation keeps the last one given.

**Coverage.** Orientations start in October 2018 and exist for about half the
roll calls (1,041 records, 492 with any orientation). They join to
`/votacao` through `sequencialVotacao` (`sequencial` in
`data/senado/votacoes/`), which is empty before 2019: the 5 oriented roll
calls of 2018 do not join. Some oriented roll calls are missing from
`/votacao` itself (59 in 2021, 18 in 2022, 10 in 2023: veto votes and
amendments, the API survey found); the build log counts them as
`orientacoes_sem_votacao`.

**Which orientation applies.** The Senado's lists have no blocs or
federations, so a senator follows their own party's orientation, matched on
the party at the vote (`partido` in `votes/`) with the Câmara's key
(`party_key()`) plus the panel's own abbreviations (`Republica`, `PROGRES`,
`Progressistas`). `LIVRE` frees the senator. Senators with no party
(`S/Partido`) have none.

**Discipline.** `politicaleye.senado.orientations.discipline(month)` counts,
per senator, the contested votes of the window ending at `month`, as in the
Câmara: `with_party`, `with_gov` (against the Government leader),
`with_majority` (against the other senators of their party who voted,
needing no orientation), and `n_free`, `n_none`. `data/senado/index.csv`
adds `oriented_share`, `with_party`, `with_gov` and `with_majority` per
window. `OBSTRUÇÃO` (8 times in all) counts as a `Não`.

## Explorer

[mbottoni.github.io/political-eye/senado/](https://mbottoni.github.io/political-eye/senado/)
draws both graphs for any window in the browser, from the committed tables:
the Câmara explorer's code (`docs/camara/core.js`) with the Senado's
defaults and windows (`docs/senado/window.js`). With the default twelve-month
window it reproduces every count in `index.csv` exactly
(`tests/senado/parity.mjs`, run in CI); it also offers 6-, 3- and 1-month
windows, which the index does not record.

## Tables

| table | one row per |
|---|---|
| `data/senado/votacoes/YYYY-MM.csv` | roll call: `id` (`codigoSessaoVotacao`), `data`, `sessao`, `sequencial` (`sequencialVotacao`), `tipo_sessao`, `processo_id`, `materia`, `sigla`, `secreta`, `resultado` (`A` approved, `R` rejected), `votos_sim`, `votos_nao`, `votos_abstencao`, `descricao` |
| `data/senado/votes/YYYY-MM.csv` | senator and roll call: `voto`, `partido` and `uf` as recorded |
| `data/senado/orientations/YYYY-MM.csv` | roll call and bench: `orientacao` as published |
| `data/senado/authorship/YYYY-MM.csv` | senator and matéria: `processo_id`, `sigla_tipo`, `materia`, `data_apresentacao`, `partido`, `lider` |
| `data/senado/senators/YYYY-MM.csv` | senator seen that month: `nome`, `partido` and `uf` from the latest vote (else the latest signature, else the legislature list), `n_votes`, `n_authored` |

Months are calendar months: the session date for votes (a session that runs
past midnight keeps its date) and the presentation date for matérias.
Senators are identified by `CodigoParlamentar`, the Senado's own code.

**Size.** About 8 MB in all; a year adds under 1 MB.

## Not included (yet)

- **Joint sessions of the Congresso Nacional**, published per veto without
  senator codes.
- **Committee votes.**
