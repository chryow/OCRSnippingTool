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

    popup.set_ai_output_format("latex")
    with qtbot.waitSignal(popup.enhance_ai_requested, timeout=1000) as ai_blocker:
        popup.ai_btn.click()
    assert ai_blocker.args == ["latex"]

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


def test_app_controller_end_to_end_capture_to_clipboard_and_popup(qtbot, tmp_path) -> None:
    from PyQt6.QtWidgets import QApplication

    from ocr_snip.history import HistoryStore
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
    store = HistoryStore(path=tmp_path / "history.json")
    controller = OCRSnippingApp(qt_app, config=cfg, history_store=store)
    controller.manager._local = FastStubLocal()

    try:
        controller._on_region_captured(Image.new("RGB", (120, 40), "white"), QPoint(50, 50))
        qtbot.waitUntil(lambda: controller.popup.text_edit.toPlainText() == "こんにちは世界", timeout=3000)

        assert QGuiApplication.clipboard().text() == "こんにちは世界"
        assert "Japanese" in controller.popup.lang_pill.text()
        assert controller.popup.copied_badge.isVisible()
        assert controller.tray.contextMenu() is controller._tray_menu
        assert len(store.entries) == 1
        assert store.entries[0].text == "こんにちは世界"
    finally:
        controller.hotkey.stop()
        controller.tray.hide()
        controller.popup.hide()


def test_settings_dialog_live_ai_status(qtbot, monkeypatch, tmp_path) -> None:
    from ocr_snip.ocr.local_rapidocr import SCRIPT_PROFILES, LocalRapidOCREngine

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    (tmp_path / SCRIPT_PROFILES["korean"].model_filename).write_bytes(b"fake")
    cfg = AppConfig(ai_provider="gemini", gemini_api_key="")
    dialog = SettingsDialog(cfg, local_engine=LocalRapidOCREngine(models_dir=tmp_path))
    qtbot.addWidget(dialog)

    assert "Not configured" in dialog.ai_status_label.text()
    dialog.gemini_key_edit.setText("live-key-123")
    assert "Ready" in dialog.ai_status_label.text()

    # Language Packs tab reflects installed Korean pack
    status_lbl, _dl, rm_btn = dialog._pack_rows["korean"]
    assert "Installed" in status_lbl.text()
    assert rm_btn.isEnabled()


def test_result_popup_unwrap_and_translation_flow(qtbot) -> None:
    from ocr_snip.translate import TranslationResult

    popup = ResultPopup()
    qtbot.addWidget(popup)
    popup.show()

    popup.show_result(
        OCRResult(
            text="Line one\nline two",
            engine_name="Local ML",
            confidence=0.95,
            languages=[DetectedLanguage("en", "English")],
        )
    )
    popup.unwrap_btn.setChecked(True)
    assert popup.text_edit.toPlainText() == "Line one line two"
    popup.unwrap_btn.setChecked(False)
    assert popup.text_edit.toPlainText() == "Line one\nline two"

    popup.text_edit.setPlainText("こんにちは世界")
    popup.set_target_language("en")

    with qtbot.waitSignal(popup.translate_requested, timeout=1000) as blocker:
        popup.translate_btn.click()
    assert blocker.args == ["こんにちは世界", "en"]

    popup.show_translation_result(
        TranslationResult(
            translated_text="Hello world",
            target_language="English",
            provider_name="Free Translate",
            elapsed_ms=85.0,
        )
    )
    assert popup.translate_panel.isVisible()
    assert popup.translated_edit.toPlainText() == "Hello world"

    popup.copy_translated_text()
    assert QGuiApplication.clipboard().text() == "Hello world"


def test_history_dialog_search_pin_and_copy(qtbot, tmp_path) -> None:
    from ocr_snip.history import HistoryStore
    from ocr_snip.ui.history_dialog import HistoryDialog

    store = HistoryStore(path=tmp_path / "history.json")
    e1 = store.add(text="Alpha snippet", language="English", engine="Local ML", confidence=0.98)
    e2 = store.add(text="東京タワー", language="Japanese", engine="Local ML", confidence=0.99)
    assert e1 and e2
    store.update_translation(e2.id, "Tokyo Tower", "English")

    dlg = HistoryDialog(store)
    qtbot.addWidget(dlg)
    dlg.show()

    assert dlg.list_widget.count() == 2
    dlg.search_edit.setText("Tokyo")
    assert dlg.list_widget.count() == 1
    assert dlg.detail_trans.toPlainText() == "Tokyo Tower"

    dlg.copy_trans_btn.click()
    assert QGuiApplication.clipboard().text() == "Tokyo Tower"

    dlg.pin_btn.click()
    assert store.entries[0].pinned is True


