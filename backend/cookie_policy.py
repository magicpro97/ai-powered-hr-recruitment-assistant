"""Cookie transport policy for auth sessions."""

# Standard library imports
import os
from urllib.parse import urlparse

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def cookies_require_https(frontend_url: str, secure_setting: str | None = None) -> bool:
    """Allow HTTP cookies only for explicit local loopback development."""
    host = urlparse(frontend_url).hostname
    if secure_setting is None:
        secure_setting = os.getenv("COOKIE_SECURE")
    if secure_setting is not None:
        wants_insecure = secure_setting.lower() in {"0", "false", "no"}
        return not (wants_insecure and host in _LOOPBACK_HOSTS)

    return host not in _LOOPBACK_HOSTS


def cookie_domain_for_origin(origin: str, configured_domain: str | None) -> str | None:
    """Use host-only cookies unless request host belongs to configured domain."""
    if not configured_domain:
        return None
    host = (urlparse(origin).hostname or "").lower()
    domain = configured_domain.lstrip(".").lower()
    if host in _LOOPBACK_HOSTS or (host != domain and not host.endswith(f".{domain}")):
        return None
    return configured_domain


def cookie_transport_for_frontend(
    frontend_url: str, configured_domain: str | None
) -> tuple[bool, str | None]:
    """Derive cookie transport only from trusted application configuration."""
    return (
        cookies_require_https(frontend_url),
        cookie_domain_for_origin(frontend_url, configured_domain),
    )
