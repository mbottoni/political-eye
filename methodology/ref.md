# Reference tables: methodology

`data/ref/` holds what ties the sources together.

## One politician across sources: `politicians.csv`

Each source names people its own way:

| `fonte` | `id` | from |
|---|---|---|
| `camara` | deputy id | the Câmara's `deputados.csv` (everyone who served from the 54th legislature, 2011, on) |
| `senado` | `CodigoParlamentar` | the Senado's legislature lists, 54th to 58th, everyone who took office |
| `tse` | `sq_candidato`, one per candidacy | TSE's candidate files for 2018, 2022 and 2026 (federal deputy, senator and senate-suplente candidacies) |
| `emendas` | the Portal da Transparência's author code | `data/emendas/por_autor.csv`; the Portal gives a legislator a new code per mandate |

Each row maps one of those ids to a `pessoa`, named after the person's Câmara
id if they have one (`camara:160649`), else their Senado code, and records the
`metodo` that linked it (empty for the id the person is named after; `manual`
for an override).

**No CPF.** The Câmara's file no longer carries deputies' CPFs, and TSE stopped
publishing candidates' in 2026, so matching does not use them, and nothing in
`data/` carries one.

**How ids are linked**, in this order. A key links two ids only when it is
filled and unique on both sides, so a homonym is left unlinked rather than
guessed:

1. **Câmara ↔ TSE**, one election at a time (people run again): the civil
   name (accents, case and punctuation removed) and birth date
   (`nome_civil+nascimento`); then, for candidacies left, the civil name and
   state (`nome_civil+uf`), the deputy's state taken from their vote records;
   then birth date, first name and state (`nascimento+primeiro_nome+uf`),
   since the two registries spell names differently (SOUZA and SOUSA, an
   added JUNIOR or married name, ORLEANS BRAGANCA and ORLEANS E BRAGANCA).
2. **Senado ↔ TSE**, one election at a time: the full name and state. The
   legislature lists give a senator's state in the identification block
   only for senators in office today, so it is read from the mandate that
   covers the legislature, as in [senado.md](senado.md#votes). Until
   2026-11-14 it was not, and half the Senate candidacies that link now went
   unlinked (122 of 248 in 2018, 2022 and 2026; Rodrigo Pacheco's and Leila
   Barros's among them).
3. **Senado ↔ Câmara**: the full civil name (`nome_civil`), for senators who
   were deputies.
4. **Amendment authors ↔ legislators**: the author's name against deputies'
   and senators' parliamentary names, among those in office in an
   amendment's year or the year before (`nome_parlamentar+mandato`). A name
   that hits a deputy and a senator who are already one person (Esperidião
   Amin, deputy then senator) links to that person; two different people
   leave it unlinked. Benches, committees and the budget rapporteur are not
   people and stay unlinked.

People are the connected groups of these links. `data/ref/overrides.csv`
(`fonte, id, pessoa`) fixes or adds a link by hand. It links Eduardo Gomes
(TO) to his 2018 Senate candidacy: TSE lists him twice that year, as first
suplente and as senator, so name and state are not unique.

**Coverage** (2026-11-07):

- 99.4% of the federal deputies elected in 2018, and 99.8% in 2022, link to
  a Câmara id; every deputy who voted in this legislature links to a
  candidacy.
- 2026: 64% of elected deputies and 26% of elected senators, because those
  elected for the first time get a Câmara or Senado id only when they take
  office on 1 February 2027. The weekly job links them then.
- Senators (2026-11-14, with states read from the mandates): 53 of the 54
  elected in 2018 and all 27 elected in 2022 link to a Senado id, and 105 of
  the 106 senators who sat in the 57th legislature link to a Senate
  candidacy of 2018, 2022 or 2026.
- 1,478 of 1,664 amendment-author codes link to a person. Of the rest, 121
  are benches, committees or the rapporteur; the others are homonyms or
  names written differently.

Rebuilt weekly (`.github/workflows/ref.yml`) after the Saturday jobs.

## Mayors: `prefeitos.csv`

Every municipality's elected mayor, from TSE's candidate files for the
municipal elections of 2016, 2020 and 2024
(`cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_<year>.zip`,
the `*_BRASIL.csv` member, latin1, `;`). Built by
`python -m politicaleye ref prefeitos` (`politicaleye/ref/prefeitos.py`).

| column | meaning |
|---|---|
| `ano` | the election year of the file (2016, 2020, 2024) |
| `cod_ibge` | the municipality's IBGE code |
| `municipio`, `uf`, `sg_ue` | TSE's name, state and own code for it |
| `eleicao`, `data_eleicao`, `suplementar` | the election (`1` for a supplementary election held during the term) |
| `turno`, `sq_candidato`, `nome_urna`, `partido`, `genero`, `cor_raca` | the winner, as TSE records them |

One row per municipality and election won: candidates for `PREFEITO` whose
result (`DS_SIT_TOT_TURNO`) is `ELEITO`, in the last round. No CPF is kept.

**Matching to IBGE.** TSE names municipalities by its own code and name.
Each is matched to `data/siconfi/entes.csv` by state and normalised name (no
accents, apostrophes or hyphens: `Santa Bárbara d'Oeste` is
`SANTA BARBARA DOESTE`), with a short list of spellings that differ between
the two registries (`EMBU` is `Embu das Artes`, `ASSU` is `Açu`; the list is
`SPELLING` in the code). Every municipality matches. In 2024, 5,528 regular
elections had a winner. The rest had none at build time: annulled or
contested elections, Brasília, Fernando de Noronha.

**Who governed in a year** (`mayor_by_year`). For the terms 2017–2020,
2021–2024 and 2025–2028, the regular winner of the election before the term.
A supplementary election's winner replaces them from the year after that
election. The calendar year is the unit, so a mayor replaced mid-year is
attributed the whole year.

**Parties across elections.** Pages that compare parties across terms count
merged and renamed parties under their successor's name today: PMDB is MDB,
PR is PL, PRB is Republicanos, DEM and PSL are União, PPS is Cidadania,
PTN, PHS and PSC are Podemos, PEN, Patriota, PRP and PTB are PRD, PSDC is DC,
PT do B is Avante, SD and PROS are Solidariedade, PPL is PCdoB.
