# TSE: methodology

Where the money of each candidate in Brazil's general elections (president,
governors, senators, federal, state and district deputies) came from and
went to, for 2018, 2022 and 2026. Since 2015 companies cannot donate, so a
campaign's money is public funds handed out by party leaderships (the
Special Campaign Fund, FEFC, and the Party Fund), private individuals, and
the candidate's own pocket.

## Source

TSE's open-data CDN, two zips per election, regenerated as accounts are
filed and judged:

| file | size (2026) | what it gives us |
|---|---|---|
| `consulta_cand/consulta_cand_<year>.zip` | 3 MB | every candidate: office, state, party, federation, status, result per round |
| `prestacao_contas/prestacao_de_contas_eleitorais_candidatos_<year>.zip` | 350 MB (2022: 495 MB) | every revenue, contracted expense and payment declared |

Each zip holds a `*_BRASIL.csv` for the whole country and one copy per
state; only the national file is read. latin-1, `;`-separated.
`data/tse/sources.json` records each zip's URL, size, ETag and
`Last-Modified`. The weekly job rebuilds the latest general election;
earlier ones are rebuilt on request (`python -m politicaleye tse update
2018 2022`).

**Raw files are not committed.** A single election's expenses are over 1.5
GB uncompressed. Only the derived tables below are.

## Tables

All under `data/tse/<year>/`; a candidate is `sq_candidato`, TSE's id for a
candidacy.

| table | one row per |
|---|---|
| `candidatos.csv` | candidate: `cargo`, `uf`, `ue`, `numero`, `nome`, `nome_urna`, `partido`, `federacao`, `situacao_candidatura`, `resultado` (of the last round they ran in), `genero`, `cor_raca`, `ocupacao` |
| `receitas_por_candidato.csv` | candidate: `total`, `financeiro` (cash, as opposed to estimated in-kind), by origin (`origem_partido`, `origem_pessoas_fisicas`, `origem_outros_candidatos`, `origem_proprios`, `origem_financiamento_coletivo`, `origem_internet`, `origem_outras`), by fund (`fonte_fefc`, `fonte_fundo_partidario`, `fonte_outros_recursos`, `fonte_outras`), and `n_doadores_pf` |
| `repasses_partidarios.csv` | candidate, party organ and fund: what each party directorate (`cnpj_orgao`, `partido`, `esfera` national/state/municipal, `uf_orgao`) transferred, from which `fonte` |
| `grandes_doadores.csv` | private donor who gave R$50,000 or more in the election: `doador` (CPF masked), `nome`, `uf`, `total`, `n_candidatos` |
| `doacoes_grandes_doadores.csv` | large donor and candidate: `valor` |
| `despesas_por_candidato.csv` | candidate: `contratado`, `pago` |
| `fornecedores.csv` | company (14-digit CNPJ) that candidates contracted for R$50,000 or more in all: `nome`, `cnae`, `total`, `n_candidatos` |

Money is in reais with two decimals, summed in centavos. TSE's placeholders
(`#NULO`, `#NULO#`, `-1`, `-4`) become empty.

**Payments carry no candidate.** The paid-expenses file names only the
account (`SQ_PRESTADOR_CONTAS`); it is joined to the candidate through the
revenue and contracted-expense files, which name both. No payment has been
left unmatched so far (the build log prints the amount if one is).

## People's data

- **Candidates** are listed by name, as TSE publishes them; TSE itself no
  longer publishes their CPF or voter id (`-4`).
- **Private donors are listed only above R$50,000** (`DONOR_MIN` in
  `build.py`), with their CPF masked the CGU way (`***.462.240-**`). A
  donation that size is a matter of public interest; a citizen who gave R$100
  is not, so smaller donors appear only as a count (`n_doadores_pf`) and in
  each candidate's totals. Donors are grouped on their full CPF before it is
  masked, so two people with the same masked CPF and name stay apart. Large
  donors hold about half of all money from individuals (2018: 38%; 2022:
  51%; 2026: 52%), from 1,215 people in 2018, 2,463 in 2022 and 2,738 in 2026.
- **Suppliers** are listed only when they are companies; people paid by
  campaigns (canvassers, drivers) are not.

## What the numbers show

| | 2018 | 2022 | 2026 |
|---|---|---|---|
| candidates | 29,227 | 29,270 | 20,989 |
| money declared (R$ bn) | 3.34 | 6.64 | 6.99 |
| of which FEFC (R$ bn) | 1.83 | 4.90 | 5.03 |
| elected federal deputies' median (R$ M) | 1.05 | 1.95 | 2.50 |
| share of their money from their parties | 78% | 85% | 89% |

Since the public fund grew, a deputy's campaign is mostly money their party
leadership chose to give them: `repasses_partidarios.csv` shows which
directorate gave how much to whom.

## Gaps

- **2026 candidacy status** (`situacao_candidatura`) is blank in TSE's file.
- **Amapá's 2026 federal deputies have no result yet** (2026-11-14): all 91 candidates are `#NULO` (empty
  here), so 505 of the 513 seats are known. Every other state has as many elected as seats.
- **2026 accounts are still being filed and judged**: second-round accounts
  and late or rectifying filings arrive in the weeks after the election, so
  2026 numbers will move in the weekly diffs.
- **Municipal elections** (2020, 2024) are not included: 2024's accounts file
  alone is 1.3 GB.
- **Original donors** (`receitas_candidatos_doador_originario`, who funded a
  party before it passed money on) are not used yet.

## Size

About 10–12 MB per election, 32 MB in all.
