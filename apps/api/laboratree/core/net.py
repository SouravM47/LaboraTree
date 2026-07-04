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
from urllib.parse import urljoin, urlparse

log = logging.getLogger(__name__)

USER_AGENT = "Laboratree/0.1"
_REDIRECT_CODES = {301, 302, 303, 307, 308}


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


def safe_fetch(
    url: str,
    *,
    timeout: float = 20.0,
    max_bytes: int = 25 * 1024 * 1024,
    max_redirects: int = 5,
    user_agent: str = USER_AGENT,
) -> bytes | None:
    """Fetch a URL with SSRF protection AT EVERY HOP + a size cap. Redirects are followed manually so
    each target is re-validated as public — closing the common bypass where a public URL 302-redirects
    to an internal/metadata address. Returns body bytes, or None on any block/error. Never raises."""
    import httpx

    current = url
    for _ in range(max_redirects + 1):
        if not is_public_http_url(current):
            log.info("safe_fetch blocked non-public target %s", current)
            return None
        try:
            with httpx.stream("GET", current, timeout=timeout, follow_redirects=False,
                              headers={"User-Agent": user_agent}) as resp:
                if resp.status_code in _REDIRECT_CODES:
                    loc = resp.headers.get("location")
                    if not loc:
                        return None
                    current = urljoin(current, loc)  # re-validated at the top of the next iteration
                    continue
                if resp.status_code != 200:
                    return None
                length = resp.headers.get("content-length", "")
                if length.isdigit() and int(length) > max_bytes:
                    return None
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        return None
                    chunks.append(chunk)
                return b"".join(chunks)
        except Exception as exc:
            log.debug("safe_fetch %s failed: %s", current, exc)
            return None
    log.info("safe_fetch: too many redirects for %s", url)
    return None


__all__ = ["is_public_http_url", "safe_fetch"]
