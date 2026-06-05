"""Voice Activity Detection - Phát hiện giọng nói sử dụng Silero VAD"""

import numpy as np
import torch
import threading
from typing import Optional, List
from loguru import logger
from dataclasses import dataclass, field

from ..config import VADConfig


@dataclass
class VADSession:
    """
    Per-connection VAD state.

    Mỗi WebSocket connection hoặc pipeline worker tạo 1 session riêng.
    Hoàn toàn không share giữa các connections → không cần lock.

    Thay thế toàn bộ instance state cũ (self._is_speech, self._speech_buffer, ...).
    """
    is_speech: bool = False
    speech_buffer: List[np.ndarray] = field(default_factory=list)
    silence_frames: int = 0
    speech_frames: int = 0


class VoiceActivityDetector:
    """
    Silero VAD - Phát hiện giọng nói trong audio stream.
    Chỉ pass audio có giọng nói qua STT, bỏ qua silence/noise.
    Giảm 60-80% compute cho STT.

    ARCHITECTURE (sau refactor):
    ┌─────────────────────────────────────────────────────────┐
    │  Model weights   : load 1 lần, SHARED toàn bộ clients  │
    │  (ONNX stateless): read-only khi inference → thread-safe│
    │                                                         │
    │  VADSession      : per-connection, KHÔNG shared         │
    │  (inference state): tạo qua create_session()            │
    └─────────────────────────────────────────────────────────┘

    Trước:   1 instance VAD/connection  → N×RAM để load model
    Sau:     1 model shared + N session → 1×RAM, song song thực sự
    """

    def __init__(self, config: VADConfig):
        self.config = config
        self._model = None
        # Lock CHỈ dùng lúc load_model() để tránh double-load
        self._model_lock = threading.Lock()

    def load_model(self):
        """Load Silero VAD model (gọi 1 lần lúc startup)"""
        with self._model_lock:
            if self._model is not None:
                return  # Đã load rồi, bỏ qua
            logger.info("Loading Silero VAD model...")
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=True,
            )
            self._model = model
            self._get_speech_timestamps = utils[0]
            logger.info("Silero VAD loaded successfully")

    def create_session(self) -> VADSession:
        """
        Tạo VADSession mới cho 1 WebSocket connection / pipeline worker.

        Gọi 1 lần khi client connect hoặc pipeline khởi động.
        Thay thế reset() — tạo session mới = đã reset hoàn toàn.
        """
        return VADSession()

    def process_chunk(
        self,
        audio_chunk: np.ndarray,
        session: VADSession,
    ) -> Optional[np.ndarray]:
        """
        Xử lý 1 audio chunk (512 samples = 32ms @ 16kHz) với state của session cụ thể.

        KHÔNG dùng lock vì:
        - ONNX model inference là stateless / thread-safe
        - State hoàn toàn nằm trong `session` riêng của mỗi connection
        - Các connections không share state → không có race condition

        Args:
            audio_chunk: 512 samples PCM float32 @ 16kHz
            session:     VADSession của connection đang xử lý

        Returns:
            None  nếu đang silence hoặc câu nói chưa kết thúc
            np.ndarray (complete speech segment) khi phát hiện kết thúc câu
        """
        if self._model is None:
            self.load_model()

        if len(audio_chunk) < 512:
            return None

        # ONNX model inference — stateless, không cần lock
        audio_tensor = torch.from_numpy(audio_chunk[:512]).float()
        speech_prob  = self._model(audio_tensor, 16000).item()
        is_speech    = speech_prob >= self.config.threshold

        # Cập nhật state trong session riêng của connection này
        if is_speech:
            session.speech_frames  += 1
            session.silence_frames  = 0
            session.speech_buffer.append(audio_chunk)
            session.is_speech = True

        else:
            session.silence_frames += 1

            if session.is_speech:
                # Thêm padding sau khi dừng nói
                pad_frames = max(1, self.config.speech_pad_ms // 32)  # 32ms/frame

                if session.silence_frames <= pad_frames:
                    session.speech_buffer.append(audio_chunk)
                else:
                    # Kết thúc speech segment
                    min_frames = max(1, self.config.min_speech_duration_ms // 32)

                    if session.speech_frames >= min_frames:
                        # Đủ dài → trả về speech segment hoàn chỉnh
                        result = np.concatenate(session.speech_buffer)
                        # Reset session state (giữ session object, chỉ clear data)
                        session.speech_buffer  = []
                        session.speech_frames  = 0
                        session.silence_frames = 0
                        session.is_speech      = False
                        return result
                    else:
                        # Quá ngắn → noise, bỏ qua
                        session.speech_buffer  = []
                        session.speech_frames  = 0
                        session.is_speech      = False

        return None

    def is_speaking(self, session: VADSession) -> bool:
        """Kiểm tra session hiện tại có đang nhận dạng giọng nói không"""
        return session.is_speech
    
    @property
    def is_loaded(self) -> bool:
        return self._model is not None
