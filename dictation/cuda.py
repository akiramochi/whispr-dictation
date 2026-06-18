"""CUDA discovery for CTranslate2 / faster-whisper on Windows.

The cuBLAS and cuDNN DLLs ship inside the `nvidia-*-cu12` pip wheels. They must
be on the DLL search path before CTranslate2 loads them, otherwise GPU
inference fails with "cublas64_12.dll is not found".
"""
from __future__ import annotations

import glob
import os

_setup_done = False


def setup_dll_path() -> None:
    """Make the bundled CUDA runtime DLLs discoverable. Safe to call repeatedly."""
    global _setup_done
    if _setup_done:
        return
    _setup_done = True
    try:
        import nvidia
    except ImportError:
        return
    # `nvidia` is a namespace package (no __init__), so use __path__, not __file__.
    bins: list[str] = []
    for base in list(getattr(nvidia, "__path__", [])):
        bins.extend(glob.glob(os.path.join(base, "*", "bin")))
    if not bins:
        return
    # CTranslate2 loads cuBLAS via plain LoadLibrary, which honours PATH.
    os.environ["PATH"] = os.pathsep.join(bins) + os.pathsep + os.environ.get("PATH", "")
    for b in bins:
        try:
            os.add_dll_directory(b)
        except OSError:
            pass


def is_available() -> bool:
    """True if an NVIDIA GPU usable by CTranslate2 is present."""
    setup_dll_path()
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False
