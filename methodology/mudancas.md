# What changed: methodology

The repository's history is a record of what changed in each source and when (`git log -p data/sancoes/ceis.csv`),
but only git can read it. Each source's job also keeps a short **change log** in one shape for every source, which
the [what-changed page](https://mbottoni.github.io/political-eye/mudancas/) and the Atom feeds read.

Built by `python -m politicaleye site changes <source>` (`politicaleye/site/mudancas.py`) in each source's own
workflow, right after its page summaries, into `data/site/mudancas/`; the feeds go to `docs/feeds/`, where GitHub
Pages serves them. `site build mudancas` updates every log and feed at once (`site.yml` runs it when the code
changes).

## Files

| file | what it holds |
|---|---|
| `data/site/mudancas/<source>.csv` | one row per change in the source's last 90 days: `data` (the day it is dated), `fonte`, `tipo` (the kind of change), `chave` (what changed: a CNPJ, a contract, a payment, a month), `titulo` (the name shown), `pf` (1 when an individual firm's name is withheld), `detalhe` and `detalhe_en`, `valor`, `n` (a count), `link` (the page that explains it) |
| `data/site/mudancas/<source>.json` | the rule behind the log, since when it runs, coverage (PNCP), the label of each kind of change, and one summary per day in Portuguese and English |
| `data/site/mudancas/estado/<source>.json` | for the two logs that compare builds: what the last build held (`chaves`) and since when (`desde`) |
| `docs/feeds/<source>.xml`, `docs/feeds/todas.xml` | Atom, in Portuguese: one feed per source and one for every source |
| `docs/feeds/en/<source>.xml`, `docs/feeds/en/all.xml` | the same in English |

Sources: `sancoes`, `alertas`, `emendas`, `pncp`, `camara`, `senado`.

## What each log records

### Dated by the source

These logs are rebuilt from the data every time.

- **Sanctions** (`sancoes`). Companies and organisations that entered or left CEIS, CNEP, CEPIM or the leniency
  list, from the lists' own change log `data/sancoes/changes.csv` ([sancoes.md](sancoes.md)), on the date of the CGU
  snapshot that first showed the change. One row per company, list, direction and day; a company with several
  sanctions entering on one day is one row with their count. New CEIS and CNEP entries carry the category, the
  sanctioning body and the end date as the sanctions page labels them; CNEP fines carry their value.
