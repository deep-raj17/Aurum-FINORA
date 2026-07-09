"""Security primitives for secrets, identity, authorization, encryption, and RAG safety."""

from __future__ import annotations

import base64
import hmac
import os
import re
import stat
import threading
import time
from collections import defaultdict, deque
from collections.abc import Iterable
from importlib import import_module
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["viewer", "analyst", "model_operator", "administrator"]
VALID_ROLES: set[str] = {"viewer", "analyst", "model_operator", "administrator"}


class Principal(BaseModel):
    subject: str
    roles: set[Role]
    issuer: str
    expires_at: int
    claims: dict[str, Any] = Field(default_factory=dict)


class SecretManager:
    """Reads secrets from environment or mounted files without logging their values."""

    def get(self, name: str, *, required: bool = True) -> str | None:
        value = os.getenv(name)
        file_name = os.getenv(f"{name}_FILE")
        if value and file_name:
            raise RuntimeError(f"configure only one of {name} or {name}_FILE")
        if file_name:
            path = Path(file_name).resolve(strict=True)
            if os.name != "nt":
                mode = stat.S_IMODE(path.stat().st_mode)
                if mode & (stat.S_IRWXG | stat.S_IRWXO):
                    raise PermissionError(f"secret file for {name} is accessible by group/other")
            value = path.read_text(encoding="utf-8").strip()
        if required and not value:
            raise RuntimeError(f"required secret is not configured: {name}")
        return value


class JWTAuthenticator:
    """OIDC/JWT verification using a static public key or remote JWKS."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        public_key: str | None = None,
        jwks_url: str | None = None,
        algorithms: tuple[str, ...] = ("RS256",),
    ) -> None:
        if bool(public_key) == bool(jwks_url):
            raise ValueError("configure exactly one of public_key or jwks_url")
        if not algorithms or any(algorithm == "none" for algorithm in algorithms):
            raise ValueError("JWT algorithms must be explicit and cannot include none")
        self.issuer = issuer
        self.audience = audience
        self.public_key = public_key
        self.jwks_url = jwks_url
        self.algorithms = algorithms
        self._jwks_client: Any | None = None

    def authenticate(self, token: str) -> Principal:
        jwt = import_module("jwt")
        key: Any = self.public_key
        if self.jwks_url:
            if self._jwks_client is None:
                self._jwks_client = jwt.PyJWKClient(self.jwks_url, cache_keys=True)
            key = self._jwks_client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key=key,
            algorithms=list(self.algorithms),
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
        raw_roles = claims.get("roles", [])
        roles = {role for role in raw_roles if role in VALID_ROLES}
        if not roles:
            raise PermissionError("authenticated principal has no recognized FINORA role")
        return Principal(
            subject=str(claims["sub"]),
            roles=roles,
            issuer=str(claims["iss"]),
            expires_at=int(claims["exp"]),
            claims=claims,
        )


PERMISSIONS: dict[Role, set[str]] = {
    "viewer": {"reports:read", "health:read"},
    "analyst": {
        "reports:read",
        "health:read",
        "analysis:run",
        "evidence:read",
        "models:infer",
    },
    "model_operator": {
        "reports:read",
        "health:read",
        "analysis:run",
        "evidence:read",
        "evidence:write",
        "models:infer",
        "models:deploy",
    },
    "administrator": {"*"},
}


def require_permission(principal: Principal, permission: str) -> None:
    allowed = set().union(*(PERMISSIONS[role] for role in principal.roles))
    if "*" not in allowed and permission not in allowed:
        raise PermissionError(f"principal lacks permission: {permission}")


class SlidingWindowRateLimiter:
    """Thread-safe per-principal sliding-window limiter."""

    def __init__(self, requests: int, window_seconds: float) -> None:
        if requests < 1 or window_seconds <= 0:
            raise ValueError("rate-limit values must be positive")
        self.requests = requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, float]:
        timestamp = time.monotonic() if now is None else now
        cutoff = timestamp - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.requests:
                return False, max(0.0, events[0] + self.window_seconds - timestamp)
            events.append(timestamp)
            return True, 0.0


class FieldEncryptor:
    """Authenticated AES-256-GCM encryption with per-value nonces."""

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES-256-GCM requires exactly 32 key bytes")
        aes_type = import_module("cryptography.hazmat.primitives.ciphers.aead").AESGCM
        self._aes = aes_type(key)

    @classmethod
    def from_base64(cls, value: str) -> FieldEncryptor:
        try:
            key = base64.b64decode(value, validate=True)
        except ValueError as exc:
            raise ValueError("encryption key must be valid base64") from exc
        return cls(key)

    def encrypt(self, plaintext: str, *, context: str) -> str:
        nonce = os.urandom(12)
        ciphertext = self._aes.encrypt(nonce, plaintext.encode(), context.encode())
        return base64.urlsafe_b64encode(nonce + ciphertext).decode()

    def decrypt(self, value: str, *, context: str) -> str:
        packed = base64.urlsafe_b64decode(value)
        if len(packed) < 29:
            raise ValueError("encrypted value is truncated")
        plaintext = self._aes.decrypt(packed[:12], packed[12:], context.encode())
        return plaintext.decode()


class ContentSafetyReport(BaseModel):
    accepted: bool
    score: float = Field(ge=0, le=1)
    reasons: list[str]
    content_sha256: str


class RAGContentGuard:
    """Detects instruction injection and suspicious evidence manipulation."""

    INSTRUCTION_PATTERNS = (
        re.compile(r"\b(ignore|override|bypass)\b.{0,40}\b(instruction|policy|system)\b", re.I),
        re.compile(r"\b(system|developer|assistant)\s*(message|prompt)\b", re.I),
        re.compile(r"\b(do not|never)\s+(cite|mention|reveal)\b", re.I),
        re.compile(r"<\s*(system|assistant|tool)\b", re.I),
        re.compile(r"\b(exfiltrate|api[_ -]?key|secret|password)\b", re.I),
    )

    def inspect(
        self,
        content: str,
        *,
        expected_sha256: str | None = None,
        trusted_origins: Iterable[str] = (),
        origin: str = "",
    ) -> ContentSafetyReport:
        from hashlib import sha256

        digest = sha256(content.encode()).hexdigest()
        reasons = [
            f"instruction pattern {index + 1}"
            for index, pattern in enumerate(self.INSTRUCTION_PATTERNS)
            if pattern.search(content)
        ]
        if expected_sha256 and not hmac.compare_digest(digest, expected_sha256):
            reasons.append("content integrity mismatch")
        trusted = set(trusted_origins)
        if trusted and origin not in trusted:
            reasons.append("untrusted origin")
        score = min(1.0, len(reasons) * 0.35)
        return ContentSafetyReport(
            accepted=not reasons,
            score=score,
            reasons=reasons,
            content_sha256=digest,
        )
