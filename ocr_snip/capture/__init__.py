"""Cross-platform screen capture and global hotkey utilities."""

from ocr_snip.capture.hotkey import GlobalHotkeyBridge
from ocr_snip.capture.screenshot import ScreenCapture, capture_virtual_desktop

__all__ = ["GlobalHotkeyBridge", "ScreenCapture", "capture_virtual_desktop"]
