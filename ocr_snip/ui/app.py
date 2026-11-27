"""Main PyQt6 desktop application controller, system tray, and async OCR/translation workers."""

from __future__ import annotations

import io
import logging
import sys
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import QBuffer, QIODevice, QObject, QPoint, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices, QGuiApplication, QImage
from PyQt6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon

from ocr_snip import __app_name__, __version__
from ocr_snip.capture.hotkey import GlobalHotkeyBridge, format_hotkey_display
from ocr_snip.capture.screenshot import capture_virtual_desktop
from ocr_snip.config import AppConfig
from ocr_snip.language import language_name
from ocr_snip.logging_utils import get_logs_dir, install_crash_handler, setup_logging
from ocr_snip.ocr.base import OCRResult
from ocr_snip.ocr.manager import OCRManager
from ocr_snip.single_instance import SingleInstanceGuard
from ocr_snip.translate import TranslationResult, Translator
from ocr_snip.ui.overlay import SnipOverlay
from ocr_snip.ui.result_popup import ResultPopup
from ocr_snip.ui.settings_dialog import SettingsDialog
from ocr_snip.ui.theme import DARK_STYLESHEET, create_app_icon

logger = logging.getLogger("ocr_snip.app")


def qimage_to_pil(qimg: QImage) -> Image.Image:
    """Convert a QImage (e.g. from clipboard) to a PIL RGB Image."""
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    qimg.save(buf, "PNG")
    data = bytes(buf.data())
    return Image.open(io.BytesIO(data)).convert("RGB")


