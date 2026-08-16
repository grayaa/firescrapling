"""Flat-plan billing (Stripe Checkout + webhooks). Secrets never hardcoded.

When STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET are unset, checkout and webhook
endpoints return 503 (fail closed). Managed-fetch access is gated by plan when
a subscription row exists for the user.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

logger = logging.getLogger(__name__)

PlanId = Literal["free", "pro", "team"]

# Flat workspace plans — concurrency / pages / managed fetch / seats.
PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "Free",
        "concurrency": 1,
        "pages_per_month": 500,
        "managed_fetch": False,
        "seats": 1,
        "stripe_price_env": None,
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "concurrency": 4,
        "pages_per_month": 20_000,
        "managed_fetch": True,
        "seats": 3,
        "stripe_price_env": "STRIPE_PRICE_PRO",
    },
    "team": {
        "id": "team",
        "name": "Team",
        "concurrency": 12,
        "pages_per_month": 100_000,
        "managed_fetch": True,
        "seats": 15,
        "stripe_price_env": "STRIPE_PRICE_TEAM",
    },
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stripe_secret_key() -> str:
    return (os.environ.get("STRIPE_SECRET_KEY") or "").strip()


def stripe_webhook_secret() -> str:
    return (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()


def stripe_configured() -> bool:
    return bool(stripe_secret_key())


def ensure_subscriptions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE,
            plan TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'active',
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            current_period_end TEXT,
            seats INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def get_plan(plan_id: str) -> Dict[str, Any]:
    return dict(PLANS.get(plan_id, PLANS["free"]))


def get_subscription(user_id: str) -> Optional[Dict[str, Any]]:
    import main as core

    conn = core._get_db()
    try:
        ensure_subscriptions_table(conn)
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_subscription(
    user_id: str,
    *,
    plan: str,
    status: str = "active",
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    current_period_end: Optional[str] = None,
    seats: Optional[int] = None,
) -> Dict[str, Any]:
    import main as core

    if plan not in PLANS:
        plan = "free"
    plan_meta = PLANS[plan]
    now = _utcnow()
    conn = core._get_db()
    try:
        ensure_subscriptions_table(conn)
        existing = conn.execute(
            "SELECT id FROM subscriptions WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        sid = existing["id"] if existing else str(uuid.uuid4())
        seat_count = seats if seats is not None else int(plan_meta["seats"])
        if existing:
            conn.execute(
                """
                UPDATE subscriptions SET
                    plan = ?, status = ?, stripe_customer_id = COALESCE(?, stripe_customer_id),
                    stripe_subscription_id = COALESCE(?, stripe_subscription_id),
                    current_period_end = COALESCE(?, current_period_end),
                    seats = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    plan,
                    status,
                    stripe_customer_id,
                    stripe_subscription_id,
                    current_period_end,
                    seat_count,
                    now,
                    user_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO subscriptions (
                    id, user_id, plan, status, stripe_customer_id, stripe_subscription_id,
                    current_period_end, seats, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    user_id,
                    plan,
                    status,
                    stripe_customer_id,
                    stripe_subscription_id,
                    current_period_end,
                    seat_count,
                    now,
                    now,
                ),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else {"user_id": user_id, "plan": plan, "status": status}
    finally:
        conn.close()


def effective_plan_for_user(user_id: Optional[str]) -> Dict[str, Any]:
    """Plan limits for a user. No subscription row → Free defaults."""
    if not user_id:
        return get_plan("free")
    sub = get_subscription(user_id)
    if not sub or sub.get("status") not in ("active", "trialing"):
        return get_plan("free")
    return get_plan(str(sub.get("plan") or "free"))


def can_use_managed_fetch(user_id: Optional[str]) -> bool:
    """
    Self-host (HOSTED_MODE=false): no plan gating — the operator owns the infrastructure.
    Still respects process-wide MANAGED_FETCH_ENABLED as a kill switch.

    Hosted mode: when a subscription row exists, managed fetch follows the plan.
    When no row exists, fall back to process-wide MANAGED_FETCH_ENABLED.
    """
    from settings import get_settings

    settings = get_settings()
    if not settings.hosted_mode:
        return settings.managed_fetch_enabled

    if not user_id:
        return settings.managed_fetch_enabled

    sub = get_subscription(user_id)
    if sub is None:
        return settings.managed_fetch_enabled

    if sub.get("status") not in ("active", "trialing"):
        return False
    plan = get_plan(str(sub.get("plan") or "free"))
    return bool(plan.get("managed_fetch")) and settings.managed_fetch_enabled


