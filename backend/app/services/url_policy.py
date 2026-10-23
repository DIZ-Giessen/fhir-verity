"""
Which URLs Verity may send requests (and stored credentials) to.

Server URLs are entered by users, so without limits the backend could be
used to probe the internal network. Link-local addresses (cloud metadata
services) are always refused; FHIR_ALLOWED_HOSTS narrows it down further.
"""

import ipaddress
from fnmatch import fnmatch
from urllib.parse import urlsplit

from app.core.config import get_settings

settings = get_settings()


def _allowed_hosts() -> list[str]:
    return [
        h.strip().lower() for h in settings.FHIR_ALLOWED_HOSTS.split(",") if h.strip()
    ]


def check_outbound_url(url: str) -> None:
    """Raise ValueError if Verity must not connect to this URL."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise ValueError("URL has no host")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_link_local or ip.is_multicast or ip.is_unspecified):
        raise ValueError(f"Connections to {host} are not allowed")

    allowed = _allowed_hosts()
    if allowed and not any(fnmatch(host, pattern) for pattern in allowed):
        raise ValueError(
            f"Host {host} is not in FHIR_ALLOWED_HOSTS. Ask your administrator "
            "to add it."
        )


def origin(url: str) -> tuple[str, str, int | None]:
    parts = urlsplit(url)
    port = parts.port or {"http": 80, "https": 443}.get(parts.scheme)
    return parts.scheme, (parts.hostname or "").lower(), port


def same_origin(a: str, b: str) -> bool:
    return origin(a) == origin(b)
