"""
Culture Engine - Facade gom 3 module văn hóa (Capability C).

Kết hợp:
- HonorificResolver: xưng hô / tôn ti (Req 3.6, 3.7)
- CulturalInsightModule: thành ngữ / tiếng lóng (Req 3.1-3.4)
- RegionalVariant: vùng miền Bắc/Trung/Nam (Req 3.8)

Dùng trong TranslationRouter để hậu xử lý bản dịch Việt-Anh.
"""

from typing import Optional, List, Tuple
from loguru import logger

from .honorifics import HonorificResolver, HonorificPair
from .insight import CulturalInsightModule, CulturalNote
from .regional import RegionalVariant


class CultureEngine:
    """Facade cho toàn bộ xử lý văn hóa Việt-Anh."""

    def __init__(self, region: str = "standard"):
        self.honorifics = HonorificResolver()
        self.insight = CulturalInsightModule()
        self.regional = RegionalVariant(region)
        self._enabled = True

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def set_region(self, region: str):
        self.regional.set_region(region)

    def set_manual_honorific(self, pair_id: Optional[str]):
        self.honorifics.set_manual_pair(pair_id)

    def process(
        self,
        source_text: str,
        translated: str,
        source_lang: str,
        target_lang: str,
        context_window: List[str],
    ) -> Tuple[str, Optional[CulturalNote], Optional[HonorificPair]]:
        """
        Hậu xử lý văn hóa cho 1 bản dịch.

        Returns:
            (final_text, cultural_note, honorific_pair)
            - final_text: bản dịch đã áp dụng xưng hô + vùng miền
            - cultural_note: ghi chú thành ngữ nếu có (None nếu không)
            - honorific_pair: cặp xưng hô đã dùng (None nếu không áp dụng)
        """
        if not self._enabled:
            return translated, None, None

        # Chỉ xử lý Việt-Anh / Anh-Việt
        is_vi_en = {source_lang.lower(), target_lang.lower()} == {"vi", "en"}
        if not is_vi_en:
            return translated, None, None

        final = translated
        note = None
        pair = None

        # 1. Phát hiện thành ngữ/tiếng lóng (Req 3.1-3.3)
        note = self.insight.detect(source_text, source_lang, target_lang)

        # 2. Áp dụng xưng hô (chỉ khi dịch SANG tiếng Việt) (Req 3.6)
        if target_lang.lower() == "vi":
            pair, ambiguous = self.honorifics.resolve(context_window)
            final = self.honorifics.apply_to_translation(final, pair)

            # 3. Áp dụng vùng miền (Req 3.8)
            final = self.regional.apply(final)

        return final, note, pair

    def reset(self):
        self.honorifics.reset()
        self.insight.reset()
