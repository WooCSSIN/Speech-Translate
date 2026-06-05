"""
Honorific Resolver - Xử lý xưng hô / tôn ti tiếng Việt (Req 3.6, 3.7).

Theo tư vấn chuyên môn: cách xưng hô / tôn ti / vùng miền ảnh hưởng CỰC LỚN
đến nghĩa và sắc thái khi dịch Anh-Việt.

Vấn đề: tiếng Anh chỉ có "you", "I", "he", "she" — tiếng Việt có hàng chục
đại từ tùy quan hệ và vai vế:
    you  -> anh / chị / em / ông / bà / cô / chú / bác / cháu / con / bạn / mày...
    I    -> tôi / mình / em / anh / chị / con / cháu / tớ / tao...
    he   -> anh ấy / ông ấy / chú ấy / nó / cậu ấy...

Module này phân tích ngữ cảnh (Context_Window) để chọn cặp xưng hô phù hợp,
hoặc dùng cặp trung lập + đánh dấu khi thiếu thông tin (Req 3.7).
"""

import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from loguru import logger


@dataclass
class HonorificPair:
    """Một cặp xưng hô (cách người nói gọi mình - I, và gọi người nghe - you)."""
    id: str
    label: str            # mô tả quan hệ
    first_person: str     # I -> ...
    second_person: str    # you -> ...
    third_male: str       # he -> ...
    third_female: str     # she -> ...
    formality: str        # formal / neutral / casual / intimate


# ============ CÁC CẶP XƯNG HÔ PHỔ BIẾN ============
HONORIFIC_PAIRS: Dict[str, HonorificPair] = {
    # Trung lập - mặc định an toàn (Req 3.7)
    "neutral": HonorificPair(
        "neutral", "Trung lập / lịch sự",
        first_person="tôi", second_person="bạn",
        third_male="anh ấy", third_female="cô ấy",
        formality="neutral",
    ),
    # Trang trọng - công việc, người lạ lớn tuổi
    "formal_senior": HonorificPair(
        "formal_senior", "Trang trọng với người lớn tuổi/cấp trên",
        first_person="tôi", second_person="ông/bà",
        third_male="ông ấy", third_female="bà ấy",
        formality="formal",
    ),
    # Anh (nam lớn hơn) - em (mình nhỏ hơn)
    "younger_to_older_male": HonorificPair(
        "younger_to_older_male", "Em nói với anh (nam lớn hơn)",
        first_person="em", second_person="anh",
        third_male="anh ấy", third_female="chị ấy",
        formality="casual",
    ),
    # Chị (nữ lớn hơn) - em
    "younger_to_older_female": HonorificPair(
        "younger_to_older_female", "Em nói với chị (nữ lớn hơn)",
        first_person="em", second_person="chị",
        third_male="anh ấy", third_female="chị ấy",
        formality="casual",
    ),
    # Anh/chị nói với em (mình lớn hơn)
    "older_to_younger": HonorificPair(
        "older_to_younger", "Anh/chị nói với em (mình lớn hơn)",
        first_person="anh/chị", second_person="em",
        third_male="cậu ấy", third_female="cô ấy",
        formality="casual",
    ),
    # Bạn bè đồng trang lứa
    "peer": HonorificPair(
        "peer", "Bạn bè đồng trang lứa",
        first_person="mình", second_person="bạn",
        third_male="cậu ấy", third_female="cô ấy",
        formality="casual",
    ),
    # Thân mật (gia đình, người yêu)
    "intimate": HonorificPair(
        "intimate", "Thân mật",
        first_person="anh/em", second_person="em/anh",
        third_male="anh ấy", third_female="em ấy",
        formality="intimate",
    ),
}

DEFAULT_PAIR_ID = "neutral"


# ============ TỪ KHÓA GỢI Ý NGỮ CẢNH XƯNG HÔ ============
# Dựa vào context window để suy luận quan hệ
_FORMAL_CUES = [
    "sir", "madam", "mr", "mrs", "ms", "dr", "professor", "doctor",
    "meeting", "contract", "company", "business", "sincerely", "regards",
    "ngài", "quý", "kính", "thưa",
]
_INTIMATE_CUES = [
    "love", "honey", "darling", "sweetheart", "miss you", "my dear",
    "yêu", "thương", "nhớ em", "nhớ anh", "cưng",
]
_PEER_CUES = [
    "dude", "bro", "buddy", "mate", "hey", "what's up", "lol",
    "ông", "bà", "mày", "tao", "ê",
]
_FAMILY_CUES = [
    "mom", "dad", "mother", "father", "grandma", "grandpa", "uncle", "aunt",
    "son", "daughter", "brother", "sister", "child",
    "mẹ", "bố", "ba", "má", "ông", "bà", "cô", "chú", "bác", "con", "cháu",
]


