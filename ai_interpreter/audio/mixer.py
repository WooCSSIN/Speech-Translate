"""Audio Mixer - Trộn giọng thuyết minh với audio gốc"""

import numpy as np
import sounddevice as sd
import threading
import queue
from typing import Optional
from loguru import logger

from ..config import MixerConfig


class AudioMixer:
    """
    Audio Mixer - Phát giọng thuyết minh AI.
    
    Modes:
    - narration: Giảm volume gốc, phát giọng Việt lên trên (thuyết minh)
    - dubbing: Mute gốc, chỉ phát giọng Việt (lồng tiếng)
    - bilingual: Giữ nguyên gốc, phát giọng Việt song song
    """

    def __init__(self, config: MixerConfig):
        self.config = config
        self._playback_queue: queue.Queue = queue.Queue()
        self._running = False
        self._stream: Optional[sd.OutputStream] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Bắt đầu audio output stream"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()
        logger.info(f"Audio mixer started (mode={self.config.mode})")

    def _playback_loop(self):
        """Loop phát audio từ queue"""
        while self._running:
            try:
                audio = self._playback_queue.get(timeout=0.5)
                if audio is not None and len(audio) > 0:
                    self._play_audio(audio)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Playback error: {e}")

    def _play_audio(self, audio: np.ndarray):
        """Phát audio ra speaker"""
        try:
            # Adjust volume
            audio = audio * self.config.tts_volume

            # Clip to prevent distortion
            audio = np.clip(audio, -1.0, 1.0)

            # Play using sounddevice (blocking within thread)
            sd.play(audio, samplerate=16000, blocking=True)

        except Exception as e:
            logger.error(f"Play audio error: {e}")

    def queue_audio(self, audio: np.ndarray):
        """Thêm audio vào queue để phát"""
        if audio is not None and len(audio) > 0:
            self._playback_queue.put(audio)

    def stop(self):
        """Dừng mixer"""
        self._running = False

        # Clear queue
        while not self._playback_queue.empty():
            try:
                self._playback_queue.get_nowait()
            except queue.Empty:
                break

        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

        sd.stop()
        logger.info("Audio mixer stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def queue_size(self) -> int:
        return self._playback_queue.qsize()
