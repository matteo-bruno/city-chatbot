"""Optional server-side conversation memory.

The service is stateless by default: a client sends the history back with each
message, which is what makes it trivial to embed in another website or to run
behind a load balancer. `session_id` is a convenience for simple front ends
that would rather not hold the transcript, and this store is deliberately a
capped in-process dict. For multiple workers or persistence across restarts,
either keep history on the client or swap this for Redis.

A session records which provider produced it, because histories are
provider-native and cannot be replayed against a different API.
"""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class SessionState:
    provider: str = ""
    messages: list[dict] = field(default_factory=list)


class SessionStore:
    def __init__(self, max_sessions: int = 200, ttl_seconds: float = 3 * 3600) -> None:
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._data: OrderedDict[str, tuple[float, SessionState]] = OrderedDict()

    def new_id(self) -> str:
        return secrets.token_urlsafe(12)

    def _expire(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        for key in [k for k, (ts, _) in self._data.items() if ts < cutoff]:
            self._data.pop(key, None)

    def get(self, session_id: str) -> SessionState:
        self._expire()
        entry = self._data.get(session_id)
        if entry is None:
            return SessionState()
        self._data.move_to_end(session_id)
        return entry[1]

    def set(self, session_id: str, provider: str, messages: list[dict]) -> None:
        self._expire()
        self._data[session_id] = (time.time(), SessionState(provider=provider, messages=messages))
        self._data.move_to_end(session_id)
        while len(self._data) > self.max_sessions:
            self._data.popitem(last=False)

    def clear(self, session_id: str) -> bool:
        return self._data.pop(session_id, None) is not None

    def __len__(self) -> int:
        return len(self._data)
