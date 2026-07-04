"""SSRF guard — outbound fetches from untrusted URLs must refuse private/internal targets."""

from __future__ import annotations

from laboratree.core.net import is_public_http_url


def test_blocks_cloud_metadata_and_internal():
    for url in (
        "http://169.254.169.254/latest/meta-data/",   # cloud metadata (link-local)
        "http://127.0.0.1:5432/",                       # loopback (local Postgres)
        "http://localhost/admin",                       # loopback by name
        "http://10.0.0.5/internal",                     # private
        "http://192.168.1.1/",                          # private
        "http://172.16.0.1/",                           # private
        "http://[::1]/",                                # IPv6 loopback
    ):
        assert is_public_http_url(url) is False, url


def test_blocks_non_http_schemes_and_junk():
    for url in ("ftp://8.8.8.8/x", "file:///etc/passwd", "gopher://8.8.8.8", "", "not-a-url", "http://"):
        assert is_public_http_url(url) is False, url


def test_allows_public_addresses():
    assert is_public_http_url("http://8.8.8.8/") is True          # public literal IP (no DNS needed)
    assert is_public_http_url("https://1.1.1.1/data.csv") is True


def test_safe_fetch_revalidates_redirect_targets(monkeypatch):
    """A public URL that redirects to an internal address must NOT be followed (redirect-SSRF)."""
    import httpx

    from laboratree.core import net

    class FakeResp:
        def __init__(self, status, headers=None):
            self.status_code = status
            self.headers = headers or {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_bytes(self):
            yield b"data"

    def fake_stream(method, url, **kw):
        # the public entrypoint 302-redirects to the cloud-metadata endpoint
        if "8.8.8.8" in url:
            return FakeResp(302, {"location": "http://169.254.169.254/latest/meta-data/"})
        raise AssertionError(f"should never fetch the internal target, but tried {url}")

    monkeypatch.setattr(httpx, "stream", fake_stream)
    # 8.8.8.8 is public so the first hop passes the guard, but the redirect target is link-local →
    # safe_fetch must re-validate and refuse, returning None without fetching it.
    assert net.safe_fetch("http://8.8.8.8/innocent.csv") is None
