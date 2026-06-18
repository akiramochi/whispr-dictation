"""Microphone capture at 16 kHz mono using sounddevice."""
from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000


class Recorder:
    """Records mic audio into memory and exposes a live RMS level (0..1)."""

    def __init__(self, device_index: int | None = None):
        self.device_index = device_index
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self.level = 0.0  # smoothed RMS, read by the overlay animation
        self.recording = False

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        with self._lock:
            self._chunks.append(indata.copy())
        rms = float(np.sqrt(np.mean(np.square(indata)))) if frames else 0.0
        # Smooth and scale so quiet speech still moves the meter.
        target = min(1.0, rms * 12.0)
        self.level += (target - self.level) * 0.4

    def start(self) -> None:
        if self.recording:
            return
        with self._lock:
            self._chunks = []
        self.level = 0.0
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=self.device_index,
            callback=self._callback,
            blocksize=1024,
        )
        self._stream.start()
        self.recording = True

    def snapshot(self) -> np.ndarray:
        """Return a copy of the audio captured so far, without stopping."""
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._chunks, axis=0).flatten().astype(np.float32)

    def stop(self) -> np.ndarray:
        """Stop recording and return the captured audio as a float32 mono array."""
        self.recording = False
        self.level = 0.0
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks, axis=0).flatten().astype(np.float32)
            self._chunks = []
        return audio

    @staticmethod
    def list_devices() -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    out.append((i, dev["name"]))
        except Exception:
            pass
        return out
