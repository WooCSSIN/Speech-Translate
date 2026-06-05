"""
Adaptive Learning Engine - Facade (Capability E).

Kết hợp Translation Memory + Personal Phrasebook.
Tích hợp vào translation flow:
1. Trước khi dịch: kiểm tra Phrasebook → TM → nếu có thì dùng luôn (Req 7.2)
2. Sau khi dịch: lưu vào TM (tự động)
3. Khi người dùng sửa: cập nhật TM (Req 7.1)

Ưu tiên: Phrasebook > Translation Memory > Engine (Req 7.5)
"""

from typing import Optional, Tuple
from loguru import logger

from .memory import TranslationMemory
from .phrasebook import PersonalPhrasebook


class AdaptiveEngine:
    """
    Adaptive translation: càng dùng càng chính xác.

    Cách dùng trong pipeline:
        adaptive = AdaptiveEngine()

        # Trước khi gọi translation engine
        cached = adaptive.lookup(source, src_lang, tgt_lang)
        if cached:
            use cached  # không cần gọi engine

        # Sau khi dịch xong
        adaptive.remember(source, translated, src_lang, tgt_lang)

        # Khi người dùng sửa
        adaptive.correct(source, corrected, src_lang, tgt_lang)
    """

    def __init__(self):
        self.memory = TranslationMemory()
        self.phrasebook = PersonalPhrasebook()

    def lookup(self, source: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        Tra cứu bản dịch đã lưu.

        Thứ tự ưu tiên (Req 7.5): Phrasebook > Translation Memory
        """
        # 1. Phrasebook (ưu tiên cao nhất)
        pb_result = self.phrasebook.lookup(source)
        if pb_result:
            logger.debug(f"Adaptive hit (phrasebook): '{source[:20]}' → '{pb_result[:20]}'")
            return pb_result

        # 2. Translation Memory
        tm_result = self.memory.lookup(source, source_lang, target_lang)
        if tm_result:
            logger.debug(f"Adaptive hit (TM): '{source[:20]}' → '{tm_result[:20]}'")
            return tm_result

        return None

    def remember(self, source: str, target: str, source_lang: str, target_lang: str):
        """Tự động lưu bản dịch vào TM (sau mỗi lần dịch)."""
        self.memory.add(source, target, source_lang, target_lang)

    def correct(self, source: str, corrected: str, source_lang: str, target_lang: str):
        """
        Người dùng chỉnh sửa bản dịch (Req 7.1).

        Lưu vào TM để lần sau dùng bản đã sửa.
        """
        self.memory.add(source, corrected, source_lang, target_lang)
        logger.info(f"User correction saved: '{source[:20]}' → '{corrected[:20]}'")

    def get_stats(self) -> dict:
        return {
            "translation_memory_count": self.memory.count,
            "phrasebook_count": self.phrasebook.count,
        }

    def clear_all(self):
        """Xóa toàn bộ dữ liệu adaptive."""
        self.memory.clear()
        self.phrasebook.clear()
