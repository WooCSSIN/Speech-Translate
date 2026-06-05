"""
Model Integrity Verification (Req 11.3, 11.4).

Xác minh tính toàn vẹn của file model AI trước khi load để chống:
- Model bị thay thế bằng file độc hại
- Model bị hỏng (corrupt) trong quá trình tải

Cơ chế:
- Tính SHA-256 checksum của file model
- So sánh với checksum đã đăng ký (manifest)
- Nếu không khớp → TỪ CHỐI load (Req 11.4: no exceptions)

Manifest lưu ở: <model_dir>/model_checksums.json
"""

import os
import json
import hashlib
from typing import Dict, Optional, Tuple
from loguru import logger

MANIFEST_NAME = "model_checksums.json"
CHUNK_SIZE = 1024 * 1024  # 1MB - đọc file theo chunk để tiết kiệm RAM


def compute_sha256(file_path: str) -> Optional[str]:
    """Tính SHA-256 của file (đọc theo chunk)."""
    if not os.path.isfile(file_path):
        return None
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.error(f"Lỗi tính checksum {file_path}: {e}")
        return None


def load_manifest(model_dir: str) -> Dict[str, str]:
    """Đọc manifest checksum. Trả dict {filename: sha256}."""
    manifest_path = os.path.join(model_dir, MANIFEST_NAME)
    if not os.path.isfile(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Lỗi đọc manifest: {e}")
        return {}


def save_manifest(model_dir: str, checksums: Dict[str, str]) -> bool:
    """Lưu manifest checksum."""
    manifest_path = os.path.join(model_dir, MANIFEST_NAME)
    try:
        os.makedirs(model_dir, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(checksums, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Lỗi lưu manifest: {e}")
        return False


def register_model(model_dir: str, file_name: str) -> Optional[str]:
    """
    Đăng ký checksum cho 1 model file vào manifest.
    Dùng khi cài model lần đầu (trusted source).

    Returns: checksum đã đăng ký hoặc None nếu lỗi.
    """
    file_path = os.path.join(model_dir, file_name)
    checksum = compute_sha256(file_path)
    if not checksum:
        logger.error(f"Không tính được checksum cho {file_name}")
        return None

    manifest = load_manifest(model_dir)
    manifest[file_name] = checksum
    if save_manifest(model_dir, manifest):
        logger.info(f"Đã đăng ký model: {file_name} -> {checksum[:16]}...")
        return checksum
    return None


def verify_model(model_dir: str, file_name: str) -> Tuple[bool, str]:
    """
    Xác minh tính toàn vẹn của model trước khi load (Req 11.3).

    Returns:
        (is_valid, message)

    Logic (Req 11.4 - deny by default):
    - Manifest không có entry → coi như chưa tin cậy → TỪ CHỐI
    - Checksum không khớp → TỪ CHỐI
    - Khớp → cho phép
    """
    file_path = os.path.join(model_dir, file_name)

    if not os.path.isfile(file_path):
        return False, f"Model không tồn tại: {file_name}"

    manifest = load_manifest(model_dir)
    expected = manifest.get(file_name)

    if not expected:
        # Chưa đăng ký → không tin cậy
        return False, (
            f"Model '{file_name}' chưa được đăng ký trong manifest. "
            f"Hãy đăng ký bằng register_model() từ nguồn tin cậy."
        )

    actual = compute_sha256(file_path)
    if not actual:
        return False, f"Không tính được checksum cho {file_name}"

    if actual != expected:
        # Checksum không khớp → TỪ CHỐI (Req 11.4)
        logger.error(
            f"CẢNH BÁO BẢO MẬT: checksum không khớp cho {file_name}! "
            f"Model có thể đã bị thay đổi hoặc hỏng."
        )
        return False, (
            f"Checksum không khớp cho '{file_name}'. "
            f"Model có thể đã bị thay đổi. Từ chối load."
        )

    return True, "OK"


def verify_or_register(model_dir: str, file_name: str, trust_on_first_use: bool = False) -> Tuple[bool, str]:
    """
    Verify model; nếu chưa đăng ký và trust_on_first_use=True thì tự đăng ký
    (TOFU - Trust On First Use, dùng cho model tự tải từ nguồn chính thức).

    Mặc định trust_on_first_use=False để an toàn nhất (Req 11.4).
    """
    manifest = load_manifest(model_dir)
    if file_name not in manifest and trust_on_first_use:
        checksum = register_model(model_dir, file_name)
        if checksum:
            return True, "Đã đăng ký lần đầu (TOFU)"
        return False, "Không đăng ký được model"
    return verify_model(model_dir, file_name)
