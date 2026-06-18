"""Application controller: wires hotkey -> recorder -> transcriber -> injector."""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import APP_NAME, __version__
from .audio import Recorder
from .config import Config
from .hotkey import HotkeyManager, pretty
from .injector import inject, type_diff
from .logger import get_logger
from .overlay import Overlay
from .resources import mic_icon
from .settings_window import SettingsWindow
from .transcriber import TranscriberThread
from . import winfocus

IDLE, RECORDING, BUSY = "idle", "recording", "busy"
PARTIAL_INTERVAL_MS = 1100  # how often to refresh the live transcript
_log = get_logger()


class Controller(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.config = Config.load()
        self.state = IDLE
        self._settings: SettingsWindow | None = None
        self._target_hwnd = None
        self._live_active = False
        self._committed = ""

        self.recorder = Recorder(self.config.device_index)
        self.overlay = Overlay(self.recorder, self.config.accent)

        self.transcriber = TranscriberThread(
            self.config.model, self.config.compute_type, self.config.language
        )
        self.transcriber.worker.finished.connect(self._on_transcribed)
        self.transcriber.worker.partial.connect(self._on_partial_text)
        self.transcriber.worker.error.connect(self._on_error)
        self.transcriber.worker.model_loading.connect(self._on_model_loading)

        # Timer that drives the live (partial) transcript while recording.
        self._partial_timer = QTimer(self)
        self._partial_timer.setInterval(PARTIAL_INTERVAL_MS)
        self._partial_timer.timeout.connect(self._emit_partial)

        self.hotkeys = HotkeyManager(self.config.hotkey)
        self.hotkeys.activated.connect(self._on_hotkey_down, Qt.QueuedConnection)
        self.hotkeys.deactivated.connect(self._on_hotkey_up, Qt.QueuedConnection)
        self.hotkeys.start()

        self._build_tray()
        # Warm up the model in the background so the first dictation is snappy.
        QTimer.singleShot(400, self.transcriber.preload)

    # --- tray ------------------------------------------------------------
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(mic_icon(self.config.accent))
        self.tray.setToolTip(f"{APP_NAME} — {pretty(self.config.hotkey)}")
        menu = QMenu()

        self._status_action = QAction("Ready", menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        menu.addSeparator()

        self._hint_action = QAction("", menu)
        self._hint_action.setEnabled(False)
        menu.addAction(self._hint_action)
        menu.addSeparator()

        settings_act = QAction("Settings…", menu)
        settings_act.triggered.connect(self.open_settings)
        menu.addAction(settings_act)

        about_act = QAction(f"About {APP_NAME}", menu)
        about_act.triggered.connect(self._about)
        menu.addAction(about_act)
        menu.addSeparator()

        quit_act = QAction("Quit", menu)
        quit_act.triggered.connect(self.quit)
        menu.addAction(quit_act)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self._refresh_hint()
        self.tray.showMessage(
            APP_NAME,
            f"Ready. Press {pretty(self.config.hotkey)} to dictate.",
            mic_icon(self.config.accent), 4000,
        )

    def _refresh_hint(self) -> None:
        verb = "Hold" if self.config.mode == "hold" else "Press"
        self._hint_action.setText(f"{verb} {pretty(self.config.hotkey)} to dictate")
        self.tray.setToolTip(f"{APP_NAME} — {pretty(self.config.hotkey)}")

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.open_settings()

    # --- hotkey flow -----------------------------------------------------
    def _on_hotkey_down(self) -> None:
        if self.config.mode == "hold":
            if self.state == IDLE:
                self._start_recording()
        else:  # toggle
            if self.state == IDLE:
                self._start_recording()
            elif self.state == RECORDING:
                self._stop_and_transcribe()

    def _on_hotkey_up(self) -> None:
        if self.config.mode == "hold" and self.state == RECORDING:
            self._stop_and_transcribe()

    def _start_recording(self) -> None:
        # Remember where the text should go before our overlay appears.
        self._target_hwnd = winfocus.get_foreground()
        # Live typing is only safe in toggle mode (hold mode keeps Ctrl+Alt down).
        self._live_active = self.config.live_typing and self.config.mode == "toggle"
        self._committed = ""
        try:
            self.recorder.device_index = self.config.device_index
            self.recorder.start()
        except Exception as exc:  # noqa: BLE001
            _log.exception("mic start failed")
            self.overlay.show_error(f"Mic error: {exc}")
            return
        self.state = RECORDING
        self._status_action.setText("● Listening…")
        self.overlay.show_listening()
        self._partial_timer.start()
        _log.info("recording started (mode=%s)", self.config.mode)

    def _emit_partial(self) -> None:
        if self.state == RECORDING:
            self.transcriber.partial(self.recorder.snapshot())

    def _format_live(self, text: str) -> str:
        """Display form used for both partials and final, minus trailing space,
        so the live-typed prefix stays stable through to the final pass."""
        text = text.strip()
        if self.config.auto_capitalize and text:
            text = text[0].upper() + text[1:]
        return text

    def _on_partial_text(self, text: str) -> None:
        if self.state != RECORDING:
            return
        if self._live_active:
            # Never type while a modifier is held, or backspaces/letters turn
            # into shortcuts (Ctrl+Backspace, etc.). Skip; the next pass catches up.
            if winfocus.modifiers_down():
                return
            core = self._format_live(text)
            winfocus.restore_foreground(getattr(self, "_target_hwnd", None))
            self._committed = type_diff(self._committed, core)
        else:
            self.overlay.set_partial(text)

    def _stop_and_transcribe(self) -> None:
        self._partial_timer.stop()
        audio = self.recorder.stop()
        self.state = BUSY
        self._status_action.setText("Transcribing…")
        self.overlay.show_transcribing()
        _log.info("recording stopped: %.1fs of audio", len(audio) / 16000)
        self.transcriber.transcribe(audio)

    # --- results ---------------------------------------------------------
    def _on_transcribed(self, text: str) -> None:
        _log.info("transcript: %r", text)
        # Defer insertion until the hotkey's modifier keys are released, so the
        # keystrokes don't get reinterpreted as shortcuts.
        self._wait_then_insert(text)

    def _wait_then_insert(self, text: str, attempts: int = 0) -> None:
        if winfocus.modifiers_down() and attempts < 80:  # poll up to ~4s
            QTimer.singleShot(50, lambda: self._wait_then_insert(text, attempts + 1))
            return
        winfocus.restore_foreground(getattr(self, "_target_hwnd", None))
        if self._live_active:
            # Reconcile whatever we typed live with the higher-quality final
            # pass, then add the trailing space.
            core = self._format_live(text)
            type_diff(self._committed, core)
            if core and self.config.trailing_space:
                type_diff(core, core + " ")
            final = core
        else:
            final = self._postprocess(text)
            if final:
                inject(final, self.config.inject_method, self.config.restore_clipboard)
            else:
                _log.info("nothing to insert (empty transcript)")
        self.overlay.show_done(final)
        self._status_action.setText("Ready")
        self.state = IDLE

    def _postprocess(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        if self.config.auto_capitalize:
            text = text[0].upper() + text[1:]
        if self.config.trailing_space:
            text += " "
        return text

    def _on_error(self, msg: str) -> None:
        self.overlay.show_error(msg)
        self._status_action.setText("Ready")
        self.state = IDLE

    def _on_model_loading(self, name: str) -> None:
        self._status_action.setText(f"Loading {name}…")
        if self.state == BUSY:
            self.overlay.message = f"Loading {name}…"
            self.overlay.update()

    # --- settings / lifecycle -------------------------------------------
    def open_settings(self) -> None:
        if self._settings is None:
            self._settings = SettingsWindow(self.config)
            self._settings.saved.connect(self._apply_settings)
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    def _apply_settings(self) -> None:
        self.transcriber.reconfigure(
            self.config.model, self.config.compute_type, self.config.language
        )
        self.hotkeys.set_hotkey(self.config.hotkey)
        self.recorder.device_index = self.config.device_index
        self.overlay.accent.setNamedColor(self.config.accent)
        self._refresh_hint()
        QTimer.singleShot(200, self.transcriber.preload)

    def _about(self) -> None:
        self.tray.showMessage(
            f"{APP_NAME} v{__version__}",
            "Local-AI dictation powered by faster-whisper. "
            "Your audio never leaves this device.",
            mic_icon(self.config.accent), 5000,
        )

    def quit(self) -> None:
        self.hotkeys.stop()
        try:
            self.recorder.stop()
        except Exception:
            pass
        self.transcriber.shutdown()
        self.tray.hide()
        self.app.quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # tray app keeps running

    if not QSystemTrayIcon.isSystemTrayAvailable():
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, APP_NAME, "No system tray available.")
        return 1

    app.setWindowIcon(mic_icon())
    controller = Controller(app)  # noqa: F841  (kept alive for app lifetime)
    return app.exec()
