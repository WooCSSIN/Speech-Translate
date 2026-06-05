"""
Packaging Security (Req 11.7).

Đảm bảo an toàn khi đóng gói và phân phối Han Translate cho người dùng cài về:

1. Pre-build scan: quét hardcoded secrets trước khi build (chặn build nếu phát hiện)
2. First-run setup: mỗi máy tự sinh API key riêng (không dùng key của dev)
3. Distribution manifest: danh sách file ĐƯỢC PHÉP và BỊ LOẠI khỏi bản phân phối

Nguyên tắc:
- Credential của dev (API key, encryption key) KHÔNG được nhúng vào .exe (Req 11.7)
- Mỗi cài đặt là độc lập, tự sinh key riêng
"""

import os
import re
from typing import List, Tuple
from loguru import logger


# ============================================================
# PRE-BUILD SECRET SCAN (Req 11.7)
# ============================================================
# Các pattern phát hiện secret có thể lọt vào build
_SECRET_PATTERNS = [
    # API keys / tokens dài (>=20 ký tự base64/hex)
    (r'["\'][A-Za-z0-9_\-]{32,}["\']', "Possible API key/token"),
    # Password gán trực tiếp
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']', "Hardcoded password"),
    # Secret/token gán trực tiếp
    (r'(?i)(secret|api[_-]?key|access[_-]?token)\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded secret"),
    # AWS-style keys
    (r'AKIA[0-9A-Z]{16}', "AWS access key"),
    # Private key headers
    (r'-----BEGIN (RSA |EC )?PRIVATE KEY-----', "Private key"),
]

# File/thư mục được phép bỏ qua khi scan (không phải secret thật)
_SCAN_SKIP = {
    "packaging_security.py",  # chính file này chứa pattern
    "security.py",            # chứa tên biến, không phải value
    "__pycache__",
}

# Whitelist các chuỗi an toàn (tên hằng, không phải secret)
_WHITELIST = {
    "HAN_TRANSLATE_API_KEY",
    "N8N_ENCRYPTION_KEY",
    "HAN_TRANSLATE_CORS_ORIGINS",
    "vi-VN-HoaiMyNeural",
    "vi-VN-NamMinhNeural",
}


def scan_for_secrets(root_dir: str) -> List[Tuple[str, int, str]]:
    """
    Quét secrets trong source code trước khi build.

    Returns:
        List of (file_path, line_number, reason). Rỗng = an toàn.
    """
    findings: List[Tuple[str, int, str]] = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Bỏ qua thư mục không cần scan
        dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP and not d.startswith(".")]

        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            if fname in _SCAN_SKIP:
                continue

            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):
                        # Bỏ qua dòng comment thuần
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            continue
                        for pattern, reason in _SECRET_PATTERNS:
                            for match in re.finditer(pattern, line):
                                matched = match.group(0)
                                # Bỏ qua nếu nằm trong whitelist
                                if any(w in matched for w in _WHITELIST):
                                    continue
                                findings.append((fpath, lineno, reason))
            except Exception as e:
                logger.warning(f"Không scan được {fpath}: {e}")

    return findings


def assert_no_secrets(root_dir: str) -> bool:
    """
    Chặn build nếu phát hiện secret (Req 11.7).

    Returns True nếu an toàn, raise nếu phát hiện secret.
    """
    findings = scan_for_secrets(root_dir)
    if findings:
        logger.error("=" * 60)
        logger.error("CHẶN BUILD: Phát hiện secret trong source code!")
        for fpath, lineno, reason in findings:
            logger.error(f"  {fpath}:{lineno} - {reason}")
        logger.error("=" * 60)
        raise RuntimeError(
            f"Phát hiện {len(findings)} secret(s) trong code. "
            f"Xóa/di chuyển ra env var hoặc Credential Manager trước khi build."
        )
    logger.info("Pre-build scan: KHÔNG phát hiện secret. An toàn để build.")
    return True


# ============================================================
# FIRST-RUN SETUP (mỗi máy 1 key riêng)
# ============================================================
def first_run_setup() -> dict:
    """
    Chạy khi app khởi động lần đầu trên máy người dùng.

    - Tự sinh API key riêng cho máy này (không dùng key của dev)
    - Tạo thư mục dữ liệu người dùng
    - KHÔNG dùng bất kỳ credential nào nhúng sẵn trong app

    Returns: dict trạng thái setup.
    """
    from . import security, privacy

    status = {"first_run": False, "api_key_created": False}

    # Tạo thư mục dữ liệu
    data_dir = privacy.get_user_data_dir()
    marker = os.path.join(data_dir, ".initialized")

    if not os.path.exists(marker):
        status["first_run"] = True
        # Sinh API key RIÊNG cho máy này
        existing = security.get_api_key()
        if not existing:
            security.ensure_api_key()  # tự sinh + lưu Credential Manager
            status["api_key_created"] = True

        # Đánh dấu đã khởi tạo
        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write("initialized")
        except Exception as e:
            logger.warning(f"Không tạo được marker: {e}")

        logger.info("First-run setup hoàn tất: API key riêng cho máy này đã sẵn sàng.")

    return status


# ============================================================
# DISTRIBUTION FILE FILTER
# ============================================================
# File/pattern KHÔNG được đưa vào bản phân phối (chứa dữ liệu/secret cục bộ)
EXCLUDE_FROM_DISTRIBUTION = [
    ".env",
    ".env.*",
    "*.key",
    "n8n_encryption_key.txt",
    ".han_translate",          # thư mục dữ liệu user
    "venv",
    "__pycache__",
    "*.log",
    ".git",
    "model_checksums.json",    # manifest sinh ở máy đích, không nhúng
]


def get_distribution_excludes() -> List[str]:
    """Danh sách pattern loại khỏi bản phân phối."""
    return EXCLUDE_FROM_DISTRIBUTION.copy()
