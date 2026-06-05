"""
Cultural Insight Module - Thành ngữ, tiếng lóng, hàm ý văn hóa (Req 3.1-3.3).

App quốc tế dịch sát nghĩa từng từ → mất ý. Module này:
- Phát hiện thành ngữ/tiếng lóng Việt-Anh
- Tạo ghi chú giải thích ý nghĩa văn hóa (Req 3.1)
- Đề xuất cách diễn đạt tự nhiên hơn (Req 3.2)
- Cung cấp ví dụ thực tế (Req 3.3)
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
from loguru import logger


@dataclass
class CulturalNote:
    """Ghi chú văn hóa cho một thành ngữ/tiếng lóng."""
    phrase: str            # cụm từ gốc
    literal: str           # nghĩa đen (dịch sát)
    meaning: str           # ý nghĩa thực sự
    natural: str           # cách diễn đạt tự nhiên ở ngôn ngữ đích
    example: str           # ví dụ sử dụng


# ============ CƠ SỞ DỮ LIỆU THÀNH NGỮ / TIẾNG LÓNG ============
# Việt -> Anh
VI_IDIOMS: Dict[str, CulturalNote] = {
    "anh ấy đi rồi": CulturalNote(
        phrase="anh ấy đi rồi",
        literal="he went already",
        meaning="Tùy ngữ cảnh: ra ngoài / nghỉ việc / qua đời. Cần xét tình huống.",
        natural="He's gone / He left / He has passed away (tùy ngữ cảnh)",
        example="'Anh ấy đi rồi' (trong đám tang) = He has passed away.",
    ),
    "ăn cơm chưa": CulturalNote(
        phrase="ăn cơm chưa",
        literal="have you eaten rice yet",
        meaning="Lời chào hỏi thân mật, không phải hỏi thật về việc ăn uống.",
        natural="How are you? / Hey, how's it going?",
        example="Gặp nhau hỏi 'ăn cơm chưa' = cách chào thân mật.",
    ),
    "trà xanh": CulturalNote(
        phrase="trà xanh",
        literal="green tea",
        meaning="Tiếng lóng: người thứ ba xen vào mối quan hệ, giả vờ ngây thơ.",
        natural="homewrecker / the other woman",
        example="'Nó là trà xanh' = She's the other woman.",
    ),
    "gato": CulturalNote(
        phrase="gato",
        literal="gateau (cake)",
        meaning="Tiếng lóng: ghen ăn tức ở (Ghen Ăn Tức Ở viết tắt).",
        natural="jealous / envious",
        example="'Đừng gato' = Don't be jealous.",
    ),
    "chém gió": CulturalNote(
        phrase="chém gió",
        literal="chop the wind",
        meaning="Nói chuyện phóng đại, khoác lác, bốc phét.",
        natural="to brag / talk big / exaggerate",
        example="'Nó chém gió thôi' = He's just bragging.",
    ),
    "thả thính": CulturalNote(
        phrase="thả thính",
        literal="release bait",
        meaning="Tiếng lóng: tán tỉnh, gây chú ý để người khác thích mình.",
        natural="to flirt / lead someone on",
        example="'Đừng thả thính nữa' = Stop flirting.",
    ),
}

# Anh -> Việt
EN_IDIOMS: Dict[str, CulturalNote] = {
    "break a leg": CulturalNote(
        phrase="break a leg",
        literal="gãy chân",
        meaning="Lời chúc may mắn (đặc biệt trước khi biểu diễn).",
        natural="Chúc may mắn! / Cố lên!",
        example="'Break a leg!' trước buổi diễn = Chúc may mắn!",
    ),
    "piece of cake": CulturalNote(
        phrase="piece of cake",
        literal="miếng bánh",
        meaning="Việc rất dễ dàng.",
        natural="dễ như ăn kẹo / dễ ợt",
        example="'It's a piece of cake' = Dễ như ăn kẹo.",
    ),
    "hit the books": CulturalNote(
        phrase="hit the books",
        literal="đánh sách",
        meaning="Học hành chăm chỉ.",
        natural="cắm đầu vào học / học bài",
        example="'I need to hit the books' = Tôi phải cắm đầu vào học.",
    ),
    "under the weather": CulturalNote(
        phrase="under the weather",
        literal="dưới thời tiết",
        meaning="Cảm thấy không khỏe, hơi ốm.",
        natural="thấy không khỏe / hơi mệt",
        example="'I'm under the weather' = Tôi thấy không khỏe.",
    ),
    "spill the tea": CulturalNote(
        phrase="spill the tea",
        literal="làm đổ trà",
        meaning="Kể chuyện bí mật, tin đồn, drama.",
        natural="kể hết đi / bóc phốt đi",
        example="'Spill the tea!' = Kể hết đi!",
    ),
}


class CulturalInsightModule:
    """
    Phát hiện và giải thích thành ngữ/tiếng lóng (Req 3.1-3.3).

    Chỉ áp dụng cho cặp Việt-Anh / Anh-Việt (Req 3.4).
    """

    def __init__(self):
        # Lưu ghi chú để truy cập sau (Req 3.1)
        self._notes_history: List[CulturalNote] = []

    def is_supported_pair(self, source_lang: str, target_lang: str) -> bool:
        """Chỉ Việt-Anh / Anh-Việt (Req 3.4)."""
        pair = {source_lang.lower(), target_lang.lower()}
        return pair == {"vi", "en"}

    def detect(self, text: str, source_lang: str, target_lang: str) -> Optional[CulturalNote]:
        """
        Phát hiện thành ngữ/tiếng lóng trong text.

        Returns CulturalNote nếu tìm thấy, None nếu không.
        """
        if not self.is_supported_pair(source_lang, target_lang):
            return None  # Req 3.4: bỏ qua cặp ngôn ngữ khác

        text_lower = text.lower()

        # Chọn DB theo ngôn ngữ nguồn
        db = VI_IDIOMS if source_lang.lower() == "vi" else EN_IDIOMS

        # Tìm thành ngữ xuất hiện trong text
        for phrase, note in db.items():
            if phrase in text_lower:
                self._notes_history.append(note)
                logger.debug(f"Cultural note: '{phrase}' -> {note.meaning[:40]}")
                return note

        return None

    def get_example(self, phrase: str, source_lang: str) -> Optional[str]:
        """Lấy ví dụ sử dụng cho 1 cụm từ (Req 3.3)."""
        db = VI_IDIOMS if source_lang.lower() == "vi" else EN_IDIOMS
        note = db.get(phrase.lower())
        return note.example if note else None

    @property
    def notes_history(self) -> List[CulturalNote]:
        """Lịch sử ghi chú văn hóa (Req 3.1 - lưu để truy cập sau)."""
        return self._notes_history.copy()

    def reset(self):
        self._notes_history = []
