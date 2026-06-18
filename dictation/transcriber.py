"""Local speech-to-text via faster-whisper, running on a worker thread."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from . import cuda
from .audio import SAMPLE_RATE


class Transcriber(QObject):
    """Loads a Whisper model lazily and transcribes audio off the UI thread.

    Lives inside its own QThread; call requests via the `transcribe_requested`
    signal and listen on `finished` / `error` / `model_loading` / `model_ready`.
    """

    transcribe_requested = Signal(object)      # np.ndarray
    partial_requested = Signal(object)         # np.ndarray
    load_requested = Signal()

    finished = Signal(str)
    partial = Signal(str)                       # live partial transcript
    error = Signal(str)
    model_loading = Signal(str)                 # model name
    model_ready = Signal(str)                    # active device ("cuda"/"cpu")

    def __init__(self, model_name: str, processor: str, language: str):
        super().__init__()
        self.model_name = model_name
        self.processor = processor
        self.language = language
        self._model = None
        self.active_device = "cpu"
        self.transcribe_requested.connect(self._on_transcribe)
        self.partial_requested.connect(self._on_partial)
        self.load_requested.connect(self._ensure_model)

    def reconfigure(self, model_name: str, processor: str, language: str) -> None:
        changed = (model_name != self.model_name) or (processor != self.processor)
        self.model_name = model_name
        self.processor = processor
        self.language = language
        if changed:
            self._model = None  # force reload on next use

    def _device_plan(self) -> list[tuple[str, str]]:
        """Ordered (device, compute_type) attempts based on the processor pref.

        "auto"/"cuda" try the GPU first (when present) and fall back to CPU;
        "cpu" stays on the CPU.
        """
        plan: list[tuple[str, str]] = []
        if self.processor in ("auto", "cuda") and cuda.is_available():
            plan.append(("cuda", "float16"))
        plan.append(("cpu", "int8"))
        return plan

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        from faster_whisper import WhisperModel
        self.model_loading.emit(self.model_name)
        last_exc: Exception | None = None
        for device, compute_type in self._device_plan():
            try:
                self._model = WhisperModel(
                    self.model_name, device=device, compute_type=compute_type
                )
                self.active_device = device
                if device == "cuda":
                    self._warmup()  # absorb one-time CUDA/cuDNN JIT cost now
                self.model_ready.emit(device)
                return True
            except Exception as exc:  # noqa: BLE001
                last_exc = exc  # e.g. GPU OOM -> fall through to CPU
        self.error.emit(f"Could not load model '{self.model_name}': {last_exc}")
        return False

    def _warmup(self) -> None:
        try:
            silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
            segments, _ = self._model.transcribe(silence, beam_size=1)
            list(segments)
        except Exception:
            pass

    def _on_transcribe(self, audio: np.ndarray) -> None:
        if audio is None or len(audio) < SAMPLE_RATE * 0.2:
            self.finished.emit("")
            return
        if not self._ensure_model():
            return
        try:
            segments, _info = self._model.transcribe(
                audio,
                language=self.language or None,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
            )
            text = "".join(seg.text for seg in segments).strip()
            self.finished.emit(text)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"Transcription failed: {exc}")

    def _on_partial(self, audio: np.ndarray) -> None:
        # Fast, best-effort pass over the audio captured so far. Skipped if no
        # model is loaded yet; greedy decoding keeps latency low.
        if self._model is None or audio is None or len(audio) < SAMPLE_RATE * 0.4:
            return
        try:
            segments, _info = self._model.transcribe(
                audio, language=self.language or None, beam_size=1,
                condition_on_previous_text=False,
            )
            text = "".join(seg.text for seg in segments).strip()
            self.partial.emit(text)
        except Exception:  # noqa: BLE001
            pass  # partials are non-critical; the final pass is authoritative


class TranscriberThread:
    """Owns a QThread hosting a Transcriber and forwards its signals."""

    def __init__(self, model_name: str, processor: str, language: str):
        self.thread = QThread()
        self.thread.setObjectName("whispr-transcriber")
        self.worker = Transcriber(model_name, processor, language)
        self.worker.moveToThread(self.thread)
        self.thread.start()

    def preload(self) -> None:
        self.worker.load_requested.emit()

    def transcribe(self, audio: np.ndarray) -> None:
        self.worker.transcribe_requested.emit(audio)

    def partial(self, audio: np.ndarray) -> None:
        self.worker.partial_requested.emit(audio)

    def reconfigure(self, model_name: str, processor: str, language: str) -> None:
        self.worker.reconfigure(model_name, processor, language)

    def shutdown(self) -> None:
        self.thread.quit()
        self.thread.wait(2000)
