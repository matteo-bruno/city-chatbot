"""The HTTP client, resolved once.

`httpx` and `httpx2` expose the same surface for everything used here
(`Client`, `stream`, `Response.iter_lines`, `MockTransport`, `HTTPError`), and
which one is installed depends on the Anthropic SDK's internals: 1.x pulls in
`httpx2`, older versions `httpx`. Relying on whichever happened to arrive as a
transitive dependency was fragile, so `httpx` is now declared directly in
requirements.txt and this module prefers it, falling back to `httpx2` when only
that is present.

Import the module from here rather than either package by name, so the
provider and its test double can never end up on different ones - a
`MockTransport` from one package is not accepted by the other's `Client`.
"""

from __future__ import annotations

from typing import Any

httpx: Any
HTTP_PACKAGE: str

try:
    import httpx as _httpx

    httpx = _httpx
    HTTP_PACKAGE = "httpx"
except ImportError:  # pragma: no cover - exercised by test_http.py via a stub
    try:
        import httpx2 as _httpx2

        httpx = _httpx2
        HTTP_PACKAGE = "httpx2"
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "No HTTP client found. Install the project's dependencies:\n"
            "    pip install -r requirements.txt\n"
            "(this needs `httpx`; `httpx2`, which ships with the Anthropic SDK, "
            "also works)"
        ) from exc

__all__ = ["HTTP_PACKAGE", "httpx"]
