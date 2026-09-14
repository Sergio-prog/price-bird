from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from app.i18n import LocalizedError


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
        raise LocalizedError("error-url-https") from exc
    if not valid or len(url) > 2048:
        raise LocalizedError("error-url-invalid")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return url
    if not address.is_global or address.is_multicast:
        raise LocalizedError("error-url-public")
    return url
