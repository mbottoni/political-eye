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

