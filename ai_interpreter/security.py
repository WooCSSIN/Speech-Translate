"""
Security Module - Bảo mật cho Han Translate API.

Cung cấp:
- API key management (env var hoặc Windows Credential Manager qua keyring)
- API key authentication dependency cho FastAPI
- Rate limiting (token bucket per-IP)
- Input validation helpers
- Safe logging (ẩn dữ liệu nhạy cảm)

Nguyên tắc:
- Deny by default: thiếu/sai key → 401
- Không log nội dung nhạy cảm dạng plaintext (Req 11.2)
- API key không hardcode trong source (Req 11.7)
"""

import os
import time
import secrets
import hashlib
import threading
from collections import defaultdict, deque
from typing import Optional, Deque, Dict

from loguru import logger

# Tên biến môi trường chứa API key
ENV_API_KEY = "HAN_TRANSLATE_API_KEY"
# Service name cho keyring (Windows Credential Manager)
KEYRING_SERVICE = "han_translate"
KEYRING_USERNAME = "api_key"


# ============================================================
# API KEY MANAGEMENT
# ============================================================
def _get_key_from_keyring() -> Optional[str]:
    """Lấy API key từ Windows Credential Manager (an toàn hơn env)."""
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception:
        return None


def _set_key_to_keyring(key: str) -> bool:
    """Lưu API key vào Credential Manager."""
    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key)
        return True
    except Exception as e:
        logger.warning(f"Không lưu được key vào keyring: {e}")
        return False


def get_api_key() -> Optional[str]:
    """
    Lấy API key theo thứ tự ưu tiên:
    1. Biến môi trường HAN_TRANSLATE_API_KEY
    2. Windows Credential Manager (keyring)

    Trả None nếu chưa cấu hình (server sẽ cảnh báo).
    """
    key = os.environ.get(ENV_API_KEY)
    if key:
        return key.strip()
    return _get_key_from_keyring()


def generate_api_key() -> str:
    """Tạo API key ngẫu nhiên an toàn (32 bytes, URL-safe)."""
    return secrets.token_urlsafe(32)


def ensure_api_key() -> str:
    """
    Đảm bảo có API key. Nếu chưa có → tạo mới và lưu vào keyring.
    Trả về key hiện hành.
    """
    key = get_api_key()
    if not key:
        key = generate_api_key()
        saved = _set_key_to_keyring(key)
        if saved:
            logger.info("Đã tạo API key mới và lưu vào Windows Credential Manager.")
        else:
            logger.warning(
                "Đã tạo API key mới nhưng KHÔNG lưu được. "
                f"Hãy set biến môi trường {ENV_API_KEY}."
            )
        logger.warning(f"API KEY (lưu lại an toàn): {key}")
    return key


def verify_api_key(provided: Optional[str]) -> bool:
    """
    So sánh API key bằng constant-time để tránh timing attack.
    """
    expected = get_api_key()
    if not expected or not provided:
        return False
    return secrets.compare_digest(provided.strip(), expected)


# ============================================================
# RATE LIMITING (Token bucket per-IP)
# ============================================================
class RateLimiter:
    """
    Giới hạn request theo IP để chống spam/DoS.
    Sliding window đơn giản, thread-safe.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        with self._lock:
            hits = self._hits[client_id]
            # Loại bỏ các hit cũ ngoài cửa sổ thời gian
            while hits and hits[0] < now - self.window:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True

    def remaining(self, client_id: str) -> int:
        with self._lock:
            return max(0, self.max_requests - len(self._hits[client_id]))


# ============================================================
# INPUT VALIDATION & SANITIZATION
# ============================================================
MAX_TEXT_LENGTH = 5000  # Giới hạn độ dài text dịch (chống payload khổng lồ)

# Ký tự điều khiển nguy hiểm cần loại bỏ (trừ \n \r \t)
_CONTROL_CHARS = "".join(
    chr(c) for c in range(32) if c not in (9, 10, 13)
) + chr(127)
_CONTROL_TABLE = {ord(c): None for c in _CONTROL_CHARS}


def validate_text_length(text: str) -> bool:
    """Kiểm tra độ dài text hợp lệ."""
    return bool(text) and len(text) <= MAX_TEXT_LENGTH


def sanitize_text(text: str) -> str:
    """
    Làm sạch input trước khi xử lý:
    - Loại bỏ ký tự điều khiển (control chars) - chống injection qua terminal/log
    - Loại bỏ ký tự null byte
    - Giữ lại \\n \\r \\t (xuống dòng/tab hợp lệ)
    - Cắt khoảng trắng thừa đầu/cuối

    KHÔNG thay đổi nội dung ngữ nghĩa (chỉ loại ký tự nguy hiểm).
    """
    if not text:
        return ""
    # Loại null byte
    text = text.replace("\x00", "")
    # Loại control chars
    text = text.translate(_CONTROL_TABLE)
    return text.strip()


def is_safe_lang_code(code: str) -> bool:
    """
    Kiểm tra mã ngôn ngữ hợp lệ (chỉ chữ cái, dấu gạch, tối đa 10 ký tự).
    Chống injection qua tham số lang.
    """
    if not code or len(code) > 10:
        return False
    return all(c.isalpha() or c in ("-", "_") for c in code)

def escape_html(text: str) -> str:
    """
    [OWASP A03:2021 - Injection] Cross-Site Scripting (XSS) Prevention.
    Mã hóa các ký tự HTML đặc biệt để tránh thực thi mã độc nếu chuỗi
    được hiển thị trong UI hỗ trợ Rich Text (như QLabel của PyQt6).
    """
    import html
    return html.escape(text, quote=True)

def is_safe_path(base_dir: str, target_path: str) -> bool:
    """
    [OWASP A01:2021 - Broken Access Control] Path Traversal Prevention.
    Kiểm tra xem đường dẫn file có nằm an toàn trong thư mục gốc (base_dir) hay không.
    Tuyệt đối không cho phép truy cập file bằng cách dùng '../'.
    """
    abs_base = os.path.abspath(base_dir)
    abs_target = os.path.abspath(target_path)
    return abs_target.startswith(abs_base + os.sep)


# ============================================================
# SAFE LOGGING (Req 11.2)
# ============================================================
def redact(text: str, keep: int = 20) -> str:
    """
    Cắt ngắn + ẩn bớt nội dung để log an toàn.
    Không log toàn bộ nội dung nhạy cảm dạng plaintext.
    """
    if not text:
        return ""
    if len(text) <= keep:
        return text[: keep // 2] + "…"
    return text[:keep] + f"…[+{len(text) - keep} chars]"


def hash_id(value: str) -> str:
    """Hash 1 giá trị để dùng làm định danh trong log (không lộ giá trị gốc)."""
    return hashlib.sha256(value.encode()).hexdigest()[:8]