def create_checkout_session(
    user_id: str,
    *,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    """Create a Stripe Checkout Session. Raises RuntimeError if Stripe unset."""
    secret = stripe_secret_key()
    if not secret:
        raise RuntimeError("stripe_not_configured")

    if plan not in ("pro", "team"):
        raise ValueError("plan must be 'pro' or 'team'")

    price_env = PLANS[plan]["stripe_price_env"]
    price_id = (os.environ.get(price_env) or "").strip() if price_env else ""
    if not price_id:
        raise RuntimeError(f"missing_price:{price_env}")

    try:
        import stripe
    except ImportError as e:
        raise RuntimeError("stripe_sdk_missing") from e

    stripe.api_key = secret
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=user_id,
        metadata={"user_id": user_id, "plan": plan},
    )
    return {
        "success": True,
        "checkout_url": session.url,
        "session_id": session.id,
        "plan": plan,
    }


def handle_stripe_webhook(payload: bytes, sig_header: Optional[str]) -> Dict[str, Any]:
    """Verify and apply Stripe webhook. Raises RuntimeError if misconfigured."""
    wh_secret = stripe_webhook_secret()
    secret = stripe_secret_key()
    if not wh_secret or not secret:
        raise RuntimeError("stripe_not_configured")

    try:
        import stripe
    except ImportError as e:
        raise RuntimeError("stripe_sdk_missing") from e

    stripe.api_key = secret
    try:
        event = stripe.Webhook.construct_event(payload, sig_header or "", wh_secret)
    except Exception as e:
        logger.warning("stripe webhook verify failed: %s", type(e).__name__)
        raise ValueError("invalid_signature") from e

    etype = event["type"]
    data = event["data"]["object"]

    if etype in ("checkout.session.completed", "invoice.paid", "customer.subscription.updated"):
        user_id = None
        plan = "pro"
        if etype == "checkout.session.completed":
            user_id = (data.get("client_reference_id") or (data.get("metadata") or {}).get("user_id"))
            plan = (data.get("metadata") or {}).get("plan") or "pro"
            upsert_subscription(
                str(user_id),
                plan=plan,
                status="active",
                stripe_customer_id=data.get("customer"),
                stripe_subscription_id=data.get("subscription"),
            )
        elif etype == "customer.subscription.updated":
            meta = data.get("metadata") or {}
            user_id = meta.get("user_id")
            # Map price → plan via env price ids when possible
            plan = meta.get("plan") or _plan_from_subscription_obj(data)
            status = data.get("status") or "active"
            if user_id:
                upsert_subscription(
                    str(user_id),
                    plan=plan,
                    status=status,
                    stripe_customer_id=data.get("customer"),
                    stripe_subscription_id=data.get("id"),
                    current_period_end=_ts_to_iso(data.get("current_period_end")),
                )
        elif etype == "invoice.paid":
            # Keep subscription active; metadata may be sparse
            sub_id = data.get("subscription")
            cust = data.get("customer")
            logger.info("stripe invoice.paid subscription=%s customer=%s", sub_id, cust)

    elif etype in ("customer.subscription.deleted", "customer.subscription.canceled"):
        meta = data.get("metadata") or {}
        user_id = meta.get("user_id")
        if user_id:
            upsert_subscription(str(user_id), plan="free", status="canceled")
        else:
            # Fall back: look up by stripe_subscription_id
            import main as core

            conn = core._get_db()
            try:
                ensure_subscriptions_table(conn)
                row = conn.execute(
                    "SELECT user_id FROM subscriptions WHERE stripe_subscription_id = ?",
                    (data.get("id"),),
                ).fetchone()
                if row:
                    upsert_subscription(row["user_id"], plan="free", status="canceled")
            finally:
                conn.close()

    return {"success": True, "type": etype}


def _plan_from_subscription_obj(data: Dict[str, Any]) -> str:
    items = (data.get("items") or {}).get("data") or []
    price_ids = set()
    for it in items:
        price = it.get("price") or {}
        if isinstance(price, dict) and price.get("id"):
            price_ids.add(price["id"])
    pro = (os.environ.get("STRIPE_PRICE_PRO") or "").strip()
    team = (os.environ.get("STRIPE_PRICE_TEAM") or "").strip()
    if team and team in price_ids:
        return "team"
    if pro and pro in price_ids:
        return "pro"
    return "pro"


def _ts_to_iso(ts: Any) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError):
        return None


def plans_public() -> Dict[str, Any]:
    """Safe plan catalog for docs/UI (no secrets)."""
    return {
        "plans": [
            {
                "id": p["id"],
                "name": p["name"],
                "concurrency": p["concurrency"],
                "pages_per_month": p["pages_per_month"],
                "managed_fetch": p["managed_fetch"],
                "seats": p["seats"],
            }
            for p in PLANS.values()
        ]
    }
