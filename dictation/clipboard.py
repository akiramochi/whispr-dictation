"""Synchronous Win32 clipboard access.

Qt's QClipboard only flushes to the OS clipboard when the event loop runs, so
setting it and immediately pasting (while the GUI thread is blocked) pastes
stale content. These helpers write the clipboard synchronously via the Win32
API so a paste sent right after is guaranteed to see the new text.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

_k32 = ctypes.windll.kernel32
_u32 = ctypes.windll.user32

# 64-bit-safe signatures (handles/pointers must not be truncated to int).
_k32.GlobalAlloc.restype = wintypes.HGLOBAL
_k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_k32.GlobalLock.restype = wintypes.LPVOID
_k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
_u32.OpenClipboard.argtypes = [wintypes.HWND]
_u32.GetClipboardData.restype = wintypes.HANDLE
_u32.GetClipboardData.argtypes = [wintypes.UINT]
_u32.SetClipboardData.restype = wintypes.HANDLE
_u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]


def _open(retries: int = 5) -> bool:
    for _ in range(retries):
        if _u32.OpenClipboard(0):
            return True
        time.sleep(0.02)
    return False


def get_text() -> str:
    if not _open():
        return ""
    try:
        h = _u32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        ptr = _k32.GlobalLock(h)
        if not ptr:
            return ""
        try:
            return ctypes.c_wchar_p(ptr).value or ""
        finally:
            _k32.GlobalUnlock(h)
    finally:
        _u32.CloseClipboard()


def set_text(text: str) -> bool:
    if not _open():
        return False
    try:
        _u32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        h = _k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            return False
        ptr = _k32.GlobalLock(h)
        ctypes.memmove(ptr, data, len(data))
        _k32.GlobalUnlock(h)
        # Ownership of `h` transfers to the system on success.
        return bool(_u32.SetClipboardData(CF_UNICODETEXT, h))
    finally:
        _u32.CloseClipboard()
