"""Global system hotkey listener bridged safely into PyQt6 via signals."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


def format_hotkey_display(hotkey: str) -> str:
    """Format a pynput hotkey string like '<ctrl>+<shift>+x' into 'Ctrl + Shift + X'."""
    parts = [p.strip() for p in hotkey.split("+") if p.strip()]
    pretty: list[str] = []
    mapping = {
        "<ctrl>": "Ctrl",
        "<shift>": "Shift",
        "<alt>": "Alt",
        "<cmd>": "Win/Cmd",
        "<super>": "Win/Cmd",
        "<space>": "Space",
    }
    for part in parts:
        lower = part.lower()
        if lower in mapping:
            pretty.append(mapping[lower])
        else:
            cleaned = part.strip("<>").upper()
            pretty.append(cleaned)
    return " + ".join(pretty) if pretty else "Unset"


class GlobalHotkeyBridge(QObject):
    """Runs `pynput.keyboard.GlobalHotKeys` in a background thread and emits `triggered`."""

    triggered = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listener = None
        self._current_hotkey: str = ""
        self._last_error: str = ""

    @property
    def current_hotkey(self) -> str:
        return self._current_hotkey

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def is_active(self) -> bool:
        return self._listener is not None

    def start(self, hotkey: str) -> bool:
        """Register and start listening for `hotkey` (e.g. '<ctrl>+<shift>+x')."""
        self.stop()
        hotkey = hotkey.strip()
        if not hotkey:
            self._last_error = "No hotkey configured"
            return False

        try:
            from pynput import keyboard

            def _on_activate() -> None:
                self.triggered.emit()

            listener = keyboard.GlobalHotKeys({hotkey: _on_activate})
            listener.daemon = True
            listener.start()
            self._listener = listener
            self._current_hotkey = hotkey
            self._last_error = ""
            return True
        except Exception as exc:
            self._listener = None
            self._current_hotkey = ""
            self._last_error = str(exc)
            return False

    def stop(self) -> None:
        """Stop the active global hotkey listener if running."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
