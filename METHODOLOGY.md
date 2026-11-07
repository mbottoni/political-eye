# Methodology

Each source has its own file under `methodology/`, with every rule that
changes its numbers and every problem found in its data:

| source | data | methodology |
|---|---|---|
| Câmara dos Deputados | `data/camara/` | [methodology/camara.md](methodology/camara.md) |
| Senado Federal | `data/senado/` | [methodology/senado.md](methodology/senado.md) |
| Parliamentary amendments | `data/emendas/` | [methodology/emendas.md](methodology/emendas.md) |
| Sanctions | `data/sancoes/` | [methodology/sancoes.md](methodology/sancoes.md) |

The rules below hold for every source.

## Official data only

Every table comes from a government publisher's open data, named with its
URLs in the source's methodology file. Nothing is scraped from news sites or
third-party mirrors.

## What is committed

- **Raw files are not committed.** They are downloaded to
  `.cache/raw/<source>/`, which git ignores. The repo holds the tidy tables
  built from them, in `data/<source>/`.
- **Tables are deterministic.** CSV, sorted, `\n` line endings. A rebuild
  that changes nothing produces no diff, so each commit's diff is what
  changed at the source that week or day, corrections included.
- **Provenance.** `data/<source>/sources.json` records what every build
  used: the URL, size, ETag and `Last-Modified` of each bulk file, or the
  URL, size and SHA-256 of each API response.
- **Dropped rows are counted.** A build that drops rows (off-year dates,
  duplicates, missing keys) prints how many and why.
- **Size.** Each source's methodology states how much it adds per year. Raw
  files that are too big to commit stay in the cache, and only what is
  derived from them is committed.

## Downloads

`politicaleye/fetch.py` is shared by every source. Interrupted transfers
resume with `Range` requests guarded by `If-Range`, so two versions of a file
are never spliced together. An unchanged file is not downloaded again, and
zips are CRC-checked, since some servers serve a truncated copy of a file
they are regenerating. Requests identify themselves as
`political-eye (+https://github.com/mbottoni/political-eye)`.

## People's data

- Public officials (deputies, senators, ministers, judges) and companies are
  identified the way their sources publish them.
- **No private individual's full CPF is committed.** Where a private person
  appears (a campaign donor, a sanctioned individual), the name is kept and
  the CPF is masked the way CGU masks it (`***.123.456-**`). Hashing would not
  protect it: there are only 10⁹ possible CPFs, so a hash can be reversed by
  trying them all.

## Schedules

Each source has its own workflow in `.github/workflows/` and its own
concurrency group, and its commits start with its name (`camara: …`). Sources
write to separate directories, so two of them pushing at the same time
rebase cleanly.