class HonorificResolver:
    """
    Xác định cách xưng hô tiếng Việt phù hợp dựa trên ngữ cảnh.

    Cách dùng:
        resolver = HonorificResolver()
        pair, is_ambiguous = resolver.resolve(context_sentences)
        text = resolver.apply_to_translation(translated, pair)
    """

    def __init__(self):
        self._current_pair_id = DEFAULT_PAIR_ID
        # Người dùng có thể override thủ công
        self._manual_pair_id: Optional[str] = None

    def set_manual_pair(self, pair_id: Optional[str]):
        """Đặt cặp xưng hô thủ công (None = tự động)."""
        self._manual_pair_id = pair_id

    def resolve(self, context_sentences: List[str]) -> Tuple[HonorificPair, bool]:
        """
        Suy luận cặp xưng hô từ ngữ cảnh.

        Args:
            context_sentences: các câu gần nhất (context window)

        Returns:
            (HonorificPair, is_ambiguous)
            is_ambiguous=True nghĩa là thiếu thông tin, dùng trung lập (Req 3.7)
        """
        if self._manual_pair_id:
            return HONORIFIC_PAIRS[self._manual_pair_id], False

        context = " ".join(context_sentences).lower()

        if not context.strip():
            return HONORIFIC_PAIRS[DEFAULT_PAIR_ID], True

        # Tính điểm cho từng nhóm cue
        scores = {
            "formal": self._count_cues(context, _FORMAL_CUES),
            "intimate": self._count_cues(context, _INTIMATE_CUES),
            "peer": self._count_cues(context, _PEER_CUES),
            "family": self._count_cues(context, _FAMILY_CUES),
        }

        max_score = max(scores.values())
        if max_score == 0:
            # Không có cue rõ ràng → trung lập + đánh dấu mơ hồ (Req 3.7)
            return HONORIFIC_PAIRS[DEFAULT_PAIR_ID], True

        # Chọn nhóm điểm cao nhất → map sang pair
        best = max(scores, key=scores.get)
        pair_id = {
            "formal": "formal_senior",
            "intimate": "intimate",
            "peer": "peer",
            "family": "younger_to_older_male",  # mặc định gia đình
        }.get(best, DEFAULT_PAIR_ID)

        self._current_pair_id = pair_id
        logger.debug(f"Honorific: {best} cues -> {HONORIFIC_PAIRS[pair_id].label}")
        return HONORIFIC_PAIRS[pair_id], False

    def _count_cues(self, text: str, cues: List[str]) -> int:
        return sum(1 for cue in cues if cue in text)

    def apply_to_translation(self, translated: str, pair: HonorificPair) -> str:
        """
        Hậu xử lý: thay đại từ trung lập trong bản dịch bằng cặp xưng hô đã chọn.

        Lưu ý: đây là bản heuristic. Bản LLM sẽ đưa pair vào prompt để dịch
        chính xác hơn ngay từ đầu.
        """
        if pair.id == DEFAULT_PAIR_ID:
            return translated

        result = translated
        # Thay "bạn" (you trung lập) bằng second_person của pair
        # Chỉ thay khi pair khác trung lập
        replacements = [
            (r"\btôi\b", pair.first_person),
            (r"\bbạn\b", pair.second_person),
        ]
        for pattern, repl in replacements:
            result = re.sub(pattern, repl, result)

        return result

    def list_pairs(self) -> List[HonorificPair]:
        """Danh sách các cặp xưng hô để UI cho người dùng chọn."""
        return list(HONORIFIC_PAIRS.values())

    def reset(self):
        self._current_pair_id = DEFAULT_PAIR_ID

    @property
    def current_pair(self) -> HonorificPair:
        if self._manual_pair_id:
            return HONORIFIC_PAIRS[self._manual_pair_id]
        return HONORIFIC_PAIRS[self._current_pair_id]
