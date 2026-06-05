"""TTS Engine - Giọng thuyết minh AI đa ngôn ngữ"""

import asyncio
import io
import threading
import numpy as np
from typing import Optional
from loguru import logger

from ..config import TTSConfig


class TTSEngine:
    """
    Text-to-Speech Engine - Tạo giọng thuyết minh đa ngôn ngữ.

    Tối ưu latency:
    - Event loop chạy nền liên tục (không tạo lại mỗi câu)
    - Decode MP3 trong memory (không ghi file tạm)

    Hỗ trợ:
    - Edge TTS (Microsoft, online, giọng tự nhiên)
    - Piper TTS (offline, nhẹ) - TODO
    - XTTS v2 (voice clone) - TODO
    """

    def __init__(self, config: TTSConfig):
        self.config = config
        self._lock = threading.Lock()

        # Persistent event loop chạy trong thread riêng
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_event_loop()

    def _start_event_loop(self):
        """Khởi tạo event loop chạy nền — tránh tạo lại mỗi lần synthesize"""
        self._loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

    def synthesize(self, text: str) -> Optional[np.ndarray]:
        """
        Tổng hợp giọng nói từ text.

        Args:
            text: Text cần đọc (đã dịch)

        Returns:
            Audio numpy array (float32, 16kHz mono) hoặc None nếu lỗi
        """
        if not text or not text.strip():
            return None

        try:
            if self.config.engine == "edge":
                return self._synthesize_edge(text)
            elif self.config.engine == "piper":
                return self._synthesize_piper(text)
            elif self.config.engine == "xtts":
                return self._synthesize_xtts(text)
            else:
                return self._synthesize_edge(text)
        except Exception as e:
            logger.error(f"TTS error ({self.config.engine}): {e}")
            return None

    def _synthesize_edge(self, text: str) -> Optional[np.ndarray]:
        """Microsoft Edge TTS - Giọng tự nhiên, cần internet"""
        import edge_tts

        async def _generate():
            communicate = edge_tts.Communicate(
                text,
                voice=self.config.voice,
                rate=self._speed_to_rate_string(),
            )
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            return audio_data

        # Submit coroutine vào event loop đang chạy nền
        future = asyncio.run_coroutine_threadsafe(_generate(), self._loop)
        audio_bytes = future.result(timeout=15)

        if not audio_bytes:
            return None

        return self._decode_mp3(audio_bytes)

    def _decode_mp3(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        """Decode MP3 bytes → numpy 16kHz mono float32 (trong memory)"""
        try:
            # Thử decode bằng soundfile trước (nhanh)
            import soundfile as sf
            audio_io = io.BytesIO(audio_bytes)
            audio_np, sample_rate = sf.read(audio_io, dtype="float32")
        except Exception:
            # Fallback: dùng av (PyAV) decode MP3 trong memory
            try:
                import av
                audio_io = io.BytesIO(audio_bytes)
                container = av.open(audio_io, format="mp3")
                frames = []
                sample_rate = 24000
                for frame in container.decode(audio=0):
                    sample_rate = frame.sample_rate
                    arr = frame.to_ndarray()
                    frames.append(arr.flatten())
                container.close()
                if not frames:
                    return None
                audio_np = np.concatenate(frames).astype(np.float32)
                # Normalize nếu là int
                if audio_np.max() > 1.0 or audio_np.min() < -1.0:
                    audio_np = audio_np / 32768.0
            except Exception as e:
                logger.error(f"MP3 decode failed: {e}")
                return None

        # Convert to mono
        if audio_np.ndim > 1:
            audio_np = audio_np.mean(axis=1)
        audio_np = audio_np.astype(np.float32)

        # Resample to 16kHz nếu cần
        if sample_rate != 16000:
            import scipy.signal as signal
            num_samples = int(len(audio_np) * 16000 / sample_rate)
            audio_np = signal.resample(audio_np, num_samples).astype(np.float32)

        return audio_np

    def _synthesize_piper(self, text: str) -> Optional[np.ndarray]:
        """Piper TTS - Offline (TODO)"""
        logger.warning("Piper TTS chưa implement, dùng Edge TTS")
        return self._synthesize_edge(text)

    def _synthesize_xtts(self, text: str) -> Optional[np.ndarray]:
        """XTTS v2 - Voice clone (TODO)"""
        logger.warning("XTTS chưa implement, dùng Edge TTS")
        return self._synthesize_edge(text)

    def _speed_to_rate_string(self) -> str:
        """Convert speed float → Edge TTS rate string"""
        percent = int((self.config.speed - 1.0) * 100)
        return f"+{percent}%" if percent >= 0 else f"{percent}%"

    def shutdown(self):
        """Dừng event loop khi thoát app"""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
