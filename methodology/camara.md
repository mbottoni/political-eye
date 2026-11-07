# Câmara: methodology

Every choice below changes the graphs. Each one is a parameter of
`politicaleye.camara.graph()`, and the defaults are what `data/camara/index.csv`
and the explorer use.

## Source

Five yearly bulk files from the Câmara's open data portal,
`https://dadosabertos.camara.leg.br/arquivos/<dataset>/csv/<dataset>-<year>.csv`:

| dataset | what it gives us |
|---|---|
| `votacoes` | every votação: date, body (`siglaOrgao`), outcome, description |
| `votacoesVotos` | how each deputy voted, for votações with a per-deputy record, and their party at that moment |
| `votacoesOrientacoes` | how each party, federation, bloc and leadership told its members to vote |
| `proposicoes` | every proposição: type (`siglaTipo`) and presentation date |
| `proposicoesAutores` | every signer of every proposição |

The schema has been identical since at least 2015. The server republishes
the files nightly. The scheduled job rebuilds the previous and current year
each week, so corrections to recent records show up as diffs.
`data/camara/sources.json` records the ETag, size and `Last-Modified` of
every file a build used.

## Votes

**Only Plenário roll calls.** A votação is kept if `siglaOrgao == "PLEN"` and
it has per-deputy records. Symbolic votes have no per-deputy record, and
committee votes have a different electorate every time.

**Coding.**

| `voto` | default coding | why |
|---|---|---|
| Sim | +1 | |
| Não | −1 | |
| Obstrução | −1 | obstruction is a strategic "no": the party withholds quorum to defeat the measure. `obstruction_as_no=False` drops it instead |
| Abstenção | not a vote | |
| Artigo 17 | not a vote | recorded for the presiding officer, who does not vote |

**Lopsided votes are dropped.** If the minority side is under 2.5% of
yes + no, the vote is removed (`lop=0.025`, W-NOMINATE's default).
Near-unanimous votes make everyone agree with everyone and carry no
information about structure. In 2025 that removed 30 of 429 roll calls.

## Co-voting graph

For deputies *i* and *j* in a month:

    n_shared = contested votes both cast
    n_agree  = of those, votes where they were on the same side
    agreement = n_agree / n_shared

- A pair is only considered if `n_shared >= 10` (`min_shared`).
- Edge if `agreement >= 0.8` (`tau`).
- Nodes are deputies with at least `min_shared` contested votes that month.

**On `tau`.** No value is canonical. In September 2025 the median pair agreed
on 66% of votes. `tau = 0.8` gave density 0.30, and `tau = 0.9` gave 0.16.
For a weighted graph use `covote_edges()`, or sweep `tau`. Raw agreement also
does not correct for how contested each vote was. If that matters for your
model, the deputy x vote matrix is one call away (`vote_matrix`).

## Co-authorship graph

**Items.** An item is a proposição presented that month with at least one
deputy signer. That includes bills (PL, PLP, PEC, PDL), requests (REQ, RIC),
amendments (EMC, EMP) and more. `sigla_tipo` is stored on every row, and
`types={"PL", "PLP", "PEC"}` restricts to bills.

**Two types are excluded by default**, because the Câmara's records changed,
not Congress (`exclude=EXCLUDE_TYPES`, pass `exclude=()` to keep them):

- **RPD:** floor-procedure requests (withdraw from the agenda, postpone,
  invert the agenda, demand a roll call). These are obstruction tactics,
  usually signed by party leaders.
- **DOC:** administrative paperwork (committee seat changes, letters from the
  Secretariat or the Senate).

Neither shows up co-signed until 2020–2022, after which RPD becomes one of
the largest types. Items co-signed by 2 to 50 deputies, per year:

| type | 2015 | 2017 | 2019 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RPD | 2 | 3 | 0 | 3 | 43 | 1,176 | 1,707 | 1,232 |
| DOC | 0 | 0 | 0 | 150 | 82 | 146 | 147 | 114 |
| REQ | 1,307 | 490 | 819 | 1,698 | 930 | 1,960 | 1,520 | 1,411 |
| PL | 127 | 102 | 189 | 282 | 162 | 400 | 276 | 228 |

Smaller shifts remain even with the default. RIC and PDL are rarely co-signed
before 2019, and EMP (floor amendments) jumps in 2020–2021, when remote
sessions under the pandemic ran many urgent bills. For comparisons across
many years, `types={"REQ", "PL", "PLP", "PEC"}` is the most stable set.

**Signers.** Every deputy row in `proposicoesAutores` counts as a signer:
proposers (`proponente = 1`) and supporting signatures (`proponente = 0`)
alike. Rows for non-deputy authors (Senate, Executive, committees) are
dropped.

**Signature drives are dropped.** Items with more than 50 deputy signers are
left out (`max_authors=50`, `None` keeps everything). PECs and CPI requests
need 171 signatures, a third of the house. Collecting them is a petition,
not collaboration, and a single one forms a clique that swamps the month.
Uncapped, the monthly graph had density 0.58 (Mar 2025) and 0.74 (Sep 2025).
Capped, it had 0.07 and 0.05.

**Edges and weights.**

- Edge if two deputies co-signed at least 1 item (`min_items`).
- `n_items` counts the items they co-signed. `weight` is Newman's
  collaboration weight, the sum of `1 / (k - 1)` over those items, where *k*
  is the number of signers.

**Nodes** are deputies who signed anything that month, including items above
the cap. A deputy who only joined signature drives is an isolated node, not a
missing one.

## Party orientations

**What is published.** For each votação, one row per *bancada* that oriented,
kept as published in `data/camara/orientations/` (`votacao_id, bancada,
orientacao`) for the Plenário roll calls above. The orientation is `Sim`,
`Não`, `Obstrução`, `Liberado` (members are free), `Abstenção` (6 times, all
in 2015), or empty: the bancada is listed but gave no orientation, which
appears from 2021 on. Almost every roll call has orientations (all but 5 of
about 3,900 since 2015).

**What a bancada is.** `politicaleye.camara.decode()` reads the name:

- **A party**, under a label that is often cut short (`Solidaried`,
  `Republican`) and that differs from the deputies' own records (`SOLIDARI`,
  `REPUBLIC`, `PP**`). Both sides are matched on one key (`party_key()`), which
  also maps renames to the current name: PMDB→MDB, PR→PL, PPS→Cidadania,
  PTN→Podemos, PEN→Patriota, PTdoB→Avante, PSDC→DC, PRB→Republicanos.
  Mergers are not mapped: DEM and PSL both existed before they became União.
