"""Limite di tentativi a finestra scorrevole, in memoria (un processo API).

Usato per il login: 5 tentativi falliti in 15 minuti dallo stesso IP → 429 (RF-09).
Con più istanze dell'API servirebbe un archivio condiviso (es. Redis).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float, clock=time.monotonic) -> None:  # type: ignore[no-untyped-def]
        self.max_events = max_events
        self.window = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        events = self._events[key]
        while events and now - events[0] >= self.window:
            events.popleft()
        return events

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            blocked = len(self._prune(key, self._clock())) >= self.max_events
            if not self._events[key]:
                del self._events[key]  # niente chiavi vuote: la memoria non cresce
            return blocked

    def retry_after(self, key: str) -> int:
        with self._lock:
            events = self._prune(key, self._clock())
            if len(events) < self.max_events:
                if not events:
                    del self._events[key]
                return 0
            return max(1, int(self.window - (self._clock() - events[0])))

    def hit(self, key: str) -> None:
        with self._lock:
            self._prune(key, self._clock()).append(self._clock())

    def check_and_hit(self, key: str) -> bool:
        """Registra un evento se c'è spazio; restituisce False se il limite è raggiunto."""
        with self._lock:
            events = self._prune(key, self._clock())
            if len(events) >= self.max_events:
                return False
            events.append(self._clock())
            return True

    def __len__(self) -> int:
        return len(self._events)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)