class OCRWorker(QThread):
    """Runs OCR extraction off the UI thread."""

    finished_result = pyqtSignal(object)  # OCRResult

    def __init__(
        self,
        manager: OCRManager,
        image: Image.Image,
        *,
        force_engine: str | None = None,
        script_override: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._image = image
        self._force_engine = force_engine
        self._script_override = script_override

    def run(self) -> None:
        result = self._manager.recognize(
            self._image,
            force_engine=self._force_engine,
            script_override=self._script_override,
        )
        self.finished_result.emit(result)


class TranslateWorker(QThread):
    """Runs 1-click translation off the UI thread."""

    finished_translation = pyqtSignal(object)  # TranslationResult

    def __init__(
        self,
        translator: Translator,
        text: str,
        target_lang: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._text = text
        self._target_lang = target_lang

    def run(self) -> None:
        res = self._translator.translate(self._text, target_lang=self._target_lang)
        self.finished_translation.emit(res)


class OCRSnippingApp(QObject):
    """Top-level controller coordinating tray icon, hotkey, overlay, popup, OCR, and translation."""

    def __init__(
        self,
        qt_app: QApplication,
        config: AppConfig | None = None,
        instance_guard: SingleInstanceGuard | None = None,
    ) -> None:
        super().__init__()
        self.qt_app = qt_app
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setApplicationName(__app_name__)
        self.qt_app.setApplicationVersion(__version__)
        self.qt_app.setStyleSheet(DARK_STYLESHEET)

        self.icon = create_app_icon(64)
        self.qt_app.setWindowIcon(self.icon)

        self.config = config or AppConfig.load()
        self.manager = OCRManager(self.config)
        self.translator = Translator(self.config)
        self._instance_guard = instance_guard

        self._overlay: SnipOverlay | None = None
        self._snip_pending: bool = False
        self._settings_open: bool = False
        self._worker: OCRWorker | None = None
        self._translate_worker: TranslateWorker | None = None
        self._last_image: Image.Image | None = None
        self._last_anchor: QPoint | None = None

        self.popup = ResultPopup()
        self.popup.set_target_language(self.config.translate_target_lang)
        self.popup.new_snip_requested.connect(self.start_snip)
        self.popup.settings_requested.connect(self.open_settings)
        self.popup.rescan_script_requested.connect(self.rescan_with_script)
        self.popup.enhance_ai_requested.connect(self.enhance_with_ai)
        self.popup.translate_requested.connect(self.translate_text)
        self.popup.target_language_changed.connect(self._on_popup_target_lang_changed)

        self.hotkey = GlobalHotkeyBridge(self)
        self.hotkey.triggered.connect(self.start_snip)

        if self._instance_guard is not None:
            self._instance_guard.activate_requested.connect(self._on_external_activation)

        self.tray = QSystemTrayIcon(self.icon, self)
        self._setup_tray()
        self._apply_hotkey()
        logger.info("%s v%s initialized (mode=%s)", __app_name__, __version__, self.config.engine_mode)

    def _setup_tray(self) -> None:
        self._tray_menu = QMenu()

        self.snip_action = QAction("✂ New OCR Snip", self)
        self.snip_action.triggered.connect(self.start_snip)
        self._tray_menu.addAction(self.snip_action)

        clip_action = QAction("📋 Extract from Clipboard Image", self)
        clip_action.triggered.connect(self.ocr_from_clipboard)
        self._tray_menu.addAction(clip_action)

        file_action = QAction("🖼 Extract from Image File...", self)
        file_action.triggered.connect(self.ocr_from_file)
        self._tray_menu.addAction(file_action)

        self._tray_menu.addSeparator()

        settings_action = QAction("⚙ Settings...", self)
        settings_action.triggered.connect(self.open_settings)
        self._tray_menu.addAction(settings_action)

        logs_action = QAction("📄 Open Logs Folder", self)
        logs_action.triggered.connect(self.open_logs_folder)
        self._tray_menu.addAction(logs_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit)
        self._tray_menu.addAction(quit_action)

        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.start_snip()

    def _on_external_activation(self, command: str) -> None:
        logger.info("Activated by secondary launch command: %s", command)
        self.start_snip()

    def _apply_hotkey(self) -> None:
        ok = self.hotkey.start(self.config.hotkey)
        pretty = format_hotkey_display(self.config.hotkey)
        self.snip_action.setText(f"✂ New OCR Snip  ({pretty})")
        if ok:
            self.tray.setToolTip(f"{__app_name__} — Press {pretty} or click to snip")
        else:
            logger.warning("Global hotkey %s unavailable: %s", self.config.hotkey, self.hotkey.last_error)
            self.tray.setToolTip(
                f"{__app_name__} — Click tray icon to snip (hotkey unavailable)"
            )

    def show_startup_notice(self) -> None:
        pretty = format_hotkey_display(self.config.hotkey)
        if self.tray.supportsMessages():
            self.tray.showMessage(
                __app_name__,
                f"Running in tray. Press {pretty} or click the tray icon to extract text.",
                self.icon,
                3000,
            )

    def open_logs_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_logs_dir())))

    def start_snip(self) -> None:
        """Freeze the desktop and show the fullscreen snipping selection overlay."""
        if self._overlay is not None or self._snip_pending:
            return
        self._snip_pending = True
        self.popup.hide()
        # Allow popup window to vanish cleanly before grabbing screenshot
        QTimer.singleShot(90, self._launch_overlay)

    def _launch_overlay(self) -> None:
        self._snip_pending = False
        try:
            capture = capture_virtual_desktop()
        except Exception as exc:
            logger.exception("Screen capture failed")
            QMessageBox.critical(None, __app_name__, f"Failed to capture screen:\n{exc}")
            return

        overlay = SnipOverlay(capture)
        overlay.region_captured.connect(self._on_region_captured)
        overlay.cancelled.connect(self._on_overlay_closed)
        overlay.destroyed.connect(self._on_overlay_closed)
        self._overlay = overlay
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()

    def _on_overlay_closed(self) -> None:
        self._overlay = None
        self._snip_pending = False

    def _on_region_captured(self, image: Image.Image, global_pos: QPoint) -> None:
        self._overlay = None
        self._snip_pending = False
        self._last_image = image
        self._last_anchor = global_pos
        self._run_ocr(image, anchor=global_pos)

    def ocr_from_clipboard(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return
        qimg = clipboard.image()
        if qimg.isNull():
            if self.tray.supportsMessages():
                self.tray.showMessage(
                    __app_name__,
                    "No image found in clipboard.",
                    self.icon,
                    2500,
                )
            return
        img = qimage_to_pil(qimg)
        self._last_image = img
        self._last_anchor = None
        self._run_ocr(img, anchor=None)

    def ocr_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Select Image for OCR",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff);;All Files (*)",
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
        except Exception as exc:
            logger.warning("Could not open image %s: %s", path, exc)
            QMessageBox.warning(None, __app_name__, f"Could not open image:\n{exc}")
            return
        self._last_image = img
        self._last_anchor = None
        self._run_ocr(img, anchor=None)

    def rescan_with_script(self, script_key: str) -> None:
        if self._last_image is None:
            return
        self._run_ocr(
            self._last_image,
            anchor=self._last_anchor,
            force_engine="local",
            script_override=script_key,
            loading_msg=f"Scanning ({script_key})...",
        )

    def enhance_with_ai(self) -> None:
        if self._last_image is None:
            return
        if not self.config.is_vision_ai_configured():
            self.open_settings(initial_tab=2)
            if not self.config.is_vision_ai_configured():
                return
        self._run_ocr(
            self._last_image,
            anchor=self._last_anchor,
            force_engine="vision_ai",
            loading_msg=f"Enhancing with {self.config.ai_provider.title()} AI...",
        )

    def _on_popup_target_lang_changed(self, target_code: str) -> None:
        self.config.translate_target_lang = target_code
        self.translator.update_config(self.config)
        try:
            self.config.save()
        except Exception as exc:
            logger.warning("Could not persist target language preference: %s", exc)

    def translate_text(self, text: str, target_lang: str | None = None) -> None:
        if not text.strip():
            return
        if self._translate_worker is not None and self._translate_worker.isRunning():
            return

        code = target_lang or self.config.translate_target_lang or "en"
        self.popup.show_translation_loading(language_name(code))

        worker = TranslateWorker(self.translator, text, code, parent=self)
        worker.finished_translation.connect(self._on_translation_finished)
        worker.finished.connect(worker.deleteLater)
        self._translate_worker = worker
        worker.start()

    def _on_translation_finished(self, result: TranslationResult) -> None:
        self._translate_worker = None
        if not result.ok:
            logger.warning("Translation failed: %s", result.error)
        self.popup.show_translation_result(result)

    def _run_ocr(
        self,
        image: Image.Image,
        *,
        anchor: QPoint | None,
        force_engine: str | None = None,
        script_override: str | None = None,
        loading_msg: str = "Extracting text...",
    ) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        if self.config.show_popup or force_engine is not None or script_override is not None:
            self.popup.show_loading(anchor=anchor, message=loading_msg)

        worker = OCRWorker(
            self.manager,
            image,
            force_engine=force_engine,
            script_override=script_override,
            parent=self,
        )
        worker.finished_result.connect(self._on_ocr_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_ocr_finished(self, result: OCRResult) -> None:
        self._worker = None
        auto_copied = False

        if not result.ok:
            logger.warning("OCR failed (%s): %s", result.engine_name, result.error)

        if self.config.auto_copy and result.text.strip():
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(result.text)
                auto_copied = True

        if self.config.show_popup or self.popup.isVisible():
            self.popup.show_result(
                result,
                auto_copied=auto_copied,
                auto_close_seconds=self.config.popup_auto_close_seconds,
                anchor=self._last_anchor,
            )
            if self.config.auto_translate and result.ok and result.text.strip():
                primary_code = (
                    result.primary_language.code.split("-")[0].lower()
                    if result.primary_language and result.primary_language.code
                    else ""
                )
                target_base = self.config.translate_target_lang.split("-")[0].lower()
                if not primary_code or primary_code != target_base:
                    self.translate_text(result.text, self.config.translate_target_lang)
        elif self.tray.supportsMessages():
            preview = result.text.strip().replace("\n", " ")[:110] or "No text detected"
            lang = result.language_summary
            title = f"Copied ({lang})" if auto_copied else f"OCR Result ({lang})"
            self.tray.showMessage(title, preview, self.icon, 3000)

    def open_settings(self, _checked: bool = False, *, initial_tab: int = 0) -> None:
        if self._settings_open:
            return
        self._settings_open = True
        try:
            dialog = SettingsDialog(self.config)
            if 0 <= initial_tab < dialog.tabs.count():
                dialog.tabs.setCurrentIndex(initial_tab)
            if dialog.exec():
                self.config = dialog.updated_config()
                self.config.save()
                self.manager.update_config(self.config)
                self.translator.update_config(self.config)
                self.popup.set_target_language(self.config.translate_target_lang)
                self._apply_hotkey()
        finally:
            self._settings_open = False

    def quit(self) -> None:
        logger.info("Shutting down %s", __app_name__)
        self.hotkey.stop()
        if self._instance_guard is not None:
            self._instance_guard.stop()
        self.tray.hide()
        self.qt_app.quit()


def run_gui(start_with_snip: bool = False) -> int:
    """Launch the PyQt6 desktop application with logging and single-instance guard."""
    setup_logging()
    install_crash_handler(gui=True)

    qt_app = QApplication(sys.argv)
    guard = SingleInstanceGuard()
    if guard.try_notify_existing("SNIP"):
        return 0
    guard.start_listening()

    controller = OCRSnippingApp(qt_app, instance_guard=guard)
    if start_with_snip:
        QTimer.singleShot(150, controller.start_snip)
    else:
        controller.show_startup_notice()
    return qt_app.exec()
