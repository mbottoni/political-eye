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
