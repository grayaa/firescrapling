"""Billing HTTP routes — 404 with billing_disabled when HOSTED_MODE is false."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from api_auth import get_session_user


def require_hosted_mode() -> None:
    from settings import get_settings

    if not get_settings().hosted_mode:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "billing_disabled",
                "message": "Billing is disabled in self-host mode (set HOSTED_MODE=true to enable)",
            },
        )


router = APIRouter(tags=["billing"], dependencies=[Depends(require_hosted_mode)])


class CheckoutRequest(BaseModel):
    plan: str = Field(description="pro or team")
    success_url: str = Field(..., min_length=8, max_length=2048)
    cancel_url: str = Field(..., min_length=8, max_length=2048)

    @field_validator("plan")
    @classmethod
    def plan_ok(cls, v: str) -> str:
        p = (v or "").strip().lower()
        if p not in ("pro", "team"):
            raise ValueError("plan must be 'pro' or 'team'")
        return p


@router.get("/v1/billing/plans")
def billing_plans() -> Dict[str, Any]:
    from billing import plans_public

    return plans_public()


@router.post("/v1/billing/checkout")
def billing_checkout(
    req: CheckoutRequest,
    user_id: str = Depends(get_session_user),
) -> Dict[str, Any]:
    from billing import create_checkout_session, stripe_configured

    if not stripe_configured():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "billing_disabled",
                "message": "Stripe is not configured (STRIPE_SECRET_KEY unset)",
            },
        )
    try:
        return create_checkout_session(
            user_id,
            plan=req.plan,
            success_url=req.success_url,
            cancel_url=req.cancel_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "invalid_plan", "message": str(e)}) from e
    except RuntimeError as e:
        code = str(e)
        raise HTTPException(
            status_code=503,
            detail={"code": code, "message": "Billing checkout unavailable"},
        ) from e


@router.post("/v1/billing/webhook")
async def billing_webhook(request: Request) -> Dict[str, Any]:
    from billing import handle_stripe_webhook, stripe_configured, stripe_webhook_secret

    if not stripe_configured() or not stripe_webhook_secret():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "billing_disabled",
                "message": "Stripe webhook is not configured",
            },
        )
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        return handle_stripe_webhook(payload, sig)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_signature", "message": "Invalid Stripe signature"},
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail={"code": str(e), "message": "Billing webhook unavailable"},
        ) from e
