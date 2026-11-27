"""Searchable Snip History dialog for revisiting, pinning, and copying past OCR captures."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ocr_snip.history import HistoryEntry, HistoryStore
from ocr_snip.ui.icons import svg_icon
from ocr_snip.ui.theme import apply_sleek_theme, create_app_icon


class HistoryDialog(QDialog):
    """Searchable window showing past OCR extractions and translations."""

    def __init__(self, store: HistoryStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self._current_entry: HistoryEntry | None = None

        self._copy_reset_timer = QTimer(self)
        self._copy_reset_timer.setSingleShot(True)
        self._copy_reset_timer.timeout.connect(self._reset_copy_labels)

        self.setWindowTitle("Snip History")
        self.setWindowIcon(create_app_icon(64))
        self.resize(780, 500)

        self._build_ui()
        apply_sleek_theme(self)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_edit.setFocus)
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # --- Top search & filter bar ---
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search extracted text, translations, or languages... (Ctrl+F)")
        self.search_edit.textChanged.connect(self.refresh)
        top_bar.addWidget(self.search_edit, stretch=1)

        self.favorites_cb = QCheckBox("Favorites only")
        self.favorites_cb.toggled.connect(self.refresh)
        top_bar.addWidget(self.favorites_cb)

        self.clear_btn = QPushButton("Clear Unpinned")
        self.clear_btn.setToolTip("Remove all non-pinned items from history")
        self.clear_btn.clicked.connect(self._clear_unpinned)
        top_bar.addWidget(self.clear_btn)

        root.addLayout(top_bar)

        # --- Main splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, stretch=1)

        # Left: entries list
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.list_widget)

        # Right: detail pane
        detail_card = QFrame()
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(10, 0, 0, 0)
        detail_layout.setSpacing(8)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        self.meta_lang_pill = QLabel("No selection")
        self.meta_lang_pill.setObjectName("LangPill")
        meta_row.addWidget(self.meta_lang_pill)

        self.meta_info_pill = QLabel("")
        self.meta_info_pill.setObjectName("EnginePill")
        self.meta_info_pill.hide()
        meta_row.addWidget(self.meta_info_pill)
        meta_row.addStretch()
        detail_layout.addLayout(meta_row)

        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText(
            "No snips yet — press Ctrl+Shift+X or click the tray icon to capture text."
        )
        detail_layout.addWidget(self.detail_text, stretch=2)

        self.trans_label = QLabel("Translation")
        self.trans_label.setObjectName("MutedLabel")
        self.trans_label.hide()
        detail_layout.addWidget(self.trans_label)

        self.detail_trans = QPlainTextEdit()
        self.detail_trans.setReadOnly(True)
        self.detail_trans.setMaximumHeight(110)
        self.detail_trans.hide()
        detail_layout.addWidget(self.detail_trans, stretch=1)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.pin_btn = QPushButton(" Pin")
        self.pin_btn.setIcon(svg_icon("star", 14, "#a1a1aa"))
        self.pin_btn.setIconSize(QSize(14, 14))
        self.pin_btn.clicked.connect(self._toggle_pin_selected)
        actions_row.addWidget(self.pin_btn)

        self.delete_btn = QPushButton(" Delete")
        self.delete_btn.setIcon(svg_icon("trash", 14, "#a1a1aa"))
        self.delete_btn.setIconSize(QSize(14, 14))
        self.delete_btn.clicked.connect(self._delete_selected)
        actions_row.addWidget(self.delete_btn)

        actions_row.addStretch()

        self.copy_trans_btn = QPushButton(" Copy Translation")
        self.copy_trans_btn.setObjectName("TranslateButton")
        self.copy_trans_btn.setIcon(svg_icon("copy", 14, "#d4d4d8"))
        self.copy_trans_btn.setIconSize(QSize(14, 14))
        self.copy_trans_btn.clicked.connect(self._copy_translation)
        self.copy_trans_btn.hide()
        actions_row.addWidget(self.copy_trans_btn)

        self.copy_btn = QPushButton(" Copy Text")
        self.copy_btn.setObjectName("PrimaryButton")
        self.copy_btn.setIcon(svg_icon("copy", 14, "#09090b"))
        self.copy_btn.setIconSize(QSize(14, 14))
        self.copy_btn.clicked.connect(self._copy_text)
        actions_row.addWidget(self.copy_btn)

        detail_layout.addLayout(actions_row)
        splitter.addWidget(detail_card)
        splitter.setSizes([310, 450])

        # Bottom summary bar
        bottom = QHBoxLayout()
        self.status_label = QLabel("0 items")
        self.status_label.setObjectName("MutedLabel")
        bottom.addWidget(self.status_label)
        bottom.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)

    def refresh(self) -> None:
        selected_id = self._current_entry.id if self._current_entry else None
        items = self.store.search(
            self.search_edit.text(), pinned_only=self.favorites_cb.isChecked()
        )

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        restore_row = 0
        for idx, entry in enumerate(items):
            prefix = "Pinned · " if entry.pinned else ""
            label = f"{prefix}{entry.language}  ·  {entry.display_time}\n{entry.short_preview}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list_widget.addItem(item)
            if entry.id == selected_id:
                restore_row = idx
        self.list_widget.blockSignals(False)

        total = len(self.store.entries)
        shown = len(items)
        self.status_label.setText(
            f"Showing {shown} of {total} snips" if shown != total else f"{total} snips saved"
        )

        if items:
            self.list_widget.setCurrentRow(restore_row)
            self._show_entry(items[restore_row])
        else:
            self._show_entry(None)

    def _on_selection_changed(self, row: int) -> None:
        if row < 0:
            self._show_entry(None)
            return
        item = self.list_widget.item(row)
        entry = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._show_entry(entry)

    def _show_entry(self, entry: HistoryEntry | None) -> None:
        self._current_entry = entry
        has_entry = entry is not None
        self.pin_btn.setEnabled(has_entry)
        self.delete_btn.setEnabled(has_entry)
        self.copy_btn.setEnabled(has_entry)

        if entry is None:
            self.meta_lang_pill.setText("No snip selected")
            self.meta_info_pill.hide()
            self.detail_text.setPlainText("")
            self.trans_label.hide()
            self.detail_trans.hide()
            self.copy_trans_btn.hide()
            self.pin_btn.setIcon(svg_icon("star", 14, "#a1a1aa"))
            self.pin_btn.setText(" Pin")
            return

        self.meta_lang_pill.setText(entry.language)
        info_parts = [entry.display_time]
        if entry.engine:
            info_parts.append(entry.engine)
        if entry.confidence > 0:
            info_parts.append(f"{entry.confidence:.0%}")
        self.meta_info_pill.setText(" · ".join(info_parts))
        self.meta_info_pill.show()

        self.detail_text.setPlainText(entry.text)
        if entry.pinned:
            self.pin_btn.setIcon(svg_icon("star_filled", 14, "#f4f4f5"))
            self.pin_btn.setText(" Unpin")
        else:
            self.pin_btn.setIcon(svg_icon("star", 14, "#a1a1aa"))
            self.pin_btn.setText(" Pin")

        if entry.translation:
            lbl = (
                f"Translation ({entry.translation_lang})"
                if entry.translation_lang
                else "Translation"
            )
            self.trans_label.setText(lbl)
            self.trans_label.show()
            self.detail_trans.setPlainText(entry.translation)
            self.detail_trans.show()
            self.copy_trans_btn.show()
        else:
            self.trans_label.hide()
            self.detail_trans.hide()
            self.copy_trans_btn.hide()

    def _copy_text(self) -> None:
        if self._current_entry is None:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._current_entry.text)
        self.copy_btn.setIcon(svg_icon("check", 14, "#09090b"))
        self.copy_btn.setText(" Copied")
        self._copy_reset_timer.start(1400)

    def _copy_translation(self) -> None:
        if self._current_entry is None or not self._current_entry.translation:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._current_entry.translation)
        self.copy_trans_btn.setIcon(svg_icon("check", 14, "#4ade80"))
        self.copy_trans_btn.setText(" Copied")
        self._copy_reset_timer.start(1400)

    def _reset_copy_labels(self) -> None:
        self.copy_btn.setIcon(svg_icon("copy", 14, "#09090b"))
        self.copy_btn.setText(" Copy Text")
        self.copy_trans_btn.setIcon(svg_icon("copy", 14, "#d4d4d8"))
        self.copy_trans_btn.setText(" Copy Translation")

    def _toggle_pin_selected(self) -> None:
        if self._current_entry is None:
            return
        self.store.toggle_pin(self._current_entry.id)
        self.refresh()

    def _delete_selected(self) -> None:
        if self._current_entry is None:
            return
        self.store.delete(self._current_entry.id)
        self._current_entry = None
        self.refresh()

    def _clear_unpinned(self) -> None:
        self.store.clear(keep_pinned=True)
        self._current_entry = None
        self.refresh()
