from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver

from app.core.config import settings
from app.db.models import ConnectedApp


class DeliveryError(Exception):
    def __init__(self, message: str, *, retryable: bool = True, retry_after: float = 0):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def validate_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
        )
    except ValueError as exc:
        raise ValueError("Use an HTTPS URL on port 443.") from exc
    if not valid or len(url) > 2048:
        raise ValueError("Use an HTTPS URL on port 443, without credentials or fragments.")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return url
    if not address.is_global or address.is_multicast:
        raise ValueError("Webhook addresses must be public.")
    return url


class PublicResolver(AbstractResolver):
    """Return only validated addresses to the connector, avoiding a second DNS lookup."""

    def __init__(self):
        self.resolver = aiohttp.resolver.ThreadedResolver()

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET):
        answers = await self.resolver.resolve(host, port, family)
        if not answers or any(
            not ipaddress.ip_address(answer["host"]).is_global or ipaddress.ip_address(answer["host"]).is_multicast
            for answer in answers
        ):
            raise DeliveryError("Webhook resolved to a non-public address", retryable=False)
        return answers

    async def close(self):
        await self.resolver.close()


def connection_secret(connection: ConnectedApp) -> str:
    if connection.kind == "trenchbook":
        secret = settings.trenchbook_webhook_secret
    else:
        master = settings.webhook_signing_key
        if len(master) < 32:
            raise ValueError("Custom webhooks are not configured by the operator.")
        secret = hmac.new(master.encode(), f"{connection.id}:{connection.secret_version}".encode(), hashlib.sha256).hexdigest()
    if len(secret) < 32:
        raise ValueError("Webhook signing is not configured by the operator.")
    return secret


def signature(secret: str, timestamp: str, delivery_id: str, body: bytes) -> str:
    message = f"{timestamp}.{delivery_id}.".encode() + body
    return "v1=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


async def send_webhook(connection: ConnectedApp, delivery_id: str, payload: dict) -> None:
    try:
        validate_url(connection.url)
        secret = connection_secret(connection)
    except ValueError as exc:
        raise DeliveryError(str(exc), retryable=False) from exc
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-PriceBird-Timestamp": timestamp,
        "X-PriceBird-Delivery-Id": delivery_id,
        "X-PriceBird-Event-Id": payload["event_id"],
        "X-PriceBird-Signature": signature(secret, timestamp, delivery_id, body),
    }
    resolver = PublicResolver()
    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(resolver=resolver, use_dns_cache=False),
            timeout=aiohttp.ClientTimeout(total=10),
            trust_env=False,
        ) as client:
            async with client.post(connection.url, data=body, headers=headers, allow_redirects=False) as response:
                if 200 <= response.status < 300:
                    return
                try:
                    delay = min(3600, max(0, float(response.headers.get("Retry-After", "0"))))
                except ValueError:
                    delay = 0
                raise DeliveryError(
                    f"HTTP {response.status}",
                    retryable=response.status in (408, 429) or response.status >= 500,
                    retry_after=delay,
                )
    finally:
        await resolver.close()
