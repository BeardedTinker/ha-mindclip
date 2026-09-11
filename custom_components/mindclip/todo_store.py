"""Persistent pending To-Do tracking for MindClip."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .api import MindClipTodo
from .const import DOMAIN

STORAGE_VERSION = 1
SEEN_TODO_LIMIT = 5000


@dataclass(frozen=True, slots=True)
class PendingTodo:
    """One locally pending MindClip To-Do."""

    uid: str
    title: str
    created_time: int
    reminder_time: int | None


class MindClipTodoStore:
    """Persist seen and pending To-Dos for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the store."""
        self._store = Store[dict[str, Any]](
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.todos"
        )
        self._lock = asyncio.Lock()
        self._initialized = False
        self._seen: dict[str, int] = {}
        self._pending: dict[str, PendingTodo] = {}

    @property
    def pending(self) -> tuple[PendingTodo, ...]:
        """Return pending items in reminder and creation order."""
        return tuple(
            sorted(
                self._pending.values(),
                key=lambda item: (
                    item.reminder_time is None,
                    item.reminder_time or item.created_time,
                    item.created_time,
                    item.uid,
                ),
            )
        )

    async def async_load(self) -> None:
        """Load valid persisted state, ignoring malformed fields."""
        data = await self._store.async_load()
        if not isinstance(data, Mapping):
            return

        self._initialized = data.get("initialized") is True
        seen = data.get("seen")
        if isinstance(seen, Mapping):
            self._seen = {
                uid: created_time
                for uid, created_time in seen.items()
                if _valid_uid(uid) and _valid_timestamp(created_time)
            }

        pending = data.get("pending")
        if not isinstance(pending, list):
            return
        for raw_item in pending:
            item = _parse_pending(raw_item)
            if item is not None:
                self._pending[item.uid] = item

    async def async_process(
        self, todos: tuple[MindClipTodo, ...], *, truncated: bool
    ) -> tuple[PendingTodo, ...]:
        """Add newly observed To-Dos after establishing an initial baseline."""
        if truncated:
            return self.pending

        async with self._lock:
            changed = False
            if not self._initialized:
                self._seen.update({todo.uid: todo.created_time for todo in todos})
                self._initialized = True
                changed = True
            else:
                for todo in todos:
                    pending = PendingTodo(
                        uid=todo.uid,
                        title=todo.title,
                        created_time=todo.created_time,
                        reminder_time=todo.reminder_time,
                    )
                    if todo.uid not in self._seen:
                        self._pending[todo.uid] = pending
                        changed = True
                    elif (
                        todo.uid in self._pending and self._pending[todo.uid] != pending
                    ):
                        self._pending[todo.uid] = pending
                        changed = True
                    self._seen[todo.uid] = todo.created_time

            if len(self._seen) > SEEN_TODO_LIMIT:
                self._seen = dict(
                    sorted(self._seen.items(), key=lambda item: item[1], reverse=True)[
                        :SEEN_TODO_LIMIT
                    ]
                )
                changed = True

            if changed:
                await self._async_save()
            return self.pending

    async def async_acknowledge(self, uid: str) -> tuple[PendingTodo, ...]:
        """Remove one pending item idempotently."""
        async with self._lock:
            if self._pending.pop(uid, None) is not None:
                await self._async_save()
            return self.pending

    async def _async_save(self) -> None:
        """Persist current state."""
        await self._store.async_save(
            {
                "initialized": self._initialized,
                "seen": self._seen,
                "pending": [asdict(item) for item in self.pending],
            }
        )


def _parse_pending(value: object) -> PendingTodo | None:
    """Parse one valid pending item from storage."""
    if not isinstance(value, Mapping):
        return None
    uid = value.get("uid")
    title = value.get("title")
    created_time = value.get("created_time")
    reminder_time = value.get("reminder_time")
    if (
        not _valid_uid(uid)
        or not isinstance(title, str)
        or not title
        or not _valid_timestamp(created_time)
        or (reminder_time is not None and not _valid_timestamp(reminder_time))
    ):
        return None
    return PendingTodo(uid, title, created_time, reminder_time)


def _valid_uid(value: object) -> bool:
    """Return whether a value is a bounded hexadecimal To-Do UID."""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_timestamp(value: object) -> bool:
    """Return whether a value is a non-negative integer timestamp."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
