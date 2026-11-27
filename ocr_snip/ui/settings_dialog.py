"""Modern Settings dialog for OCR engine, multilingual script, hotkey, and Vision AI."""

from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ocr_snip.capture.hotkey import format_hotkey_display
from ocr_snip.config import AppConfig
from ocr_snip.logging_utils import get_logs_dir
from ocr_snip.ocr.local_rapidocr import SCRIPT_PROFILES
from ocr_snip.translate import TARGET_LANGUAGES
from ocr_snip.ui.theme import DARK_STYLESHEET, create_app_icon


class SettingsDialog(QDialog):
    """Configuration dialog for OCRSnippingTool."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = replace(config)
        self.setWindowTitle("OCRSnippingTool Settings")
        self.setWindowIcon(create_app_icon(64))
        self.setMinimumWidth(520)
        self.setStyleSheet(DARK_STYLESHEET)
        self._build_ui()
        self._load_from_config()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self._build_general_tab()
        self._build_ocr_tab()
        self._build_vision_ai_tab()

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

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
        presets_label = QLabel("Presets:")
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

        wf_group = QGroupBox("Post-Capture Workflow")
        wf_layout = QVBoxLayout(wf_group)

        self.auto_copy_cb = QCheckBox("Automatically copy extracted text to clipboard")
        wf_layout.addWidget(self.auto_copy_cb)

        self.show_popup_cb = QCheckBox("Show floating preview & edit popup after snip")
        wf_layout.addWidget(self.show_popup_cb)

        self.preserve_breaks_cb = QCheckBox("Preserve multi-line breaks in extracted text")
        wf_layout.addWidget(self.preserve_breaks_cb)

        timer_form = QFormLayout()
        self.auto_close_spin = QSpinBox()
        self.auto_close_spin.setRange(0, 120)
        self.auto_close_spin.setSuffix(" s  (0 = stay open)")
        timer_form.addRow("Auto-close popup:", self.auto_close_spin)
        wf_layout.addLayout(timer_form)

        layout.addWidget(wf_group)

        diag_row = QHBoxLayout()
        logs_btn = QPushButton("📄 Open Logs Folder")
        logs_btn.setToolTip("Open diagnostic log directory")
        logs_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_logs_dir())))
        )
        diag_row.addWidget(logs_btn)
        diag_row.addStretch()
        layout.addLayout(diag_row)

        layout.addStretch()
        self.tabs.addTab(tab, "General")

    def _build_ocr_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        mode_group = QGroupBox("Hybrid AI/ML OCR Mode")
        form = QFormLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Hybrid (Offline ML + Auto Vision AI fallback)", "hybrid")
        self.mode_combo.addItem("Offline ML Only (RapidOCR — 100% private)", "local")
        self.mode_combo.addItem("Vision AI Only (Gemini / OpenAI / Ollama)", "vision_ai")
        form.addRow("Engine mode:", self.mode_combo)

        self.script_combo = QComboBox()
        for key, profile in SCRIPT_PROFILES.items():
            self.script_combo.addItem(profile.label, key)
        form.addRow("Default offline script:", self.script_combo)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.10, 0.99)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setDecimals(2)
        self.threshold_spin.setToolTip(
            "In Hybrid mode, if offline confidence drops below this threshold "
            "and Vision AI is configured, automatically refine with Vision AI."
        )
        form.addRow("Hybrid AI fallback threshold:", self.threshold_spin)

        tip = QLabel(
            "Tip: PP-OCRv6 'Auto' handles English, Latin, Chinese, Japanese, and Greek offline "
            "out-of-the-box. Switch scripts anytime right in the floating popup, or configure "
            "Vision AI for automatic recognition of every world language & handwriting."
        )
        tip.setObjectName("MutedLabel")
        tip.setWordWrap(True)
        form.addRow(tip)

        layout.addWidget(mode_group)

        trans_group = QGroupBox("Built-In 1-Click Translation")
        t_form = QFormLayout(trans_group)

        self.translate_lang_combo = QComboBox()
        for code, name in TARGET_LANGUAGES:
            self.translate_lang_combo.addItem(name, code)
        t_form.addRow("Default target language:", self.translate_lang_combo)

        self.translate_provider_combo = QComboBox()
        self.translate_provider_combo.addItem("Auto (AI if configured, else Free Web)", "auto")
        self.translate_provider_combo.addItem("Free Web Translate (no API key)", "google_free")
        self.translate_provider_combo.addItem("Configured AI Provider only", "ai")
        t_form.addRow("Translation backend:", self.translate_provider_combo)

        self.auto_translate_cb = QCheckBox(
            "Automatically translate when detected language differs from target"
        )
        t_form.addRow(self.auto_translate_cb)

        layout.addWidget(trans_group)
        layout.addStretch()
        self.tabs.addTab(tab, "OCR & Translate")

    def _build_vision_ai_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        provider_group = QGroupBox("Vision AI Provider (Optional)")
        form = QFormLayout(provider_group)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("Google Gemini", "gemini")
        self.provider_combo.addItem("OpenAI / OpenAI-Compatible API", "openai")
        self.provider_combo.addItem("Ollama (Local Vision Model)", "ollama")
        self.provider_combo.currentIndexChanged.connect(self._update_provider_fields)
        form.addRow("Active provider:", self.provider_combo)

        self.ai_status_label = QLabel("")
        self.ai_status_label.setObjectName("MutedLabel")
        form.addRow("Status:", self.ai_status_label)
        layout.addWidget(provider_group)

        # Gemini group
        self.gemini_group = QGroupBox("Google Gemini")
        g_form = QFormLayout(self.gemini_group)
        self.gemini_key_edit = self._make_secret_edit("Reads GEMINI_API_KEY env var if left blank")
        self.gemini_key_edit.textChanged.connect(self._update_provider_fields)
        g_form.addRow("API Key:", self.gemini_key_edit)
        self.gemini_model_edit = QLineEdit()
        self.gemini_model_edit.setPlaceholderText("gemini-2.5-flash")
        g_form.addRow("Model:", self.gemini_model_edit)
        layout.addWidget(self.gemini_group)

        # OpenAI group
        self.openai_group = QGroupBox("OpenAI / Compatible Endpoint")
        o_form = QFormLayout(self.openai_group)
        self.openai_key_edit = self._make_secret_edit("Reads OPENAI_API_KEY env var if left blank")
        self.openai_key_edit.textChanged.connect(self._update_provider_fields)
        o_form.addRow("API Key:", self.openai_key_edit)
        self.openai_url_edit = QLineEdit()
        self.openai_url_edit.setPlaceholderText("https://api.openai.com/v1")
        o_form.addRow("Base URL:", self.openai_url_edit)
        self.openai_model_edit = QLineEdit()
        self.openai_model_edit.setPlaceholderText("gpt-4o-mini")
        o_form.addRow("Model:", self.openai_model_edit)
        layout.addWidget(self.openai_group)

        # Ollama group
        self.ollama_group = QGroupBox("Ollama (100% Local Vision LLM)")
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
        self.tabs.addTab(tab, "Vision AI")

    def _make_secret_edit(self, placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText(placeholder)
        return edit

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
        self.threshold_spin.setValue(c.hybrid_confidence_threshold)

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
            self.ai_status_label.setText("✓ Ready")
        else:
            self.ai_status_label.setText("Not configured (optional — offline ML still works)")

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
            hybrid_confidence_threshold=round(self.threshold_spin.value(), 2),
            translate_target_lang=str(self.translate_lang_combo.currentData() or "en"),
            translation_provider=str(self.translate_provider_combo.currentData() or "auto"),
            auto_translate=self.auto_translate_cb.isChecked(),
            ai_provider=str(self.provider_combo.currentData() or "gemini"),
            gemini_api_key=self.gemini_key_edit.text().strip(),
            gemini_model=self.gemini_model_edit.text().strip() or "gemini-2.5-flash",
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
