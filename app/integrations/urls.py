from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


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
