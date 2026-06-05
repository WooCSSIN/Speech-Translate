"""Speech-to-Text Engine - Faster Whisper"""

import numpy as np
import threading
from typing import Optional, Tuple
from loguru import logger

from ..config import STTConfig


class STTEngine:
    """
    Faster-Whisper STT Engine.
    Chuyển audio thành text với GPU acceleration.
    """

    def __init__(self, config: STTConfig):
        self.config = config
        self._model = None
        self._lock = threading.Lock()

    def load_model(self):
        """Load Faster-Whisper model"""
        logger.info(f"Loading Faster-Whisper model: {self.config.model_size} "
                    f"(device={self.config.device}, compute={self.config.compute_type})")

        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self.config.model_size,
            device=self.config.device,
            compute_type=self.config.compute_type,
        )
        logger.info("Faster-Whisper model loaded successfully")

    def transcribe(self, audio: np.ndarray) -> Tuple[str, str]:
        """
        Transcribe audio segment thành text.
        
        Args:
            audio: numpy array float32, 16kHz mono
            
        Returns:
            Tuple[List[str], str]: Danh sách các câu/cụm từ (chunks) và ngôn ngữ.
        """
        if self._model is None:
            self.load_model()

        with self._lock:
            try:
                # Faster-whisper expects float32 audio
                if audio.dtype != np.float32:
                    audio = audio.astype(np.float32)

                # Transcribe
                language = None if self.config.language == "auto" else self.config.language

                segments, info = self._model.transcribe(
                    audio,
                    language=language,
                    beam_size=self.config.beam_size,
                    vad_filter=True,  # Bật lại VAD filter nội bộ của Whisper cho an toàn
                    vad_parameters=dict(min_silence_duration_ms=500),
                    word_timestamps=True, # Lấy timestamp từng từ để làm Smart Chunker
                    without_timestamps=False,
                )

                # Smart Chunker: Nhóm từ thành các cụm (clauses/sentences) dựa trên dấu câu
                chunks = []
                current_chunk = []
                
                for segment in segments:
                    if not segment.words:
                        continue
                        
                    for word_obj in segment.words:
                        word_text = word_obj.word.strip()
                        current_chunk.append(word_obj.word)
                        
                        # Tách chunk nếu gặp dấu câu kết thúc câu/mệnh đề
                        if word_text.endswith(('.', '?', '!', ',', '。', '？', '！', '，')):
                            chunk_text = "".join(current_chunk).strip()
                            if chunk_text:
                                chunks.append(chunk_text)
                            current_chunk = []

                # Add phần dư cuối cùng nếu có
                if current_chunk:
                    chunk_text = "".join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(chunk_text)

                detected_lang = info.language if info else self.config.language

                if chunks:
                    logger.debug(f"STT [{detected_lang}] Smart Chunks: {chunks}")

                return chunks, detected_lang

            except Exception as e:
                err_msg = str(e).lower()
                logger.error(f"STT error: {e}")
                
                # Fallback Model: Nếu lỗi liên quan đến Memory/OOM hoặc CUDA, thử hạ model xuống 'base'
                if ("memory" in err_msg or "cuda" in err_msg or "alloc" in err_msg) and self.config.model_size != "base":
                    logger.warning(f"VRAM/Memory error detected. Fallback from '{self.config.model_size}' to 'base' model...")
                    self._model = None # Giải phóng RAM/VRAM
                    import gc
                    gc.collect()
                    
                    self.config.model_size = "base"
                    try:
                        self.load_model()
                        logger.info("Successfully reloaded with 'base' fallback model. Skipping this chunk.")
                    except Exception as fallback_err:
                        logger.error(f"Fallback model failed to load: {fallback_err}")

                return [], self.config.language

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
