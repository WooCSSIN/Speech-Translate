"""
Translation Memory - Lưu cặp câu đã dịch/chỉnh sửa (Req 7.1, 7.2, 7.6).

Cơ chế:
- Khi người dùng chỉnh sửa bản dịch → lưu vào Translation Memory (Req 7.1)
- Khi câu nguồn trùng khớp → dùng bản dịch đã lưu thay vì gọi engine (Req 7.2)
- Round-trip: lưu rồi truy xuất lại phải bằng nhau (Req 7.6)

Lưu trữ: JSON file tại ~/.han_translate/translation_memory.json
"""

import os
import json
import time
from typing import Optional, Dict, List, Tuple
from loguru import logger


class TranslationMemory:
    """
    Kho lưu trữ cặp câu nguồn-đích đã xác nhận.

    Mỗi entry: {source: str, target: str, timestamp: float, source_lang: str, target_lang: str}
    """

    MAX_ENTRIES = 10000  # Giới hạn để không quá nặng

    def __init__(self, storage_path: Optional[str] = None):
        self._path = storage_path or self._default_path()
        self._entries: List[Dict] = []
        self._index: Dict[str, int] = {}  # source_key → index (cho lookup nhanh)
        self._load()

    def _default_path(self) -> str:
        d = os.path.join(os.path.expanduser("~"), ".han_translate")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "translation_memory.json")

    def _make_key(self, source: str, source_lang: str, target_lang: str) -> str:
        """Tạo key duy nhất cho 1 cặp."""
        return f"{source_lang}|{target_lang}|{source.strip().lower()}"

    def _load(self):
        if os.path.isfile(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
                self._rebuild_index()
                logger.debug(f"Loaded {len(self._entries)} translation memory entries")
            except Exception as e:
                logger.error(f"Error loading translation memory: {e}")
                self._entries = []

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving translation memory: {e}")

    def _rebuild_index(self):
        self._index = {}
        for i, entry in enumerate(self._entries):
            key = self._make_key(entry["source"], entry["source_lang"], entry["target_lang"])
            self._index[key] = i

    def add(self, source: str, target: str, source_lang: str, target_lang: str) -> bool:
        """
        Thêm cặp câu vào memory (Req 7.1).

        Luôn thêm mới, bất kể nội dung hiện có (Req 7.1: "bất kể nội dung hiện có").
        Nếu key trùng → cập nhật entry cũ.
        """
        if not source.strip() or not target.strip():
            return False

        key = self._make_key(source, source_lang, target_lang)
        entry = {
            "source": source.strip(),
            "target": target.strip(),
            "source_lang": source_lang,
            "target_lang": target_lang,
            "timestamp": time.time(),
        }

        if key in self._index:
            # Cập nhật entry cũ
            self._entries[self._index[key]] = entry
        else:
            # Thêm mới
            if len(self._entries) >= self.MAX_ENTRIES:
                # Xóa entry cũ nhất
                self._entries.pop(0)
                self._rebuild_index()
            self._entries.append(entry)
            self._index[key] = len(self._entries) - 1

        self._save()
        logger.debug(f"TM added: '{source[:30]}' → '{target[:30]}'")
        return True

    def lookup(self, source: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        Tra cứu bản dịch đã lưu (Req 7.2).

        Returns target nếu tìm thấy, None nếu không.
        """
        key = self._make_key(source, source_lang, target_lang)
        idx = self._index.get(key)
        if idx is not None and idx < len(self._entries):
            return self._entries[idx]["target"]
        return None

    def delete(self, source: str, source_lang: str, target_lang: str) -> bool:
        """Xóa 1 entry."""
        key = self._make_key(source, source_lang, target_lang)
        idx = self._index.get(key)
        if idx is not None:
            self._entries.pop(idx)
            self._rebuild_index()
            self._save()
            return True
        return False

    def clear(self):
        """Xóa toàn bộ memory."""
        self._entries = []
        self._index = {}
        self._save()

    @property
    def count(self) -> int:
        return len(self._entries)

    def recent(self, n: int = 20) -> List[Dict]:
        """Lấy n entry gần nhất."""
        return self._entries[-n:]
