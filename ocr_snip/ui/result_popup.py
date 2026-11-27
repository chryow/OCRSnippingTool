"""Sleek floating preview & quick-edit popup for extracted OCR text."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ocr_snip.ocr.base import OCRResult
from ocr_snip.ocr.local_rapidocr import SCRIPT_PROFILES
from ocr_snip.ui.theme import DARK_STYLESHEET


class ResultPopup(QWidget):
    """Frameless floating card showing extracted text, detected language, and quick actions."""

    new_snip_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    rescan_script_requested = pyqtSignal(str)
    enhance_ai_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self._pinned = True
        self._updating_combo = False
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._on_auto_close)

        self._copied_reset_timer = QTimer(self)
        self._copied_reset_timer.setSingleShot(True)
        self._copied_reset_timer.timeout.connect(self._reset_copy_button)

        self._setup_window()
        self._build_ui()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(460)
        self.setMaximumWidth(640)
        self.resize(500, 340)
        self.setStyleSheet(DARK_STYLESHEET)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self.card = QFrame()
        self.card.setObjectName("PopupCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.card.setGraphicsEffect(shadow)
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # --- Header bar (draggable) ---
        self.header = QFrame()
        self.header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(14, 9, 10, 9)
        header_layout.setSpacing(8)

        self.title_label = QLabel("OCRSnippingTool")
        self.title_label.setObjectName("TitleLabel")
        header_layout.addWidget(self.title_label)

        self.copied_badge = QLabel("✓ Copied")
        self.copied_badge.setObjectName("CopiedPill")
        self.copied_badge.hide()
        header_layout.addWidget(self.copied_badge)

        header_layout.addStretch()

        self.snip_btn = QPushButton("✂ Snip")
        self.snip_btn.setObjectName("IconButton")
        self.snip_btn.setToolTip("Capture a new region")
        self.snip_btn.clicked.connect(self.new_snip_requested.emit)
        header_layout.addWidget(self.snip_btn)

        self.pin_btn = QPushButton("📌")
        self.pin_btn.setObjectName("IconButton")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(True)
        self.pin_btn.setToolTip("Keep popup on top")
        self.pin_btn.toggled.connect(self._toggle_pin)
        header_layout.addWidget(self.pin_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("IconButton")
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        header_layout.addWidget(self.settings_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("IconButton")
        self.close_btn.setToolTip("Close (Esc)")
        self.close_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.close_btn)

        card_layout.addWidget(self.header)

        # --- Progress bar (visible while extracting) ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        card_layout.addWidget(self.progress)

        # --- Body ---
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 12, 14, 14)
        body_layout.setSpacing(10)

        # Metadata pills row
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)

        self.lang_pill = QLabel("🌐 Detecting...")
        self.lang_pill.setObjectName("LangPill")
        meta_row.addWidget(self.lang_pill)

        self.engine_pill = QLabel("Local ML")
        self.engine_pill.setObjectName("EnginePill")
        meta_row.addWidget(self.engine_pill)

        self.stats_pill = QLabel("")
        self.stats_pill.setObjectName("EnginePill")
        self.stats_pill.hide()
        meta_row.addWidget(self.stats_pill)

        meta_row.addStretch()
        body_layout.addLayout(meta_row)

        # Optional note / error pill
        self.note_label = QLabel("")
        self.note_label.setObjectName("WarnPill")
        self.note_label.setWordWrap(True)
        self.note_label.hide()
        body_layout.addWidget(self.note_label)

        # Editable text box
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Extracted text will appear here...")
        self.text_edit.textChanged.connect(self._update_counts)
        body_layout.addWidget(self.text_edit, stretch=1)

        # Bottom controls row
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.script_combo = QComboBox()
        self.script_combo.setToolTip("Re-scan this snip with a specific offline script model")
        for key, profile in SCRIPT_PROFILES.items():
            self.script_combo.addItem(profile.label, userData=key)
        self.script_combo.currentIndexChanged.connect(self._on_script_changed)
        footer.addWidget(self.script_combo, stretch=1)

        self.ai_btn = QPushButton("✨ AI Enhance")
        self.ai_btn.setObjectName("AIButton")
        self.ai_btn.setToolTip("Re-extract using Vision AI (Gemini / OpenAI / Ollama)")
        self.ai_btn.clicked.connect(self.enhance_ai_requested.emit)
        footer.addWidget(self.ai_btn)

        self.copy_btn = QPushButton("Copy")
        self.copy_btn.setObjectName("PrimaryButton")
        self.copy_btn.clicked.connect(self.copy_current_text)
        footer.addWidget(self.copy_btn)

        body_layout.addLayout(footer)

        # Subtle counts row
        self.count_label = QLabel("0 chars")
        self.count_label.setObjectName("MutedLabel")
        body_layout.addWidget(self.count_label)

        card_layout.addWidget(body, stretch=1)

    def show_loading(self, anchor: QPoint | None = None, message: str = "Extracting text...") -> None:
        """Display the floating popup in a sleek loading state while OCR runs."""
        self._auto_close_timer.stop()
        self.progress.show()
        self.copied_badge.hide()
        self.note_label.hide()
        self.lang_pill.setText(f"🌐 {message}")
        self.lang_pill.setToolTip("")
        self.engine_pill.setText("Processing...")
        self.stats_pill.hide()
        self.text_edit.setReadOnly(True)
        self.script_combo.setEnabled(False)
        self.ai_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)

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
        self.progress.hide()
        self.text_edit.setReadOnly(False)
        self.script_combo.setEnabled(True)
        self.ai_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)

        # Set extracted text
        self.text_edit.setPlainText(result.text)

        # Detected language pill + detailed tooltip
        if result.languages:
            self.lang_pill.setText(f"🌐 {result.language_summary}")
            tooltip_lines = [
                f"• {lang.label}"
                + (f" [{lang.script}]" if lang.script else "")
                + f" — {lang.confidence:.0%}"
                for lang in result.languages
            ]
            self.lang_pill.setToolTip("Detected languages:\n" + "\n".join(tooltip_lines))
        elif result.text.strip():
            self.lang_pill.setText("🌐 Symbols / Numeric")
            self.lang_pill.setToolTip("No natural language letters detected")
        else:
            self.lang_pill.setText("🌐 No text detected")
            self.lang_pill.setToolTip("")

        # Engine & confidence/timing pills
        self.engine_pill.setText(result.engine_name)
        stats_parts: list[str] = []
        if result.confidence > 0:
            stats_parts.append(f"{result.confidence:.0%}")
        if result.elapsed_ms > 0:
            stats_parts.append(f"{int(round(result.elapsed_ms))} ms")
        if stats_parts:
            self.stats_pill.setText(" • ".join(stats_parts))
            self.stats_pill.show()
        else:
            self.stats_pill.hide()

        # Sync script selector without re-triggering signal
        if result.script_used in SCRIPT_PROFILES:
            idx = self.script_combo.findData(result.script_used)
            if idx >= 0:
                self._updating_combo = True
                self.script_combo.setCurrentIndex(idx)
                self._updating_combo = False

        # Copied badge
        if auto_copied and result.text.strip():
            self.copied_badge.setText("✓ Auto-copied")
            self.copied_badge.show()
        else:
            self.copied_badge.hide()

        # Error or fallback note
        if result.error:
            self.note_label.setText(f"⚠ {result.error}")
            self.note_label.show()
        elif result.fallback_note:
            self.note_label.setText(f"ℹ {result.fallback_note}")
            self.note_label.show()
        elif not result.text.strip():
            self.note_label.setText(
                "No text found. Try selecting a different script below or click ✨ AI Enhance."
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

        if auto_close_seconds > 0 and result.ok and result.text.strip():
            self._auto_close_timer.start(auto_close_seconds * 1000)

    def copy_current_text(self) -> None:
        text = self.text_edit.toPlainText()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        self.copied_badge.setText("✓ Copied")
        self.copied_badge.show()
        self.copy_btn.setText("✓ Copied!")
        self._copied_reset_timer.start(1600)

    def _reset_copy_button(self) -> None:
        self.copy_btn.setText("Copy")

    def _update_counts(self) -> None:
        text = self.text_edit.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        lines = text.count("\n") + 1 if text else 0
        self.count_label.setText(f"{chars} chars  •  {words} words  •  {lines} lines")

    def _on_script_changed(self, index: int) -> None:
        if self._updating_combo or index < 0:
            return
        script_key = self.script_combo.itemData(index)
        if script_key:
            self.rescan_script_requested.emit(str(script_key))

    def _toggle_pin(self, checked: bool) -> None:
        self._pinned = checked
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

    # --- Frameless dragging via header bar ---
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
