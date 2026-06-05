"""
Offline Model Manager (Req 8.4, 8.5, 8.7).

Quản lý mô hình AI on-device:
- Nạp model ONNX cho STT, Translation, TTS (Req 8.4)
- Tăng tốc GPU CUDA khi khả dụng (Req 8.5)
- Giới hạn VRAM <= 4GB trên RTX 3050 (Req 8.7)
- Thông báo lỗi nếu nạp thất bại (Req 8.6)

Mô hình offline khuyến nghị:
- STT: Faster-Whisper (đã có, chạy local)
- Translation: CTranslate2 NLLB hoặc OPUS-MT (ONNX)
- TTS: Piper TTS (ONNX, offline, nhẹ)
"""

import os
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ModelInfo:
    """Thông tin 1 model on-device."""
    name: str
    role: str  # stt / translation / tts
    format: str  # onnx / ctranslate2 / piper
    path: str  # đường dẫn thư mục/file model
    size_mb: float = 0.0
    vram_mb: float = 0.0  # ước tính VRAM cần
    loaded: bool = False


# Giới hạn VRAM cho RTX 3050 (Req 8.7)
MAX_VRAM_MB = 4096  # 4GB


class OfflineModelManager:
    """
    Quản lý model on-device cho chế độ offline.

    Đảm bảo:
    - Tổng VRAM không vượt 4GB (Req 8.7)
    - Dùng CUDA khi khả dụng (Req 8.5)
    - Thông báo lỗi rõ ràng khi load thất bại (Req 8.6)
    """

    def __init__(self, models_dir: Optional[str] = None):
        self.models_dir = models_dir or self._default_models_dir()
        self._models: Dict[str, ModelInfo] = {}
        self._total_vram_used: float = 0.0
        self._cuda_available: Optional[bool] = None

    def _default_models_dir(self) -> str:
        d = os.path.join(os.path.expanduser("~"), ".han_translate", "models")
        os.makedirs(d, exist_ok=True)
        return d

    def check_cuda(self) -> bool:
        """Kiểm tra CUDA khả dụng (Req 8.5)."""
        if self._cuda_available is None:
            try:
                import torch
                self._cuda_available = torch.cuda.is_available()
                if self._cuda_available:
                    gpu_name = torch.cuda.get_device_name(0)
                    vram = torch.cuda.get_device_properties(0).total_mem / 1024**2
                    logger.info(f"CUDA available: {gpu_name} ({vram:.0f}MB VRAM)")
            except Exception:
                self._cuda_available = False
        return self._cuda_available

    def can_load(self, vram_needed_mb: float) -> bool:
        """Kiểm tra có đủ VRAM để load model không (Req 8.7)."""
        return (self._total_vram_used + vram_needed_mb) <= MAX_VRAM_MB

    def register_model(self, model: ModelInfo) -> bool:
        """
        Đăng ký model vào manager.

        Returns False nếu vượt VRAM limit (Req 8.7).
        """
        if not self.can_load(model.vram_mb):
            logger.error(
                f"Không thể load model '{model.name}': "
                f"cần {model.vram_mb}MB VRAM, "
                f"đã dùng {self._total_vram_used}MB / {MAX_VRAM_MB}MB"
            )
            return False

        self._models[model.role] = model
        logger.info(f"Đăng ký model offline: {model.name} ({model.role}, {model.format})")
        return True

    def load_model(self, role: str) -> Tuple[bool, str]:
        """
        Nạp model theo role (stt/translation/tts).

        Returns (success, message). Req 8.6: thông báo lỗi rõ ràng.
        """
        model = self._models.get(role)
        if not model:
            return False, f"Chưa đăng ký model cho role '{role}'"

        if model.loaded:
            return True, "Model đã được nạp"

        # Kiểm tra file tồn tại
        if not os.path.exists(model.path):
            msg = f"Model '{model.name}' không tìm thấy tại: {model.path}"
            logger.error(msg)
            return False, msg

        # Kiểm tra VRAM (Req 8.7)
        if not self.can_load(model.vram_mb):
            msg = (
                f"Không đủ VRAM để load '{model.name}': "
                f"cần {model.vram_mb}MB, còn {MAX_VRAM_MB - self._total_vram_used:.0f}MB"
            )
            logger.error(msg)
            return False, msg

        # Verify integrity trước khi load (Req 11.3)
        from ..model_integrity import verify_or_register
        model_dir = os.path.dirname(model.path)
        model_file = os.path.basename(model.path)
        ok, integrity_msg = verify_or_register(model_dir, model_file, trust_on_first_use=True)
        if not ok:
            msg = f"Model '{model.name}' không qua kiểm tra toàn vẹn: {integrity_msg}"
            logger.error(msg)
            return False, msg

        # Đánh dấu loaded + cập nhật VRAM
        model.loaded = True
        self._total_vram_used += model.vram_mb
        logger.info(f"Đã nạp model: {model.name} (VRAM: {self._total_vram_used:.0f}/{MAX_VRAM_MB}MB)")
        return True, "OK"

    def get_model(self, role: str) -> Optional[ModelInfo]:
        return self._models.get(role)

    def unload_model(self, role: str):
        """Giải phóng model."""
        model = self._models.get(role)
        if model and model.loaded:
            model.loaded = False
            self._total_vram_used -= model.vram_mb
            logger.info(f"Đã giải phóng model: {model.name}")

    @property
    def vram_used(self) -> float:
        return self._total_vram_used

    @property
    def vram_available(self) -> float:
        return MAX_VRAM_MB - self._total_vram_used

    def list_models(self) -> list:
        return list(self._models.values())

    def get_status(self) -> dict:
        return {
            "cuda": self.check_cuda(),
            "vram_used_mb": self._total_vram_used,
            "vram_max_mb": MAX_VRAM_MB,
            "models": {
                role: {"name": m.name, "loaded": m.loaded, "vram_mb": m.vram_mb}
                for role, m in self._models.items()
            },
        }
