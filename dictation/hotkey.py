"""Global hotkey detection with both toggle and hold-to-talk semantics.

Runs a pynput keyboard Listener on its own thread and emits Qt signals when
the configured key combination is fully pressed / released. Signals are
delivered to the UI thread via Qt's queued connections.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from pynput import keyboard

# Map both physical sides of each modifier onto one canonical token.
_MODIFIER_ALIASES = {
    keyboard.Key.ctrl_l: "ctrl", keyboard.Key.ctrl_r: "ctrl", keyboard.Key.ctrl: "ctrl",
    keyboard.Key.alt_l: "alt", keyboard.Key.alt_r: "alt", keyboard.Key.alt_gr: "alt",
    keyboard.Key.alt: "alt",
    keyboard.Key.shift_l: "shift", keyboard.Key.shift_r: "shift", keyboard.Key.shift: "shift",
    keyboard.Key.cmd_l: "cmd", keyboard.Key.cmd_r: "cmd", keyboard.Key.cmd: "cmd",
}

_NAMED_KEYS = {
    "space": keyboard.Key.space, "enter": keyboard.Key.enter, "tab": keyboard.Key.tab,
    "esc": keyboard.Key.esc, "escape": keyboard.Key.esc,
    **{f"f{i}": getattr(keyboard.Key, f"f{i}") for i in range(1, 13)},
}


def _vk_token(vk: int | None) -> str | None:
    """Map a Windows virtual-key code to a letter/digit token."""
    if vk is None:
        return None
    if 0x41 <= vk <= 0x5A:          # A-Z
        return chr(vk).lower()
    if 0x30 <= vk <= 0x39:          # 0-9 (top row)
        return chr(vk)
    if 0x60 <= vk <= 0x69:          # numpad 0-9
        return chr(vk - 0x30)
    return None


def canonical(key) -> str | None:
    """Reduce a pynput key event to a canonical lowercase token.

    When a modifier (e.g. Ctrl) is held, Windows often reports a letter key
    with ``char=None`` or as a control character, so we resolve letters and
    digits from the virtual-key code first and only fall back to ``char``.
    """
    if key in _MODIFIER_ALIASES:
        return _MODIFIER_ALIASES[key]
    if isinstance(key, keyboard.KeyCode):
        tok = _vk_token(getattr(key, "vk", None))
        if tok:
            return tok
        ch = key.char
        # Ignore control characters (e.g. Ctrl+D -> '\x04').
        if ch and ch.isprintable():
            return ch.lower()
        return None
    # Other named special keys -> their name (e.g. "space", "f5").
    name = getattr(key, "name", None)
    return name.lower() if name else None


def parse_hotkey(spec: str) -> frozenset[str]:
    """'ctrl+alt+space' -> frozenset({'ctrl','alt','space'})."""
    return frozenset(p.strip().lower() for p in spec.split("+") if p.strip())


def pretty(spec: str) -> str:
    parts = [p.strip() for p in spec.split("+") if p.strip()]
    return " + ".join(p.capitalize() for p in parts)


class HotkeyManager(QObject):
    """Emits `activated` / `deactivated` as the configured combo is held."""

    activated = Signal()
    deactivated = Signal()

    def __init__(self, hotkey: str):
        super().__init__()
        self._combo = parse_hotkey(hotkey)
        self._pressed: set[str] = set()
        self._combo_active = False
        self._listener: keyboard.Listener | None = None

    def set_hotkey(self, hotkey: str) -> None:
        self._combo = parse_hotkey(hotkey)
        self._pressed.clear()
        self._combo_active = False

    def start(self) -> None:
        if self._listener:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key) -> None:
        tok = canonical(key)
        if tok is None:
            return
        self._pressed.add(tok)
        if not self._combo_active and self._combo and self._combo.issubset(self._pressed):
            self._combo_active = True
            self.activated.emit()

    def _on_release(self, key) -> None:
        tok = canonical(key)
        if tok is None:
            return
        self._pressed.discard(tok)
        if self._combo_active and not self._combo.issubset(self._pressed):
            self._combo_active = False
            self.deactivated.emit()


class HotkeyCapture(QObject):
    """One-shot capture of the next key combo, for the settings rebind UI."""

    captured = Signal(str)

    def __init__(self):
        super().__init__()
        self._pressed: list[str] = []
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        self._pressed = []
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.daemon = True
        self._listener.start()

    def _on_press(self, key) -> None:
        tok = canonical(key)
        if tok and tok not in self._pressed:
            self._pressed.append(tok)

    def _on_release(self, key) -> None:  # noqa: ARG002
        if not self._pressed:
            return
        # Order modifiers first for a tidy, conventional display.
        order = {"ctrl": 0, "alt": 1, "shift": 2, "cmd": 3}
        keys = sorted(self._pressed, key=lambda k: order.get(k, 9))
        spec = "+".join(keys)
        if self._listener:
            self._listener.stop()
            self._listener = None
        self.captured.emit(spec)