- **A federation** (from 2023), whose name lists its parties:
  `Fdr PT-PCdoB-PV`.
- **A bloc**, named by concatenating its parties' abbreviations
  (`PmdbPpPtbPscPhsPen`, `Bl MdbPsdRepPode`). A federation inside a bloc is
  written `Fdr` plus its first party (`FdrPt` means PT, PCdoB and PV). Long
  names are cut off with `...`; see "Blocs, recorded daily" below for how
  the parties after the cut are recovered.
- **A leadership**: the Government (`GOV.` until 2022, then `Governo`), the
  Majority, the Minority, the Opposition.

**Which orientation applies to a deputy.** The party is the one on the vote
record (`partido` in `data/camara/votes/`, recorded at the moment of the
vote), so a deputy who switched parties mid-month is held to the right party
on each side of the switch. That party's own orientation applies first, then
its federation's, then its bloc's. An empty orientation passes to the next
level; `Liberado` does not. If two bancadas at the same level disagree for a
party, no orientation applies.

**Discipline.** `politicaleye.camara.discipline(month)` (or
`python -m politicaleye camara discipline YYYY-MM`) counts, per deputy, the
contested votes of the co-voting graph (lopsided votes dropped: a unanimous
vote says nothing about discipline), coded the same way:

- `with_party`: of the votes where the party had a line to follow (`Sim`,
  `Não`, `Obstrução`), the share where the deputy voted it. An `Obstrução`
  orientation is followed by an `Obstrução` or `Não` vote, as in the vote
  coding.
- `with_gov`: the same against the Government leader's orientation.
- `with_majority`: of the votes where the *other* deputies of the same party
  who voted had a majority side, the share where the deputy voted with it.
  This is the usual party-unity measure in political science. It needs no
  orientations, so it covers 97–99% of contested votes in every month, the
  2025 gap included. A deputy's own vote never counts towards the majority they
  are measured against, so a party's only deputy, or a tie among the others,
  gives no majority. Deputies with no party (`S.PART.`) have none.
- `n_free`: the party freed its members. `n_none`: the party, federation or
  bloc is listed but gave no orientation, or the deputy has no party.
  `n_unknown`: the deputy's party matches no published bancada, almost
  always because a bloc's name was cut off.

**Coverage, and the 2025 gap.** `data/camara/index.csv` has, per month,
`orientation_coverage` (the share of contested votes whose party matches a
published bancada), `oriented_share` (the share with a line to follow), and
the pooled `with_party`, `with_gov` and `with_majority`.

