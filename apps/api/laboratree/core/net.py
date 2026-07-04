"""Outbound-request safety (SSRF guard).

Several agent features fetch URLs that originate from web-search results, the LLM, or paper text —
untrusted input. Without a guard, a crafted URL (http://169.254.169.254/ cloud-metadata,
http://localhost:5432, an internal 10.x host) could make the server exfiltrate secrets or reach
internal services. `is_public_http_url` resolves the host and only allows http(s) to a globally
routable address, blocking loopback/private/link-local/reserved ranges.

Residual risk: DNS rebinding (host resolves public here but flips before the socket connects) — a
known, advanced attack; mitigating it fully needs connection-time IP pinning. This guard stops the
common, high-impact vectors and is the right first line for launch.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urlparse

log = logging.getLogger(__name__)


def is_public_http_url(url: str) -> bool:
    """True only for an http(s) URL whose host resolves entirely to public IP addresses."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except Exception as exc:
        log.info("SSRF guard: cannot resolve %r: %s", parsed.hostname, exc)
        return False
    addrs = {info[4][0] for info in infos}
    if not addrs:
        return False
    for addr in addrs:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if not ip.is_global or ip.is_private or ip.is_loopback or ip.is_link_local \
                or ip.is_reserved or ip.is_multicast:
            log.info("SSRF guard: blocked non-public address %s for %r", addr, url)
            return False
    return True


__all__ = ["is_public_http_url"]
