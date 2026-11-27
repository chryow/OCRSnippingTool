"""Persistent local snip history store with search and favorites."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from ocr_snip.config import get_config_dir


def get_history_path() -> Path:
    """Return the default path to the persistent JSON snip history file."""
    return get_config_dir() / "history.json"


@dataclass
class HistoryEntry:
    """A single recorded OCR snip in local history."""

    id: str
    timestamp: str
    text: str
    language: str = "Unknown"
    engine: str = ""
    confidence: float = 0.0
    translation: str = ""
    translation_lang: str = ""
    pinned: bool = False

    @property
    def short_preview(self) -> str:
        one_line = " ".join(self.text.split())
        if len(one_line) > 72:
            return one_line[:69] + "..."
        return one_line or "(empty)"

    @property
    def display_time(self) -> str:
        try:
            dt = datetime.fromisoformat(self.timestamp)
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return self.timestamp


class HistoryStore:
    """Manages persistent JSON storage for past OCR extractions."""

    def __init__(self, path: Path | None = None, max_entries: int = 100) -> None:
        self.path = path or get_history_path()
        self.max_entries = max(1, max_entries)
        self._entries: list[HistoryEntry] = []
        self.load()

    @property
    def entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def load(self) -> None:
        if not self.path.exists():
            self._entries = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._entries = []
            return
        if not isinstance(raw, list):
            self._entries = []
            return

        valid_fields = set(HistoryEntry.__dataclass_fields__.keys())
        loaded: list[HistoryEntry] = []
        for item in raw:
            if isinstance(item, dict) and "text" in item:
                filtered = {k: v for k, v in item.items() if k in valid_fields}
                filtered.setdefault("id", uuid.uuid4().hex[:12])
                filtered.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
                loaded.append(HistoryEntry(**filtered))
        self._entries = loaded

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(entry) for entry in self._entries]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def add(
        self,
        *,
        text: str,
        language: str = "Unknown",
        engine: str = "",
        confidence: float = 0.0,
    ) -> HistoryEntry | None:
        """Record a non-empty OCR extraction at the top of history."""
        cleaned = text.strip()
        if not cleaned:
            return None

        entry = HistoryEntry(
            id=uuid.uuid4().hex[:12],
            timestamp=datetime.now().isoformat(timespec="seconds"),
            text=cleaned,
            language=language or "Unknown",
            engine=engine,
            confidence=round(confidence, 3),
        )
        self._entries.insert(0, entry)
        self._trim()
        self.save()
        return entry

    def update_translation(
        self, entry_id: str, translated_text: str, target_lang: str
    ) -> bool:
        for entry in self._entries:
            if entry.id == entry_id:
                entry.translation = translated_text.strip()
                entry.translation_lang = target_lang
                self.save()
                return True
        return False

    def toggle_pin(self, entry_id: str) -> bool | None:
        for entry in self._entries:
            if entry.id == entry_id:
                entry.pinned = not entry.pinned
                self.save()
                return entry.pinned
        return None

    def delete(self, entry_id: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        if len(self._entries) != before:
            self.save()
            return True
        return False

    def clear(self, *, keep_pinned: bool = True) -> int:
        before = len(self._entries)
        if keep_pinned:
            self._entries = [e for e in self._entries if e.pinned]
        else:
            self._entries = []
        removed = before - len(self._entries)
        if removed:
            self.save()
        return removed

    def search(self, query: str = "", *, pinned_only: bool = False) -> list[HistoryEntry]:
        q = query.strip().lower()
        results: list[HistoryEntry] = []
        for entry in self._entries:
            if pinned_only and not entry.pinned:
                continue
            if q:
                haystack = (
                    f"{entry.text}\n{entry.translation}\n{entry.language}\n{entry.engine}"
                ).lower()
                if q not in haystack:
                    continue
            results.append(entry)
        return results

    def _trim(self) -> None:
        """Keep at most `max_entries` unpinned items while never evicting pinned favorites."""
        if len(self._entries) <= self.max_entries:
            return
        pinned = [e for e in self._entries if e.pinned]
        unpinned = [e for e in self._entries if not e.pinned]
        allowed_unpinned = max(0, self.max_entries - len(pinned))
        keep_ids = {e.id for e in pinned} | {e.id for e in unpinned[:allowed_unpinned]}
        self._entries = [e for e in self._entries if e.id in keep_ids]
