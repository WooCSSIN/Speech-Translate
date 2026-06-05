"""
Terminology Base - Kho thuật ngữ chuẩn theo lĩnh vực (Req 2.2, 2.6).

Mỗi Domain_Profile có Terminology_Base riêng (KHÔNG all-in-one, Req 2.7).
Cho phép người dùng thêm, chỉnh sửa, xóa thuật ngữ (Req 2.6).

Lưu trữ: JSON file per domain trong ~/.han_translate/terminology/
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from loguru import logger


class TerminologyBase:
    """
    Kho thuật ngữ chuẩn cho 1 lĩnh vực.

    Mỗi entry: source_term → target_term
    Áp dụng khi dịch: nếu source text chứa term → dùng bản dịch chuẩn.
    """

    def __init__(self, domain_id: str, storage_dir: Optional[str] = None):
        self.domain_id = domain_id
        self._storage_dir = storage_dir or self._default_dir()
        self._terms: Dict[str, str] = {}  # source → target
        self._load()

    def _default_dir(self) -> str:
        d = os.path.join(os.path.expanduser("~"), ".han_translate", "terminology")
        os.makedirs(d, exist_ok=True)
        return d

    def _file_path(self) -> str:
        return os.path.join(self._storage_dir, f"{self.domain_id}.json")

    def _load(self):
        """Load terminology từ file."""
        path = self._file_path()
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._terms = json.load(f)
                logger.debug(f"Loaded {len(self._terms)} terms for domain '{self.domain_id}'")
            except Exception as e:
                logger.error(f"Error loading terminology {self.domain_id}: {e}")
                self._terms = {}

    def _save(self):
        """Lưu terminology ra file."""
        os.makedirs(self._storage_dir, exist_ok=True)
        path = self._file_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._terms, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving terminology {self.domain_id}: {e}")

    def add(self, source: str, target: str) -> bool:
        """Thêm thuật ngữ (Req 2.6)."""
        source = source.strip().lower()
        target = target.strip()
        if not source or not target:
            return False
        self._terms[source] = target
        self._save()
        logger.info(f"[{self.domain_id}] Added term: '{source}' → '{target}'")
        return True

    def edit(self, source: str, new_target: str) -> bool:
        """Chỉnh sửa thuật ngữ (Req 2.6)."""
        source = source.strip().lower()
        if source not in self._terms:
            return False
        self._terms[source] = new_target.strip()
        self._save()
        return True

    def delete(self, source: str) -> bool:
        """Xóa thuật ngữ (Req 2.6)."""
        source = source.strip().lower()
        if source in self._terms:
            del self._terms[source]
            self._save()
            return True
        return False

    def lookup(self, source: str) -> Optional[str]:
        """Tra cứu thuật ngữ."""
        return self._terms.get(source.strip().lower())

    def apply_to_text(self, translated: str) -> str:
        """
        Áp dụng thuật ngữ chuẩn vào bản dịch (Req 2.2).

        Hậu xử lý: tìm và thay thế thuật ngữ trong bản dịch.
        """
        result = translated
        for source, target in self._terms.items():
            # Case-insensitive replace trong bản dịch
            import re
            result = re.sub(re.escape(source), target, result, flags=re.IGNORECASE)
        return result

    def bulk_add(self, terms: Dict[str, str]):
        """Thêm nhiều thuật ngữ cùng lúc."""
        for src, tgt in terms.items():
            self._terms[src.strip().lower()] = tgt.strip()
        self._save()

    @property
    def terms(self) -> Dict[str, str]:
        return self._terms.copy()

    @property
    def count(self) -> int:
        return len(self._terms)

    def search(self, query: str) -> List[Tuple[str, str]]:
        """Tìm kiếm thuật ngữ."""
        q = query.lower()
        return [(s, t) for s, t in self._terms.items() if q in s or q in t.lower()]


class TerminologyManager:
    """Quản lý Terminology Base cho tất cả domains."""

    def __init__(self):
        self._bases: Dict[str, TerminologyBase] = {}

    def get_base(self, domain_id: str) -> TerminologyBase:
        """Lấy (hoặc tạo) Terminology Base cho 1 domain."""
        if domain_id not in self._bases:
            self._bases[domain_id] = TerminologyBase(domain_id)
        return self._bases[domain_id]

    def init_defaults(self):
        """Khởi tạo thuật ngữ mặc định từ domain_profiles (nếu chưa có)."""
        from .domain_profiles import ALL_PROFILES
        for pid, profile in ALL_PROFILES.items():
            if profile.terminology:
                base = self.get_base(pid)
                if base.count == 0:
                    base.bulk_add(profile.terminology)
                    logger.info(f"Initialized {base.count} default terms for '{pid}'")
