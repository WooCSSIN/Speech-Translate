"""Pipeline Orchestrator - Điều phối pipeline realtime với worker song song"""

import threading
import time
import queue
import numpy as np
from typing import Optional, Callable
from loguru import logger

from ..config import InterpreterConfig
from ..audio.capture import AudioCapture
from ..audio.vad import VoiceActivityDetector
from ..audio.mixer import AudioMixer
from ..stt.engine import STTEngine
from ..translation.engine import TranslationEngine
from ..tts.engine import TTSEngine
from ..context.router import TranslationRouter


class InterpreterPipeline:
    """
    Pipeline Orchestrator với kiến trúc multi-stage song song.

    Flow: Capture → VAD → [STT Queue] → STT Worker → [TL Queue]
          → TL Worker → [TTS Queue] → TTS Worker → [Play Queue] → Mixer

    Mỗi stage chạy trên thread riêng → các câu được xử lý song song,
    giảm độ trễ đáng kể so với xử lý tuần tự.
    """

    def __init__(self, config: InterpreterConfig):
        self.config = config

        # Components
        self.capture = AudioCapture(config.audio)
        self.vad = VoiceActivityDetector(config.vad)
        self.stt = STTEngine(config.stt)
        self.translator = TranslationEngine(config.translation)
        self.tts = TTSEngine(config.tts)
        self.mixer = AudioMixer(config.mixer)

        # Context-aware translation router (Capability A)
        self.router = TranslationRouter(self.translator, enable_context=True)

        # Inter-stage queues (bounded để tránh dồn ứ quá nhiều)
        self._stt_queue: queue.Queue = queue.Queue(maxsize=10)
        self._tl_queue: queue.Queue = queue.Queue(maxsize=10)
        self._tts_queue: queue.Queue = queue.Queue(maxsize=10)

        # State
        self._running = False
        self._threads: list = []

        # Callbacks
        self.on_transcription: Optional[Callable[[str, str], None]] = None
        self.on_translation: Optional[Callable[[str], None]] = None
        self.on_tts_start: Optional[Callable[[], None]] = None
        self.on_tts_done: Optional[Callable[[], None]] = None
        self.on_domain_change: Optional[Callable] = None  # (DomainProfile)

        # Stats
        self._stats = {
            "speech_segments": 0,
            "translations": 0,
            "total_latency_ms": 0,
        }

    def start(self):
        """Khởi động toàn bộ pipeline"""
        if self._running:
            logger.warning("Pipeline already running")
            return

        logger.info("=" * 50)
        logger.info("Starting AI Interpreter Pipeline (parallel)...")
        logger.info(f"  Audio: {self.config.audio.mode}")
        logger.info(f"  STT: Faster-Whisper {self.config.stt.model_size} ({self.config.stt.device})")
        logger.info(f"  Translation: {self.config.translation.engine} "
                    f"({self.config.translation.source_lang} → {self.config.translation.target_lang})")
        logger.info(f"  TTS: {self.config.tts.engine} ({self.config.tts.voice})")
        logger.info("=" * 50)

        # Load models
        logger.info("Loading models...")
        self.vad.load_model()
        self.stt.load_model()

        # Start components
        self.mixer.start()
        self.capture.start()

        # Start worker threads
        self._running = True
        self._threads = [
            threading.Thread(target=self._capture_vad_loop, daemon=True, name="capture-vad"),
            threading.Thread(target=self._stt_worker, daemon=True, name="stt"),
            threading.Thread(target=self._translation_worker, daemon=True, name="translation"),
            threading.Thread(target=self._tts_worker, daemon=True, name="tts"),
        ]
        for t in self._threads:
            t.start()

        logger.info("✓ AI Interpreter is RUNNING. Listening...")

    # ---------- Stage 1: Capture + VAD ----------
    def _capture_vad_loop(self):
        """Capture audio + VAD → đẩy speech segment vào STT queue"""
        audio_buffer = np.array([], dtype=np.float32)
        frame_size   = 512  # Silero VAD frame size
        
        frames_since_last_partial = 0
        PARTIAL_INTERVAL_FRAMES = 15  # ~0.48s

        # Tạo VADSession riêng cho pipeline worker này
        vad_session = self.vad.create_session()

        while self._running:
            try:
                chunk = self.capture.get_chunk(timeout=0.3)
                if chunk is None:
                    continue

                audio_buffer = np.concatenate([audio_buffer, chunk])

                while len(audio_buffer) >= frame_size:
                    frame = audio_buffer[:frame_size]
                    audio_buffer = audio_buffer[frame_size:]

                    speech_segment = self.vad.process_chunk(frame, vad_session)
                    
                    # --- Xử lý Partial Result ---
                    if vad_session.is_speech:
                        frames_since_last_partial += 1
                        if frames_since_last_partial >= PARTIAL_INTERVAL_FRAMES:
                            if vad_session.speech_buffer:
                                partial_audio = np.concatenate(vad_session.speech_buffer)
                                try:
                                    self._stt_queue.put_nowait((partial_audio, time.time(), False))
                                except queue.Full:
                                    pass
                            frames_since_last_partial = 0
                    else:
                        frames_since_last_partial = 0

                    # --- Xử lý Final Result ---
                    if speech_segment is not None:
                        self._stats["speech_segments"] += 1
                        try:
                            self._stt_queue.put_nowait((speech_segment, time.time(), True))
                        except queue.Full:
                            logger.warning("STT queue full, dropping segment")

            except Exception as e:
                if self._running:
                    logger.error(f"Capture/VAD error: {e}")
                    time.sleep(0.3)

    # ---------- Stage 2: STT Worker ----------
    def _stt_worker(self):
        """Audio segment → Text"""
        while self._running:
            try:
                segment, t_start, is_final = self._stt_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                # transcribe giờ trả về danh sách các chunks (Smart Chunker)
                chunks, lang = self.stt.transcribe(segment)
                for text_chunk in chunks:
                    if text_chunk:
                        if self.on_transcription:
                            self.on_transcription(text_chunk, lang, is_final)
                        try:
                            # Đẩy từng cụm nhỏ (chunk) vào queue dịch để stream mượt hơn
                            self._tl_queue.put_nowait((text_chunk, lang, t_start, is_final))
                        except queue.Full:
                            logger.warning("Translation queue full, dropping chunk")
            except Exception as e:
                logger.error(f"STT worker error: {e}")

    # ---------- Stage 3: Translation Worker ----------
    def _translation_worker(self):
        """Text → Translated text (context-aware via router)"""
        while self._running:
            try:
                text, lang, t_start, is_final = self._tl_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                # Dùng context-aware router thay vì translator trực tiếp
                translated, profile = self.router.translate(text, source_lang=lang)

                # Thông báo domain change cho UI
                if self.on_domain_change:
                    self.on_domain_change(profile)

                if translated:
                    if self.on_translation:
                        self.on_translation(translated, is_final)
                    
                    if is_final:
                        self._stats["translations"] += 1
                        try:
                            self._tts_queue.put_nowait((translated, t_start))
                        except queue.Full:
                            logger.warning("TTS queue full, dropping")
            except Exception as e:
                logger.error(f"Translation worker error: {e}")

    # ---------- Stage 4: TTS Worker ----------
    def _tts_worker(self):
        """Vietnamese text → Audio → Play"""
        while self._running:
            try:
                text, t_start = self._tts_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                if self.on_tts_start:
                    self.on_tts_start()

                tts_audio = self.tts.synthesize(text)

                if self.on_tts_done:
                    self.on_tts_done()

                if tts_audio is not None:
                    self.mixer.queue_audio(tts_audio)

                # Stats
                latency = (time.time() - t_start) * 1000
                self._stats["total_latency_ms"] += latency
                logger.info(f"[{latency:.0f}ms total] → {text}")

            except Exception as e:
                logger.error(f"TTS worker error: {e}")

    def stop(self):
        """Dừng toàn bộ pipeline"""
        logger.info("Stopping AI Interpreter Pipeline...")
        self._running = False

        self.capture.stop()
        self.mixer.stop()
        # VAD session tự hủy khi _capture_vad_loop kết thúc
        # Không cần gọi reset() nữa vì state nằm trong session riêng
        self.router.reset()

        for t in self._threads:
            t.join(timeout=2)
        self._threads = []

        # Clear queues
        for q in [self._stt_queue, self._tl_queue, self._tts_queue]:
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break

        logger.info("Pipeline stopped.")
        self._print_stats()

    def _print_stats(self):
        logger.info("--- Session Stats ---")
        logger.info(f"  Speech segments: {self._stats['speech_segments']}")
        logger.info(f"  Translations: {self._stats['translations']}")
        if self._stats["translations"] > 0:
            avg = self._stats["total_latency_ms"] / self._stats["translations"]
            logger.info(f"  Avg latency: {avg:.0f}ms")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return self._stats.copy()
