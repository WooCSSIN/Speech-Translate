"""
Offline Engine - Facade cho chế độ offline (Req 8.1-8.3).

Kết hợp:
- NetworkMonitor: phát hiện mất mạng
- OfflineModelManager: quản lý model on-device
- Auto-switch: tự chuyển sang offline khi mất mạng (Req 8.3)

Đảm bảo:
- Chế độ offline KHÔNG gửi dữ liệu ra ngoài (Req 8.2)
- Tự chuyển khi mất mạng + thông báo (Req 8.3)
"""

from typing import Optional, Callable
from loguru import logger

from .network_monitor import NetworkMonitor
from .model_manager import OfflineModelManager, ModelInfo


class OfflineEngine:
    """
    Quản lý chế độ offline cho Han Translate.

    Modes:
    - "auto": tự chuyển offline khi mất mạng (Req 8.3)
    - "always_offline": luôn dùng on-device (Req 8.1)
    - "always_online": luôn dùng cloud (bỏ qua offline)
    """

    def __init__(self, mode: str = "auto"):
        self.mode = mode
        self.model_manager = OfflineModelManager()
        self.network = NetworkMonitor(
            on_offline=self._on_network_lost,
            on_online=self._on_network_restored,
        )

        self._is_offline_active = (mode == "always_offline")

        # Callbacks cho UI
        self.on_mode_change: Optional[Callable[[bool, str], None]] = None  # (is_offline, reason)

    def start(self):
        """Khởi động network monitor."""
        if self.mode == "auto":
            self.network.start()
        elif self.mode == "always_offline":
            self._is_offline_active = True
            logger.info("Offline mode: ALWAYS ON (không gửi dữ liệu ra ngoài)")

    def _on_network_lost(self):
        """Callback khi mất mạng (Req 8.3)."""
        if self.mode == "auto" and not self._is_offline_active:
            self._is_offline_active = True
            reason = "Mất kết nối mạng - đã chuyển sang chế độ offline"
            logger.warning(reason)
            if self.on_mode_change:
                self.on_mode_change(True, reason)

    def _on_network_restored(self):
        """Callback khi có mạng lại."""
        if self.mode == "auto" and self._is_offline_active:
            # KHÔNG tự chuyển lại online (bảo mật) — chỉ thông báo
            reason = "Đã có mạng trở lại. Bạn có thể chuyển sang chế độ online."
            logger.info(reason)
            if self.on_mode_change:
                self.on_mode_change(True, reason)  # vẫn giữ offline

    def set_mode(self, mode: str):
        """Đổi chế độ (auto/always_offline/always_online)."""
        self.mode = mode
        if mode == "always_offline":
            self._is_offline_active = True
        elif mode == "always_online":
            self._is_offline_active = False
        # auto: phụ thuộc network monitor

    def switch_to_online(self):
        """Người dùng chủ động chuyển sang online."""
        if self.network.is_online:
            self._is_offline_active = False
            logger.info("Đã chuyển sang chế độ online")
            if self.on_mode_change:
                self.on_mode_change(False, "Đã chuyển sang online")
        else:
            logger.warning("Không thể chuyển online: không có kết nối mạng")

    def stop(self):
        self.network.stop()

    @property
    def is_offline(self) -> bool:
        """True nếu đang ở chế độ offline (Req 8.2: không gửi dữ liệu ra ngoài)."""
        return self._is_offline_active

    @property
    def is_online(self) -> bool:
        return not self._is_offline_active

    def get_status(self) -> dict:
        return {
            "mode": self.mode,
            "is_offline_active": self._is_offline_active,
            "network_connected": self.network.is_online,
            "models": self.model_manager.get_status(),
        }