- **2015–2022:** median monthly coverage 95–100%.
- **2023–2026:** lower, because large blocs' names are cut off. In 2023 the
  missing parties (PDT, PSB, Avante, Solidariedade, Patriota) are the hidden
  tail of `Bl UniPpFdrPsdbCid...`. In 2026 they are Republicanos, MDB,
  Podemos and PSDB, the tail of `Bl UniPpPsd...`.
- **February to October 2025:** almost every party sat in one bloc
  (`Bl PlFdrPTUniPp...`) that gave no orientation on most votes. The open
  data (the bulk files and the API alike) records no separate orientation
  for its parties.

A month's `with_party` is left empty when under half of its contested votes
had a line to follow (`MIN_ORIENTED` in `summary.py`), since it would describe
only the few parties that did orient: February to October 2025, and
February 2019, the first month of the 56th legislature. The per-deputy
numbers stay correct for deputies whose party did orient. `with_majority`
is unaffected: the median month is 87–94% in every year.

**Blocs, recorded daily.** The Câmara's blocs API
(`/api/v2/blocos?idLegislatura=N`) names each bloc by its full list of
parties (`UNIÃO, PP, PSD, REPUBLICANOS, MDB, Federação PSDB CIDADANIA,
PODE`) and lists its members, but it has no dates and stops listing a bloc
once it is dissolved: the 2023–2024 bloc behind `Bl UniPpFdrPsdbCid...` is
already gone. A daily job (`.github/workflows/camara-blocos.yml`,
`python -m politicaleye camara blocos`) records what it lists for the
legislatures since 2015 in `data/camara/blocos/`:

- `blocos.csv`: `bloco_id, legislatura, nome, federacao, listed_from,
  listed_until`;
- `members.csv`: `bloco_id, partido, listed_from, listed_until`. Members come
  from `/blocos/{id}/partidos`, or, when that is empty (it is for some
  blocs), from the parties the bloc's name lists.

`listed_from` is the first snapshot that listed the row and `listed_until`
the first that no longer did (empty while still listed); a row that comes
back gets a new row. Recording started on 2026-11-07, so rows listed that day
may be older. The job runs at 03:23 in Brasília, before any session: a row
first listed on day D counts for votes from D on, and a row first missing on
day D counts until D−2, since it may have left during D−1. A skipped run
widens that window. A listing with no blocs at all is treated as an outage
and not recorded.

**Completing cut-off names.** A cut-off name is completed when exactly one
recorded bloc of the same legislature, in effect on the day of the votação,
has a name that starts with the same parties in the same order and members
that include them. Two candidate blocs, a different order or a missing party
leave it unknown. `discipline(month, blocs=...)` chooses which record counts:

- `"recorded"` (the default, and what `index.csv` uses): only days the record
  covers, so it changes nothing before 2026-11-07;
- `"listed"`: also earlier days, for blocs already listed when recording
  started. This assumes the bloc had the same members all its life, which
  the API cannot confirm. It completes `Bl UniPpPsd...` and
  `Bl AvanSolidPrd...` and raises coverage from November 2025 to October
  2026 from about 76% to 100%;
- `None`: never.

## Months and vertex sets

**Buckets.** Months are calendar months: the votação date for votes, and
`dataApresentacao` for proposições. Legislatures start on 1 February, so no
month straddles two. `legislatura` is a column of `data/camara/index.csv` and an
attribute of every graph.

**Thin months.** Some months have little or no voting:

- January and the second half of July are recess.
- Election years (2018, 2022, 2026) are thin from August to October.

Check `votacoes_contested` in `data/camara/index.csv` before trusting a month.
Agreement over fewer than about 20 contested votes is noisy.

**The vertex set moves.**

- *Substitutes:* suplentes take seats when a deputy becomes a minister or
  takes leave, so 551 distinct deputies voted in 2025 for 513 seats.
  `aligned()` intersects the two graphs of one month. For a series, intersect
  across months yourself.
- *Party:* a deputy's party is the one on their latest record that month,
  with vote records preferred. Deputies switch parties (14 did in 2025), and
  parties merge (DEM and PSL became União Brasil in 2022). Use the deputy id
  as the identity, never the party. Each vote also carries the party at the
  moment of the vote (`partido` in `data/camara/votes/`).

## Rows that are dropped

Each month is built from its own year's files. A row dated in a different
year than its file is dropped. For example, a handful of proposições in the
2025 file carry 2024 or 2026 dates (50 of 107,587). The build log prints
every such count.

## Not included (yet)

- **The Senado**: its own source, `data/senado/`
  ([methodology/senado.md](senado.md)).
- **Committee and symbolic votes.**
