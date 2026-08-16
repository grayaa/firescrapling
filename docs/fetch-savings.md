# Fetch savings model

FireScrapling reports **estimated** credit savings from the fetch escalation ladder.
These numbers are **not** your Scrape.do / Scrapfly invoice — they use fixed relative
weights from our bake-off so the dashboard can show a comparable receipt.

## Baseline

Every successful fetch is compared to a hypothetical **`sf_asp`** request (paid anti-bot /
super proxy). That is the expensive default many teams run for every URL.

## Actual cost

Actual cost is the **sum of modeled weights for each ladder attempt** that ran
(`local` → `sf_static` → `sf_js` → `sf_asp` → `sf_residential`), or a single weight when
escalation is off / the client forced flags.

| Tier | Modeled weight |
|------|----------------|
| local | 0 |
| sf_static | 1 |
| sf_js | 5 |
| sf_asp | 25 |
| sf_residential | 75 |

## API

`GET /v1/usage/fetch-savings?days=30` (session auth) returns aggregate `savings_pct`,
`baseline_cost`, `actual_cost`, and a `by_domain` breakdown. The payload always includes
`"estimated": true`.

## Dashboard

The **Savings** page in the app surfaces the same numbers and labels them as estimated.
