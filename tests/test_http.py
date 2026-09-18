"""How the HTTP client is resolved.

The Gemini provider and the optional geocoder speak HTTP directly. Which
client is present depends on the Anthropic SDK version (1.x brings `httpx2`,
older ones `httpx`), so the resolution has to work either way - and the
provider and its test double must land on the *same* one, since a
`MockTransport` from one package is rejected by the other's `Client`.
"""

from __future__ import annotations

import builtins
import importlib
import sys

import pytest

import citychat.http


def reload_with_blocked(*blocked: str):
    """Re-import citychat.http with some modules pretending to be absent."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in blocked:
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    saved = {name: sys.modules.pop(name, None) for name in blocked}
    sys.modules.pop("citychat.http", None)
    builtins.__import__ = fake_import
    try:
        return importlib.import_module("citychat.http")
    finally:
        builtins.__import__ = real_import
        for name, module in saved.items():
            if module is not None:
                sys.modules[name] = module
        sys.modules.pop("citychat.http", None)
        importlib.import_module("citychat.http")


def test_the_resolved_client_has_everything_the_project_uses():
    httpx = citychat.http.httpx
    for attribute in ("Client", "Request", "Response", "MockTransport", "HTTPError"):
        assert hasattr(httpx, attribute), attribute
    assert hasattr(httpx.Response, "iter_lines")
    assert hasattr(httpx.Response, "read")
    assert citychat.http.HTTP_PACKAGE in ("httpx", "httpx2")


def test_httpx_is_preferred_when_both_are_installed():
    pytest.importorskip("httpx")
    pytest.importorskip("httpx2")
    assert citychat.http.HTTP_PACKAGE == "httpx"


def test_it_falls_back_to_httpx2_when_httpx_is_absent():
    pytest.importorskip("httpx2")
    module = reload_with_blocked("httpx")
    assert module.HTTP_PACKAGE == "httpx2"
    assert hasattr(module.httpx, "Client")


def test_with_no_client_at_all_the_error_says_what_to_install():
    with pytest.raises(ImportError, match="requirements.txt"):
        reload_with_blocked("httpx", "httpx2")


def test_the_provider_and_the_stub_share_one_client():
    """A cross-package transport would fail at request time, not import time."""
    from gemini_stub import GeminiStub

    from citychat.providers.gemini import GeminiProvider

    assert isinstance(GeminiStub(), citychat.http.httpx.MockTransport)
    provider = GeminiProvider(
        model="m", system_prompt="s", tools=[], api_key="k", transport=GeminiStub()
    )
    with provider._client() as client:
        assert isinstance(client, citychat.http.httpx.Client)
