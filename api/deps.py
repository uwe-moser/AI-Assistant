"""
Shared dependencies for the API: a Sidekick registry that keeps one
orchestrator per session_id alive across HTTP and WebSocket requests.
"""

import asyncio
import logging
from typing import Dict

from sidekick import Sidekick

log = logging.getLogger(__name__)


class SidekickRegistry:
    """Lazy, per-session Sidekick cache.

    A single Sidekick is expensive to spin up (loads the LangGraph, opens an
    aiosqlite checkpoint connection, optionally starts a Chromium browser via
    Playwright). We keep one per session_id and protect concurrent setup with
    a per-session lock so two simultaneous requests don't double-init.
    """

    def __init__(self):
        self._instances: Dict[str, Sidekick] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get(self, session_id: str, *, include_browser: bool = True) -> Sidekick:
        async with self._global_lock:
            lock = self._locks.setdefault(session_id, asyncio.Lock())

        async with lock:
            sk = self._instances.get(session_id)
            if sk is not None:
                return sk
            sk = Sidekick(session_id=session_id)
            await sk.setup(include_browser=include_browser)
            self._instances[session_id] = sk
            log.info("Sidekick ready for session %s", session_id)
            return sk

    async def evict(self, session_id: str):
        sk = self._instances.pop(session_id, None)
        self._locks.pop(session_id, None)
        if sk is not None:
            try:
                sk.cleanup()
            except Exception as e:
                log.warning("Cleanup failed for session %s: %s", session_id, e)

    async def shutdown_all(self):
        for sid in list(self._instances.keys()):
            await self.evict(sid)


sidekick_registry = SidekickRegistry()
