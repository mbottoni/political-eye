# Câmara: methodology

Every choice below changes the graphs. Each one is a parameter of
`politicaleye.camara.graph()`, and the defaults are what `data/camara/index.csv`
and the explorer use.

## Source

Four yearly bulk files from the Câmara's open data portal,
`https://dadosabertos.camara.leg.br/arquivos/<dataset>/csv/<dataset>-<year>.csv`:

| dataset | what it gives us |
|---|---|
| `votacoes` | every votação: date, body (`siglaOrgao`), outcome, description |
| `votacoesVotos` | how each deputy voted, for votações with a per-deputy record |
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
  as the identity, never the party.

## Rows that are dropped

Each month is built from its own year's files. A row dated in a different
year than its file is dropped. For example, a handful of proposições in the
2025 file carry 2024 or 2026 dates (50 of 107,587). The build log prints
every such count.

## Not included (yet)

- **Party orientations** (`votacoesOrientacoes`, how each party leader told
  the party to vote). This would allow party-discipline features per edge.
- **The Senado**, which publishes its own API. It will be its own source
  in this repo (`data/senado/`), not part of these tables.
- **Committee and symbolic votes.**
