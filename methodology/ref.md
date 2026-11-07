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
2. **Senado ↔ TSE**, one election at a time: the full name and state.
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
(`fonte, id, pessoa`) fixes or adds a link by hand.

**Coverage** (2026-11-07):

- 99.4% of the federal deputies elected in 2018, and 99.8% in 2022, link to
  a Câmara id; every deputy who voted in this legislature links to a
  candidacy.
- 2026: 64% of elected deputies and 26% of elected senators, because those
  elected for the first time get a Câmara or Senado id only when they take
  office on 1 February 2027. The weekly job links them then.
- 1,478 of 1,664 amendment-author codes link to a person. Of the rest, 121
  are benches, committees or the rapporteur; the others are homonyms or
  names written differently.

Rebuilt weekly (`.github/workflows/ref.yml`) after the Saturday jobs.
