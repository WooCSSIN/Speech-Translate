"""
Personal Phrasebook - Sổ tay cụm từ cá nhân (Req 7.3, 7.4, 7.5).

Cho phép người dùng:
- Thêm cặp cụm từ nguồn-đích + ghi chú (Req 7.3)
- Áp dụng ngay cho bản dịch tiếp theo trong 1 giây (Req 7.4)
- Ưu tiên hơn Translation Memory khi mâu thuẫn (Req 7.5)

Lưu trữ: JSON file tại ~/.han_translate/phrasebook.json
"""

import os
import json
import time
from typing import Optional, Dict, List
from loguru import logger


class PersonalPhrasebook:
    """
    Sổ tay cụm từ cá nhân.

    Ưu tiên cao hơn Translation Memory (Req 7.5).
    Áp dụng ngay khi thêm (Req 7.4: trong 1 giây).
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._path = storage_path or self._default_path()
        self._entries: Dict[str, Dict] = {}  # key → {source, target, note, timestamp}
        self._load()

    def _default_path(self) -> str:
        d = os.path.join(os.path.expanduser("~"), ".han_translate")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "phrasebook.json")

    def _make_key(self, source: str) -> str:
        return source.strip().lower()

    def _load(self):
        if os.path.isfile(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
                logger.debug(f"Loaded {len(self._entries)} phrasebook entries")
            except Exception as e:
                logger.error(f"Error loading phrasebook: {e}")

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving phrasebook: {e}")

    def add(self, source: str, target: str, note: str = "") -> bool:
        """Thêm cặp cụm từ (Req 7.3). Áp dụng ngay (Req 7.4)."""
        if not source.strip() or not target.strip():
            return False
        key = self._make_key(source)
        self._entries[key] = {
            "source": source.strip(),
            "target": target.strip(),
            "note": note.strip(),
            "timestamp": time.time(),
        }
        self._save()
        logger.info(f"Phrasebook: '{source}' → '{target}'")
        return True

    def edit(self, source: str, new_target: str, note: str = "") -> bool:
        """Chỉnh sửa (Req 7.3)."""
        key = self._make_key(source)
        if key not in self._entries:
            return False
        self._entries[key]["target"] = new_target.strip()
        self._entries[key]["note"] = note.strip()
        self._entries[key]["timestamp"] = time.time()
        self._save()
        return True

    def delete(self, source: str) -> bool:
        """Xóa (Req 7.3)."""
        key = self._make_key(source)
        if key in self._entries:
            del self._entries[key]
            self._save()
            return True
        return False

    def lookup(self, source: str) -> Optional[str]:
        """
        Tra cứu cụm từ.

        Ưu tiên hơn Translation Memory (Req 7.5).
        """
        key = self._make_key(source)
        entry = self._entries.get(key)
        return entry["target"] if entry else None

    def find_in_text(self, text: str) -> Optional[Dict]:
        """
        Tìm cụm từ phrasebook xuất hiện trong text.

        Dùng để áp dụng phrasebook vào bản dịch.
        """
        text_lower = text.lower()
        for key, entry in self._entries.items():
            if key in text_lower:
                return entry
        return None

    def clear(self):
        self._entries = {}
        self._save()

    @property
    def count(self) -> int:
        return len(self._entries)

    def list_all(self) -> List[Dict]:
        return list(self._entries.values())
