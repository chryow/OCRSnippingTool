"""Sleek floating preview, edit & 1-click translation popup for extracted OCR text."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QKeyEvent, QKeySequence, QMouseEvent, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ocr_snip.formatting import unwrap_paragraphs
from ocr_snip.ocr.base import OCRResult
from ocr_snip.ocr.local_rapidocr import SCRIPT_PROFILES
from ocr_snip.ocr.vision_ai import AI_OUTPUT_FORMATS
from ocr_snip.translate import TARGET_LANGUAGES, TranslationResult
from ocr_snip.ui.icons import svg_icon
from ocr_snip.ui.theme import SleekComboBox, apply_sleek_theme


class ResultPopup(QWidget):
    """Frameless floating card showing extracted text, detected language, and quick actions."""

    new_snip_requested = pyqtSignal()
    history_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    rescan_script_requested = pyqtSignal(str)
    enhance_ai_requested = pyqtSignal(str)      # ai_output_format: "text" | "markdown" | "latex"
    translate_requested = pyqtSignal(str, str)  # (text, target_lang_code)
    target_language_changed = pyqtSignal(str)   # target_lang_code

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self._pinned = True
        self._updating_combo = False
        self._updating_target_combo = False
        self._raw_ocr_text: str = ""
        self._prev_lang_text: str = ""
        self._prev_lang_tooltip: str = ""
        self._prev_engine_text: str = ""
        self._prev_stats_text: str = ""

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._on_auto_close)

        self._copied_reset_timer = QTimer(self)
        self._copied_reset_timer.setSingleShot(True)
        self._copied_reset_timer.timeout.connect(self._reset_copy_button)

        self._trans_copied_reset_timer = QTimer(self)
        self._trans_copied_reset_timer.setSingleShot(True)
        self._trans_copied_reset_timer.timeout.connect(self._reset_trans_copy_button)

        self._setup_window()
        self._build_ui()
        apply_sleek_theme(self)
        self._bind_shortcuts()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(636)
        self.setMaximumWidth(780)
        self.resize(644, 415)

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_current_text)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._on_translate_clicked)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_snip_requested.emit)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self.card = QFrame()
        self.card.setObjectName("PopupCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 165))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # --- 1. Draggable Header Bar ---
        self.header = QFrame()
        self.header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(14, 8, 10, 8)
        header_layout.setSpacing(6)

        self.title_label = QLabel("OCRSnippingTool")
        self.title_label.setObjectName("TitleLabel")
        header_layout.addWidget(self.title_label)

        self.copied_badge = QLabel("Copied")
        self.copied_badge.setObjectName("CopiedPill")
        self.copied_badge.hide()
        header_layout.addWidget(self.copied_badge)

        header_layout.addStretch()

        self.snip_btn = QPushButton(" Snip")
        self.snip_btn.setObjectName("IconButton")
        self.snip_btn.setIcon(svg_icon("snip", 14, "#a1a1aa"))
        self.snip_btn.setIconSize(QSize(14, 14))
        self.snip_btn.setToolTip("Capture a new region (Ctrl+N)")
        self.snip_btn.clicked.connect(self.new_snip_requested.emit)
        header_layout.addWidget(self.snip_btn)

        self.history_btn = QPushButton()
        self.history_btn.setObjectName("IconButton")
        self.history_btn.setIcon(svg_icon("history", 15, "#a1a1aa"))
        self.history_btn.setIconSize(QSize(15, 15))
        self.history_btn.setFixedSize(28, 28)
        self.history_btn.setToolTip("Snip History")
        self.history_btn.clicked.connect(self.history_requested.emit)
        header_layout.addWidget(self.history_btn)

        self.pin_btn = QPushButton()
        self.pin_btn.setObjectName("IconButton")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(True)
        self.pin_btn.setIcon(svg_icon("pin_filled", 15, "#f4f4f5"))
        self.pin_btn.setIconSize(QSize(15, 15))
        self.pin_btn.setFixedSize(28, 28)
        self.pin_btn.setToolTip("Keep floating window on top")
        self.pin_btn.toggled.connect(self._toggle_pin)
        header_layout.addWidget(self.pin_btn)

        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("IconButton")
        self.settings_btn.setIcon(svg_icon("settings", 15, "#a1a1aa"))
        self.settings_btn.setIconSize(QSize(15, 15))
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        header_layout.addWidget(self.settings_btn)

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("IconButton")
        self.close_btn.setIcon(svg_icon("close", 14, "#a1a1aa"))
        self.close_btn.setIconSize(QSize(14, 14))
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setToolTip("Close (Esc)")
        self.close_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.close_btn)

        card_layout.addWidget(self.header)

        # --- Progress Bar ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(2)
        self.progress.hide()
        card_layout.addWidget(self.progress)

        # --- 2. Main Body ---
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 12, 14, 12)
        body_layout.setSpacing(10)

        # Quiet metadata strip
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        self.lang_pill = QLabel("Detecting...")
        self.lang_pill.setObjectName("LangPill")
        meta_row.addWidget(self.lang_pill)

        self.engine_pill = QLabel("Local OCR")
        self.engine_pill.setObjectName("EnginePill")
        meta_row.addWidget(self.engine_pill)

        self.stats_pill = QLabel("")
        self.stats_pill.setObjectName("EnginePill")
        self.stats_pill.hide()
        meta_row.addWidget(self.stats_pill)

        meta_row.addStretch()

        self.unwrap_btn = QPushButton(" Unwrap")
        self.unwrap_btn.setObjectName("IconButton")
        self.unwrap_btn.setIcon(svg_icon("unwrap", 14, "#a1a1aa"))
        self.unwrap_btn.setIconSize(QSize(14, 14))
        self.unwrap_btn.setCheckable(True)
        self.unwrap_btn.setToolTip("Join hard line breaks into smooth paragraphs")
        self.unwrap_btn.toggled.connect(self._on_unwrap_toggled)
        meta_row.addWidget(self.unwrap_btn)

        body_layout.addLayout(meta_row)

        # Optional status / warning banner
        self.note_label = QLabel("")
        self.note_label.setObjectName("WarnPill")
        self.note_label.setWordWrap(True)
        self.note_label.hide()
        body_layout.addWidget(self.note_label)

        # Main editable text area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Extracted text will appear here...")
        self.text_edit.textChanged.connect(self._update_counts)
        body_layout.addWidget(self.text_edit, stretch=1)

        # Collapsible Translation Drawer (hidden until needed)
        self.translate_panel = QFrame()
        self.translate_panel.setObjectName("TranslatePanel")
        tp_layout = QVBoxLayout(self.translate_panel)
        tp_layout.setContentsMargins(10, 8, 10, 10)
        tp_layout.setSpacing(6)

        tp_header = QHBoxLayout()
        tp_header.setSpacing(6)
        self.translate_meta_label = QLabel("Translation")
        self.translate_meta_label.setObjectName("MutedLabel")
        self.translate_meta_label.setWordWrap(True)
        tp_header.addWidget(self.translate_meta_label, stretch=1)

        self.copy_trans_btn = QPushButton(" Copy")
        self.copy_trans_btn.setObjectName("IconButton")
        self.copy_trans_btn.setIcon(svg_icon("copy", 13, "#a1a1aa"))
        self.copy_trans_btn.setIconSize(QSize(13, 13))
        self.copy_trans_btn.clicked.connect(self.copy_translated_text)
        tp_header.addWidget(self.copy_trans_btn)

        self.hide_trans_btn = QPushButton()
        self.hide_trans_btn.setObjectName("IconButton")
        self.hide_trans_btn.setIcon(svg_icon("close", 13, "#a1a1aa"))
        self.hide_trans_btn.setIconSize(QSize(13, 13))
        self.hide_trans_btn.setFixedSize(24, 24)
        self.hide_trans_btn.setToolTip("Hide translation")
        self.hide_trans_btn.clicked.connect(self.translate_panel.hide)
        tp_header.addWidget(self.hide_trans_btn)
        tp_layout.addLayout(tp_header)

        self.translated_edit = QPlainTextEdit()
        self.translated_edit.setMaximumHeight(115)
        self.translated_edit.setPlaceholderText("Translated text...")
        tp_layout.addWidget(self.translated_edit)

        self.translate_panel.hide()
        body_layout.addWidget(self.translate_panel)

        # Clean Primary Action Bar: Translate | Enhance | Copy
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.target_lang_combo = SleekComboBox()
        self.target_lang_combo.setToolTip("Target language for translation")
        self.target_lang_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.target_lang_combo.setMinimumContentsLength(10)
        self.target_lang_combo.setMinimumWidth(136)
        for code, name in TARGET_LANGUAGES:
            self.target_lang_combo.addItem(name, userData=code)
        self.target_lang_combo.currentIndexChanged.connect(self._on_target_lang_changed)
        actions_row.addWidget(self.target_lang_combo, stretch=1)

        self.translate_btn = QPushButton(" Translate")
        self.translate_btn.setObjectName("TranslateButton")
        self.translate_btn.setIcon(svg_icon("translate", 14, "#d4d4d8"))
        self.translate_btn.setIconSize(QSize(14, 14))
        self.translate_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.translate_btn.setToolTip("Translate extracted text (Ctrl+T)")
        self.translate_btn.clicked.connect(self._on_translate_clicked)
        actions_row.addWidget(self.translate_btn)

        self.ai_format_combo = SleekComboBox()
        self.ai_format_combo.setToolTip("Output format when enhancing with AI")
        self.ai_format_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.ai_format_combo.setMinimumContentsLength(10)
        self.ai_format_combo.setMinimumWidth(132)
        for code, label in AI_OUTPUT_FORMATS:
            self.ai_format_combo.addItem(label, userData=code)
        actions_row.addWidget(self.ai_format_combo)

        self.ai_btn = QPushButton(" Enhance")
        self.ai_btn.setObjectName("AIButton")
        self.ai_btn.setIcon(svg_icon("enhance", 14, "#d4d4d8"))
        self.ai_btn.setIconSize(QSize(14, 14))
        self.ai_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.ai_btn.setToolTip("Re-read this snip with Vision AI in the selected format")
        self.ai_btn.clicked.connect(self._on_enhance_ai_clicked)
        actions_row.addWidget(self.ai_btn)

        self.copy_btn = QPushButton(" Copy")
        self.copy_btn.setObjectName("PrimaryButton")
        self.copy_btn.setIcon(svg_icon("copy", 14, "#09090b"))
        self.copy_btn.setIconSize(QSize(14, 14))
        self.copy_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.copy_btn.setToolTip("Copy text to clipboard (Ctrl+Shift+C)")
        self.copy_btn.clicked.connect(self.copy_current_text)
        actions_row.addWidget(self.copy_btn)

        body_layout.addLayout(actions_row)
        card_layout.addWidget(body, stretch=1)

        # --- 3. Quiet Utility Footer Strip ---
        utility = QFrame()
        utility.setObjectName("UtilityStrip")
        u_layout = QHBoxLayout(utility)
        u_layout.setContentsMargins(14, 7, 14, 7)
        u_layout.setSpacing(8)

        script_lbl = QLabel("Script")
        script_lbl.setObjectName("MutedLabel")
        u_layout.addWidget(script_lbl)

        self.script_combo = SleekComboBox()
        self.script_combo.setObjectName("CompactCombo")
        self.script_combo.setToolTip("Re-scan this snip with another offline script model")
        for key, profile in SCRIPT_PROFILES.items():
            self.script_combo.addItem(profile.label, userData=key)
        self.script_combo.currentIndexChanged.connect(self._on_script_changed)
        u_layout.addWidget(self.script_combo)

        u_layout.addStretch()

        self.count_label = QLabel("0 chars")
        self.count_label.setObjectName("MutedLabel")
        u_layout.addWidget(self.count_label)

        card_layout.addWidget(utility)

    def show_loading(
        self,
        anchor: QPoint | None = None,
        message: str = "Extracting text...",
        *,
        clear_text: bool = False,
    ) -> None:
        """Display the floating popup in a sleek loading state while OCR runs."""
        self._auto_close_timer.stop()
        if clear_text:
            self.text_edit.setPlainText("")
            self._raw_ocr_text = ""
            self._prev_lang_text = ""
            self._prev_lang_tooltip = ""
            self._prev_engine_text = ""
            self._prev_stats_text = ""
        elif self.text_edit.toPlainText().strip():
            self._prev_lang_text = self.lang_pill.text()
            self._prev_lang_tooltip = self.lang_pill.toolTip()
            self._prev_engine_text = self.engine_pill.text()
            self._prev_stats_text = self.stats_pill.text() if self.stats_pill.isVisible() else ""

        self.progress.setRange(0, 0)
        self.progress.show()
        self.copied_badge.hide()
        self.note_label.hide()
        self.translate_panel.hide()
        self.unwrap_btn.setEnabled(False)
        self.lang_pill.setText(message)
        self.lang_pill.setToolTip("")
        self.engine_pill.setText("")
        self.stats_pill.hide()
        self.text_edit.setReadOnly(True)
        self.script_combo.setEnabled(False)
        self.ai_format_combo.setEnabled(False)
        self.ai_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.translate_btn.setEnabled(False)

        if not self.isVisible():
            self._position_near(anchor)
        self.show()
        self.raise_()
        self.activateWindow()

    def show_result(
        self,
        result: OCRResult,
        *,
        auto_copied: bool = False,
        auto_close_seconds: int = 0,
        anchor: QPoint | None = None,
    ) -> None:
        """Populate the popup with an `OCRResult`."""
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.hide()
        self.text_edit.setReadOnly(False)
        self.script_combo.setEnabled(True)
        self.ai_format_combo.setEnabled(True)
        self.ai_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
        has_text = bool(result.text.strip())
        existing_text = self.text_edit.toPlainText().strip()
        preserve_existing = not result.ok and not has_text and bool(existing_text)

        self.translate_panel.hide()

        if preserve_existing:
            self.translate_btn.setEnabled(True)
            self.unwrap_btn.setEnabled(True)
            if self._prev_lang_text:
                self.lang_pill.setText(self._prev_lang_text)
                self.lang_pill.setToolTip(self._prev_lang_tooltip)
            if self._prev_engine_text:
                self.engine_pill.setText(self._prev_engine_text)
            if self._prev_stats_text:
                self.stats_pill.setText(self._prev_stats_text)
                self.stats_pill.show()
            else:
                self.stats_pill.hide()
            self.copied_badge.hide()
        else:
            self.translate_btn.setEnabled(has_text)
            self.unwrap_btn.setEnabled(has_text)
            self._raw_ocr_text = result.text
            self.unwrap_btn.blockSignals(True)
            self.unwrap_btn.setChecked(False)
            self.unwrap_btn.blockSignals(False)

            self.text_edit.setPlainText(result.text)

            if result.languages:
                self.lang_pill.setText(result.language_summary)
                tooltip_lines = [
                    f"{lang.label}"
                    + (f" [{lang.script}]" if lang.script else "")
                    + f" — {lang.confidence:.0%}"
                    for lang in result.languages
                ]
                self.lang_pill.setToolTip("Detected languages:\n" + "\n".join(tooltip_lines))
            elif has_text:
                self.lang_pill.setText("Symbols / Numeric")
                self.lang_pill.setToolTip("No natural language letters detected")
            else:
                self.lang_pill.setText("No text detected")
                self.lang_pill.setToolTip("")

            self.engine_pill.setText(result.engine_name)
            stats_parts: list[str] = []
            if result.confidence > 0:
                stats_parts.append(f"{result.confidence:.0%}")
            if result.elapsed_ms > 0:
                stats_parts.append(f"{int(round(result.elapsed_ms))} ms")
            if stats_parts:
                self.stats_pill.setText(" · ".join(stats_parts))
                self.stats_pill.show()
            else:
                self.stats_pill.hide()

            if result.script_used in SCRIPT_PROFILES:
                idx = self.script_combo.findData(result.script_used)
                if idx >= 0:
                    self._updating_combo = True
                    self.script_combo.setCurrentIndex(idx)
                    self._updating_combo = False

            if auto_copied and has_text:
                self.copied_badge.setText("Copied")
                self.copied_badge.show()
            else:
                self.copied_badge.hide()

        if result.error:
            self.note_label.setText(result.error)
            self.note_label.show()
        elif result.fallback_note:
            self.note_label.setText(result.fallback_note)
            self.note_label.show()
        elif not has_text and not preserve_existing:
            self.note_label.setText(
                "No text found. Try switching Script below or click Enhance."
            )
            self.note_label.show()
        else:
            self.note_label.hide()

        self._update_counts()

        if anchor is not None and not self.isVisible():
            self._position_near(anchor)
        self.show()
        self.raise_()
        self.activateWindow()

        if auto_close_seconds > 0 and result.ok and has_text:
            self._auto_close_timer.start(auto_close_seconds * 1000)

    def set_target_language(self, lang_code: str) -> None:
        idx = self.target_lang_combo.findData(lang_code)
        if idx >= 0:
            self._updating_target_combo = True
            self.target_lang_combo.setCurrentIndex(idx)
            self._updating_target_combo = False

    def set_ai_output_format(self, fmt: str) -> None:
        idx = self.ai_format_combo.findData(fmt)
        if idx >= 0:
            self.ai_format_combo.setCurrentIndex(idx)

    def _on_unwrap_toggled(self, checked: bool) -> None:
        if checked:
            self._raw_ocr_text = self.text_edit.toPlainText()
            self.text_edit.setPlainText(unwrap_paragraphs(self._raw_ocr_text))
        else:
            self.text_edit.setPlainText(self._raw_ocr_text)

    def _on_enhance_ai_clicked(self) -> None:
        fmt = str(self.ai_format_combo.currentData() or "text")
        self.enhance_ai_requested.emit(fmt)

    def show_translation_loading(self, target_label: str) -> None:
        self._auto_close_timer.stop()
        self.translate_btn.setEnabled(False)
        self.translate_btn.setText(" Translating...")
        self.translate_meta_label.setText(f"Translating to {target_label}...")
        self.translated_edit.setPlaceholderText("Translating...")
        self.translated_edit.setPlainText("")
        self.translated_edit.setReadOnly(True)
        self.copy_trans_btn.setEnabled(False)
        self.translate_panel.show()

    def show_translation_result(self, result: TranslationResult) -> None:
        self.translate_btn.setEnabled(bool(self.text_edit.toPlainText().strip()))
        self.translate_btn.setText(" Translate")
        self.translated_edit.setReadOnly(False)
        self.translate_panel.show()

        if result.ok:
            meta_parts = [result.target_language]
            if result.provider_name:
                meta_parts.append(result.provider_name)
            if result.elapsed_ms > 0:
                meta_parts.append(f"{int(round(result.elapsed_ms))} ms")
            self.translate_meta_label.setText(" · ".join(meta_parts))
            self.translated_edit.setPlaceholderText("Translated text...")
            self.translated_edit.setPlainText(result.translated_text)
            self.copy_trans_btn.setEnabled(bool(result.translated_text.strip()))
        else:
            self.translate_meta_label.setText(str(result.error or "Translation failed"))
            self.translated_edit.setPlaceholderText(
                "Translation failed — try again or switch provider in Settings."
            )
            self.translated_edit.setPlainText("")
            self.copy_trans_btn.setEnabled(False)

    def copy_current_text(self) -> None:
        text = self.text_edit.toPlainText()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self.copied_badge.setText("Copied")
        self.copied_badge.show()
        self.copy_btn.setIcon(svg_icon("check", 14, "#09090b"))
        self.copy_btn.setText(" Copied")
        self._copied_reset_timer.start(1500)

    def copy_translated_text(self) -> None:
        text = self.translated_edit.toPlainText()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self.copy_trans_btn.setIcon(svg_icon("check", 13, "#4ade80"))
        self.copy_trans_btn.setText(" Copied")
        self._trans_copied_reset_timer.start(1500)

    def _reset_copy_button(self) -> None:
        self.copy_btn.setIcon(svg_icon("copy", 14, "#09090b"))
        self.copy_btn.setText(" Copy")

    def _reset_trans_copy_button(self) -> None:
        self.copy_trans_btn.setIcon(svg_icon("copy", 13, "#a1a1aa"))
        self.copy_trans_btn.setText(" Copy")

    def _update_counts(self) -> None:
        text = self.text_edit.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        lines = text.count("\n") + 1 if text else 0
        self.count_label.setText(f"{chars} chars · {words} words · {lines} lines")
        if not self.text_edit.isReadOnly():
            self.translate_btn.setEnabled(bool(text.strip()))

    def _on_translate_clicked(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        target_code = str(self.target_lang_combo.currentData() or "en")
        self.translate_requested.emit(text, target_code)

    def _on_target_lang_changed(self, index: int) -> None:
        if self._updating_target_combo or index < 0:
            return
        code = self.target_lang_combo.itemData(index)
        if code:
            self.target_language_changed.emit(str(code))

    def _on_script_changed(self, index: int) -> None:
        if self._updating_combo or index < 0:
            return
        script_key = self.script_combo.itemData(index)
        if script_key:
            self.rescan_script_requested.emit(str(script_key))

    def _toggle_pin(self, checked: bool) -> None:
        self._pinned = checked
        self.pin_btn.setIcon(
            svg_icon("pin_filled" if checked else "pin", 15, "#f4f4f5" if checked else "#a1a1aa")
        )
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        if self.isVisible():
            self.show()

    def _on_auto_close(self) -> None:
        if not self.text_edit.hasFocus():
            self.hide()

    def _position_near(self, anchor: QPoint | None) -> None:
        screen = (
            QGuiApplication.screenAt(anchor) if anchor is not None else None
        ) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        if anchor is not None:
            x = anchor.x() + 18
            y = anchor.y() + 18
        else:
            x = avail.right() - self.width() - 24
            y = avail.bottom() - self.height() - 24

        x = max(avail.left() + 12, min(avail.right() - self.width() - 12, x))
        y = max(avail.top() + 12, min(avail.bottom() - self.height() - 12, y))
        self.move(x, y)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._auto_close_timer.stop()
            if event.position().y() <= 58:
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event and event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
