import asyncio
import ipaddress
import socket
from urllib.parse import urlparse


def _resolve_addresses(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


async def validate_public_http_url(url: str) -> str | None:
    """
    SSRF guard for hosted crawling: returns an error string if `url` must not be fetched from
    inside the cluster, or None if it's safe. Blocks non-http(s) schemes and any hostname
    resolving to a non-global address — loopback, RFC 1918, link-local (incl. the 169.254.169.254
    cloud metadata endpoint), CGNAT 100.64/10, IPv6 ULA, unspecified, multicast, reserved — via
    `ipaddress.is_global`, on EVERY resolved address (a public name resolving to one private A
    record is still an attack). DNS re-resolution happens per navigation in crawl_url; the
    remaining rebinding TOCTOU window is a documented accepted residual risk (Playwright can't
    pin IPs).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"URL scheme '{parsed.scheme}' is not allowed on the hosted server — use http or https."
    host = parsed.hostname
    if not host:
        return "URL has no hostname."
    try:
        # Literal IPs don't need DNS; check them directly (also catches formats getaddrinfo
        # would happily pass through, like zone-indexed IPv6).
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            addresses = await asyncio.to_thread(_resolve_addresses, host)
        except socket.gaierror:
            return f"Could not resolve host '{host}'."
    if not addresses:
        return f"Could not resolve host '{host}'."
    for addr in addresses:
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
        except ValueError:
            return f"Host '{host}' resolved to an unparseable address."
        if not ip.is_global:
            return (
                f"URL is not reachable from the hosted server: '{host}' resolves to a "
                f"private/internal address. Crawl internal apps with the local (stdio) server instead."
            )
    return None
