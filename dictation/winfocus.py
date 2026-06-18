"""Remember and restore the target foreground window.

Safety net so the transcribed text always lands in the window you were in when
you started dictating, even if focus drifted in the meantime.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

_u = ctypes.windll.user32
_u.GetForegroundWindow.restype = wintypes.HWND
_u.SetForegroundWindow.argtypes = [wintypes.HWND]
_u.IsWindow.argtypes = [wintypes.HWND]
_u.GetAsyncKeyState.restype = ctypes.c_short
_u.GetAsyncKeyState.argtypes = [ctypes.c_int]

# Virtual-key codes for the modifiers our hotkeys use.
_MOD_VKS = (0x11, 0x12, 0x10, 0x5B, 0x5C)  # Ctrl, Alt, Shift, LWin, RWin


def modifiers_down() -> bool:
    """True while any modifier key is physically held down right now."""
    return any(_u.GetAsyncKeyState(vk) & 0x8000 for vk in _MOD_VKS)


def get_foreground():
    return _u.GetForegroundWindow()


def restore_foreground(hwnd) -> None:
    """Bring `hwnd` back to the foreground if it isn't already."""
    if not hwnd or not _u.IsWindow(hwnd):
        return
    if _u.GetForegroundWindow() == hwnd:
        return
    try:
        # Tapping Alt satisfies Windows' foreground-change lock so the call is
        # allowed; the key is released immediately and won't affect the paste.
        _u.keybd_event(0x12, 0, 0, 0)
        _u.keybd_event(0x12, 0, 2, 0)
        _u.SetForegroundWindow(hwnd)
    except Exception:
        pass
