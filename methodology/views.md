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
| `prefeito_mesmo_partido_valor` | that money in reais: amendment money paid to towns whose mayor was of the deputy's party that year |
| `prefeito_base` | the same share by chance: the share of the deputy's own state's towns that party ran that year, averaged over the same payments |
| `presenca`, `votacoes_mandato` | roll-call participation: the votes they cast over the roll calls held, in the months they appear in the Câmara's tables (voting or signing), and that number of roll calls |
| `propostas_autor`, `projetos_autor`, `propostas_coautor` | proposals they presented as first signer (all, and bills: PL, PLP, PEC, PDL, PRC) and proposals they co-signed |
| `relatorias`, `partidos` | rapporteur opinions and substitutes as first signer; how many parties they were in over the legislature |

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

**The profile's work record.** `atividade_<leg>.csv` has, per deputy and
month, the roll calls held, the votes they cast, and the proposals they
presented as first signer (all, and bills) or co-signed. Every proposal of the
Câmara's authorship tables counts ([camara.md](camara.md)): the first signer
is signing order 1, everyone after is a co-signer. `propostas_<leg>.csv`
groups them by kind, from the type code: bills (PL, PLP, PEC, PDL, PRC);
rapporteur opinions and substitutes (PRL and its variants, PPP, PEP, PSS, SBT,
SBR, EMR, CVO, VTS, RDF); amendments to bills (EMC, EMP, ESB, EMS, EMA, EML,
EMO, SOR, SLD); information requests and oversight (RIC, PFC, SIT);
procedural requests and suggestions to the executive (REQ, RPD, RPDR, DTQ,
INC); and everything else. `coautores_<leg>.csv` keeps each deputy's eight
most frequent co-signers, over proposals with at most 50 signers (the same
cut that leaves signature drives out of the co-authorship graph).
`partidos_<leg>.csv` lists the parties a deputy sat under, from the first
to the last month they appear under each.

Three cautions the page states where they apply:

- **Participation is not attendance.** It counts votes registered in roll
  calls. The Câmara's official attendance (present at a session) is a
  different record. A month a deputy missed entirely does not count against
  them, since they don't appear in that month's tables.
- **The Speaker votes only to break a tie.** Rodrigo Maia (February 2019 to
  January 2021), Arthur Lira (February 2021 to January 2025) and Hugo Motta
  (from February 2025) have low participation for that reason; their profile
  says so.
- **Board members sign opinions by the thousand.** Members of the Mesa
  Diretora sign the board's opinions on information requests as rapporteur
  (PRL): on 2026-11-08, Altineu Côrtes had 10,969 and Marcos Pereira 7,634.
  Those counts are real but measure administrative work, not bill
  rapporteurships, so the page compares deputies on bills filed, not on
  opinions.

The profile ranks a deputy among the legislature's deputies with six months
or more in office, so a substitute's few weeks don't set the scale. On
2026-11-08 the median deputy of the 57th legislature had voted in 80% of roll
calls and filed 20 bills.

## The election tab: `data/site/eleicao/`

Built by `python -m politicaleye site build eleicao` (in the weekly `tse` and
`ref` workflows) for the deputies page's **Eleição** tab: what the general
election at the end of a legislature did to its deputies, and the Chamber it
chose. The 57th legislature goes with the 2026 election, the 56th with 2022.

**Each deputy's outcome** (`deputados_<leg>.csv`, one row per deputy of the
legislature, substitutes who took a seat included). The deputy's candidacies
in that election come from the crosswalk, for any office ([ref.md](ref.md)).
When a deputy has two (registered for the Câmara, then ran for the Senate),
the one that went to the ballot counts: a candidacy with a result before one
without, a win before a loss. The outcome (`grupo`):

| `grupo` | rule |
|---|---|
| `reeleito` | ran for federal deputy and TSE's result starts with ELEITO (ELEITO POR QP, ELEITO POR MÉDIA) |
| `nao_reeleito` | ran for federal deputy and ended SUPLENTE or NÃO ELEITO |
| `outro_eleito`, `outro_derrotado` | ran for another office (senator or Senate substitute, governor or deputy governor, state or district deputy, president or vice-president) and won or lost |
| `sem_resultado` | the candidacy has no result in TSE's file: Amapá's federal deputies on 2026-11-14 (the state's count is not in it yet), or a candidacy withdrawn, refused or under appeal |
| `nao_concorreu` | no candidacy linked: they did not run, or the crosswalk could not tie their candidacy to them |

Beside the outcome: the office, result, party, state and gender of the
candidacy, the money it raised (`campanha_total`, TSE's revenue), the party
they ran under or, if they did not run, their last party in the Câmara
(`partido_eleicao`, one name per party), and what the tab compares the
outcomes on: the ranking page's index with its default weights (`indice`,
computed as [ranking.md](ranking.md) describes, only for deputies with 12
months or more), roll-call participation (the Speaker's left out), amendment
money paid, and the share and amount of it paid to towns run by their party
(`prefeito_mesmo_partido`, `prefeito_base`, `prefeito_mesmo_partido_valor`,
above). The tab compares deputies with 12 months or more in office and states
that it describes the groups: the re-elected also differ in party, state, time
in office and campaign money.

**The Chamber the election chose** (`eleitos_<year>.csv`): every federal
deputy elected, with `origem`: `reeleito` if they are a deputy of the outgoing
legislature, `ex_deputado` if they first appear in the Câmara's monthly tables
(from 2015) in an earlier legislature or have a Câmara id from before 2015,
`novo` otherwise. The Câmara gives new deputies an id only when they take
office, so until February those elected for the first time are the ones with
no Câmara id; after it, the first legislature they appear in tells them apart.

**Seats per party** (`partidos_<year>.csv`): won at the election before
(`eleitos_antes`), held by the deputies in the Câmara's tables in the election
month (`em_exercicio`: those who voted or filed a proposal in October; former
deputies credited as authors of a paper, with no party or state, are left
out), and won at this election, split by origin. Merged parties count under
today's name (PSC as PODE, PTB and PATRIOTA as PRD, PROS as SOLIDARIEDADE).

`resumo.json` has, per legislature, the counts per outcome, the re-election
rate among those who ran for the Câmara again and have a result, the seats
known and the states still without a result (a state with fewer elected than
its seats).

On 2026-11-14, of the 57th legislature's 644 deputies: 306 re-elected, 186 not
re-elected (168 of them substitutes), 34 elected to another office (19 to the
Senate), 41 lost a race for another office, 17 with no result, 60 did not run.
62% of those who ran for the Câmara again and have a result were re-elected
(61% in 2022). Of the 505 elected so far (Amapá's 8 seats missing), 306 sat in
the 57th, 25 are former deputies, 174 are new.
