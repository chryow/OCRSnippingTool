"""Editorial E-Ink floating ledger window for extracted OCR text and 1-click translation."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QKeyEvent, QKeySequence, QMouseEvent, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ocr_snip.formatting import unwrap_paragraphs
from ocr_snip.ocr.base import OCRResult
from ocr_snip.ocr.local_rapidocr import SCRIPT_PROFILES
from ocr_snip.ocr.vision_ai import AI_OUTPUT_FORMATS
from ocr_snip.translate import TARGET_LANGUAGES, TranslationResult
from ocr_snip.ui.icons import svg_icon
from ocr_snip.ui.theme import (
    THEME,
    SleekComboBox,
    SleekSizeGrip,
    StatusSlip,
    apply_sleek_theme,
    make_accent_square,
)


class ResultPopup(QWidget):
    """Frameless, freely resizable Editorial E-Ink floating ledger window."""

    new_snip_requested = pyqtSignal()
    history_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    rescan_script_requested = pyqtSignal(str)
    enhance_ai_requested = pyqtSignal(str)      # ai_output_format: "text" | "markdown" | "latex"
    translate_requested = pyqtSignal(str, str)  # (text, target_lang_code)
    target_language_changed = pyqtSignal(str)   # target_lang_code
    size_changed = pyqtSignal(int, int)         # (width, height) when user finishes resizing

    _RESIZE_MARGIN = 8
    _SIDE_BY_SIDE_WIDTH = 860

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self._resize_edges: Qt.Edge = Qt.Edge(0)
        self._resize_start_pos: QPoint | None = None
        self._resize_start_geom: QRect | None = None
        self._pinned = True
        self._updating_combo = False
        self._updating_target_combo = False
        self._raw_ocr_text: str = ""
        self._detected_lang_code: str = ""
        self._hotkey_display: str = "CTRL+SHIFT+X"
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

        self._resize_save_timer = QTimer(self)
        self._resize_save_timer.setSingleShot(True)
        self._resize_save_timer.timeout.connect(
            lambda: self.size_changed.emit(self.width(), self.height())
        )

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
        self.setMouseTracking(True)
        self.setMinimumSize(680, 440)
        self.resize(740, 520)

    def apply_saved_size(self, width: int, height: int) -> None:
        """Apply persisted user window dimensions safely clamped to screen bounds."""
        screen = QGuiApplication.primaryScreen()
        max_w, max_h = 1600, 1000
        if screen is not None:
            avail = screen.availableGeometry()
            max_w = max(740, avail.width() - 48)
            max_h = max(520, avail.height() - 48)
        w = max(self.minimumWidth(), min(max_w, int(width)))
        h = max(self.minimumHeight(), min(max_h, int(height)))
        self.resize(w, h)
        self._sync_pane_orientation()

    def set_hotkey_hint(self, hotkey_display: str) -> None:
        """Update the muted monospace hotkey hint shown in the colophon bar."""
        self._hotkey_display = hotkey_display.replace(" + ", "+").upper()
        self._update_counts()

    def _bind_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_current_text)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self._on_translate_clicked)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_snip_requested.emit)

    def _build_ui(self) -> None:
        # Tight 2px outer frame (zero heavy drop shadow, crisp 1px #1A1A18 outer border)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)

        self.card = QFrame()
        self.card.setObjectName("PopupCard")
        self.card.setMouseTracking(True)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # --- 1. Minimal Editorial Title Bar (#F7F5F0 + 1px #D8D4CA rule) ---
        self.header = QFrame()
        self.header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(14, 9, 10, 9)
        header_layout.setSpacing(8)

        self.title_label = QLabel("OCRSnippingTool")
        self.title_label.setObjectName("TitleLabel")
        header_layout.addWidget(self.title_label)

        # Printed slip toast/status badge with 5x5px colored square
        self.copied_badge = StatusSlip("COPIED TO CLIPBOARD", THEME.green)
        self.copied_badge.hide()
        header_layout.addWidget(self.copied_badge)

        header_layout.addStretch()

        self.snip_btn = QPushButton(" SNIP")
        self.snip_btn.setObjectName("CaptureButton")
        self.snip_btn.setIcon(svg_icon("snip", 13, THEME.paper))
        self.snip_btn.setIconSize(QSize(13, 13))
        self.snip_btn.setToolTip("Capture a new region (Ctrl+N)")
        self.snip_btn.clicked.connect(self.new_snip_requested.emit)
        header_layout.addWidget(self.snip_btn)

        self.history_btn = QPushButton()
        self.history_btn.setObjectName("IconButton")
        self.history_btn.setIcon(svg_icon("history", 15, THEME.ink))
        self.history_btn.setIconSize(QSize(15, 15))
        self.history_btn.setFixedSize(28, 28)
        self.history_btn.setToolTip("Snip History")
        self.history_btn.clicked.connect(self.history_requested.emit)
        header_layout.addWidget(self.history_btn)

        self.pin_btn = QPushButton()
        self.pin_btn.setObjectName("IconButton")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(True)
        self.pin_btn.setIcon(svg_icon("pin_filled", 15, THEME.ink))
        self.pin_btn.setIconSize(QSize(15, 15))
        self.pin_btn.setFixedSize(28, 28)
        self.pin_btn.setToolTip("Keep floating window on top")
        self.pin_btn.toggled.connect(self._toggle_pin)
        header_layout.addWidget(self.pin_btn)

        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("IconButton")
        self.settings_btn.setIcon(svg_icon("settings", 15, THEME.ink))
        self.settings_btn.setIconSize(QSize(15, 15))
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        header_layout.addWidget(self.settings_btn)

        self.close_btn = QPushButton()
        self.close_btn.setObjectName("IconButton")
        self.close_btn.setIcon(svg_icon("close", 14, THEME.ink))
        self.close_btn.setIconSize(QSize(14, 14))
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setToolTip("Close (Esc)")
        self.close_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.close_btn)

        card_layout.addWidget(self.header)

        # --- Progress Bar (razor-thin Stamp Vermilion indicator) ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(2)
        self.progress.hide()
        card_layout.addWidget(self.progress)

        # --- 2. Editorial Language & Action Bar ---
        lang_bar = QFrame()
        lang_bar.setObjectName("LangBar")
        lb_layout = QHBoxLayout(lang_bar)
        lb_layout.setContentsMargins(14, 9, 14, 9)
        lb_layout.setSpacing(8)

        self.lang_pill = QLabel("Detecting...")
        self.lang_pill.setObjectName("LangPill")
        lb_layout.addWidget(self.lang_pill)

        self.swap_btn = QPushButton()
        self.swap_btn.setObjectName("SwapButton")
        self.swap_btn.setIcon(svg_icon("swap", 14, THEME.ink))
        self.swap_btn.setIconSize(QSize(14, 14))
        self.swap_btn.setFixedSize(30, 30)
        self.swap_btn.setToolTip("Swap source and target languages")
        self.swap_btn.clicked.connect(self._on_swap_languages)
        lb_layout.addWidget(self.swap_btn)

        self.target_lang_combo = SleekComboBox()
        self.target_lang_combo.setToolTip("Target language for translation")
        self.target_lang_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.target_lang_combo.setMinimumContentsLength(10)
        self.target_lang_combo.setMinimumWidth(140)
        for code, name in TARGET_LANGUAGES:
            self.target_lang_combo.addItem(name, userData=code)
        self.target_lang_combo.currentIndexChanged.connect(self._on_target_lang_changed)
        lb_layout.addWidget(self.target_lang_combo, stretch=1)

        self.translate_btn = QPushButton("TRANSLATE")
        self.translate_btn.setObjectName("TranslateButton")
        self.translate_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.translate_btn.setToolTip("Translate extracted text (Ctrl+T)")
        self.translate_btn.clicked.connect(self._on_translate_clicked)
        lb_layout.addWidget(self.translate_btn)

        self.ai_format_combo = SleekComboBox()
        self.ai_format_combo.setToolTip("Output format when enhancing with Vision AI")
        self.ai_format_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.ai_format_combo.setMinimumContentsLength(9)
        self.ai_format_combo.setMinimumWidth(132)
        for code, label in AI_OUTPUT_FORMATS:
            self.ai_format_combo.addItem(label, userData=code)
        lb_layout.addWidget(self.ai_format_combo)

        self.ai_btn = QPushButton("ENHANCE")
        self.ai_btn.setObjectName("AIButton")
        self.ai_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.ai_btn.setToolTip("Re-read this snip with Vision AI in the selected format")
        self.ai_btn.clicked.connect(self._on_enhance_ai_clicked)
        lb_layout.addWidget(self.ai_btn)

        card_layout.addWidget(lang_bar)

        # --- 3. Main Ledger Body (Printed Warning Slip + Source/Translated Sheets) ---
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 12, 14, 12)
        body_layout.setSpacing(10)

        # Optional printed warning / status slip
        self.note_label = QLabel("")
        self.note_label.setObjectName("WarnPill")
        self.note_label.setWordWrap(True)
        self.note_label.hide()
        body_layout.addWidget(self.note_label)

        # Responsive Splitter: stacked when narrow, side-by-side when wide
        self.panes_splitter = QSplitter(Qt.Orientation.Vertical)
        self.panes_splitter.setChildrenCollapsible(False)

        # --- Source Text Sheet ---
        self.source_pane = QFrame()
        self.source_pane.setObjectName("SheetPane")
        sp_layout = QVBoxLayout(self.source_pane)
        sp_layout.setContentsMargins(0, 0, 0, 0)
        sp_layout.setSpacing(0)

        sp_header = QFrame()
        sp_header.setObjectName("PaneHeader")
        sp_header.setMinimumHeight(34)
        sph_layout = QHBoxLayout(sp_header)
        sph_layout.setContentsMargins(12, 5, 8, 5)
        sph_layout.setSpacing(8)

        src_title = QLabel("EXTRACTED")
        src_title.setObjectName("MonoLabel")
        sph_layout.addWidget(src_title)

        self.engine_pill = QLabel("Local OCR")
        self.engine_pill.setObjectName("EnginePill")
        sph_layout.addWidget(self.engine_pill)

        self.stats_pill = QLabel("")
        self.stats_pill.setObjectName("EnginePill")
        self.stats_pill.hide()
        sph_layout.addWidget(self.stats_pill)

        sph_layout.addStretch()

        self.unwrap_btn = QPushButton("UNWRAP")
        self.unwrap_btn.setObjectName("IconButton")
        self.unwrap_btn.setCheckable(True)
        self.unwrap_btn.setToolTip("Join hard line breaks into smooth paragraphs")
        self.unwrap_btn.toggled.connect(self._on_unwrap_toggled)
        sph_layout.addWidget(self.unwrap_btn)

        self.copy_btn = QPushButton("[ COPY ]")
        self.copy_btn.setObjectName("PaneCopyButton")
        self.copy_btn.setToolTip("Copy extracted text to clipboard (Ctrl+Shift+C)")
        self.copy_btn.clicked.connect(self.copy_current_text)
        sph_layout.addWidget(self.copy_btn)

        sp_layout.addWidget(sp_header)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("SheetEdit")
        self.text_edit.setPlaceholderText("Extracted text will appear here...")
        self.text_edit.textChanged.connect(self._update_counts)
        sp_layout.addWidget(self.text_edit, stretch=1)

        self.panes_splitter.addWidget(self.source_pane)

        # --- Translated Text Sheet (hidden until requested) ---
        self.translate_panel = QFrame()
        self.translate_panel.setObjectName("TranslatePanel")
        tp_layout = QVBoxLayout(self.translate_panel)
        tp_layout.setContentsMargins(0, 0, 0, 0)
        tp_layout.setSpacing(0)

        tp_header = QFrame()
        tp_header.setObjectName("PaneHeader")
        tp_header.setMinimumHeight(34)
        tph_layout = QHBoxLayout(tp_header)
        tph_layout.setContentsMargins(12, 5, 8, 5)
        tph_layout.setSpacing(8)

        trans_title = QLabel("TRANSLATED")
        trans_title.setObjectName("MonoLabel")
        tph_layout.addWidget(trans_title)

        self.translate_meta_label = QLabel("")
        self.translate_meta_label.setObjectName("MonoMuted")
        self.translate_meta_label.setWordWrap(False)
        tph_layout.addWidget(self.translate_meta_label, stretch=1)

        self.copy_trans_btn = QPushButton("[ COPY ]")
        self.copy_trans_btn.setObjectName("PaneCopyButton")
        self.copy_trans_btn.clicked.connect(self.copy_translated_text)
        tph_layout.addWidget(self.copy_trans_btn)

        self.hide_trans_btn = QPushButton()
        self.hide_trans_btn.setObjectName("IconButton")
        self.hide_trans_btn.setIcon(svg_icon("close", 13, THEME.ink))
        self.hide_trans_btn.setIconSize(QSize(13, 13))
        self.hide_trans_btn.setFixedSize(24, 24)
        self.hide_trans_btn.setToolTip("Hide translation")
        self.hide_trans_btn.clicked.connect(self.translate_panel.hide)
        tph_layout.addWidget(self.hide_trans_btn)

        tp_layout.addWidget(tp_header)

        self.translated_edit = QPlainTextEdit()
        self.translated_edit.setObjectName("SheetEdit")
        self.translated_edit.setMinimumHeight(100)
        self.translated_edit.setPlaceholderText("Translated text...")
        tp_layout.addWidget(self.translated_edit, stretch=1)

        self.translate_panel.hide()
        self.panes_splitter.addWidget(self.translate_panel)
        self.panes_splitter.setStretchFactor(0, 1)
        self.panes_splitter.setStretchFactor(1, 1)

        body_layout.addWidget(self.panes_splitter, stretch=1)
        card_layout.addWidget(body, stretch=1)

        # --- 4. Editorial Colophon Footer Strip (1px #D8D4CA top rule) ---
        utility = QFrame()
        utility.setObjectName("ColophonBar")
        u_layout = QHBoxLayout(utility)
        u_layout.setContentsMargins(14, 7, 8, 7)
        u_layout.setSpacing(8)

        script_lbl = QLabel("SCRIPT")
        script_lbl.setObjectName("MonoMuted")
        u_layout.addWidget(script_lbl)

        self.script_combo = SleekComboBox()
        self.script_combo.setObjectName("CompactCombo")
        self.script_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.script_combo.setMinimumContentsLength(12)
        self.script_combo.setMaximumWidth(210)
        self.script_combo.setToolTip("Re-scan this snip with another offline script model")
        for key, profile in SCRIPT_PROFILES.items():
            self.script_combo.addItem(profile.label, userData=key)
        self.script_combo.currentIndexChanged.connect(self._on_script_changed)
        u_layout.addWidget(self.script_combo)

        self.count_label = QLabel("0 CHARS")
        self.count_label.setObjectName("MonoMuted")
        u_layout.addWidget(self.count_label)

        u_layout.addStretch()

        colophon_lbl = QLabel(THEME.colophon_credit)
        colophon_lbl.setObjectName("MonoMuted")
        u_layout.addWidget(colophon_lbl)

        u_layout.addWidget(make_accent_square(THEME.vermilion, 5))

        self.size_grip = SleekSizeGrip(self)
        self.size_grip.setToolTip("Drag corner or any window edge to resize")
        u_layout.addWidget(
            self.size_grip,
            alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
        )

        card_layout.addWidget(utility)

    def _sync_pane_orientation(self) -> None:
        if not hasattr(self, "panes_splitter"):
            return
        desired = (
            Qt.Orientation.Horizontal
            if self.width() >= self._SIDE_BY_SIDE_WIDTH
            else Qt.Orientation.Vertical
        )
        if self.panes_splitter.orientation() != desired:
            self.panes_splitter.setOrientation(desired)

    def show_loading(
        self,
        anchor: QPoint | None = None,
        message: str = "Extracting text...",
        *,
        clear_text: bool = False,
    ) -> None:
        """Display the floating ledger in a calm printed processing state."""
        self._auto_close_timer.stop()
        if clear_text:
            self.text_edit.setPlainText("")
            self._raw_ocr_text = ""
            self._detected_lang_code = ""
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
        self.copied_badge.set_status("EXTRACTING...", THEME.vermilion)
        self.copied_badge.show()
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
        self.swap_btn.setEnabled(False)

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
        """Populate the ledger with an `OCRResult`."""
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.hide()
        self.text_edit.setReadOnly(False)
        self.script_combo.setEnabled(True)
        self.ai_format_combo.setEnabled(True)
        self.ai_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
        self.swap_btn.setEnabled(True)
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
                self._detected_lang_code = result.languages[0].code
                self.lang_pill.setText(f"AUTO · {result.language_summary}")
                tooltip_lines = [
                    f"{lang.label}"
                    + (f" [{lang.script}]" if lang.script else "")
                    + f" — {lang.confidence:.0%}"
                    for lang in result.languages
                ]
                self.lang_pill.setToolTip("Detected languages:\n" + "\n".join(tooltip_lines))
            elif has_text:
                self._detected_lang_code = ""
                self.lang_pill.setText("AUTO · Symbols")
                self.lang_pill.setToolTip("No natural language letters detected")
            else:
                self._detected_lang_code = ""
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
                self.copied_badge.set_status("COPIED TO CLIPBOARD", THEME.green)
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
                "No text found. Try switching Script below or click ENHANCE."
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

    def _on_swap_languages(self) -> None:
        """Swap target language to the detected source language (and swap panes if translated)."""
        current_target = str(self.target_lang_combo.currentData() or "en")
        src_code = self._detected_lang_code.strip()
        if src_code.lower() == "zh-cn":
            src_code = "zh-CN"
        elif src_code.lower() == "zh-tw":
            src_code = "zh-TW"

        new_target = ""
        if src_code and src_code.lower() != current_target.lower():
            if self.target_lang_combo.findData(src_code) >= 0:
                new_target = src_code
        if not new_target:
            new_target = "en" if current_target.lower() != "en" else "id"

        idx = self.target_lang_combo.findData(new_target)
        if idx >= 0:
            self.target_lang_combo.setCurrentIndex(idx)

        # If a translation is visible, move translated text to source and re-translate back
        if self.translate_panel.isVisible() and self.translated_edit.toPlainText().strip():
            swapped_text = self.translated_edit.toPlainText().strip()
            self.text_edit.setPlainText(swapped_text)
            self._detected_lang_code = current_target
            self.translate_requested.emit(swapped_text, new_target)

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
        self.translate_btn.setText("TRANSLATING...")
        self.translate_meta_label.setText(f"Translating to {target_label}...")
        self.translated_edit.setPlaceholderText("Translating...")
        self.translated_edit.setPlainText("")
        self.translated_edit.setReadOnly(True)
        self.copy_trans_btn.setEnabled(False)
        self.translate_panel.show()

    def show_translation_result(self, result: TranslationResult) -> None:
        self.translate_btn.setEnabled(bool(self.text_edit.toPlainText().strip()))
        self.translate_btn.setText("TRANSLATE")
        self.translated_edit.setReadOnly(False)
        self.translate_panel.show()

        if result.ok:
            self.translate_meta_label.setWordWrap(False)
            meta_parts = [result.target_language]
            if result.provider_name:
                meta_parts.append(result.provider_name)
            self.translate_meta_label.setText(" · ".join(meta_parts))
            self.translate_meta_label.setToolTip(
                f"{result.target_language} · {result.provider_name} · {int(round(result.elapsed_ms))} ms"
                if result.elapsed_ms > 0
                else " · ".join(meta_parts)
            )
            self.translated_edit.setPlaceholderText("Translated text...")
            self.translated_edit.setPlainText(result.translated_text)
            self.copy_trans_btn.setEnabled(bool(result.translated_text.strip()))
        else:
            self.translate_meta_label.setWordWrap(True)
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
        self.copied_badge.set_status("COPIED TO CLIPBOARD", THEME.green)
        self.copied_badge.show()
        self.copy_btn.setText("[ COPIED ]")
        self._copied_reset_timer.start(1500)

    def copy_translated_text(self) -> None:
        text = self.translated_edit.toPlainText()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self.copied_badge.set_status("COPIED TO CLIPBOARD", THEME.green)
        self.copied_badge.show()
        self.copy_trans_btn.setText("[ COPIED ]")
        self._trans_copied_reset_timer.start(1500)

    def _reset_copy_button(self) -> None:
        self.copy_btn.setText("[ COPY ]")

    def _reset_trans_copy_button(self) -> None:
        self.copy_trans_btn.setText("[ COPY ]")

    def _update_counts(self) -> None:
        text = self.text_edit.toPlainText()
        chars = len(text)
        self.count_label.setText(f"{self._hotkey_display} · {chars} CHARS")
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
        self.pin_btn.setIcon(svg_icon("pin_filled" if checked else "pin", 15, THEME.ink))
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

    def _hit_test_edges(self, pos: QPoint) -> Qt.Edge:
        """Detect if `pos` lies on the outer resize border of the floating ledger."""
        card_rect = self.card.geometry()
        m = self._RESIZE_MARGIN
        edges = Qt.Edge(0)
        if abs(pos.x() - card_rect.left()) <= m:
            edges |= Qt.Edge.LeftEdge
        elif abs(pos.x() - card_rect.right()) <= m:
            edges |= Qt.Edge.RightEdge
        if abs(pos.y() - card_rect.top()) <= m:
            edges |= Qt.Edge.TopEdge
        elif abs(pos.y() - card_rect.bottom()) <= m:
            edges |= Qt.Edge.BottomEdge
        return edges

    def _update_resize_cursor(self, edges: Qt.Edge) -> None:
        left_or_right = bool(edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge))
        top_or_bottom = bool(edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge))
        if (edges & Qt.Edge.LeftEdge and edges & Qt.Edge.TopEdge) or (
            edges & Qt.Edge.RightEdge and edges & Qt.Edge.BottomEdge
        ):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif (edges & Qt.Edge.RightEdge and edges & Qt.Edge.TopEdge) or (
            edges & Qt.Edge.LeftEdge and edges & Qt.Edge.BottomEdge
        ):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif left_or_right:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif top_or_bottom:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._auto_close_timer.stop()
            pos = event.position().toPoint()
            edges = self._hit_test_edges(pos)
            if edges != Qt.Edge(0):
                self._resize_edges = edges
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geom = self.geometry()
                return
            if pos.y() <= self.card.geometry().top() + 50:
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is not None:
            if (
                self._resize_edges != Qt.Edge(0)
                and self._resize_start_pos is not None
                and self._resize_start_geom is not None
            ):
                delta = event.globalPosition().toPoint() - self._resize_start_pos
                geom = QRect(self._resize_start_geom)
                min_w, min_h = self.minimumWidth(), self.minimumHeight()
                if self._resize_edges & Qt.Edge.RightEdge:
                    geom.setRight(max(geom.left() + min_w - 1, geom.right() + delta.x()))
                if self._resize_edges & Qt.Edge.BottomEdge:
                    geom.setBottom(max(geom.top() + min_h - 1, geom.bottom() + delta.y()))
                if self._resize_edges & Qt.Edge.LeftEdge:
                    new_left = min(geom.right() - min_w + 1, geom.left() + delta.x())
                    geom.setLeft(new_left)
                if self._resize_edges & Qt.Edge.TopEdge:
                    new_top = min(geom.bottom() - min_h + 1, geom.top() + delta.y())
                    geom.setTop(new_top)
                self.setGeometry(geom)
                return
            if self._drag_offset is not None:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                return
            self._update_resize_cursor(self._hit_test_edges(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if self._resize_edges != Qt.Edge(0):
            self._resize_edges = Qt.Edge(0)
            self._resize_start_pos = None
            self._resize_start_geom = None
            self.size_changed.emit(self.width(), self.height())
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_pane_orientation()
        if self.isVisible():
            self._resize_save_timer.start(400)

    def hideEvent(self, event) -> None:
        self._resize_save_timer.stop()
        super().hideEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event and event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
