"""
Privacy / Data Management (Req 11.6).

Quản lý dữ liệu cá nhân của người dùng:
- Translation Memory
- Personal Phrasebook
- API key trong Credential Manager
- Cache / log

Cho phép người dùng XÓA toàn bộ dữ liệu cá nhân theo yêu cầu (quyền được lãng quên).
Tất cả dữ liệu xử lý ở chế độ offline đều giữ trên thiết bị (Req 11.5).
"""

import os
import shutil
from typing import List, Dict
from loguru import logger

from . import security


def get_user_data_dir() -> str:
    """Thư mục lưu dữ liệu cá nhân của Han Translate."""
    base = os.path.join(os.path.expanduser("~"), ".han_translate")
    os.makedirs(base, exist_ok=True)
    return base


# Các file/thư mục dữ liệu cá nhân
def _data_paths() -> Dict[str, str]:
    base = get_user_data_dir()
    return {
        "translation_memory": os.path.join(base, "translation_memory.json"),
        "phrasebook": os.path.join(base, "phrasebook.json"),
        "terminology": os.path.join(base, "terminology"),
        "cache": os.path.join(base, "cache"),
        "logs": os.path.join(base, "logs"),
    }


def list_user_data() -> List[Dict]:
    """Liệt kê dữ liệu cá nhân hiện có (để hiển thị trước khi xóa)."""
    result = []
    for name, path in _data_paths().items():
        exists = os.path.exists(path)
        size = 0
        if exists:
            if os.path.isfile(path):
                size = os.path.getsize(path)
            elif os.path.isdir(path):
                size = sum(
                    os.path.getsize(os.path.join(dp, f))
                    for dp, _, files in os.walk(path)
                    for f in files
                )
        result.append({"name": name, "path": path, "exists": exists, "size_bytes": size})
    return result


def delete_user_data(include_api_key: bool = False) -> Dict[str, bool]:
    """
    Xóa toàn bộ dữ liệu cá nhân (Req 11.6).

    Args:
        include_api_key: True để xóa cả API key trong Credential Manager.

    Returns:
        Dict {data_name: deleted_successfully}
    """
    results = {}

    for name, path in _data_paths().items():
        try:
            if os.path.isfile(path):
                os.remove(path)
                results[name] = True
                logger.info(f"Đã xóa dữ liệu: {name}")
            elif os.path.isdir(path):
                shutil.rmtree(path)
                results[name] = True
                logger.info(f"Đã xóa thư mục dữ liệu: {name}")
            else:
                results[name] = True  # không tồn tại = coi như đã xóa
        except Exception as e:
            logger.error(f"Lỗi xóa {name}: {e}")
            results[name] = False

    # Xóa API key nếu yêu cầu
    if include_api_key:
        try:
            import keyring
            keyring.delete_password(security.KEYRING_SERVICE, security.KEYRING_USERNAME)
            results["api_key"] = True
            logger.info("Đã xóa API key khỏi Credential Manager")
        except Exception as e:
            logger.warning(f"Không xóa được API key (có thể chưa tồn tại): {e}")
            results["api_key"] = False

    return results
