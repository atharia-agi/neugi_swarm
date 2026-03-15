#!/usr/bin/env python3
"""
🤖 NEUGI CIRCUIT BREAKER
===========================

Circuit breaker pattern implementation:
- Failure tracking
- State management
- Auto-recovery

Version: 1.0
Date: March 16, 2026
"""

import time
import threading
from typing import Dict, Callable, Any

NEUGI_DIR = __import__("os").path.expanduser("~/neugi")


class CircuitBreaker:
    """Circuit breaker"""

    STATES = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}

    def __init__(
        self, name: str, failure_threshold: int = 5, timeout: int = 60, success_threshold: int = 2
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        self.state = self.STATES["CLOSED"]
        self.failures = 0
        self.successes = 0
        self.last_failure_time = None
        self._lock = threading.RLock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        with self._lock:
            if self.state == self.STATES["OPEN"]:
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = self.STATES["HALF_OPEN"]
                    self.successes = 0
                else:
                    raise Exception(f"Circuit {self.name} is OPEN")

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise e

    def _on_success(self):
        self.failures = 0
        if self.state == self.STATES["HALF_OPEN"]:
            self.successes += 1
            if self.successes >= self.success_threshold:
                self.state = self.STATES["CLOSED"]

    def _on_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = self.STATES["OPEN"]

    def get_state(self) -> str:
        for state, value in self.STATES.items():
            if value == self.state:
                return state
        return "UNKNOWN"


class CircuitBreakerManager:
    """Manage circuit breakers"""

    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}

    def get_breaker(self, name: str, **kwargs) -> CircuitBreaker:
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, **kwargs)
        return self.breakers[name]

    def list_breakers(self) -> Dict:
        return {name: b.get_state() for name, b in self.breakers.items()}


manager = CircuitBreakerManager()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Circuit Breaker")
    parser.add_argument("--list", action="store_true", help="List breakers")
    args = parser.parse_args()

    if args.list:
        for name, state in manager.list_breakers().items():
            print(f"{name}: {state}")
    else:
        print("Usage: python -m neugi_circuit_breaker [--list]")


if __name__ == "__main__":
    main()
