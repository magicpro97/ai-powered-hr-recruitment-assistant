# Standard library imports
from ipaddress import IPv6Address, ip_address, ip_network

# Third-party imports
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Local application imports
from src.config import Config


def _is_ip_trusted(ip_str: str, trusted_proxy_cidrs: tuple[str, ...]) -> bool:
    """Check if *ip_str* belongs to any of the trusted CIDR networks.

    Invalid IPs and malformed CIDRs are silently treated as *not trusted*.
    """
    try:
        addr = ip_address(ip_str)
    except ValueError:
        return False
    # Normalize IPv4-mapped IPv6 (e.g. ::ffff:10.1.2.3) so it matches IPv4 CIDRs
    if isinstance(addr, IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    for cidr in trusted_proxy_cidrs:
        try:
            if addr in ip_network(cidr):
                return True
        except ValueError:
            continue
    return False


def get_real_ip(
    request: Request, trusted_proxy_cidrs: tuple[str, ...] | None = None
) -> str:
    """
    Get the real IP address of the client, handling X-Forwarded-For.

    Multi-proxy traversal (right-to-left):
    1. If the direct peer is NOT trusted, X-Forwarded-For is always ignored.
    2. If trusted, parse the XFF header and walk entries right-to-left.
       - Entries that belong to a trusted CIDR are skipped (they are
         intermediate proxies).
       - The first entry that is NOT in any trusted CIDR is returned as the
         real client IP.
       - Invalid/malformed XFF entries are silently skipped.
    3. If all XFF entries are trusted (or the header is missing/empty),
       fall back to the direct peer IP.
    """
    direct_ip = (
        request.client.host
        if request.client and request.client.host
        else get_remote_address(request)
    )
    trusted_proxy_cidrs = (
        Config.TRUSTED_PROXY_CIDRS
        if trusted_proxy_cidrs is None
        else trusted_proxy_cidrs
    )

    # Direct peer decides whether we can trust XFF at all
    trusted_proxy = _is_ip_trusted(direct_ip, trusted_proxy_cidrs)

    forwarded = request.headers.get("X-Forwarded-For")
    if not trusted_proxy or not forwarded:
        return direct_ip

    # Trusted proxy → traverse XFF right-to-left, skip trusted hops
    entries = forwarded.split(",")
    for entry in reversed(entries):
        stripped = entry.strip()
        if not stripped:
            continue
        # Validate IP — skip malformed entries entirely
        try:
            ip_address(stripped)
        except ValueError:
            continue
        # Return the first IP that is NOT in any trusted CIDR
        if not _is_ip_trusted(stripped, trusted_proxy_cidrs):
            return stripped

    # All XFF entries are trusted (or no valid entries) — fallback to direct
    return direct_ip


# Initialize rate limiter with proxy-aware key function
limiter = Limiter(key_func=get_real_ip)
