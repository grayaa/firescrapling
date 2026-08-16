# How the fetch ladder works

When escalation is on and the client did not force `renderJs` / `asp` / `proxyPool`:

1. **local** — in-process fetch  
2. **sf_static** — paid static  
3. **sf_js** — + JS  
4. **sf_asp** — + anti-bot  
5. **sf_residential** — last resort  

Classification stops escalation on usable content, terminal HTTP errors (including
unhandled 4xx), or bot walls (401/403/429 → escalate further). Private/loopback hosts
never reach paid providers.

Successful tiers are cached per domain (~24h, Redis or memory) so the next request can
start mid-ladder.
