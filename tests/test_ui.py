"""Headless PyQt6 UI tests for SnipOverlay, ResultPopup, and SettingsDialog."""

from __future__ import annotations

from PIL import Image
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QGuiApplication

from ocr_snip.capture.screenshot import ScreenCapture
from ocr_snip.config import AppConfig
from ocr_snip.ocr.base import DetectedLanguage, OCRResult
from ocr_snip.ui.overlay import SnipOverlay
from ocr_snip.ui.result_popup import ResultPopup
from ocr_snip.ui.settings_dialog import SettingsDialog


def test_hidpi_crop_scaling() -> None:
    # Simulate 2x HiDPI display: 1000x600 physical pixels on a 500x300 logical overlay
    img = Image.new("RGB", (1000, 600), "white")
    cap = ScreenCapture(image=img, left=0, top=0, width=500, height=300)
    cropped = cap.crop_from_overlay_rect(
        x=50, y=25, w=100, h=50, overlay_width=500, overlay_height=300
    )
    assert cropped.size == (200, 100)


def test_overlay_escape_emits_cancelled(qtbot) -> None:
    img = Image.new("RGB", (400, 300), "black")
    cap = ScreenCapture(image=img, left=0, top=0, width=400, height=300)
    overlay = SnipOverlay(cap)
    qtbot.addWidget(overlay)

    with qtbot.waitSignal(overlay.cancelled, timeout=1000):
        qtbot.keyClick(overlay, Qt.Key.Key_Escape)


def test_result_popup_displays_metadata_and_copies(qtbot) -> None:
    popup = ResultPopup()
    qtbot.addWidget(popup)

    result = OCRResult(
        text="Bonjour le monde",
        engine_name="Local ML (PP-OCRv6)",
        confidence=0.97,
        elapsed_ms=112.4,
        languages=[DetectedLanguage(code="fr", name="French", script="Latin", confidence=0.99)],
        script_used="auto",
    )
    popup.show_result(result, auto_copied=True, anchor=QPoint(100, 100))

    assert popup.text_edit.toPlainText() == "Bonjour le monde"
    assert "French" in popup.lang_pill.text()
    assert popup.copied_badge.isVisible()
    assert "97%" in popup.stats_pill.text()

    # Edit text and click Copy
    popup.text_edit.setPlainText("Edited text")
    popup.copy_current_text()
    assert QGuiApplication.clipboard().text() == "Edited text"


def test_result_popup_signals(qtbot) -> None:
    popup = ResultPopup()
    qtbot.addWidget(popup)

    with qtbot.waitSignal(popup.enhance_ai_requested, timeout=1000):
        popup.ai_btn.click()

    with qtbot.waitSignal(popup.rescan_script_requested, timeout=1000) as blocker:
        idx = popup.script_combo.findData("korean")
        popup.script_combo.setCurrentIndex(idx)
    assert blocker.args == ["korean"]


def test_settings_dialog_updates_config(qtbot) -> None:
    cfg = AppConfig(hotkey="<ctrl>+<shift>+x", engine_mode="hybrid", ai_provider="gemini")
    dialog = SettingsDialog(cfg)
    qtbot.addWidget(dialog)

    dialog.hotkey_edit.setText("<ctrl>+<alt>+s")
    dialog.auto_copy_cb.setChecked(False)
    idx_mode = dialog.mode_combo.findData("local")
    dialog.mode_combo.setCurrentIndex(idx_mode)

    updated = dialog.build_config()
    assert updated.hotkey == "<ctrl>+<alt>+s"
    assert updated.auto_copy is False
    assert updated.engine_mode == "local"


def test_app_controller_end_to_end_capture_to_clipboard_and_popup(qtbot) -> None:
    from PyQt6.QtWidgets import QApplication

    from ocr_snip.ocr.base import OCREngine
    from ocr_snip.ui.app import OCRSnippingApp

    class FastStubLocal(OCREngine):
        def recognize(self, image: Image.Image, **kwargs) -> OCRResult:
            return OCRResult(
                text="こんにちは世界",
                engine_name="Local ML (PP-OCRv6)",
                confidence=0.99,
                elapsed_ms=42.0,
                languages=[
                    DetectedLanguage(code="ja", name="Japanese", script="Japanese", confidence=0.99)
                ],
                script_used="auto",
            )

    qt_app = QApplication.instance()
    assert isinstance(qt_app, QApplication)

    cfg = AppConfig(engine_mode="local", auto_copy=True, show_popup=True)
    controller = OCRSnippingApp(qt_app, config=cfg)
    controller.manager._local = FastStubLocal()

    try:
        controller._on_region_captured(Image.new("RGB", (120, 40), "white"), QPoint(50, 50))
        qtbot.waitUntil(lambda: controller.popup.text_edit.toPlainText() == "こんにちは世界", timeout=3000)

        assert QGuiApplication.clipboard().text() == "こんにちは世界"
        assert "Japanese" in controller.popup.lang_pill.text()
        assert controller.popup.copied_badge.isVisible()
        assert controller.tray.contextMenu() is controller._tray_menu
    finally:
        controller.hotkey.stop()
        controller.tray.hide()
        controller.popup.hide()


def test_settings_dialog_live_ai_status(qtbot, monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = AppConfig(ai_provider="gemini", gemini_api_key="")
    dialog = SettingsDialog(cfg)
    qtbot.addWidget(dialog)

    assert "Not configured" in dialog.ai_status_label.text()
    dialog.gemini_key_edit.setText("live-key-123")
    assert "Ready" in dialog.ai_status_label.text()


