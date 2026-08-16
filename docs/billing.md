# Billing (hosted mode only)

Billing endpoints and plan gating are active only when **`HOSTED_MODE=true`**.
Self-host defaults keep billing **404** (`code: billing_disabled`).

See [hosted.md](./hosted.md) and [decision-gate.md](./decision-gate.md).

## Plans (when hosted)

| Plan | Concurrency | Pages/mo | Managed fetch | Seats |
|------|-------------|---------|---------------|-------|
| Free | 1 | 500 | no | 1 |
| Pro | 4 | 20 000 | yes | 3 |
| Team | 12 | 100 000 | yes | 15 |

Constants: `apps/firescrapling/backend/billing.py` (`PLANS`).

## Env

```bash
HOSTED_MODE=true
STRIPE_SECRET_KEY=sk_test_…
STRIPE_WEBHOOK_SECRET=whsec_…
STRIPE_PRICE_PRO=price_…
STRIPE_PRICE_TEAM=price_…
```

When Stripe secrets are unset (but hosted is on), checkout/webhook return **503**.

## API

- `GET /v1/billing/plans`
- `POST /v1/billing/checkout` — session auth
- `POST /v1/billing/webhook` — Stripe signatures

## Managed fetch

Self-host (`HOSTED_MODE=false`): `can_use_managed_fetch` returns `MANAGED_FETCH_ENABLED`
(no plan gating). Hosted: subscription plan gates platform keys.
