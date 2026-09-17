"""Optional server-side conversation memory.

The service is stateless by default: a client sends the history back with each
message, which is what makes it trivial to embed in another website or to run
behind a load balancer. `session_id` is a convenience for simple front ends
that would rather not hold the transcript, and this store is deliberately a
capped in-process dict. For multiple workers or persistence across restarts,
either keep history on the client or swap this for Redis.
"""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict


class SessionStore:
    def __init__(self, max_sessions: int = 200, ttl_seconds: float = 3 * 3600) -> None:
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._data: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()

    def new_id(self) -> str:
        return secrets.token_urlsafe(12)

    def _expire(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        for key in [k for k, (ts, _) in self._data.items() if ts < cutoff]:
            self._data.pop(key, None)

    def get(self, session_id: str) -> list[dict]:
        self._expire()
        entry = self._data.get(session_id)
        if entry is None:
            return []
        self._data.move_to_end(session_id)
        return entry[1]

    def set(self, session_id: str, history: list[dict]) -> None:
        self._expire()
        self._data[session_id] = (time.time(), history)
        self._data.move_to_end(session_id)
        while len(self._data) > self.max_sessions:
            self._data.popitem(last=False)

    def clear(self, session_id: str) -> bool:
        return self._data.pop(session_id, None) is not None

    def __len__(self) -> int:
        return len(self._data)
