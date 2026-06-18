"""Insert transcribed text into whatever window currently has focus."""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer
from pynput.keyboard import Controller, Key

from . import clipboard
from .logger import get_logger

# How long to leave our text on the clipboard before restoring the previous
# contents. Must comfortably exceed how long the target app takes to paste.
RESTORE_DELAY_MS = 700

_kb = Controller()
_log = get_logger()

# Modifiers that may still be held from the activation hotkey when we inject.
_MODS = (Key.ctrl, Key.ctrl_l, Key.ctrl_r, Key.alt, Key.alt_l, Key.alt_r,
         Key.alt_gr, Key.shift, Key.shift_l, Key.shift_r, Key.cmd)


def _release_modifiers() -> None:
    """Defensively lift any modifier keys so Ctrl+V isn't read as Ctrl+Alt+V."""
    for m in _MODS:
        try:
            _kb.release(m)
        except Exception:
            pass


def _send_paste() -> None:
    _kb.press(Key.ctrl)
    _kb.press("v")
    _kb.release("v")
    _kb.release(Key.ctrl)


def type_diff(old: str, new: str) -> str:
    """Transform the already-typed `old` text into `new` via backspaces + typing.

    Used for live dictation: only the changed tail is rewritten, so a stable
    prefix isn't disturbed as Whisper refines its guess. Returns `new`.
    """
    _release_modifiers()
    i = 0
    limit = min(len(old), len(new))
    while i < limit and old[i] == new[i]:
        i += 1
    for _ in range(len(old) - i):
        _kb.press(Key.backspace)
        _kb.release(Key.backspace)
    if len(new) > i:
        _kb.type(new[i:])
    return new


def inject(text: str, method: str = "paste", restore_clipboard: bool = True) -> None:
    """Type `text` into the focused app.

    "paste" copies to the clipboard and sends Ctrl+V (fast, unicode-safe);
    "type" simulates individual keystrokes. The clipboard is restored after
    a paste when `restore_clipboard` is set.
    """
    if not text:
        _log.info("inject: empty text, nothing to do")
        return

    # The activation hotkey's modifiers are frequently still down at this
    # point; clear them first or the keystrokes get reinterpreted.
    _release_modifiers()
    time.sleep(0.05)

    try:
        if method == "type":
            _kb.type(text)
            _log.info("inject: typed %d chars", len(text))
            return

        # Write the clipboard synchronously (Win32) so the paste below sees it.
        previous = clipboard.get_text()
        if not clipboard.set_text(text):
            _log.error("inject: failed to set clipboard; falling back to typing")
            _kb.type(text)
            return
        time.sleep(0.03)
        _send_paste()
        _log.info("inject: pasted %d chars", len(text))
        if restore_clipboard:
            # Restore later and without blocking the UI thread, so the target
            # has time to consume the paste before the clipboard changes back.
            QTimer.singleShot(RESTORE_DELAY_MS, lambda: clipboard.set_text(previous))
    except Exception as exc:  # noqa: BLE001
        _log.exception("inject failed: %s", exc)
