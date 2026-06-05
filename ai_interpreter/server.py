"""
FastAPI Server cho AI Interpreter Backend.

Chạy trong Docker, xử lý:
- STT (Faster-Whisper)
- Translation (Google/NLLB)
- TTS (Edge TTS)

Client gửi audio qua WebSocket → Server trả về text + audio dịch.
"""

import asyncio
import io
import json
import dataclasses
import numpy as np
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import base64

from .config import InterpreterConfig, STTConfig, TranslationConfig, TTSConfig
from .audio.vad import VoiceActivityDetector
from .stt.engine import STTEngine
from .translation.engine import TranslationEngine
from .tts.engine import TTSEngine

app = FastAPI(
    title="AI Realtime Interpreter API",
    description="Backend API cho hệ thống phiên dịch AI realtime",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Global singletons (model nặng, load 1 lần) ──────────────────────────────
_global_config = InterpreterConfig()
_shared_vad = VoiceActivityDetector(_global_config.vad)   # Model VAD dùng chung
stt_engine   = STTEngine(_global_config.stt)
translator   = TranslationEngine(_global_config.translation)
tts_engine   = TTSEngine(_global_config.tts)
# ─────────────────────────────────────────────────────────────────────────────


@app.on_event("startup")
async def startup():
    """Load models on startup"""
    logger.info("Loading AI models...")
    _shared_vad.load_model()
    stt_engine.load_model()
    logger.info("Models loaded successfully!")


@app.get("/")
async def root():
    return {"status": "running", "service": "AI Realtime Interpreter", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "models": {
            "vad": _shared_vad.is_loaded,
            "stt": stt_engine.is_loaded,
        }
    }


@app.get("/config")
async def get_config():
    return {
        "stt_model":          _global_config.stt.model_size,
        "stt_device":         _global_config.stt.device,
        "translation_engine": _global_config.translation.engine,
        "source_lang":        _global_config.translation.source_lang,
        "target_lang":        _global_config.translation.target_lang,
        "tts_engine":         _global_config.tts.voice,
        "tts_voice":          _global_config.tts.voice,
    }


@app.post("/translate")
async def translate_text(data: dict):
    """Dịch text"""
    text   = data.get("text", "")
    source = data.get("source_lang", _global_config.translation.source_lang)
    target = data.get("target_lang", _global_config.translation.target_lang)

    if not text:
        return {"error": "No text provided"}

    result = translator.translate(text, source_lang=source)
    return {"original": text, "translated": result, "source": source, "target": target}


@app.post("/tts")
async def text_to_speech(data: dict):
    """Tạo audio từ text"""
    text = data.get("text", "")
    if not text:
        return {"error": "No text provided"}

    audio = tts_engine.synthesize(text)
    if audio is None:
        return {"error": "TTS failed"}

    audio_bytes = (audio * 32767).astype(np.int16).tobytes()
    audio_b64   = base64.b64encode(audio_bytes).decode("utf-8")

    return {
        "audio":       audio_b64,
        "sample_rate": 16000,
        "duration":    len(audio) / 16000,
        "format":      "int16_pcm",
    }


@app.websocket("/ws/interpret")
async def websocket_interpret(websocket: WebSocket):
    """
    WebSocket endpoint cho realtime interpretation.

    FIX 1: Per-connection config  → tránh race condition giữa nhiều client.
    FIX 2: Shared VAD model       → tiết kiệm RAM, mỗi conn chỉ giữ state riêng.
    FIX 3: Input validation       → try/except bọc toàn bộ decode audio.
    """
    await websocket.accept()
    client_id = id(websocket)
    logger.info(f"[{client_id}] WebSocket client connected")

    # FIX 1: Mỗi connection có bản sao config riêng → không shared, không race condition
    conn_config = InterpreterConfig()
    conn_config.translation.source_lang = _global_config.translation.source_lang
    conn_config.translation.target_lang = _global_config.translation.target_lang

    # FIX 2: Dùng shared VAD *model* + per-connection VADSession
    # create_session() thay thế reset() — tạo mới = đã reset hoàn toàn
    vad_session = _shared_vad.create_session()

    audio_buffer = np.array([], dtype=np.float32)
    frame_size = 512  # Silero VAD frame size
    frames_since_last_partial = 0
    PARTIAL_INTERVAL_FRAMES = 15  # ~0.48s (15 * 32ms)

    try:
        while True:
            data = await websocket.receive_text()

            # FIX 3: Validate JSON trước
            try:
                message = json.loads(data)
            except json.JSONDecodeError as e:
                logger.warning(f"[{client_id}] Invalid JSON received: {e}")
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
                continue

            msg_type = message.get("type")

            if msg_type == "audio":
                # FIX 3: Validate và decode audio an toàn
                try:
                    audio_b64   = message["data"]
                    audio_bytes = base64.b64decode(audio_b64)
                    audio_chunk = np.frombuffer(audio_bytes, dtype=np.float32).copy()
                except (KeyError, ValueError, Exception) as e:
                    logger.warning(f"[{client_id}] Audio decode error: {e}")
                    await websocket.send_text(json.dumps({"type": "error", "message": "Invalid audio data"}))
                    continue

                # Accumulate buffer
                audio_buffer = np.concatenate([audio_buffer, audio_chunk])

                # Process frames qua VAD (shared model, per-connection buffer)
                while len(audio_buffer) >= frame_size:
                    frame        = audio_buffer[:frame_size]
                    audio_buffer = audio_buffer[frame_size:]

                    try:
                        # Truyền vad_session riêng — không shared, không race condition
                        speech_segment = _shared_vad.process_chunk(frame, vad_session)
                    except Exception as e:
                        logger.error(f"[{client_id}] VAD error: {e}")
                        continue

                    # Xử lý Partial Result (Streaming)
                    if vad_session.is_speech:
                        frames_since_last_partial += 1
                        if frames_since_last_partial >= PARTIAL_INTERVAL_FRAMES:
                            if vad_session.speech_buffer:
                                partial_audio = np.concatenate(vad_session.speech_buffer)
                                result = await asyncio.to_thread(
                                    process_speech_segment, partial_audio, conn_config, False
                                )
                                if result:
                                    await websocket.send_text(json.dumps(result))
                            frames_since_last_partial = 0
                    else:
                        frames_since_last_partial = 0

                    # Xử lý Final Result (Chốt câu)
                    if speech_segment is not None:
                        result = await asyncio.to_thread(
                            process_speech_segment, speech_segment, conn_config, True
                        )
                        if result:
                            await websocket.send_text(json.dumps(result))

            elif msg_type == "config":
                # FIX 1: Cập nhật conn_config (bản sao riêng), không đụng global
                if "source_lang" in message:
                    conn_config.translation.source_lang = message["source_lang"]
                if "target_lang" in message:
                    conn_config.translation.target_lang = message["target_lang"]
                logger.info(f"[{client_id}] Config updated: "
                            f"{conn_config.translation.source_lang} → {conn_config.translation.target_lang}")
                await websocket.send_text(json.dumps({"type": "config_updated"}))

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            else:
                logger.debug(f"[{client_id}] Unknown message type: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"[{client_id}] WebSocket client disconnected")
    except Exception as e:
        logger.error(f"[{client_id}] WebSocket error: {e}")


def process_speech_segment(audio: np.ndarray, conn_config: InterpreterConfig, is_final: bool = True) -> Optional[dict]:
    """
    Xử lý speech segment: STT → Translate → TTS

    FIX 1: Nhận conn_config (per-connection) thay vì dùng global config.
    """
    import time
    start = time.time()

    # STT — trả về list[str] chunks (Smart Chunker)
    try:
        chunks, lang = stt_engine.transcribe(audio)
        text = " ".join(chunks).strip()
    except Exception as e:
        logger.error(f"STT failed: {e}")
        return None

    if not text:
        return None

    # Translation — dùng config riêng của connection
    try:
        translated = translator.translate(
            text,
            source_lang=lang or conn_config.translation.source_lang
        )
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        translated = text  # Fallback: trả text gốc, không crash pipeline

    if not translated:
        return None

    # TTS (chỉ chạy khi is_final = True để tránh nói ngắc ngứ)
    tts_audio = None
    if is_final:
        try:
            tts_audio = tts_engine.synthesize(translated)
        except Exception as e:
            logger.error(f"TTS failed (non-fatal): {e}")

    result = {
        "type":        "interpretation",
        "original":    text,
        "translated":  translated,
        "source_lang": lang or conn_config.translation.source_lang,
        "target_lang": conn_config.translation.target_lang,
        "is_final":    is_final,
        "latency_ms":  int((time.time() - start) * 1000),
    }

    if is_final and tts_audio is not None:
        audio_bytes      = (tts_audio * 32767).astype(np.int16).tobytes()
        result["audio"]              = base64.b64encode(audio_bytes).decode("utf-8")
        result["audio_sample_rate"]  = 16000
        result["audio_duration"]     = len(tts_audio) / 16000

    prefix = "[FINAL]" if is_final else "[PARTIAL]"
    logger.info(f"[{result['latency_ms']}ms] {prefix} {text} → {translated}")
    return result
