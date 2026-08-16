"""Webhook enqueue prefers the queue; falls back to inline delivery."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import main as core
from settings import clear_settings_cache


def test_notify_webhook_inline_when_queue_disabled(isolated_db: str, monkeypatch) -> None:
    monkeypatch.setenv("QUEUE_ENABLED", "false")
    clear_settings_cache()

    reg = core.register_user("hook@example.com", "HookPass1!")
    user_id = reg["user"]["id"]
    job_id = core.create_job_with_idempotency(
        user_id,
        None,
        None,
        "/v1/scrape",
        job_type="scrape",
        url="https://example.com",
        status="queued",
        webhook_url="https://example.com/hook",
        webhook_secret="sec",
    )

    with patch("webhook_delivery.deliver_webhook") as deliver:
        core._notify_job_webhook(job_id, "scrape.completed", {"url": "https://example.com"})
        deliver.assert_called_once()
        args = deliver.call_args[0]
        assert args[0] == "https://example.com/hook"
        assert args[1] == "sec"
        assert args[2] == "scrape.completed"


def test_enqueue_webhook_uses_rq_when_available(monkeypatch) -> None:
    monkeypatch.setenv("QUEUE_ENABLED", "true")
    clear_settings_cache()

    mock_q = MagicMock()
    with patch("job_queue.queue_available", return_value=True), patch(
        "job_queue.get_webhooks_queue", return_value=mock_q
    ):
        from job_queue import enqueue_webhook

        enqueue_webhook(
            "https://example.com/h",
            "s",
            "scrape.completed",
            {"a": 1},
            "idemp",
        )
        mock_q.enqueue.assert_called_once()
        assert mock_q.enqueue.call_args[0][0] == "job_tasks.run_webhook_delivery"

    clear_settings_cache()