def test_app_controller_async_translation(qtbot, tmp_path) -> None:
    from PyQt6.QtWidgets import QApplication

    from ocr_snip.history import HistoryStore
    from ocr_snip.translate import TranslationResult
    from ocr_snip.ui.app import OCRSnippingApp

    qt_app = QApplication.instance()
    assert isinstance(qt_app, QApplication)

    cfg = AppConfig(engine_mode="local", translate_target_lang="en")
    store = HistoryStore(path=tmp_path / "history.json")
    controller = OCRSnippingApp(qt_app, config=cfg, history_store=store)

    def fake_translate(text: str, target_lang: str | None = None, **kwargs):
        return TranslationResult(
            translated_text="Hello world",
            target_language="English",
            provider_name="Stub Translator",
            elapsed_ms=12.0,
        )

    controller.translator.translate = fake_translate  # type: ignore[method-assign]

    try:
        controller.popup.text_edit.setPlainText("こんにちは世界")
        controller.translate_text("こんにちは世界", "en")
        qtbot.waitUntil(
            lambda: controller.popup.translated_edit.toPlainText() == "Hello world",
            timeout=3000,
        )
        assert "Stub Translator" in controller.popup.translate_meta_label.text()
    finally:
        controller.hotkey.stop()
        controller.tray.hide()
        controller.popup.hide()


def test_result_popup_preserves_text_on_ai_error_and_resets_placeholders(qtbot) -> None:
    from ocr_snip.translate import TranslationResult

    popup = ResultPopup()
    qtbot.addWidget(popup)
    popup.show()

    popup.show_result(
        OCRResult(
            text="What does this mean?",
            engine_name="Local ML",
            confidence=0.96,
            languages=[DetectedLanguage("en", "English")],
        )
    )
    assert popup.text_edit.toPlainText() == "What does this mean?"

    # Simulate clicking ✨ AI which fails with an API error
    popup.show_loading(message="Enhancing with Gemini AI...", clear_text=False)
    assert popup.progress.maximum() == 0
    popup.show_result(
        OCRResult(
            text="",
            engine_name="Vision AI (gemini)",
            error="Gemini API HTTP 404: Model not found",
        )
    )
    assert popup.text_edit.toPlainText() == "What does this mean?"
    assert popup.translate_btn.isEnabled()
    assert "English" in popup.lang_pill.text()
    assert "404" in popup.note_label.text()
    assert popup.progress.maximum() == 1
    assert not popup.progress.isVisible()

    # Translation failure resets placeholder so it never looks stuck on "Translating..."
    popup.show_translation_loading("Indonesian")
    assert popup.translated_edit.placeholderText() == "Translating..."
    popup.show_translation_result(
        TranslationResult(
            translated_text="",
            target_language="Indonesian",
            error="Translation HTTP 429: Too Many Requests",
        )
    )
    assert "failed" in popup.translated_edit.placeholderText().lower()
    assert not popup.copy_trans_btn.isEnabled()


def test_vector_icons_and_tray_menu_styling(qtbot, tmp_path) -> None:
    from PyQt6.QtWidgets import QApplication

    from ocr_snip.history import HistoryStore
    from ocr_snip.ui.app import OCRSnippingApp
    from ocr_snip.ui.icons import svg_icon

    for name in ("snip", "history", "pin", "pin_filled", "settings", "close", "copy", "check", "translate", "enhance", "unwrap", "clipboard", "image", "timer", "folder", "quit", "star", "star_filled", "trash", "eye"):
        icon = svg_icon(name, 16)
        assert not icon.isNull()

    qt_app = QApplication.instance()
    assert isinstance(qt_app, QApplication)
    controller = OCRSnippingApp(
        qt_app,
        config=AppConfig(engine_mode="local"),
        history_store=HistoryStore(path=tmp_path / "history.json"),
    )
    try:
        assert qt_app.property("_sleek_style_installed") is True
        assert "QMenu" in controller._tray_menu.styleSheet()
        assert "QMenu" in controller._delay_menu.styleSheet()
        action_texts = [a.text() for a in controller._tray_menu.actions() if not a.isSeparator()]
        assert any("New Snip" in t for t in action_texts)
        assert any("Delayed Snip" in t for t in action_texts)
        assert any("Settings" in t for t in action_texts)
        assert any("Quit" in t for t in action_texts)
    finally:
        controller.hotkey.stop()
        controller.tray.hide()
        controller.popup.hide()


