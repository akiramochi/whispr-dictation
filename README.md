# Whispr 🎙️

A local-AI dictation app for Windows, in the spirit of Wispr Flow. Press a
global shortcut anywhere, speak, and your words are transcribed **entirely on
your machine** and typed straight into whatever app you're focused on.

No cloud. No account. Your audio never leaves the device.

---

## How it works

1. Press your shortcut (default **Ctrl + Alt + D**).
2. A floating pill appears at the bottom of the screen with a live waveform.
3. Speak.
4. Press the shortcut again (or release it, in hold-to-talk mode).
5. [faster-whisper](https://github.com/SYSTRAN/faster-whisper) transcribes the
   audio locally and the text is inserted into the active window.

Powered by:

| Concern         | Library                                   |
| --------------- | ----------------------------------------- |
| Speech-to-text  | `faster-whisper` (Whisper, runs on CPU)   |
| UI / tray / overlay | `PySide6` (Qt)                        |
| Microphone      | `sounddevice`                             |
| Global hotkey + typing | `pynput`                           |

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> The Whisper model (~140 MB for `base.en`) downloads once on first use and is
> cached under `~/.cache/huggingface`. Everything after that is offline.

### GPU acceleration (optional, NVIDIA)

Whispr runs on the CPU out of the box. If you have an NVIDIA GPU, install the
CUDA runtime wheels for a large speedup (transcription is typically 5–15×
faster, making live typing feel instant):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gpu.txt
```

That's all — no CUDA toolkit needed. Whispr auto-detects the GPU and uses it
(`float16`), falling back to CPU automatically if anything's missing. The tray
menu shows whether it's **Running on GPU (CUDA)** or **CPU**, and you can force
either in Settings → Transcription → Processor.

## Run

```powershell
.\.venv\Scripts\python.exe run.py
```

Or just double-click **`Whispr.bat`**, which launches it silently (no console
window) using the bundled virtual environment.

A microphone icon appears in the system tray. **Click it** to open Settings;
right-click for the full menu.

## Launch on startup / quick shortcut

To start Whispr with Windows (so the dictation hotkey is always available):

1. Press **Win + R**, type `shell:startup`, press Enter.
2. Right-click → **New → Shortcut**, and point it at `Whispr.bat` in this folder.

To give yourself a desktop launch shortcut, right-click `Whispr.bat` →
**Send to → Desktop (create shortcut)**, then assign a hotkey in the shortcut's
Properties if you like. The in-app dictation hotkey works regardless.

## Settings

Open from the tray icon. You can configure:

- **Model** — `tiny`→`large-v3`. `.en` variants are English-only and faster.
  Bigger = more accurate but slower on CPU.
- **Language** — auto-detect or pin a specific language.
- **Microphone** — pick any input device.
- **Shortcut** — click the hotkey button and press your desired combo.
- **Mode** — *Toggle* (press to start/stop) or *Hold to talk* (hold while speaking).
- **Behavior** — clipboard-paste vs. simulated typing, restore clipboard,
  auto-capitalize, trailing space.

Settings are saved to `%APPDATA%\Whispr\config.json`.

## Model speed guide (CPU)

| Model      | Size   | Speed     | Quality |
| ---------- | ------ | --------- | ------- |
| `tiny.en`  | ~75 MB | fastest   | basic   |
| `base.en`  | ~140 MB| fast      | good ✅ default |
| `small.en` | ~460 MB| moderate  | better  |
| `medium`   | ~1.5 GB| slow      | great   |
| `large-v3` | ~3 GB  | slowest   | best    |

## Notes

- The overlay is a non-activating window, so it never steals focus from the app
  you're dictating into.
- Clipboard-paste insertion is the default (fast, handles emoji/unicode); it
  restores your previous clipboard afterward.
- Tested on Windows 11 with Python 3.14.
