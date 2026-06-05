"""Audio Capture Module - Bắt âm thanh từ system audio, mic, hoặc app cụ thể"""

import numpy as np
import sounddevice as sd
import threading
import queue
from typing import Optional, Callable
from loguru import logger

from ..config import AudioConfig


class AudioCapture:
    """
    Capture audio từ nhiều nguồn:
    - System audio (WASAPI Loopback) - nghe mọi thứ từ máy tính
    - Microphone - thu giọng nói trực tiếp
    """

    def __init__(self, config: AudioConfig, on_audio: Optional[Callable] = None):
        self.config = config
        self.on_audio = on_audio
        self.audio_queue: queue.Queue = queue.Queue()
        self._running = False
        self._stream: Optional[sd.InputStream] = None
        self._thread: Optional[threading.Thread] = None

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback khi có audio data mới"""
        if status:
            logger.warning(f"Audio callback status: {status}")

        # Convert to mono float32 normalized
        audio_data = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
        audio_data = audio_data.flatten().astype(np.float32)

        self.audio_queue.put(audio_data)

        if self.on_audio:
            self.on_audio(audio_data)

    def get_loopback_device(self) -> Optional[int]:
        """Tìm WASAPI Loopback device để capture system audio"""
        try:
            import pyaudiowpatch as pyaudio

            p = pyaudio.PyAudio()
            wasapi_info = None

            # Tìm WASAPI host API
            for i in range(p.get_host_api_count()):
                api_info = p.get_host_api_info_by_index(i)
                if "WASAPI" in api_info["name"]:
                    wasapi_info = api_info
                    break

            if wasapi_info is None:
                logger.error("WASAPI not found")
                return None

            # Tìm default loopback device
            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

            if not default_speakers["isLoopbackDevice"]:
                # Tìm loopback device tương ứng
                for i in range(p.get_device_count()):
                    dev = p.get_device_info_by_index(i)
                    if dev.get("isLoopbackDevice") and dev["name"].startswith(
                        default_speakers["name"].split(" (")[0]
                    ):
                        p.terminate()
                        return dev["index"]

            p.terminate()
            return default_speakers["index"]

        except ImportError:
            logger.warning("pyaudiowpatch not available, falling back to sounddevice")
            return None
        except Exception as e:
            logger.error(f"Error finding loopback device: {e}")
            return None

    def list_devices(self) -> list:
        """Liệt kê tất cả audio devices"""
        devices = sd.query_devices()
        return [
            {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]

    def start(self):
        """Bắt đầu capture audio"""
        if self._running:
            logger.warning("Audio capture already running")
            return

        self._running = True

        if self.config.mode == "system":
            self._start_system_capture()
        elif self.config.mode == "mic":
            self._start_mic_capture()
        else:
            self._start_mic_capture()  # fallback

        logger.info(f"Audio capture started (mode={self.config.mode})")

    def _start_system_capture(self):
        """Capture system audio via WASAPI Loopback"""
        try:
            import pyaudiowpatch as pyaudio

            p = pyaudio.PyAudio()

            # Tìm WASAPI loopback
            wasapi_info = None
            for i in range(p.get_host_api_count()):
                api_info = p.get_host_api_info_by_index(i)
                if "WASAPI" in api_info["name"]:
                    wasapi_info = api_info
                    break

            if wasapi_info is None:
                raise RuntimeError("WASAPI not available")

            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

            # Tìm loopback device
            loopback_device = None
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice") and default_speakers["name"] in dev["name"]:
                    loopback_device = dev
                    break

            if loopback_device is None:
                raise RuntimeError("Loopback device not found")

            logger.info(f"Using loopback: {loopback_device['name']}")

            def loopback_thread():
                stream = p.open(
                    format=pyaudio.paFloat32,
                    channels=loopback_device["maxInputChannels"],
                    rate=int(loopback_device["defaultSampleRate"]),
                    input=True,
                    input_device_index=loopback_device["index"],
                    frames_per_buffer=self.config.chunk_size,
                )

                import scipy.signal as signal

                while self._running:
                    try:
                        data = stream.read(self.config.chunk_size, exception_on_overflow=False)
                        audio_np = np.frombuffer(data, dtype=np.float32)

                        # Convert to mono
                        n_channels = loopback_device["maxInputChannels"]
                        if n_channels > 1:
                            audio_np = audio_np.reshape(-1, n_channels).mean(axis=1)

                        # Resample to 16kHz if needed
                        orig_rate = int(loopback_device["defaultSampleRate"])
                        if orig_rate != self.config.sample_rate:
                            num_samples = int(len(audio_np) * self.config.sample_rate / orig_rate)
                            audio_np = signal.resample(audio_np, num_samples).astype(np.float32)

                        self.audio_queue.put(audio_np)
                        if self.on_audio:
                            self.on_audio(audio_np)

                    except Exception as e:
                        if self._running:
                            logger.error(f"Loopback read error: {e}")
                        break

                stream.stop_stream()
                stream.close()
                p.terminate()

            self._thread = threading.Thread(target=loopback_thread, daemon=True)
            self._thread.start()

        except ImportError:
            logger.warning("pyaudiowpatch not available, falling back to mic capture")
            self._start_mic_capture()
        except Exception as e:
            logger.error(f"System capture failed: {e}, falling back to mic")
            self._start_mic_capture()

    def _start_mic_capture(self):
        """Capture từ microphone via sounddevice"""
        device = None if self.config.device == "default" else self.config.device

        self._stream = sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype="float32",
            blocksize=self.config.chunk_size,
            device=device,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self):
        """Dừng capture"""
        self._running = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

        logger.info("Audio capture stopped")

    def get_chunk(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Lấy audio chunk từ queue"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def is_running(self) -> bool:
        return self._running
