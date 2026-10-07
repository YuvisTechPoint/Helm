"""Webhook signature and shared-secret verification."""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

from core.config import Settings, get_settings
from core.provider_plane import is_dev


def verify_shared_secret(header_value: str | None, secret: str | None) -> bool:
    if not secret:
        return False
    return hmac.compare_digest(header_value or "", secret)


def verify_meta_signature(body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not app_secret:
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header, expected)


def verify_twilio_signature(url: str, params: dict, signature: str | None, auth_token: str) -> bool:
    if not signature or not auth_token:
        return False
    pieces = [url] + [f"{key}{params[key]}" for key in sorted(params)]
    digest = hmac.new(auth_token.encode(), "".join(pieces).encode(), hashlib.sha1).digest()
    import base64

    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)


def require_webhook_auth(
    provider: str,
    *,
    header: str | None,
    secret: str | None,
    settings: Settings | None = None,
    dev_fallback_secret: str | None = None,
) -> None:
    settings = settings or get_settings()
    secret = secret or dev_fallback_secret or settings.webhook_shared_secret
    if verify_shared_secret(header, secret):
        return
    if is_dev(settings) and not secret:
        return
    from fastapi import HTTPException

    raise HTTPException(401, f"{provider} webhook authentication failed")
