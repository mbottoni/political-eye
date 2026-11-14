# Red flags: methodology

The [red-flags page](https://mbottoni.github.io/political-eye/alertas/) lists patterns across the open data
that deserve a closer look. **A flag is not evidence of an irregularity.** It is a pattern in official data
that a journalist, auditor or citizen may want to check; many have legitimate explanations, the data can be
wrong, and nothing on the page says anyone broke the law. Each flag below states its rule, what it is
measured against, and the innocent explanations the page repeats next to it.

Built by `python -m politicaleye site build alertas` (in the daily `sancoes` workflow, after the sanctions
page) into `data/site/alertas/`, from tables other sources already commit: the sanctions lists
([sancoes.md](sancoes.md)), amendment payments ([emendas.md](emendas.md)), campaign accounts
([tse.md](tse.md)), public contracts ([pncp.md](pncp.md)) and the politician crosswalk ([ref.md](ref.md)).

## People and names

- Private individuals are never named. Sanctioned people are not on any list (every flag is about a CNPJ).
- Companies are named as their sources publish them, except **individual firms named after a person**
  (MEIs, *empresários individuais* and EIRELIs, or any name the sanctions page's rule recognises as a
  person's): they are counted, with "Individual firm (name withheld)" in place of the name. A supplier
  with a masked CPF is always withheld.
- Members of Congress are public officials and are named, linked to their profile on this site (deputies of
  the 56th and 57th legislatures) or on the Senate's site (senators).

## The flags

### 1. Amendment money paid to a barred company (`emendas_impedidas.csv`)

**Rule.** An amendment payment to a company in a month when it was on CEIS or CNEP under a sanction that bars
contracting (*impedimento*, *inidoneidade*, *suspensão*), as the sanctions page computes it, kept when the
bar's reach covers federal money (`sim`) or may (`possivel`). One row per company, author and reach.
**Measured against.** Every amendment payment since 2014. Payments to companies barred only within another
state's or a town's sphere (`nao`) do not stop federal money; they are counted in `resumo.json`
(`fora_do_alcance`), not listed. On 2026-11-08: 675 company–author pairs, R$ 88 million, of which R$ 56
million where the bar certainly covered federal money; 995 more pairs (R$ 63 million) were out of reach.
**Innocent explanations.** The payment settles a contract signed before the sanction, which the law
allows; the member chooses where the amendment goes, not the supplier; the sanction may have been suspended
in court without the list being updated.

### 2. Contracts signed with a company barred at the time (`contratos_impedidas.csv`)

**Rule.** A contract on the PNCP whose signing day falls within a barring sanction of the supplier (a 14-digit
CNPJ) whose reach covers the buying body (`cobre = sim` in `data/pncp/sancionados/`).
Contracts with values the contracts page leaves out as typos are left out here too.
**Measured against.** The contracts read so far; the PNCP history since 2021 is read newest first, so the
count grows as it fills in (198 of 1,893 days on 2026-11-08: 1,027 contracts, R$ 91 million).
**Innocent explanations.** An amendment or continuation of a contract signed before the sanction; a court
order the list does not show; a wrong signing date on the PNCP.

### 3. A campaign supplier paid from the same deputy's amendments (`campanha_emendas.csv`)

**Rule.** A company or private body (CNPJ) that a federal deputy's 2018 or 2022 campaign contracted
(`data/tse/<year>/fornecedores_candidatos.csv`) and that, from October of that election year, received at
least R$ 10,000 in payments from that same deputy's amendments.
**Measured against.** 164,159 campaign–supplier pairs of federal-deputy and Senate candidates in 2018 and
2022. Left out: recipients that are governments, public bodies, state companies or banks, and public-service
concessionaires (power, water and sanitation, telephone, post): campaigns pay their bills, and public bodies
pay them for everything. On 2026-11-08, 10 pairs, R$ 6.2 million; before the utilities were left out there
were 16, mostly power distributors.
**Innocent explanations.** Local associations, clubs and cultural groups work in campaigns and receive
public money for legitimate projects; a small campaign payment (a venue, a service) shows no tie; the body
executing the amendment, not the member, chooses the supplier. The page shows both amounts so a reader can
weigh them.

### 4. Amendment money concentrated on one private recipient (`concentracao.csv`)

**Rule.** A single private recipient (an association, foundation, cooperative, religious organisation or
company, by its legal nature in `data/emendas/favorecidos.csv`) received at least R$ 1 million and 25% or
more of all the money a member's amendments paid since February 2019.
**Measured against.** For every member with amendment payments in that period (1,164), the largest share
going to one private recipient: 1.7% at the median, under 9.5% for 90% of them.
**Kinds.** From the name and legal nature: research support foundations of universities and Fiocruz,
health and charity bodies (Santas Casas, hospitals), other associations, and companies. Support foundations
and charity hospitals execute research and health amendments by design; they are tagged, never dropped. On
2026-11-08, 13 cases: 7 support foundations, 1 charity hospital, 3 associations, 2 companies.
**Innocent explanations.** The routes above; a member with few amendments paid concentrates more by
arithmetic.

### 5. A buyer dominated by one supplier (`fornecedor_dominante.csv`)

**Rule.** A public buyer with at least 5 large contracts (R$ 1 million or more) adding up to R$ 10 million
or more, where one supplier took 80% or more of the value (from the contracts page's `orgaos.csv`).
**Measured against.** Buyers with five or more large contracts in the history read: the largest supplier
takes 42% at the median.
**Innocent explanations.** Some services have one possible provider (the foundation that runs a town's
hospital, a sole operator of some equipment); with little history read, concentration is likelier by chance.

### 6. Contracts after a leniency agreement (`leniencia_contratos.csv`)

**Rule.** A large contract on the PNCP signed by a company (its CNPJ as listed in the agreement) on or after
the start of its leniency agreement with the CGU, in which it admitted wrongdoing.
**Innocent explanation.** A leniency agreement exists so the company can contract again on the terms it
promised; the company may have changed hands. This list is context more than a flag.

## On several lists (`entidades.csv`, `parlamentares.csv`)

Companies and members of Congress that appear on two lists or more. Appearing twice adds no guilt: often it
is one fact seen twice (a barred company that receives amendments and also signs contracts). They are the
first cases to look at.

## Thresholds

`CONC_MIN`, `CONC_SHARE`, `CONC_SINCE`, `CAMPAIGN_MIN`, `DOM_CONTRACTS`, `DOM_VALUE` and `DOM_SHARE` in
`politicaleye/site/alertas.py`, also written to `resumo.json` (`rules`) so the page quotes the values it
used. They were set to keep each list to cases far outside the usual pattern, before looking at who was on
them.
