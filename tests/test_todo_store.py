"""Tests for persistent MindClip pending To-Dos."""

from custom_components.mindclip.api import MindClipTodo
from custom_components.mindclip.todo_store import MindClipTodoStore


async def test_store_baselines_persists_and_acknowledges(hass) -> None:
    """Existing items form a baseline and later items remain pending until acked."""
    existing = MindClipTodo("a" * 64, "Existing", 1000, None)
    new = MindClipTodo("b" * 64, "Call office", 2000, 3000)
    store = MindClipTodoStore(hass, "test-entry")
    await store.async_load()

    assert await store.async_process((existing,), truncated=False) == ()
    pending = await store.async_process((existing, new), truncated=False)
    assert len(pending) == 1
    pending_item = pending[0]
    assert pending_item.uid == new.uid
    assert pending_item.title == new.title

    restored = MindClipTodoStore(hass, "test-entry")
    await restored.async_load()
    assert restored.pending == pending

    assert await restored.async_acknowledge(new.uid) == ()
