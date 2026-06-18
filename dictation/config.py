"""Persistent user configuration stored as JSON in %APPDATA%/Whispr."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = Path(base) / "Whispr"
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_PATH = config_dir() / "config.json"

# Whisper model presets, fastest -> most accurate. ".en" variants are
# English-only and noticeably faster/smaller.
MODELS = ["tiny.en", "tiny", "base.en", "base", "small.en", "small", "medium", "large-v3"]


@dataclass
class Config:
    model: str = "base.en"
    language: str = ""              # "" = autodetect, else ISO code like "en"
    processor: str = "auto"         # "auto", "cuda" (GPU), or "cpu"
    compute_type: str = "int8"      # CPU compute type; GPU uses float16
    device_index: int | None = None  # input device, None = system default
    hotkey: str = "ctrl+alt+d"
    mode: str = "toggle"            # "toggle" or "hold"
    inject_method: str = "paste"    # "paste" (clipboard) or "type" (keystrokes)
    restore_clipboard: bool = True
    live_typing: bool = False       # type into the active window while speaking
    auto_capitalize: bool = True
    trailing_space: bool = True
    accent: str = "#6C8CFF"
    launch_at_login: bool = False

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
                return cls(**known)
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
