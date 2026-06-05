"""
Regional Variant - Biến thể vùng miền tiếng Việt (Req 3.8).

Theo tư vấn chuyên môn: vùng miền ảnh hưởng cực lớn đến từ vựng.
Cùng một vật/khái niệm, mỗi miền gọi khác nhau:
    Bắc: bố mẹ, dứa, bát, cốc, ô tô...
    Nam: ba má, thơm, chén, ly, xe hơi...

Module này áp dụng từ vựng vùng miền khi người dùng chọn (Req 3.8).
"""

from typing import Dict, List
from loguru import logger

# Mã vùng miền
REGIONS = {
    "north": "Bắc",
    "central": "Trung",
    "south": "Nam",
    "standard": "Chuẩn (trung lập)",
}

DEFAULT_REGION = "standard"

# Bảng ánh xạ từ vựng: từ chuẩn -> {vùng: biến thể}
# Khi dịch sang tiếng Việt, nếu chọn vùng miền sẽ thay từ chuẩn bằng biến thể vùng.
REGIONAL_VOCAB: Dict[str, Dict[str, str]] = {
    # cha mẹ
    "bố": {"north": "bố", "south": "ba", "central": "ba"},
    "mẹ": {"north": "mẹ", "south": "má", "central": "mạ"},
    # đồ vật
    "bát": {"north": "bát", "south": "chén", "central": "chén"},
    "cốc": {"north": "cốc", "south": "ly", "central": "ly"},
    "thìa": {"north": "thìa", "south": "muỗng", "central": "muỗng"},
    # trái cây
    "dứa": {"north": "dứa", "south": "thơm", "central": "khóm"},
    "lạc": {"north": "lạc", "south": "đậu phộng", "central": "đậu phộng"},
    # phương tiện
    "ô tô": {"north": "ô tô", "south": "xe hơi", "central": "xe hơi"},
    # đại từ chỉ định
    "thế": {"north": "thế", "south": "vậy", "central": "rứa"},
    "này": {"north": "này", "south": "nè", "central": "ni"},
    # khác
    "không": {"north": "không", "south": "hông", "central": "không"},
}


class RegionalVariant:
    """Áp dụng từ vựng vùng miền cho bản dịch tiếng Việt (Req 3.8)."""

    def __init__(self, region: str = DEFAULT_REGION):
        self.region = region if region in REGIONS else DEFAULT_REGION

    def set_region(self, region: str):
        if region in REGIONS:
            self.region = region
            logger.info(f"Vùng miền: {REGIONS[region]}")

    def apply(self, vietnamese_text: str) -> str:
        """
        Thay từ vựng chuẩn bằng biến thể vùng miền đã chọn.

        Chỉ áp dụng khi region != standard.
        """
        if self.region == "standard" or self.region == DEFAULT_REGION:
            return vietnamese_text

        import re
        result = vietnamese_text
        for standard_word, variants in REGIONAL_VOCAB.items():
            variant = variants.get(self.region)
            if variant and variant != standard_word:
                # Thay theo word boundary, giữ nguyên hoa/thường đầu câu
                result = re.sub(
                    rf"\b{re.escape(standard_word)}\b",
                    variant,
                    result,
                )
        return result

    @staticmethod
    def list_regions() -> List[Dict[str, str]]:
        """Danh sách vùng miền cho UI."""
        return [{"id": k, "name": v} for k, v in REGIONS.items()]
