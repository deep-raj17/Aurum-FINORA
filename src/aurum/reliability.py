"""Circuit breaking and explicit graceful-degradation policies."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class DependencyUnavailable(RuntimeError):
    pass


class DependencyResult(BaseModel, Generic[T]):
    value: T
    degraded: bool
    dependency: str
    reason: str | None = None


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 3,
        recovery_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1 or recovery_seconds <= 0:
            raise ValueError("circuit breaker thresholds must be positive")
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.clock = clock
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.opened_at: float | None = None
        self._lock = threading.Lock()

    def call(
        self,
        operation: Callable[[], T],
        *,
        fallback: Callable[[Exception], T] | None = None,
    ) -> DependencyResult[T]:
        with self._lock:
            if self.state is CircuitState.OPEN:
                assert self.opened_at is not None
                if self.clock() - self.opened_at < self.recovery_seconds:
                    error = DependencyUnavailable(f"{self.name} circuit is open")
                    if fallback:
                        return DependencyResult(
                            value=fallback(error),
                            degraded=True,
                            dependency=self.name,
                            reason=str(error),
                        )
                    raise error
                self.state = CircuitState.HALF_OPEN
        try:
            value = operation()
        except Exception as exc:
            with self._lock:
                self.failures += 1
                if self.failures >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.opened_at = self.clock()
            if fallback:
                return DependencyResult(
                    value=fallback(exc),
                    degraded=True,
                    dependency=self.name,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            raise DependencyUnavailable(f"{self.name} failed") from exc
        with self._lock:
            self.failures = 0
            self.state = CircuitState.CLOSED
            self.opened_at = None
        return DependencyResult(value=value, degraded=False, dependency=self.name)
