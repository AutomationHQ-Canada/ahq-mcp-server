import pytest

import src.tools.url_guard as url_guard
from src.tools.url_guard import validate_public_http_url


def _resolver(*addresses):
    def fake(host):
        return list(addresses)
    return fake


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://localhost:9202/agent",  # localhost resolves via patched resolver below
    "http://10.0.0.5/internal",
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
    "http://100.64.0.1/",            # CGNAT
    "http://[fd00::1]/",             # IPv6 ULA
    "http://[::1]:8000/",
    "http://192.168.1.10/router",
])
async def test_blocks_private_and_special_addresses(monkeypatch, url):
    # For hostname forms, resolve to themselves via a private answer
    monkeypatch.setattr(url_guard, "_resolve_addresses", _resolver("127.0.0.1"))
    assert await validate_public_http_url(url) is not None


async def test_blocks_public_hostname_resolving_private(monkeypatch):
    # A public-looking name with one private A record is still an attack.
    monkeypatch.setattr(url_guard, "_resolve_addresses", _resolver("93.184.216.34", "10.0.0.7"))
    assert await validate_public_http_url("http://innocent.example.com/") is not None


async def test_blocks_non_http_schemes():
    assert await validate_public_http_url("ftp://example.com/file") is not None
    assert await validate_public_http_url("file:///etc/passwd") is not None
    assert await validate_public_http_url("gopher://example.com/") is not None


async def test_blocks_unresolvable_host(monkeypatch):
    import socket

    def raiser(host):
        raise socket.gaierror("NXDOMAIN")

    monkeypatch.setattr(url_guard, "_resolve_addresses", raiser)
    assert await validate_public_http_url("http://does-not-exist.example/") is not None


async def test_allows_public_addresses(monkeypatch):
    monkeypatch.setattr(url_guard, "_resolve_addresses", _resolver("93.184.216.34"))
    assert await validate_public_http_url("https://app.example.com/login") is None
    assert await validate_public_http_url("https://93.184.216.34/direct") is None
