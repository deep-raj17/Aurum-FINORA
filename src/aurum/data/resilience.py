"""Rate-limited, retrying, cached HTTP transport for financial connectors."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)
SENSITIVE_QUERY_KEYS = {"apikey", "api_key", "token", "access_key"}


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, "***" if key.lower() in SENSITIVE_QUERY_KEYS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class ConnectorError(RuntimeError):
    """Raised after a connector exhausts validated retry attempts."""


class TokenBucket:
    def __init__(self, requests_per_second: float, burst: int = 1) -> None:
        if requests_per_second <= 0 or burst < 1:
            raise ValueError("rate and burst must be positive")
        self.rate = requests_per_second
        self.capacity = float(burst)
        self.tokens = float(burst)
        self.updated_at = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(
                    self.capacity,
                    self.tokens + (now - self.updated_at) * self.rate,
                )
                self.updated_at = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                delay = (1 - self.tokens) / self.rate
            time.sleep(delay)


class ResponseCache:
    def __init__(self, root: str | Path = "data/cache/connectors") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{hashlib.sha256(key.encode()).hexdigest()}.json"

    def get(self, key: str, ttl_seconds: float) -> Any | None:
        path = self._path(key)
        if not path.exists() or time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, key: str, value: Any) -> None:
        path = self._path(key)
        temporary = path.with_suffix(".pending")
        temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
        os_replace(temporary, path)

    def get_bytes(self, key: str, ttl_seconds: float) -> bytes | None:
        path = self.root / f"{hashlib.sha256(key.encode()).hexdigest()}.bin"
        if not path.exists() or time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        return path.read_bytes()

    def put_bytes(self, key: str, value: bytes) -> None:
        path = self.root / f"{hashlib.sha256(key.encode()).hexdigest()}.bin"
        temporary = path.with_suffix(".pending")
        temporary.write_bytes(value)
        os_replace(temporary, path)


def os_replace(source: Path, destination: Path) -> None:
    source.replace(destination)


class ResilientJSONClient:
    def __init__(
        self,
        *,
        requests_per_second: float = 2,
        retries: int = 3,
        timeout_seconds: float = 20,
        cache_ttl_seconds: float = 300,
        cache: ResponseCache | None = None,
        transport: Callable[[Request, float], Any] | None = None,
        seed: int = 42,
    ) -> None:
        if retries < 0 or timeout_seconds <= 0 or cache_ttl_seconds < 0:
            raise ValueError("invalid resilience configuration")
        self.limiter = TokenBucket(requests_per_second)
        self.retries = retries
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache = cache or ResponseCache()
        self.transport = transport or self._urlopen
        self.random = random.Random(seed)

    @staticmethod
    def _urlopen(request: Request, timeout: float) -> Any:
        return urlopen(request, timeout=timeout)

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        validator: Callable[[Any], bool] | None = None,
    ) -> Any:
        def validate_bytes(payload: bytes) -> bool:
            try:
                value = json.loads(payload)
            except json.JSONDecodeError:
                return False
            return validator(value) if validator is not None else True

        payload = self.get_bytes(url, headers=headers, validator=validate_bytes)
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ConnectorError(f"response was not valid JSON: {url}") from exc
        return value

    def get_bytes(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        validator: Callable[[bytes], bool] | None = None,
    ) -> bytes:
        cache_key = json.dumps([url, sorted((headers or {}).items())])
        cached = self.cache.get_bytes(cache_key, self.cache_ttl_seconds)
        if cached is not None and (validator is None or validator(cached)):
            return cached
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self.limiter.acquire()
            try:
                request = Request(url, headers=headers or {})
                with self.transport(request, self.timeout_seconds) as response:
                    payload = response.read()
                if not payload:
                    raise ConnectorError("response body was empty")
                if validator is not None and not validator(payload):
                    raise ConnectorError("response schema validation failed")
                self.cache.put_bytes(cache_key, payload)
                return payload
            except (HTTPError, URLError, TimeoutError, ValueError, ConnectorError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                delay = (2**attempt) + self.random.uniform(0, 0.25)
                logger.warning(
                    "connector request failed; retrying",
                    extra={
                        "url": redact_url(url),
                        "attempt": attempt + 1,
                        "delay": delay,
                    },
                )
                time.sleep(delay)
        raise ConnectorError(
            f"request failed after {self.retries + 1} attempts: {redact_url(url)}"
        ) from last_error
