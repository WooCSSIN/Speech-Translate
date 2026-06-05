"""
Network Monitor - Phát hiện trạng thái kết nối mạng (Req 8.3).

Khi mất mạng → Pipeline tự chuyển sang On_Device_Engine.
Khi có mạng lại → thông báo cho người dùng (không tự chuyển lại).

Thread-safe, chạy nền kiểm tra định kỳ.
"""

import threading
import time
import socket
from typing import Optional, Callable
from loguru import logger


class NetworkMonitor:
    """
    Giám sát kết nối mạng, thông báo khi mất/có mạng.

    Cách dùng:
        monitor = NetworkMonitor(on_offline=..., on_online=...)
        monitor.start()
        ...
        monitor.stop()
    """

    CHECK_INTERVAL = 10  # giây giữa mỗi lần kiểm tra
    TIMEOUT = 3  # giây timeout cho mỗi lần check

    # Các host để kiểm tra (dùng nhiều để tránh false positive)
    CHECK_HOSTS = [
        ("8.8.8.8", 53),        # Google DNS
        ("1.1.1.1", 53),        # Cloudflare DNS
        ("208.67.222.222", 53), # OpenDNS
    ]

    def __init__(
        self,
        on_offline: Optional[Callable] = None,
        on_online: Optional[Callable] = None,
    ):
        self.on_offline = on_offline
        self.on_online = on_online

        self._is_online: bool = True
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        """Bắt đầu giám sát mạng."""
        if self._running:
            return
        self._running = True
        self._is_online = self._check_connection()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="network-monitor")
        self._thread.start()
        logger.info(f"Network monitor started (online={self._is_online})")

    def _monitor_loop(self):
        while self._running:
            time.sleep(self.CHECK_INTERVAL)
            current = self._check_connection()

            with self._lock:
                if current != self._is_online:
                    self._is_online = current
                    if current:
                        logger.info("Network: ONLINE")
                        if self.on_online:
                            self.on_online()
                    else:
                        logger.warning("Network: OFFLINE")
                        if self.on_offline:
                            self.on_offline()

    def _check_connection(self) -> bool:
        """Kiểm tra kết nối bằng cách thử connect tới DNS servers."""
        for host, port in self.CHECK_HOSTS:
            try:
                sock = socket.create_connection((host, port), timeout=self.TIMEOUT)
                sock.close()
                return True
            except (socket.timeout, OSError):
                continue
        return False

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    @property
    def is_online(self) -> bool:
        with self._lock:
            return self._is_online

    def force_check(self) -> bool:
        """Kiểm tra ngay lập tức (không chờ interval)."""
        result = self._check_connection()
        with self._lock:
            self._is_online = result
        return result
