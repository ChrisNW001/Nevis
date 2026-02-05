"""Webhook system -- register URLs for event notifications."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WebhookRegistration(BaseModel):
    """A registered webhook endpoint."""

    url: str
    events: list[str]  # e.g. ["task_completed", "error", "approval_needed"]
    secret: str = ""  # for HMAC signature verification
    active: bool = True


class WebhookEvent(BaseModel):
    """An event to be sent to webhook subscribers."""

    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class WebhookManager:
    """Manages webhook registrations and event delivery with retry."""

    def __init__(self, max_retries: int = 3):
        self._registrations: list[WebhookRegistration] = []
        self._max_retries = max_retries
        self._delivery_log: list[dict[str, Any]] = []

    def register(self, registration: WebhookRegistration) -> None:
        self._registrations.append(registration)
        logger.info(f"Registered webhook: {registration.url} for events {registration.events}")

    def unregister(self, url: str) -> None:
        self._registrations = [r for r in self._registrations if r.url != url]

    async def emit(self, event: WebhookEvent) -> None:
        """Send an event to all subscribed webhooks."""
        subscribers = [
            r for r in self._registrations
            if r.active and (event.event_type in r.events or "*" in r.events)
        ]

        if not subscribers:
            return

        tasks = [self._deliver(sub, event) for sub in subscribers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _deliver(self, registration: WebhookRegistration, event: WebhookEvent) -> None:
        """Deliver an event to a single webhook with retry."""
        payload = event.model_dump_json()
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if registration.secret:
            signature = hmac.new(
                registration.secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-Nevis-Signature"] = f"sha256={signature}"

        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        registration.url,
                        content=payload,
                        headers=headers,
                    )
                    response.raise_for_status()

                self._delivery_log.append({
                    "url": registration.url,
                    "event": event.event_type,
                    "status": response.status_code,
                    "attempt": attempt + 1,
                    "success": True,
                })
                return

            except Exception as e:
                if attempt < self._max_retries:
                    delay = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Webhook delivery failed (attempt {attempt + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Webhook delivery failed after {self._max_retries + 1} attempts: "
                        f"{registration.url} - {e}"
                    )
                    self._delivery_log.append({
                        "url": registration.url,
                        "event": event.event_type,
                        "attempt": attempt + 1,
                        "success": False,
                        "error": str(e),
                    })

    def get_delivery_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._delivery_log[-limit:]
