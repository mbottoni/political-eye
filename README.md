# camara-graphs

**Brazil's Chamber of Deputies, one month at a time, as two graphs on the same deputies: who votes together, and who signs together.**

Built from the Câmara's official open data, from 2015 onward, and rebuilt every week by CI. The git history of `data/` is the history of the record, including the Câmara's own corrections.

It is meant for graph statistics on real, paired and evolving networks:

- **Model fitting:** fit a random-graph model to each month and track how its parameters move.
- **Dependence testing:** test dependence between co-voting and co-authorship, which share one vertex set.
- **Change points:** look for structural breaks around the 2016 impeachment and the 2019 and 2023 turnovers of the house, with the 2027 turnover still to come.

## See it

**[Open the interactive explorer →](https://mbottoni.github.io/camara-graphs/)**

The explorer runs in your browser:

- pick any month, or click one on the timeline;
- move the vote-together threshold;
- hover or click a deputy to see who they vote and sign with;
- hover the party heatmap;
- share a view by its URL.

It recomputes the graphs from `data/` and matches the Python package exactly; CI checks this on every month (`tests/parity.mjs`).

### Charts

The charts below are re-rendered by CI after every weekly update. Click any network image to open it in the explorer.

**The latest full month as two graphs on the same deputies.** Each dot is a deputy, placed by how they voted. The top panel links deputies who voted alike on at least 80% of contested roll calls. The bottom panel links deputies who co-signed a proposição.

The two graphs are related but far from copies of each other:

- Pairs who co-sign are more likely than random pairs to also vote together. This held in every month since 2015 with at least 30 contested roll calls (as of November 2026), though sometimes only barely.
- Most pairs who vote together never co-sign.

<a href="https://mbottoni.github.io/camara-graphs/"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/network-dark.png">
  <img alt="Co-voting and co-authorship graphs of the latest full month, deputies colored PT, PL or other" src="figures/network-light.png">
</picture></a>

### Pick a party

<!-- BEGIN:PARTIES -->
Click a party to see its deputies (dark) against everyone else in 2026-03, with everyone they vote together and sign together with. Each image opens that party in the explorer.

<details>
<summary><b>PL</b> · 91 deputies · agree with each other 80% · closest: UNIÃO (55%) · farthest: PSOL (23%)</summary>

<a href="https://mbottoni.github.io/camara-graphs/?month=2026-03&amp;a=PL"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/party-PL-dark.png">
  <img alt="PL deputies and their vote-together and sign-together edges in 2026-03" src="figures/party-PL-light.png">
</picture></a>

PL deputies vote alike (≥ 80% of shared votes) with 396 deputies outside the party, and co-signed with 188 deputies, 63% of them from other parties.

</details>
<details>
<summary><b>PT</b> · 67 deputies · agree with each other 99% · closest: PCdoB (96%) · farthest: PL (30%)</summary>

<a href="https://mbottoni.github.io/camara-graphs/?month=2026-03&amp;a=PT"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/party-PT-dark.png">
  <img alt="PT deputies and their vote-together and sign-together edges in 2026-03" src="figures/party-PT-light.png">
</picture></a>

PT deputies vote alike (≥ 80% of shared votes) with 265 deputies outside the party, and co-signed with 149 deputies, 58% of them from other parties.

</details>
<details>
<summary><b>UNIÃO</b> · 53 deputies · agree with each other 66% · closest: PSB (73%) · farthest: PL (55%)</summary>

<a href="https://mbottoni.github.io/camara-graphs/?month=2026-03&amp;a=UNI%C3%83O"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/party-UNIAO-dark.png">
  <img alt="UNIÃO deputies and their vote-together and sign-together edges in 2026-03" src="figures/party-UNIAO-light.png">
</picture></a>

UNIÃO deputies vote alike (≥ 80% of shared votes) with 449 deputies outside the party, and co-signed with 235 deputies, 93% of them from other parties.

</details>
<details>
<summary><b>PP</b> · 46 deputies · agree with each other 71% · closest: PSB (77%) · farthest: PL (52%)</summary>

<a href="https://mbottoni.github.io/camara-graphs/?month=2026-03&amp;a=PP"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/party-PP-dark.png">
  <img alt="PP deputies and their vote-together and sign-together edges in 2026-03" src="figures/party-PP-light.png">
</picture></a>

PP deputies vote alike (≥ 80% of shared votes) with 454 deputies outside the party, and co-signed with 231 deputies, 91% of them from other parties.

</details>
<details>
<summary><b>PSD</b> · 45 deputies · agree with each other 75% · closest: PCdoB (80%) · farthest: PL (46%)</summary>

<a href="https://mbottoni.github.io/camara-graphs/?month=2026-03&amp;a=PSD"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/party-PSD-dark.png">
  <img alt="PSD deputies and their vote-together and sign-together edges in 2026-03" src="figures/party-PSD-light.png">
</picture></a>

PSD deputies vote alike (≥ 80% of shared votes) with 441 deputies outside the party, and co-signed with 224 deputies, 92% of them from other parties.

</details>
<details>
<summary><b>REPUBLICANOS</b> · 42 deputies · agree with each other 80% · closest: PCdoB (81%) · farthest: PL (48%)</summary>

<a href="https://mbottoni.github.io/camara-graphs/?month=2026-03&amp;a=REPUBLICANOS"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/party-REPUBLICANOS-dark.png">
  <img alt="REPUBLICANOS deputies and their vote-together and sign-together edges in 2026-03" src="figures/party-REPUBLICANOS-light.png">
</picture></a>

REPUBLICANOS deputies vote alike (≥ 80% of shared votes) with 437 deputies outside the party, and co-signed with 236 deputies, 93% of them from other parties.

</details>
<details>
<summary><b>MDB</b> · 39 deputies · agree with each other 76% · closest: PSB (79%) · farthest: PL (53%)</summary>

<a href="https://mbottoni.github.io/camara-graphs/?month=2026-03&amp;a=MDB"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/party-MDB-dark.png">
  <img alt="MDB deputies and their vote-together and sign-together edges in 2026-03" src="figures/party-MDB-light.png">
</picture></a>

MDB deputies vote alike (≥ 80% of shared votes) with 458 deputies outside the party, and co-signed with 209 deputies, 93% of them from other parties.

</details>
<!-- END:PARTIES -->

**How often each pair of parties votes alike** in that month. Parties are ordered from the government side to the opposition.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/parties-dark.svg">
  <img alt="Heatmap of mean pairwise agreement between parties" src="figures/parties-light.svg">
</picture>

**Every month since 2015.** Gaps are recesses and election campaigns.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/timeline-dark.svg">
  <img alt="Monthly density of the co-voting and co-authorship graphs, 2015 to today" src="figures/timeline-light.svg">
</picture>

### Browse the tables

GitHub shows the smaller CSVs as searchable tables. To get one, open a file, or click **Raw** and save it.

| what | file |
|---|---|
| one row per month: roll calls, graph sizes and densities | [`data/index.csv`](data/index.csv) |
| deputies active in a month, with party and state | [`data/deputies/`](data/deputies) |
| that month's roll calls, with what was voted | [`data/votacoes/`](data/votacoes) |
| every deputy's vote | [`data/votes/`](data/votes) |
| every deputy signature on a proposição | [`data/authorship/`](data/authorship) |

## Quick start

```bash
git clone https://github.com/mbottoni/camara-graphs && cd camara-graphs
uv sync
```

```python
import camaragraphs as cg

G = cg.graph("2025-09", "covote")          # networkx.Graph, nodes are deputy ids
G.nodes[204379]                             # {'name': 'Acácio Favacho', 'party': 'MDB', 'uf': 'AP'}

gv, gc = cg.aligned("2025-09")              # both graphs on the same vertex set

for month, G in cg.series("covote", start="2023-02"):
    ...                                     # every month of the 57th legislature

cg.covote_edges("2025-09")                  # weighted: n_shared, n_agree, agreement per pair
cg.cosponsor_edges("2025-09", types={"PL", "PLP", "PEC"})   # bills only
```

From the shell: `uv run camaragraphs export 2025-09 --kind cosponsor > edges.csv`.

Without cloning, install with `pip install git+https://github.com/mbottoni/camara-graphs` and pass `data_dir="https://raw.githubusercontent.com/mbottoni/camara-graphs/main/data"` to any function.

## The two graphs

| graph | edge between two deputies when… | defaults | nodes |
|---|---|---|---|
| `covote` | they agreed on at least `tau` of the contested Plenário roll calls both cast | `tau=0.8`, at least 10 shared votes, votes with under 2.5% minority dropped | deputies with at least 10 contested votes that month |
| `cosponsor` | they co-signed at least `min_items` proposições that month | `min_items=1`; items with more than 50 deputy signers (signature drives) and procedural types RPD and DOC dropped | deputies who signed anything that month |

Edges carry their evidence: `n_shared`, `n_agree` and `agreement` on co-voting edges, and `n_items` and Newman's `weight` on co-authorship edges. Nodes carry `name`, `party` and `uf`.

Every default is a parameter. **[METHODOLOGY.md](METHODOLOGY.md)** gives the reasons for each, and how much it moves the graph.

## Coverage

<!-- BEGIN:COVERAGE -->
| legislatura | from → to | months | roll calls | contested | co-signed items |
|---|---|---:|---:|---:|---:|
| 54 | 2015-01 → 2015-01 | 1 | 0 | 0 | 0 |
| 55 | 2015-02 → 2019-01 | 48 | 816 | 705 | 3,658 |
| 56 | 2019-02 → 2023-01 | 48 | 1,971 | 1,723 | 10,326 |
| 57 | 2023-02 → 2026-11 | 46 | 1,128 | 1,039 | 11,232 |
<!-- END:COVERAGE -->

## Latest months

Generated by CI. All months are in [`data/index.csv`](data/index.csv). Months in recess (January, late July) and campaign months in election years have few roll calls, so check `contested` before trusting one.

<!-- BEGIN:RECENT -->
| month | roll calls (contested) | co-voting nodes | edges | density | mean agreement | co-authorship nodes | edges | density | aligned nodes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-11 | 0 (0) | 0 | 0 | 0.000 | -- | 151 | 57 | 0.005 | 0 |
| 2026-10 | 3 (2) | 0 | 0 | 0.000 | -- | 309 | 345 | 0.007 | 0 |
| 2026-09 | 3 (2) | 0 | 0 | 0.000 | -- | 226 | 800 | 0.032 | 0 |
| 2026-08 | 5 (5) | 0 | 0 | 0.000 | -- | 432 | 310 | 0.003 | 0 |
| 2026-07 | 6 (5) | 0 | 0 | 0.000 | -- | 406 | 1,287 | 0.016 | 0 |
| 2026-06 | 7 (7) | 0 | 0 | 0.000 | -- | 458 | 1,042 | 0.010 | 0 |
| 2026-05 | 24 (20) | 484 | 41,572 | 0.356 | 0.658 | 488 | 1,772 | 0.015 | 454 |
| 2026-04 | 19 (17) | 435 | 38,543 | 0.408 | 0.715 | 474 | 3,703 | 0.033 | 401 |
| 2026-03 | 41 (39) | 503 | 51,903 | 0.411 | 0.653 | 475 | 6,590 | 0.059 | 455 |
| 2026-02 | 18 (18) | 443 | 42,049 | 0.429 | 0.652 | 484 | 3,003 | 0.026 | 415 |
| 2026-01 | 0 (0) | 0 | 0 | 0.000 | -- | 1 | 0 | 0.000 | 0 |
| 2025-12 | 44 (38) | 503 | 38,503 | 0.305 | 0.607 | 493 | 2,081 | 0.017 | 480 |
<!-- END:RECENT -->

## What is stored

Graphs are not stored. Every pair of deputies, every month, would be about 270 MB of CSV. Instead `data/` holds the tidy inputs, and a graph is a sub-second function of them:

```
data/
  votacoes/YYYY-MM.csv    Plenário roll calls: id, data, hora_registro, aprovacao, votos_sim, votos_nao, votos_outros, descricao
  votes/YYYY-MM.csv       votacao_id, deputado_id, voto (Sim | Não | Obstrução | Abstenção | Artigo 17)
  authorship/YYYY-MM.csv  proposicao_id, sigla_tipo, data_apresentacao, deputado_id, ordem_assinatura, proponente
  deputies/YYYY-MM.csv    deputado_id, nome, partido, uf, n_votes, n_authored
  index.csv               one row per month: counts, densities, aligned vertex-set size
  sources.json            ETag, size and Last-Modified of every raw file used
figures/                  the charts above, light and dark (camaragraphs figures)
docs/                     the interactive explorer (GitHub Pages), reading data/ live
```

The files are sorted and rebuilt deterministically, so `git log -p data/votes/2025-09.csv` shows exactly what the Câmara changed and when.

## How it updates

`.github/workflows/update.yml` runs every Saturday, after the week's sessions (Plenário votes Tuesday to Thursday):

1. It downloads the previous and current year's bulk files. The server drops long transfers, so downloads resume with `Range` + `If-Range`.
2. It rebuilds those years and refreshes the index, the tables and the charts above.
3. It commits only if a table or chart changed. Rendering is byte-deterministic, so an unchanged month never produces a commit.

To rebuild other years, run the workflow by hand with `years` set, or run locally:

```bash
uv run python -m camaragraphs update 2015 2016 2017   # any years
```

## Source and license

Data: [Câmara dos Deputados, Dados Abertos](https://dadosabertos.camara.leg.br/). Code: MIT.
