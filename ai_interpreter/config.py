"""Configuration for AI Interpreter"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class AudioConfig:
    """Audio capture configuration"""
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 512  # 32ms at 16kHz (Silero VAD frame size)
    format: str = "int16"
    device: str = "default"  # "default", "loopback", or device name
    mode: Literal["system", "mic", "app"] = "system"


@dataclass
class VADConfig:
    """Voice Activity Detection configuration"""
    threshold: float = 0.5
    min_speech_duration_ms: int = 200
    min_silence_duration_ms: int = 150  # Ép chốt câu thần tốc để đẩy TTS siêu nhanh (Phrase-level)
    speech_pad_ms: int = 50


@dataclass
class ChunkerConfig:
    """Smart Chunker configuration"""
    max_chunk_duration: float = 4.0  # Cắt câu dài thành đoạn nhỏ hơn
    min_chunk_duration: float = 0.5  # seconds
    silence_threshold_ms: int = 350
    overlap_ms: int = 150


@dataclass
class STTConfig:
    """Speech-to-Text configuration"""
    model_size: str = "base"  # base nhanh hơn small, đủ tốt cho realtime
    device: str = "cuda"  # cuda or cpu
    compute_type: str = "float16"  # float16, int8
    language: str = "en"  # source language or "auto"
    beam_size: int = 1  # beam_size=1 nhanh hơn nhiều so với 5


@dataclass
class TranslationConfig:
    """Translation configuration"""
    engine: Literal["google", "nllb", "gpt"] = "google"
    source_lang: str = "en"
    target_lang: str = "vi"
    # NLLB specific
    nllb_model: str = "facebook/nllb-200-distilled-600M"


@dataclass
class TTSConfig:
    """Text-to-Speech configuration"""
    engine: Literal["edge", "piper", "xtts"] = "edge"
    voice: str = "vi-VN-HoaiMyNeural"  # Edge TTS Vietnamese female
    speed: float = 1.0
    # Piper specific
    piper_model: str = "vi_VN-vivos-x_low"


@dataclass
class MixerConfig:
    """Audio Mixer configuration"""
    mode: Literal["narration", "dubbing", "bilingual"] = "narration"
    original_volume: float = 0.3  # 30% for narration mode
    tts_volume: float = 1.0


@dataclass
class InterpreterConfig:
    """Main configuration combining all components"""
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    chunker: ChunkerConfig = field(default_factory=ChunkerConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    mixer: MixerConfig = field(default_factory=MixerConfig)
