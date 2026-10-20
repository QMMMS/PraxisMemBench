"""Certificate-verified HTTP requests for memory and evaluation clients."""
from __future__ import annotations

import ssl
from functools import lru_cache
from urllib import request
from urllib.parse import urlparse


@lru_cache(maxsize=1)
def _https_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def urlopen(req, *, timeout: int):
    url = req.full_url if isinstance(req, request.Request) else str(req)
    parsed = urlparse(url)
    if parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        opener = request.build_opener(
            request.ProxyHandler({}), request.HTTPSHandler(context=_https_context())
        )
        return opener.open(req, timeout=timeout)
    return request.urlopen(req, timeout=timeout, context=_https_context())
