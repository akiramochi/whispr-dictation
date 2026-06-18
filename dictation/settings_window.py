"""Settings window — model, language, microphone, shortcut and behavior."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

from .audio import Recorder
from .config import Config, MODELS
from .hotkey import HotkeyCapture, pretty

LANGUAGES = [
    ("Auto-detect", ""), ("English", "en"), ("Spanish", "es"), ("French", "fr"),
    ("German", "de"), ("Italian", "it"), ("Portuguese", "pt"), ("Dutch", "nl"),
    ("Russian", "ru"), ("Chinese", "zh"), ("Japanese", "ja"), ("Korean", "ko"),
    ("Hindi", "hi"), ("Arabic", "ar"),
]

STYLE = """
QWidget#root { background: #15171F; }
QLabel { color: #C9CEDC; font-size: 13px; }
QLabel#title { color: #FFFFFF; font-size: 20px; font-weight: 600; }
QLabel#subtitle { color: #7B8194; font-size: 12px; }
QLabel#section { color: #8E94A8; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QFrame#card { background: #1C1F2B; border: 1px solid #272B3A; border-radius: 14px; }
QComboBox, QPushButton#field {
    background: #232735; color: #E6E9F2; border: 1px solid #313647;
    border-radius: 8px; padding: 7px 10px; font-size: 13px; min-height: 18px;
}
QComboBox:hover, QPushButton#field:hover { border-color: #46506B; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #232735; color: #E6E9F2; selection-background-color: #6C8CFF;
    border: 1px solid #313647; outline: none;
}
QPushButton#primary {
    background: #6C8CFF; color: #FFFFFF; border: none; border-radius: 9px;
    padding: 9px 18px; font-size: 13px; font-weight: 600;
}
QPushButton#primary:hover { background: #7E9BFF; }
QPushButton#ghost {
    background: transparent; color: #9AA0B4; border: 1px solid #313647;
    border-radius: 9px; padding: 9px 18px; font-size: 13px;
}
QPushButton#ghost:hover { color: #E6E9F2; border-color: #46506B; }
QPushButton#capture {
    background: #232735; color: #E6E9F2; border: 1px solid #313647;
    border-radius: 8px; padding: 7px 14px; font-size: 13px; font-weight: 600;
}
QPushButton#capture:hover { border-color: #6C8CFF; }
QCheckBox { color: #C9CEDC; font-size: 13px; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid #3A4055; background: #232735; }
QCheckBox::indicator:checked { background: #6C8CFF; border-color: #6C8CFF; }
"""


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(12)
    lbl = QLabel(title.upper())
    lbl.setObjectName("section")
    lay.addWidget(lbl)
    return card, lay


class SettingsWindow(QWidget):
    saved = Signal()

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self._capture: HotkeyCapture | None = None
        self._pending_hotkey = config.hotkey

        self.setObjectName("root")
        self.setWindowTitle("Whispr — Settings")
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("title")
        sub = QLabel("Local dictation • nothing leaves your machine")
        sub.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(sub)

        # --- Model card ---
        mcard, ml = _card("Transcription")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        self.model_box = QComboBox()
        self.model_box.addItems(MODELS)
        self.model_box.setCurrentText(config.model)
        grid.addWidget(QLabel("Model"), 0, 0)
        grid.addWidget(self.model_box, 0, 1)

        self.lang_box = QComboBox()
        for name, code in LANGUAGES:
            self.lang_box.addItem(name, code)
        idx = next((i for i, (_, c) in enumerate(LANGUAGES) if c == config.language), 0)
        self.lang_box.setCurrentIndex(idx)
        grid.addWidget(QLabel("Language"), 1, 0)
        grid.addWidget(self.lang_box, 1, 1)

        self.device_box = QComboBox()
        self.device_box.addItem("System default", None)
        for i, name in Recorder.list_devices():
            self.device_box.addItem(name, i)
        di = next((k for k in range(self.device_box.count())
                   if self.device_box.itemData(k) == config.device_index), 0)
        self.device_box.setCurrentIndex(di)
        grid.addWidget(QLabel("Microphone"), 2, 0)
        grid.addWidget(self.device_box, 2, 1)

        self.proc_box = QComboBox()
        self.proc_box.addItem("Auto (GPU if available)", "auto")
        self.proc_box.addItem("GPU (CUDA)", "cuda")
        self.proc_box.addItem("CPU", "cpu")
        pi = {"auto": 0, "cuda": 1, "cpu": 2}.get(config.processor, 0)
        self.proc_box.setCurrentIndex(pi)
        grid.addWidget(QLabel("Processor"), 3, 0)
        grid.addWidget(self.proc_box, 3, 1)
        grid.setColumnStretch(1, 1)
        ml.addLayout(grid)
        hint = QLabel("Larger models are more accurate but slower. The model "
                      "downloads once on first use.")
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        ml.addWidget(hint)
        root.addWidget(mcard)

        # --- Shortcut card ---
        scard, sl = _card("Shortcut")
        row = QHBoxLayout()
        self.mode_box = QComboBox()
        self.mode_box.addItem("Toggle (press to start / stop)", "toggle")
        self.mode_box.addItem("Hold to talk (hold while speaking)", "hold")
        self.mode_box.setCurrentIndex(0 if config.mode == "toggle" else 1)
        row.addWidget(self.mode_box, 1)
        sl.addLayout(row)

        hk_row = QHBoxLayout()
        self.hotkey_btn = QPushButton(pretty(config.hotkey))
        self.hotkey_btn.setObjectName("capture")
        self.hotkey_btn.clicked.connect(self._begin_capture)
        hk_row.addWidget(QLabel("Hotkey"))
        hk_row.addWidget(self.hotkey_btn, 1)
        sl.addLayout(hk_row)
        root.addWidget(scard)

        # --- Behavior card ---
        bcard, bl = _card("Behavior")
        self.live_chk = QCheckBox("Type live into the active window as I speak (toggle mode only)")
        self.live_chk.setChecked(config.live_typing)
        self.paste_chk = QCheckBox("Insert via clipboard paste (faster, supports emoji)")
        self.paste_chk.setChecked(config.inject_method == "paste")
        self.restore_chk = QCheckBox("Restore previous clipboard after pasting")
        self.restore_chk.setChecked(config.restore_clipboard)
        self.cap_chk = QCheckBox("Capitalize the first letter")
        self.cap_chk.setChecked(config.auto_capitalize)
        self.space_chk = QCheckBox("Add a trailing space")
        self.space_chk.setChecked(config.trailing_space)
        for w in (self.live_chk, self.paste_chk, self.restore_chk, self.cap_chk, self.space_chk):
            bl.addWidget(w)
        root.addWidget(bcard)

        # --- Buttons ---
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Close")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.close)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        root.addLayout(btns)

    def _begin_capture(self) -> None:
        self.hotkey_btn.setText("Press keys…")
        self._capture = HotkeyCapture()
        self._capture.captured.connect(self._on_captured)
        self._capture.start()

    def _on_captured(self, spec: str) -> None:
        self._pending_hotkey = spec
        self.hotkey_btn.setText(pretty(spec))
        self._capture = None

    def _save(self) -> None:
        c = self.config
        c.model = self.model_box.currentText()
        c.language = self.lang_box.currentData()
        c.device_index = self.device_box.currentData()
        c.processor = self.proc_box.currentData()
        c.mode = self.mode_box.currentData()
        c.hotkey = self._pending_hotkey
        c.inject_method = "paste" if self.paste_chk.isChecked() else "type"
        c.restore_clipboard = self.restore_chk.isChecked()
        c.live_typing = self.live_chk.isChecked()
        c.auto_capitalize = self.cap_chk.isChecked()
        c.trailing_space = self.space_chk.isChecked()
        c.save()
        self.saved.emit()
        self.close()

    def closeEvent(self, event):  # noqa: N802
        if self._capture:
            self._capture = None
        super().closeEvent(event)