- **Large contracts** (`pncp`). Contracts published on the PNCP in the 90 days to the latest day read
  (`data/pncp/dias.csv`) that count **R$ 100 million or more** under the contracts page's rules
  ([pncp.md](pncp.md#the-explorer-page)): a global value over 15 times the initial one counts at the initial value,
  and values over R$ 10 billion, or over three years of a town's revenue, are left out (`plausible()`). Dated by
  publication. The log's JSON states how many of the 90 days were read and how many contracts were left out as
  implausible.
- **Roll-call months** (`camara`, `senado`). Each month that got its first roll calls in the plenary
  (`data/<chamber>/votacoes/YYYY-MM.csv`), dated by its first roll call; the count grows each week until the month
  ends.

**Why R$ 100 million.** On the 79 days with contracts published from 15 August to 7 November 2026, contracts
counted at R$ 100 million or more were 200 of 14,853 large contracts (1.3%) and 44% of their value: about 2.5 a
day. At R$ 50 million there would be 5.6 a day, at R$ 10 million 26.

### Found by comparing two builds

These sources publish no date for a change. Each build compares what it reads with what the last build held
(`estado/<source>.json`), lists what is new, dated by the data the build read (never by the clock), and stores what it
now holds. **The first build only records what is there**, so a log starts empty.

- **Red flags** (`alertas`). Flags on the [red-flags page](alertas.md) that were not in the previous build of
  `data/site/alertas/`, dated by the sanctions snapshot that build read (`data/sancoes/sources.json`). A flag is
  identified by its case, not its amounts: the company and the member (or collective author) for amendments paid
  while barred; the contract for contracts with barred companies and contracts after a leniency agreement; the
  member and the recipient for campaign suppliers and concentration; the buyer and its supplier for a dominated
  buyer. A flag whose amount grows is not new.
  Contracts signed more than 90 days before the build are **counted per day, not listed**: nearly all come from the
  PNCP history still being read newest first ([pncp.md](pncp.md)), thousands a day while it is read, and some from
  a new sanction that reaches back to old contracts. A flag that appears because a rule changed (a code change
  rebuilds the page) is listed like any other: it is new on the page.
  **A flag is not evidence of an irregularity**, as the red-flags page says; the log repeats it.
- **Amendment payments** (`emendas`). Payment rows (one amendment, one recipient, one month,
  `data/emendas/pagamentos/`) that reached **R$ 5 million** since the previous build, dated by the amendments
  file's `Last-Modified` (`data/emendas/sources.json`). A row is listed once, at the value it had when it crossed
  the line; it keeps growing through its month. Rows with no named recipient (private individuals, summed) are not
  listed.

**Why R$ 5 million.** In 2025 and 2026, payment rows of R$ 5 million or more were 1,497 of 178,225 (0.84%) and
20.5% of the money paid: about 70 a month, ten to twenty on a busy day of November. At R$ 1 million there would be
about 250 on such a day, at R$ 10 million one to three.

**Seeded from the history.** The two logs were started on 2026-11-14 by replaying the builds committed since
2026-11-06 (amendments) and 2026-11-08 (red flags), oldest first, with the dominant-supplier list held at its first
build after the typo fix ([#11](https://github.com/mbottoni/political-eye/pull/11)): earlier builds drew it from
implausible values. Names were checked against today's rule, not the rule of each build.

## The window

Each log keeps the 90 days up to **its own latest date**, never up to today. A run with nothing new rewrites every
file byte for byte, and commits nothing; a source that stops changing keeps its last 90 days.

## Feeds

- **One entry per source and day**, newest first: the day's summary as title, and in the content the first 20
  changes, each linking to the page that explains it, then a link to the rest on the what-changed page. Each
  source's feed keeps its latest 30 days with changes; the feed of every source, the latest 60 entries.
- **Stable ids.** `tag:mbottoni.github.io,2026:political-eye/<source>/<day>` (`.../en/<source>/<day>` in English):
  a reader never sees the same day twice. Entries are dated noon UTC of their day (09:00 in Brasília), so a reader
  in Brazil shows the right day.
- **No clock.** A feed's `updated` is its newest entry's. When a later build adds to a day already published (a
  second run on the same data, a contract updated above the line), the entry keeps its id and date; readers that
  track updates show the new content, others keep the first version.
- **Two jobs at once.** Each job writes its own log and feed; the feed of every source is rebuilt from every log
  after a rebase (`site feeds`), so a job pushing just after another does not drop the other's entries.

## People and names

- Sanctioned people are **counted per day, never named**, and their documents never appear.
- Individual firms named after a person (an MEI name, a name carrying a CPF, or a name made only of words of
  people's names: the rule of the sanctions page, [sancoes.md](sancoes.md#the-explorer-page)) keep their CNPJ and
  their numbers, with "Individual firm (name withheld)" in place of the name. The rule is applied again by the log,
  so it never carries a name an earlier build of another page let through.
- Contract suppliers that are private individuals (`PF`) are never named.
- Members of Congress are public officials and are named, as on the pages they come from.

## Limits

- The red-flag and payment logs see only what changed between two builds. A payment that grows from R$ 4 million
  to R$ 9 million is listed once, at R$ 9 million; one that was already over the line and grows is not listed again.
- The contracts log is dated by publication. A contract updated above R$ 100 million after its day was read joins
  that day's entry, which feed readers may have shown already.
- Roll-call months show when a month began, not every new roll call.