def test_overlay_drag_paint_and_capture_end_to_end(qtbot) -> None:
    """Exercise SnipOverlay paintEvent in idle and active-drag states plus full capture."""
    img = Image.new("RGB", (400, 300), "white")
    cap = ScreenCapture(image=img, left=0, top=0, width=400, height=300)
    overlay = SnipOverlay(cap)
    qtbot.addWidget(overlay)
    overlay.show()

    # 1. Paint idle crosshair state
    overlay._cursor_pos = QPoint(80, 60)
    assert not overlay.grab().isNull()

    # 2. Simulate left-button press + drag + paint (tests corner handles, selection rect, pills)
    qtbot.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(30, 30))
    overlay._current = QPoint(180, 140)
    assert not overlay.grab().isNull()

    # 3. Release mouse and verify cropped image is emitted cleanly
    with qtbot.waitSignal(overlay.region_captured, timeout=1000) as blocker:
        qtbot.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(180, 140))

    cropped_img, _global_pos = blocker.args
    assert isinstance(cropped_img, Image.Image)
    assert cropped_img.width > 10 and cropped_img.height > 10


def test_all_dialogs_paint_cleanly_without_errors(qtbot) -> None:
    """Render ResultPopup and every SettingsDialog tab via grab() to verify all paintEvent overrides."""
    popup = ResultPopup()
    qtbot.addWidget(popup)
    popup.show_result(
        OCRResult(
            text="Hello world",
            engine_name="Local OCR",
            confidence=0.98,
            languages=[DetectedLanguage("en", "English")],
        ),
        auto_copied=True,
    )
    assert not popup.grab().isNull()

    dialog = SettingsDialog(AppConfig())
    qtbot.addWidget(dialog)
    dialog.show()
    for tab_idx in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(tab_idx)
        assert not dialog.grab().isNull()


def test_result_popup_resizable_and_persists_size(qtbot) -> None:
    popup = ResultPopup()
    qtbot.addWidget(popup)
    popup.show()

    # Freely resizable above old 780px cap
    popup.resize(920, 620)
    assert popup.width() == 920
    assert popup.height() == 620

    # apply_saved_size respects minimum dimensions
    popup.apply_saved_size(200, 150)
    assert popup.width() >= popup.minimumWidth()
    assert popup.height() >= popup.minimumHeight()
    assert not popup.grab().isNull()


def test_editorial_eink_tokens_and_responsive_layout(qtbot) -> None:
    from ocr_snip.ui.theme import EDITORIAL_STYLESHEET, THEME

    assert THEME.paper == "#F7F5F0"
    assert THEME.sheet == "#FFFFFF"
    assert THEME.pressed == "#EFECE4"
    assert THEME.ink == "#1A1A18"
    assert THEME.graphite == "#6B6963"
    assert THEME.hairline == "#D8D4CA"
    assert THEME.vermilion == "#C83E2B"
    assert THEME.green == "#234E3D"
    assert "#F7F5F0" in EDITORIAL_STYLESHEET
    assert "#C83E2B" in EDITORIAL_STYLESHEET

    popup = ResultPopup()
    qtbot.addWidget(popup)
    popup.show()

    # Narrow -> stacked vertical; wide -> side-by-side horizontal
    popup.resize(720, 500)
    assert popup.panes_splitter.orientation() == Qt.Orientation.Vertical
    popup.resize(920, 500)
    assert popup.panes_splitter.orientation() == Qt.Orientation.Horizontal
    assert not popup.grab().isNull()








