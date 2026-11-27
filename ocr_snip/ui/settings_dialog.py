"""Modern Settings dialog for OCR engine, Language Packs, translation, hotkey, and Vision AI."""

from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import QSize, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ocr_snip import __version__
from ocr_snip.capture.hotkey import format_hotkey_display
from ocr_snip.config import DEFAULT_GEMINI_MODEL, RECOMMENDED_GEMINI_MODELS, AppConfig
from ocr_snip.logging_utils import get_logs_dir
from ocr_snip.ocr.local_rapidocr import (
    SCRIPT_PROFILES,
    LocalRapidOCREngine,
    is_script_installed,
)
from ocr_snip.ocr.vision_ai import AI_OUTPUT_FORMATS
from ocr_snip.translate import TARGET_LANGUAGES
from ocr_snip.ui.icons import svg_icon
from ocr_snip.ui.theme import (
    THEME,
    SleekCheckBox,
    SleekComboBox,
    SleekDoubleSpinBox,
    SleekSpinBox,
    apply_sleek_theme,
    create_app_icon,
    create_colophon_bar,
)


class PackDownloadWorker(QThread):
    """Downloads an offline RapidOCR ONNX language pack without blocking the UI."""

    finished_download = pyqtSignal(str, bool, str)  # (script_key, ok, message)

    def __init__(self, engine: LocalRapidOCREngine, script_key: str, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._script_key = script_key

    def run(self) -> None:
        try:
            self._engine.download_script_pack(self._script_key)
            self.finished_download.emit(self._script_key, True, "Installed")
        except Exception as exc:
            self.finished_download.emit(self._script_key, False, str(exc))


class SettingsDialog(QDialog):
    """Configuration dialog for OCRSnippingTool."""

    def __init__(
        self,
        config: AppConfig,
        local_engine: LocalRapidOCREngine | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = replace(config)
        self._local_engine = local_engine or LocalRapidOCREngine()
        self._pack_worker: PackDownloadWorker | None = None
        self._pack_rows: dict[str, tuple[QLabel, QPushButton, QPushButton]] = {}

        self.setWindowTitle("Settings")
        self.setWindowIcon(create_app_icon(64))
        self.setMinimumSize(680, 540)
        self.resize(740, 600)
        self._build_ui()
        apply_sleek_theme(self)
        self._load_from_config()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self._build_general_tab()
        self._build_ocr_tab()
        self._build_language_packs_tab()
        self._build_vision_ai_tab()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("SAVE SETTINGS")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)
        outer.addWidget(content, stretch=1)

        colophon, _ = create_colophon_bar(
            left_text=f"OCRSNIPPINGTOOL V{__version__}",
            parent=self,
        )
        outer.addWidget(colophon)

    def _build_general_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        hk_group = QGroupBox("Global Snip Hotkey")
        hk_layout = QVBoxLayout(hk_group)

        hk_form = QFormLayout()
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setPlaceholderText("<ctrl>+<shift>+x")
        self.hotkey_edit.textChanged.connect(self._update_hotkey_preview)
        hk_form.addRow("Shortcut:", self.hotkey_edit)

        self.hotkey_preview = QLabel("")
        self.hotkey_preview.setObjectName("MutedLabel")
        hk_form.addRow("Display:", self.hotkey_preview)
        hk_layout.addLayout(hk_form)

        presets_row = QHBoxLayout()
        presets_label = QLabel("Quick presets:")
        presets_label.setObjectName("MutedLabel")
        presets_row.addWidget(presets_label)
        for label, combo in (
            ("Ctrl+Shift+X", "<ctrl>+<shift>+x"),
            ("Ctrl+Alt+S", "<ctrl>+<alt>+s"),
            ("Alt+Shift+O", "<alt>+<shift>+o"),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked=False, c=combo: self.hotkey_edit.setText(c))
            presets_row.addWidget(btn)
        presets_row.addStretch()
        hk_layout.addLayout(presets_row)
        layout.addWidget(hk_group)

        wf_group = QGroupBox("After Snipping")
        wf_layout = QVBoxLayout(wf_group)

        self.auto_copy_cb = SleekCheckBox("Automatically copy extracted text to clipboard")
        wf_layout.addWidget(self.auto_copy_cb)

        self.show_popup_cb = SleekCheckBox("Show floating preview and edit popup after snip")
        wf_layout.addWidget(self.show_popup_cb)

        self.preserve_breaks_cb = SleekCheckBox("Keep original multi-line breaks in extracted text")
        wf_layout.addWidget(self.preserve_breaks_cb)

        timer_form = QFormLayout()
        self.auto_close_spin = SleekSpinBox()
        self.auto_close_spin.setRange(0, 120)
        self.auto_close_spin.setSuffix(" s  (0 = stay open)")
        timer_form.addRow("Auto-close popup:", self.auto_close_spin)
        wf_layout.addLayout(timer_form)

        layout.addWidget(wf_group)

        diag_row = QHBoxLayout()
        logs_btn = QPushButton(" Open Logs Folder")
        logs_btn.setIcon(svg_icon("folder", 14, THEME.ink))
        logs_btn.setIconSize(QSize(14, 14))
        logs_btn.setToolTip("Open diagnostic log directory")
        logs_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_logs_dir())))
        )
        diag_row.addWidget(logs_btn)
        diag_row.addStretch()
        layout.addLayout(diag_row)

        layout.addStretch()
        self.tabs.addTab(tab, "GENERAL")

    def _build_ocr_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        mode_group = QGroupBox("OCR Engine")
        form = QFormLayout(mode_group)

        self.mode_combo = SleekComboBox()
        self.mode_combo.addItem("Hybrid — Offline OCR + AI fallback", "hybrid")
        self.mode_combo.addItem("Offline Only — 100% local OCR", "local")
        self.mode_combo.addItem("Vision AI Only — Cloud or Ollama", "vision_ai")
        form.addRow("Mode:", self.mode_combo)

        self.script_combo = SleekComboBox()
        for key, profile in SCRIPT_PROFILES.items():
            self.script_combo.addItem(profile.label, key)
        form.addRow("Default offline script:", self.script_combo)

        self.auto_probe_cb = SleekCheckBox(
            "Automatically test installed Language Packs on low confidence"
        )
        form.addRow(self.auto_probe_cb)

        self.threshold_spin = SleekDoubleSpinBox()
        self.threshold_spin.setRange(0.10, 0.99)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setDecimals(2)
        self.threshold_spin.setToolTip(
            "In Hybrid mode, if offline confidence drops below this threshold "
            "and Vision AI is configured, automatically refine with Vision AI."
        )
        form.addRow("AI fallback threshold:", self.threshold_spin)

        self.ai_format_combo = SleekComboBox()
        for code, label in AI_OUTPUT_FORMATS:
            self.ai_format_combo.addItem(label, code)
        form.addRow("Default Vision AI format:", self.ai_format_combo)

        layout.addWidget(mode_group)

        trans_group = QGroupBox("Translation")
        t_form = QFormLayout(trans_group)

        self.translate_lang_combo = SleekComboBox()
        for code, name in TARGET_LANGUAGES:
            self.translate_lang_combo.addItem(name, code)
        t_form.addRow("Default target language:", self.translate_lang_combo)

        self.translate_provider_combo = SleekComboBox()
        self.translate_provider_combo.addItem("Auto (AI if configured, else Free Web)", "auto")
        self.translate_provider_combo.addItem("Free Web Translate (no API key)", "google_free")
        self.translate_provider_combo.addItem("Configured AI Provider only", "ai")
        t_form.addRow("Translation backend:", self.translate_provider_combo)

        self.auto_translate_cb = SleekCheckBox(
            "Automatically translate when detected language differs from target"
        )
        t_form.addRow(self.auto_translate_cb)

        layout.addWidget(trans_group)
        layout.addStretch()
        self.tabs.addTab(tab, "OCR && TRANSLATE")

    def _build_language_packs_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        intro = QLabel(
            "Download extra offline ONNX language packs below. Once installed, "
            "'Auto' mode automatically probes them whenever you snip Korean, Russian, "
            "Arabic, Hindi, Thai, or other scripts — 100% offline."
        )
        intro.setObjectName("MutedLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.pack_status_banner = QLabel("")
        self.pack_status_banner.setObjectName("MutedLabel")
        layout.addWidget(self.pack_status_banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setStyleSheet("background-color: transparent;")
        scroll_body = QWidget()
        scroll_body.setObjectName("ScrollBody")
        scroll_layout = QVBoxLayout(scroll_body)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        scroll_layout.setSpacing(8)

        for key, profile in SCRIPT_PROFILES.items():
            row_frame = QFrame()
            row_frame.setObjectName("PackCard")
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(14, 10, 14, 10)
            row_layout.setSpacing(10)

            info_col = QVBoxLayout()
            info_col.setSpacing(3)
            name_lbl = QLabel(profile.label)
            name_lbl.setObjectName("PackTitle")
            desc_lbl = QLabel(profile.description)
            desc_lbl.setObjectName("PackDesc")
            desc_lbl.setWordWrap(True)
            info_col.addWidget(name_lbl)
            info_col.addWidget(desc_lbl)
            row_layout.addLayout(info_col, stretch=1)

            status_lbl = QLabel("")
            status_lbl.setMinimumWidth(68)
            status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(status_lbl)

            dl_btn = QPushButton("Download")
            dl_btn.setMinimumWidth(92)
            dl_btn.clicked.connect(lambda _checked=False, k=key: self._download_pack(k))
            row_layout.addWidget(dl_btn)

            rm_btn = QPushButton("Remove")
            rm_btn.setMinimumWidth(78)
            rm_btn.clicked.connect(lambda _checked=False, k=key: self._remove_pack(k))
            if key == "auto":
                rm_btn.setVisible(False)
            row_layout.addWidget(rm_btn)

            self._pack_rows[key] = (status_lbl, dl_btn, rm_btn)
            scroll_layout.addWidget(row_frame)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_body)
        layout.addWidget(scroll, stretch=1)

        self.tabs.addTab(tab, "LANGUAGE PACKS")
        self.refresh_language_packs()

    def refresh_language_packs(self) -> None:
        models_dir = self._local_engine.models_dir
        installed_count = 0
        for key, (status_lbl, dl_btn, rm_btn) in self._pack_rows.items():
            installed = is_script_installed(key, models_dir=models_dir)
            if installed:
                installed_count += 1
                status_lbl.setText("Installed")
                status_lbl.setObjectName("PackStatusInstalled")
                dl_btn.setText("Installed")
                dl_btn.setEnabled(False)
                rm_btn.setEnabled(key != "auto")
            else:
                status_lbl.setText("Available")
                status_lbl.setObjectName("PackStatusAvailable")
                dl_btn.setText("Download")
                dl_btn.setEnabled(self._pack_worker is None)
                rm_btn.setEnabled(False)
            status_lbl.style().unpolish(status_lbl)
            status_lbl.style().polish(status_lbl)
        self.pack_status_banner.setText(
            f"{installed_count} of {len(SCRIPT_PROFILES)} offline packs installed"
        )

    def _download_pack(self, script_key: str) -> None:
        if self._pack_worker is not None and self._pack_worker.isRunning():
            return
        status_lbl, dl_btn, _rm_btn = self._pack_rows[script_key]
        status_lbl.setText("Downloading...")
        dl_btn.setText("Downloading...")
        for _s, b_dl, _b_rm in self._pack_rows.values():
            b_dl.setEnabled(False)

        worker = PackDownloadWorker(self._local_engine, script_key, parent=self)
        worker.finished_download.connect(self._on_pack_download_finished)
        worker.finished.connect(worker.deleteLater)
        self._pack_worker = worker
        worker.start()

    def _on_pack_download_finished(self, script_key: str, ok: bool, message: str) -> None:
        self._pack_worker = None
        self.refresh_language_packs()
        if not ok:
            self.pack_status_banner.setText(f"Failed to download {script_key}: {message}")

    def _remove_pack(self, script_key: str) -> None:
        self._local_engine.remove_script_pack(script_key)
        self.refresh_language_packs()

    def _build_vision_ai_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        intro = QLabel(
            "Optional: connect an AI model for handwriting, complex tables (Markdown), "
            "math equations (LaTeX), or rare scripts. Offline OCR works with zero keys."
        )
        intro.setObjectName("MutedLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        provider_group = QGroupBox("Provider")
        form = QFormLayout(provider_group)

        self.provider_combo = SleekComboBox()
        self.provider_combo.addItem("Google Gemini", "gemini")
        self.provider_combo.addItem("OpenAI / Compatible API", "openai")
        self.provider_combo.addItem("Ollama (Local)", "ollama")
        self.provider_combo.currentIndexChanged.connect(self._update_provider_fields)
        form.addRow("Active provider:", self.provider_combo)

        self.ai_status_label = QLabel("")
        self.ai_status_label.setObjectName("MutedLabel")
        form.addRow("Status:", self.ai_status_label)
        layout.addWidget(provider_group)

        # Gemini group
        self.gemini_group = QGroupBox("Google Gemini")
        g_form = QFormLayout(self.gemini_group)
        gemini_key_row, self.gemini_key_edit = self._make_secret_row(
            "Reads GEMINI_API_KEY env var if left blank"
        )
        self.gemini_key_edit.textChanged.connect(self._update_provider_fields)
        g_form.addRow("API Key:", gemini_key_row)
        self.gemini_model_combo = SleekComboBox()
        self.gemini_model_combo.setEditable(True)
        for model_id in RECOMMENDED_GEMINI_MODELS:
            self.gemini_model_combo.addItem(model_id)
        self.gemini_model_edit = self.gemini_model_combo.lineEdit()
        assert self.gemini_model_edit is not None
        self.gemini_model_edit.setPlaceholderText(DEFAULT_GEMINI_MODEL)
        g_form.addRow("Model:", self.gemini_model_combo)
        layout.addWidget(self.gemini_group)

        # OpenAI group
        self.openai_group = QGroupBox("OpenAI / Compatible Endpoint")
        o_form = QFormLayout(self.openai_group)
        openai_key_row, self.openai_key_edit = self._make_secret_row(
            "Reads OPENAI_API_KEY env var if left blank"
        )
        self.openai_key_edit.textChanged.connect(self._update_provider_fields)
        o_form.addRow("API Key:", openai_key_row)
        self.openai_url_edit = QLineEdit()
        self.openai_url_edit.setPlaceholderText("https://api.openai.com/v1")
        o_form.addRow("Base URL:", self.openai_url_edit)
        self.openai_model_edit = QLineEdit()
        self.openai_model_edit.setPlaceholderText("gpt-4o-mini")
        o_form.addRow("Model:", self.openai_model_edit)
        layout.addWidget(self.openai_group)

        # Ollama group
        self.ollama_group = QGroupBox("Ollama (Local)")
        ol_form = QFormLayout(self.ollama_group)
        self.ollama_url_edit = QLineEdit()
        self.ollama_url_edit.setPlaceholderText("http://localhost:11434")
        self.ollama_url_edit.textChanged.connect(self._update_provider_fields)
        ol_form.addRow("Server URL:", self.ollama_url_edit)
        self.ollama_model_edit = QLineEdit()
        self.ollama_model_edit.setPlaceholderText("qwen2.5vl:7b")
        self.ollama_model_edit.textChanged.connect(self._update_provider_fields)
        ol_form.addRow("Vision model:", self.ollama_model_edit)
        layout.addWidget(self.ollama_group)

        layout.addStretch()
        self.tabs.addTab(tab, "VISION AI")

    def _make_secret_row(self, placeholder: str) -> tuple[QWidget, QLineEdit]:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText(placeholder)
        row.addWidget(edit, stretch=1)

        toggle_btn = QPushButton()
        toggle_btn.setObjectName("IconButton")
        toggle_btn.setIcon(svg_icon("eye", 15, THEME.ink))
        toggle_btn.setIconSize(QSize(15, 15))
        toggle_btn.setFixedSize(28, 28)
        toggle_btn.setCheckable(True)
        toggle_btn.setToolTip("Show / hide API key")
        toggle_btn.toggled.connect(
            lambda checked, e=edit: e.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        row.addWidget(toggle_btn)
        return container, edit

    def _load_from_config(self) -> None:
        c = self._config
        self.hotkey_edit.setText(c.hotkey)
        self._update_hotkey_preview(c.hotkey)
        self.auto_copy_cb.setChecked(c.auto_copy)
        self.show_popup_cb.setChecked(c.show_popup)
        self.preserve_breaks_cb.setChecked(c.preserve_line_breaks)
        self.auto_close_spin.setValue(c.popup_auto_close_seconds)

        self._select_combo_data(self.mode_combo, c.engine_mode)
        self._select_combo_data(self.script_combo, c.local_script)
        self.auto_probe_cb.setChecked(c.auto_probe_installed_scripts)
        self.threshold_spin.setValue(c.hybrid_confidence_threshold)
        self._select_combo_data(self.ai_format_combo, c.ai_output_format)

        self._select_combo_data(self.translate_lang_combo, c.translate_target_lang)
        self._select_combo_data(self.translate_provider_combo, c.translation_provider)
        self.auto_translate_cb.setChecked(c.auto_translate)

        self._select_combo_data(self.provider_combo, c.ai_provider)
        self.gemini_key_edit.setText(c.gemini_api_key)
        self.gemini_model_edit.setText(c.gemini_model)
        self.openai_key_edit.setText(c.openai_api_key)
        self.openai_url_edit.setText(c.openai_base_url)
        self.openai_model_edit.setText(c.openai_model)
        self.ollama_url_edit.setText(c.ollama_base_url)
        self.ollama_model_edit.setText(c.ollama_model)
        self._update_provider_fields()

    def _select_combo_data(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _update_hotkey_preview(self, text: str) -> None:
        self.hotkey_preview.setText(format_hotkey_display(text))

    def _update_provider_fields(self) -> None:
        provider = self.provider_combo.currentData()
        self.gemini_group.setVisible(provider == "gemini")
        self.openai_group.setVisible(provider == "openai")
        self.ollama_group.setVisible(provider == "ollama")

        temp = self.build_config()
        if temp.is_vision_ai_configured():
            self.ai_status_label.setText("Ready")
            self.ai_status_label.setObjectName("PackStatusInstalled")
        else:
            self.ai_status_label.setText("Not configured (optional — offline OCR works without keys)")
            self.ai_status_label.setObjectName("MutedLabel")
        self.ai_status_label.style().unpolish(self.ai_status_label)
        self.ai_status_label.style().polish(self.ai_status_label)

    def build_config(self) -> AppConfig:
        return replace(
            self._config,
            hotkey=self.hotkey_edit.text().strip() or "<ctrl>+<shift>+x",
            auto_copy=self.auto_copy_cb.isChecked(),
            show_popup=self.show_popup_cb.isChecked(),
            preserve_line_breaks=self.preserve_breaks_cb.isChecked(),
            popup_auto_close_seconds=self.auto_close_spin.value(),
            engine_mode=str(self.mode_combo.currentData() or "hybrid"),
            local_script=str(self.script_combo.currentData() or "auto"),
            auto_probe_installed_scripts=self.auto_probe_cb.isChecked(),
            hybrid_confidence_threshold=round(self.threshold_spin.value(), 2),
            ai_output_format=str(self.ai_format_combo.currentData() or "text"),
            translate_target_lang=str(self.translate_lang_combo.currentData() or "en"),
            translation_provider=str(self.translate_provider_combo.currentData() or "auto"),
            auto_translate=self.auto_translate_cb.isChecked(),
            ai_provider=str(self.provider_combo.currentData() or "gemini"),
            gemini_api_key=self.gemini_key_edit.text().strip(),
            gemini_model=self.gemini_model_edit.text().strip() or DEFAULT_GEMINI_MODEL,
            openai_api_key=self.openai_key_edit.text().strip(),
            openai_base_url=self.openai_url_edit.text().strip() or "https://api.openai.com/v1",
            openai_model=self.openai_model_edit.text().strip() or "gpt-4o-mini",
            ollama_base_url=self.ollama_url_edit.text().strip() or "http://localhost:11434",
            ollama_model=self.ollama_model_edit.text().strip() or "qwen2.5vl:7b",
        )

    def _on_save(self) -> None:
        self._config = self.build_config()
        self.accept()

    def updated_config(self) -> AppConfig:
        return self._config
