# Deputies ranked: methodology

The [ranking page](https://mbottoni.github.io/political-eye/ranking/) orders the federal deputies of a
legislature by an index of their recorded work, with weights the reader chooses. It measures work the open
data records. It does **not** measure the quality or impact of a deputy's bills, their ideology, their
honesty, committee and constituency work that leaves no record, or how they vote on any issue. A deputy who
files many bills is not for that reason a better one; the page invites readers to change the weights and see
how much the order depends on them.

Built by `python -m politicaleye site build ranking` (in the daily `sancoes` workflow) into
`data/site/ranking/`, from the deputies page's table ([views.md](views.md)), the office allowance
([camara.md](camara.md#office-allowance-ceap-datacamaracota)) and the red flags ([alertas.md](alertas.md)).

## Who is ranked

Deputies with 12 months or more in office in the legislature (554 of 644 in the 57th on 2026-11-08).
Substitutes who served a few weeks appear in the table, unranked, so their few months don't set the scale.

## The criteria

Each criterion becomes a score from 0 to 100: the deputy's percentile among the ranked deputies (ties share
the middle). The final score is the weighted average of the criteria with a weight above zero; a criterion a
deputy has no data for is left out of their average.

| criterion | measure | default weight |
|---|---|---|
| Roll-call participation | votes cast over the roll calls held in their months in office (`presenca`, [views.md](views.md)) | 3 |
| Bills filed | bills, constitutional amendments, complementary laws and legislative decrees as first signer | 2 |
| Rapporteur opinions | opinions and substitutes signed as rapporteur | 2 |
| Office-allowance thrift | allowance spending per month in office, as a percentile **within the deputy's state**, reversed (spending less scores higher) | 3 |
| Ties across parties | the share of their co-voting ties to other parties' deputies | 0 (optional) |
| Proposals co-signed | other deputies' proposals they co-signed | 0 (optional) |

Presets: balanced (the defaults), attendance only, legislative output, thrift only, dialogue.

**Why these.** Each is a record of work any deputy can be held to whatever their party or views, and each is
in the data for every deputy. What a deputy votes for is left out on purpose: whether voting with the
government or a party is good is a political judgement, not a measure. Ties across parties and co-signing
are offered but weigh nothing by default for the same reason (voting with one's party is no fault; signing
is easy).

## Cautions the page states

- **The Speaker.** The president of the Câmara votes only to break a tie: his participation is left out of
  his score (Rodrigo Maia and Arthur Lira in the 56th, Arthur Lira and Hugo Motta in the 57th).
- **Board members.** Members of the Mesa Diretora sign thousands of administrative opinions on information
  requests (Altineu Côrtes had 10,969 on 2026-11-08); as a percentile that only puts them at the top of the
  rapporteur criterion, but readers may want to weigh it down.
- **Volume is not quality.** Some deputies file hundreds of bills a year; the bill criterion rewards volume.
- **Allowance by state.** The ceiling depends on the state, so a deputy is compared only with their state's
  deputies (three or more needed). Spending little can also mean doing less travel or outreach.
- **Red flags are not scored.** The lists of the [red-flags page](alertas.md) that name a member (amendments
  to barred companies, campaign suppliers paid by their amendments, concentrated amendments) appear beside the
  name, linked, and never change the score: a flag is not evidence of an irregularity.

## Files

| file | contents |
|---|---|
| `deputados_<leg>.csv` | per deputy: the raw measures above, `cota_total`, `cota_mes`, the state's median `cota_mes_uf`, the share spent on publicity `cota_divulgacao`, and the red-flag lists (`alertas`) |
| `cota_<leg>.csv` | allowance spending per deputy and kind over the legislature |
| `resumo.json` | legislatures built, counts and medians |

The scores themselves are computed in the browser from these values, with the reader's weights.
