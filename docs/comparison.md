# Firecrawl alternative? Design tradeoffs

FireScrapling is often discovered as a **Firecrawl alternative** for teams that want a
**self-hosted** scrape/crawl/map API and optional [MCP](./mcp.md) tools — without
running someone else's credit meter for every page. That framing is fair only if the
comparison is precise: Firecrawl is a strong product with a different default
operating model. This page states the tradeoff as an engineer would, not a brochure.

Sources for Firecrawl claims are their public docs (linked inline). We do **not**
quote their dollar pricing (it changes); see [Firecrawl Pricing](https://www.firecrawl.dev/pricing)
for current plans and credit tables.

## The credit-burn problem

Many scrape pipelines default to the strongest anti-bot path on every URL. That is
reliable and expensive when most pages would have succeeded on a cheaper fetch.

FireScrapling exists for teams that already buy [Scrape.do](https://scrape.do) or
[Scrapfly](https://scrapfly.io) (or are willing to start with local fetch) and want
orchestration that **tries cheap tiers first**. Firecrawl Cloud, by design, sells a
managed API where usage is measured in **Firecrawl credits** under their plan —
see their [pricing page](https://www.firecrawl.dev/pricing) and the Cloud column in
[Open source or Firecrawl Cloud](https://docs.firecrawl.dev/contributing/open-source-or-cloud)
(“Firecrawl plan and credit model”).

Neither approach is wrong. One optimizes for “call an API and ship.” The other
optimizes for “keep the provider invoice under your control and escalate only when
needed.”

## Escalation ladder (cost model)

When escalation is enabled and the client did not force `renderJs` / `asp` /
`proxyPool`, FireScrapling walks a published ladder and can resume mid-ladder from a
per-domain profile. Details: [How the fetch ladder works](./fetch-ladder.md).

Relative **modeled** weights (from `cost_model.py` — a bake-off-derived scale, **not**
your Scrape.do/Scrapfly invoice):

| Tier | Modeled weight |
|------|----------------|
| local | 0 |
| sf_static | 1 |
| sf_js | 5 |
| sf_asp | 25 (baseline for estimated savings) |
| sf_residential | 75 |

Estimated savings vs always-`sf_asp` appear on `GET /v1/usage/fetch-savings` and the
Savings dashboard, always labelled as a **cost model** (`"estimated": true`). See
[Fetch savings model](./fetch-savings.md).

Firecrawl Cloud documents that it handles proxies, anti-bot, and JavaScript as part of
the managed product ([Introduction](https://docs.firecrawl.dev/introduction)). They do
not publish an equivalent “cheap-first ladder against *your* Scrape.do/Scrapfly meter,”
because Cloud usage is billed on **their** credit system
([pricing](https://www.firecrawl.dev/pricing)). On self-hosted Firecrawl, advanced
anti-bot (“fire-engine”) is called out as **not** included in the default stack —
you configure that path separately
([Self-hosting](https://docs.firecrawl.dev/contributing/self-host),
[Open source or Cloud](https://docs.firecrawl.dev/contributing/open-source-or-cloud)).

We have not published a head-to-head scrape success or latency bake-off between
Firecrawl and FireScrapling. Do not treat any Scrape.do-vs-Scrapfly numbers elsewhere
in this repo as that comparison.

## BYOK vs reseller economics

| | Firecrawl Cloud | FireScrapling |
|--|-----------------|---------------|
| Who you pay for successful fetches | Firecrawl (credits / plan) | Your fetch provider (or $0 local) |
| Where the “scrape vendor” key lives | Your Firecrawl API key | Your Scrape.do / Scrapfly key (BYOK) or platform env |

Firecrawl’s own comparison table states Cloud billing as the “Firecrawl plan and credit
model,” while open-source self-host billing is “your infrastructure and provider
costs” ([Open source or Firecrawl Cloud](https://docs.firecrawl.dev/contributing/open-source-or-cloud)).

FireScrapling is intentionally a thin orchestrator: BYOK stores encrypted provider
credentials on **your** instance; paid fetches debit **your** provider meter. There is
no FireScrapling credit reseller in the self-host default (`HOSTED_MODE=false`).

## Self-hosting and data residency

Both projects can run on infrastructure you control:

- Firecrawl: official [self-hosting guide](https://docs.firecrawl.dev/contributing/self-host)
  (Docker Compose; you own upgrades, auth, TLS, persistence).
- FireScrapling: [Self-host quickstart](./self-host.md) — Compose is the default path.

If compliance cares where HTML and keys sit, self-hosting either stack keeps the
control plane on your network. Outbound fetches still leave your network toward the
target site (and toward any paid fetch provider you configure). Firecrawl’s self-host
docs make the same point about outbound and optional AI/proxy providers
([Self-hosting](https://docs.firecrawl.dev/contributing/self-host)).

Licence: Firecrawl’s core repository is under the
[GNU AGPL v3](https://github.com/firecrawl/firecrawl/blob/main/LICENSE)
(see also their [README licence notes](https://github.com/firecrawl/firecrawl#license-disclaimer)).
FireScrapling is **AGPL-3.0-only** ([LICENSE](https://github.com/grayaa/firescrapling/blob/main/LICENSE)).
Read both carefully before embedding either in a network service.

Optional MCP: FireScrapling ships an MCP profile that wraps the HTTP API
([MCP](./mcp.md)). Firecrawl documents its own MCP server in their docs
([MCP Get Started](https://docs.firecrawl.dev/mcp-server)).

## When to use Firecrawl instead

Prefer **Firecrawl Cloud** when you want a hosted, managed scrape/crawl/map API with
**no infrastructure to run** — keys, credits, limits, and ops stay with them. Their
docs say that explicitly: choose Cloud for the fastest supported path to production;
choose open source when source or infrastructure control is worth the operational work
([Open source or Firecrawl Cloud](https://docs.firecrawl.dev/contributing/open-source-or-cloud)).

Prefer Firecrawl’s broader Cloud product surface (search, agent/browser interact,
managed dashboards, and Cloud-only capabilities listed in their docs) when those
features are the product requirement — FireScrapling’s self-host surface is
scrape/crawl/map plus jobs, webhooks, BYOK, and MCP over that API.

Prefer **FireScrapling** when you already (or plan to) pay Scrape.do/Scrapfly, want an
explicit escalation ladder and estimated savings model against that meter, and want
the default deploy to be self-hosted on your box.

Further reading: [Fetch ladder](./fetch-ladder.md) · [Savings model](./fetch-savings.md) ·
[Connect provider](./connect-provider.md) · [Self-host](./self-host.md)
