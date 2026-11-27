"""Tests for persistent searchable HistoryStore with favorites/pinning."""

from __future__ import annotations

from pathlib import Path

from ocr_snip.history import HistoryStore


def test_history_store_roundtrip_and_translation(tmp_path: Path) -> None:
    hist_path = tmp_path / "history.json"
    store = HistoryStore(path=hist_path, max_entries=50)

    e1 = store.add(text="こんにちは世界", language="Japanese", engine="Local ML", confidence=0.99)
    assert e1 is not None
    assert store.update_translation(e1.id, "Hello world", "English") is True

    reloaded = HistoryStore(path=hist_path, max_entries=50)
    assert len(reloaded.entries) == 1
    assert reloaded.entries[0].text == "こんにちは世界"
    assert reloaded.entries[0].translation == "Hello world"
    assert reloaded.entries[0].translation_lang == "English"


def test_history_search_pin_and_clear_keeps_favorites(tmp_path: Path) -> None:
    hist_path = tmp_path / "history.json"
    store = HistoryStore(path=hist_path, max_entries=50)

    a = store.add(text="Invoice #42", language="English")
    b = store.add(text="Bonjour café", language="French")
    assert a and b

    store.toggle_pin(a.id)
    assert len(store.search("invoice")) == 1
    assert len(store.search("french")) == 1
    assert len(store.search(pinned_only=True)) == 1

    removed = store.clear(keep_pinned=True)
    assert removed == 1
    assert len(store.entries) == 1
    assert store.entries[0].id == a.id


def test_history_trim_never_evicts_pinned(tmp_path: Path) -> None:
    hist_path = tmp_path / "history.json"
    store = HistoryStore(path=hist_path, max_entries=2)

    pinned = store.add(text="Keep me forever", language="English")
    assert pinned is not None
    store.toggle_pin(pinned.id)

    store.add(text="Second", language="English")
    store.add(text="Third", language="English")

    ids = [e.id for e in store.entries]
    assert pinned.id in ids
    assert len(ids) == 2
