"""Billing plan helpers and Stripe stub gating."""
from __future__ import annotations

from billing import (
    PLANS,
    can_use_managed_fetch,
    effective_plan_for_user,
    plans_public,
    stripe_configured,
    upsert_subscription,
)


def test_plans_have_required_fields() -> None:
    for pid in ("free", "pro", "team"):
        p = PLANS[pid]
        assert "concurrency" in p
        assert "pages_per_month" in p
        assert "managed_fetch" in p
        assert "seats" in p
    assert PLANS["free"]["managed_fetch"] is False
    assert PLANS["pro"]["managed_fetch"] is True


def test_plans_public_has_no_secrets() -> None:
    blob = str(plans_public())
    assert "sk_" not in blob
    assert "whsec" not in blob
    assert "STRIPE" not in blob


def test_can_use_managed_fetch_self_host_skips_plan_gating(isolated_db, monkeypatch) -> None:
    """HOSTED_MODE=false → free-plan users still get managed fetch when the kill switch is on."""
    import main as core
    from settings import clear_settings_cache

    monkeypatch.setenv("HOSTED_MODE", "false")
    monkeypatch.setenv("MANAGED_FETCH_ENABLED", "true")
    clear_settings_cache()
    assert can_use_managed_fetch(None) is True

    out = core.register_user("selfhost@example.com", "SelfPass99!", "Self")
    assert out["success"] is True
    uid = out["user"]["id"]
    upsert_subscription(uid, plan="free", status="active")
    assert can_use_managed_fetch(uid) is True

    monkeypatch.setenv("MANAGED_FETCH_ENABLED", "false")
    clear_settings_cache()
    assert can_use_managed_fetch(uid) is False


def test_can_use_managed_fetch_without_subscription(isolated_db, monkeypatch) -> None:
    monkeypatch.setenv("HOSTED_MODE", "true")
    monkeypatch.setenv("MANAGED_FETCH_ENABLED", "true")
    from settings import clear_settings_cache

    clear_settings_cache()
    assert can_use_managed_fetch(None) is True
    assert can_use_managed_fetch("missing-user") is True


def test_can_use_managed_fetch_with_free_subscription(isolated_db, monkeypatch) -> None:
    import main as core
    from settings import clear_settings_cache

    monkeypatch.setenv("HOSTED_MODE", "true")
    monkeypatch.setenv("MANAGED_FETCH_ENABLED", "true")
    clear_settings_cache()

    out = core.register_user("bill@example.com", "BillPass99!", "Bill")
    assert out["success"] is True
    uid = out["user"]["id"]

    upsert_subscription(uid, plan="free", status="active")
    assert can_use_managed_fetch(uid) is False

    upsert_subscription(uid, plan="pro", status="active")
    assert can_use_managed_fetch(uid) is True

    plan = effective_plan_for_user(uid)
    assert plan["id"] == "pro"
    assert plan["concurrency"] == 4


def test_billing_404_when_hosted_off(client, monkeypatch) -> None:
    monkeypatch.setenv("HOSTED_MODE", "false")
    from settings import clear_settings_cache

    clear_settings_cache()
    r = client.get("/v1/billing/plans")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "billing_disabled"


def test_checkout_503_without_stripe(client, isolated_db, monkeypatch) -> None:
    monkeypatch.setenv("HOSTED_MODE", "true")
    from settings import clear_settings_cache

    clear_settings_cache()
    client.post("/v1/auth/register", json={"email": "stripe@example.com", "password": "Stripe99!"})
    lr = client.post("/v1/auth/login", json={"email": "stripe@example.com", "password": "Stripe99!"})
    token = lr.json()["session_token"]
    r = client.post(
        "/v1/billing/checkout",
        json={
            "plan": "pro",
            "success_url": "http://localhost/ok",
            "cancel_url": "http://localhost/cancel",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "billing_disabled"


def test_webhook_503_without_stripe(client, monkeypatch) -> None:
    monkeypatch.setenv("HOSTED_MODE", "true")
    from settings import clear_settings_cache

    clear_settings_cache()
    r = client.post("/v1/billing/webhook", content=b"{}")
    assert r.status_code == 503


def test_billing_plans_endpoint(client, monkeypatch) -> None:
    monkeypatch.setenv("HOSTED_MODE", "true")
    from settings import clear_settings_cache

    clear_settings_cache()
    r = client.get("/v1/billing/plans")
    assert r.status_code == 200
    assert len(r.json()["plans"]) == 3


def test_capabilities_hosted_flag(client, monkeypatch) -> None:
    monkeypatch.setenv("HOSTED_MODE", "false")
    from settings import clear_settings_cache

    clear_settings_cache()
    r = client.get("/v1/capabilities")
    assert r.status_code == 200
    assert r.json()["hosted"] is False


def test_playground_disabled_by_default(client, monkeypatch) -> None:
    monkeypatch.delenv("PLAYGROUND_ENABLED", raising=False)
    from settings import clear_settings_cache

    clear_settings_cache()
    r = client.post("/v1/playground/scrape", json={"url": "https://example.com"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "playground_disabled"


def test_stripe_configured_false_by_default(monkeypatch) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    assert stripe_configured() is False
