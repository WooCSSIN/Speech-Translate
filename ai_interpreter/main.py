"""
AI Realtime Interpreter - Main Entry Point

Chạy: python -m ai_interpreter.main

Phiên dịch viên AI realtime:
- Bắt âm thanh từ máy tính (system audio / mic)
- Nhận dạng giọng nói (Faster-Whisper)
- Dịch sang tiếng Việt (Google Translate / NLLB)
- Đọc bằng giọng AI tiếng Việt (Edge TTS)
"""

import sys
import signal
from loguru import logger

from .config import InterpreterConfig
from .pipeline.orchestrator import InterpreterPipeline


def setup_logging():
    """Setup loguru logging"""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
        level="INFO",
    )


def main():
    """Main entry point"""
    setup_logging()

    logger.info("🎙️ AI Realtime Interpreter v0.1.0")
    logger.info("=" * 50)

    # Configuration
    config = InterpreterConfig()

    # Cho phép chọn mode qua command line
    if "--mic" in sys.argv:
        config.audio.mode = "mic"
        logger.info("Mode: Microphone input")
    else:
        config.audio.mode = "system"
        logger.info("Mode: System audio (WASAPI Loopback)")

    if "--cpu" in sys.argv:
        config.stt.device = "cpu"
        config.stt.compute_type = "int8"

    # Callbacks để hiển thị kết quả trên console
    def on_transcription(text, lang):
        print(f"  🎤 [{lang}] {text}")

    def on_translation(text):
        print(f"  🇻🇳 {text}")

    # Tạo pipeline
    pipeline = InterpreterPipeline(config)
    pipeline.on_transcription = on_transcription
    pipeline.on_translation = on_translation

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        logger.info("\nStopping...")
        pipeline.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Start
    try:
        pipeline.start()

        print("\n" + "=" * 50)
        print("  AI Interpreter đang chạy!")
        print("  Nhấn Ctrl+C để dừng.")
        print("=" * 50 + "\n")

        # Keep running
        while pipeline.is_running:
            try:
                signal.pause()
            except AttributeError:
                # Windows doesn't have signal.pause()
                import time
                time.sleep(0.5)

    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
