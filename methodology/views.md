# Views: methodology

Tables that join the sources, through the crosswalk in `data/ref/politicians.csv`
([ref.md](ref.md)). They hold no new data: each is a deterministic function
of the committed tables, rebuilt weekly (`.github/workflows/ref.yml`) and by
`python -m politicaleye views update [legislaturas]`.

## `data/views/deputados_<leg>.csv`: one row per deputy

Every deputy who cast a contested Plenário vote in legislature `<leg>` (the
current one and the one before). The Câmara's records also carry senators who
once had a deputy id and signed a bill; they are not deputies of the
legislature and are left out.

| columns | from | meaning |
|---|---|---|
| `pessoa`, `deputado_id`, `nome`, `partido`, `uf` | crosswalk, Câmara | the person; name, party and state as of their last month in the legislature |
| `meses` | Câmara | months they appear in |
| `n_votes`, `n_party`, `with_party`, `n_gov`, `with_gov`, `n_majority`, `with_majority` | Câmara ([camara.md](camara.md#party-orientations)) | discipline, pooled over every month of the legislature: counts summed, then the shares |
| `emendas`, `emendas_empenhado`, `emendas_pago` | Portal da Transparência ([emendas.md](emendas.md)) | amendments authored for the budgets the legislature approved, by every author code of the person: for the 57th (2023–2027), the budgets of 2024 to 2027, since each year's budget is voted the year before |
| `campanha_sq_candidato`, `campanha_resultado`, `campanha_total`, `campanha_partido`, `campanha_fefc`, `campanha_proprios`, `campanha_doadores_pf` | TSE ([tse.md](tse.md)) | their federal-deputy campaign in the election that chose the legislature (2022 for the 57th, 2018 for the 56th): money in all, from their party, from the public campaign fund, from their own pocket, and the number of private donors |

Empty means the source has nothing for that person: no contested vote with
an orientation, no linked amendment author, or no linked candidacy. In the
57th legislature every deputy links to a candidacy (suplentes who took office
included) and 84% to amendments; the rest took office late or briefly.

## `data/views/municipios.csv`: one row per municipality and year

Every municipality in Siconfi's list (`entes.csv`), for every year either
source covers, joined on the IBGE code.

| columns | from | meaning |
|---|---|---|
| `cod_ibge`, `ente`, `uf`, `populacao` | Siconfi | the municipality, with Siconfi's population figure |
| `ano` | | the budget year (amendments) and fiscal year (Siconfi) |
| `emendas`, `emendas_empenhado`, `emendas_pago` | Portal da Transparência ([emendas.md](emendas.md)) | amendments applied to the municipality that year, all types: distinct amendment codes, committed, paid |
| `emendas_pix_pago` | Portal da Transparência | of that, paid by "Pix" amendments (`especial`), sent straight to the town's account |
| `emendas_pago_por_habitante` | both | paid per inhabitant |
| `dtp_pct`, `situacao` | Siconfi ([siconfi.md](siconfi.md)) | payroll as a share of net current revenue, and where it stands against the legal limits |
| `caixa_liquida_livre` | Siconfi | unrestricted cash left after carried-over commitments, at the end of the year |

Amendments applied to several municipalities, to a whole state or nationally
are not split among towns, so a town's amendment money here is a lower
bound. Siconfi columns fill in as its history is read
([siconfi.md](siconfi.md#source)).

## The deputies page: `data/site/deputados/`

Built by `python -m politicaleye site build deputados` (in the weekly `ref`
workflow, after the views) for [the deputies page](https://mbottoni.github.io/political-eye/deputados/).
`deputados_<leg>.csv` is the view above plus:

| columns | meaning |
|---|---|
| `pc1`, `eigen` | mean over the legislature's months of the deputy's position on the first principal component of the roll calls (PT's side negative) and of their eigenvector centrality in the co-voting graph ([camara.md](camara.md)) |
| `cross_share` | of their co-voting ties over those months, the share to deputies of another party |
| `emendas_pago_estado`, `emendas_pago_nacional` | of their amendment money paid, the share applied in their own state and the share with no state (national programmes) |
| `grandes_doadores`, `grandes_doadores_valor` | donors of R$50,000 or more to the campaign that elected them, and what they gave |
| `sancoes_pago_total`, `sancoes_pago_sancionadas`, `sancoes_empresas` | from the sanctions page ([sancoes.md](sancoes.md)): amendment money paid, and paid to companies while under a barring sanction, every budget since 2015 |
| `prefeito_mesmo_partido` | of their amendment money that reached a town (payments table, recipient's town), the share paid in a year when that town's mayor ([ref.md](ref.md), `prefeitos.csv`) was of the deputy's party in the month of the payment |
| `prefeito_base` | the same share by chance: the share of the deputy's own state's towns that party ran that year, averaged over the same payments |

Parties are matched under one name per party as it stood in the year of the
payment: spellings and renamings are unified (PMDB is MDB, PR is PL), and
mergers count from the year they happened (DEM and PSL are UNIÃO from 2022,
PTB and PATRIOTA are PRD from 2024). Sending more than chance to towns run
by one's party is an association: those mayors may also ask more, or run
larger towns.

`vizinhos_<leg>.csv` lists each deputy's eight closest and eight furthest
co-voters over the legislature: pairs that both voted on at least 50
contested roll calls, ranked by the Wilson score interval of the share they
voted the same way (the lower bound for the closest, the upper for the
furthest), so that 480 agreements out of 500 outrank 50 out of 52.
`emendas_<leg>.csv`, `destinos_<leg>.csv` and `doadores_<leg>.csv` hold
each deputy's amendments by year and type, the towns their amendment money
was paid to, and their campaign's large donors (CPF masked).
