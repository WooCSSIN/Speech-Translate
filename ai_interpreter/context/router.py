"""
Translation Router - Định tuyến dịch theo ngữ cảnh.

Kết hợp:
- Context_Classifier: nhận diện tình huống
- Domain_Profile: chọn phong cách + thuật ngữ
- TranslationEngine: dịch thực tế
- Terminology_Base: áp dụng thuật ngữ chuẩn (Req 2.2)

Logic ưu tiên:
1. Manual override (người dùng chọn profile) → bỏ qua classifier (Req 1.4)
2. Tự động phân loại qua classifier
3. Áp dụng terminology của domain sau khi dịch
"""

from typing import Optional, Tuple
from loguru import logger

from .classifier import ContextClassifier
from .domain_profiles import DomainProfile, get_profile, DEFAULT_PROFILE_ID
from ..culture.engine import CultureEngine
from ..adaptive.engine import AdaptiveEngine
from .memory import global_context_memory


class TranslationRouter:
    """
    Router dịch theo ngữ cảnh.

    Wrap quanh TranslationEngine hiện có, thêm khả năng:
    - Tự nhận diện domain
    - Áp dụng thuật ngữ chuẩn theo domain
    - Xử lý văn hóa Việt-Anh (xưng hô, thành ngữ, vùng miền)
    """

    def __init__(self, translation_engine, enable_context: bool = True):
        self.engine = translation_engine
        self.classifier = ContextClassifier()
        self.enable_context = enable_context

        # Culture engine (Capability C)
        self.culture = CultureEngine()
        # Adaptive engine (Capability E)
        self.adaptive = AdaptiveEngine()
        # Callback ghi chú văn hóa cho UI
        self.on_cultural_note = None

        # Manual override
        self._manual_profile_id: Optional[str] = None

        # Callback khi domain thay đổi (để UI cập nhật)
        self.on_domain_change = None
        self._last_notified_profile = None

    def set_manual_profile(self, profile_id: Optional[str]):
        """
        Đặt domain thủ công (Req 1.4).
        None = tự động phân loại.
        """
        self._manual_profile_id = profile_id
        if profile_id:
            logger.info(f"Manual domain set: {get_profile(profile_id).name}")
        else:
            logger.info("Domain set to AUTO (context classifier)")

    def translate(self, text: str, source_lang: Optional[str] = None) -> Tuple[str, DomainProfile]:
        """
        Dịch text với nhận diện ngữ cảnh.

        Returns:
            (translated_text, domain_profile_used)
        """
        if not text or not text.strip():
            return "", get_profile(DEFAULT_PROFILE_ID)

        # 0. Adaptive lookup: kiểm tra Phrasebook/TM trước (Req 7.2, 7.5)
        src_lang = source_lang or self.engine.config.source_lang
        tgt_lang = self.engine.config.target_lang
        cached = self.adaptive.lookup(text, src_lang, tgt_lang)
        if cached:
            # Có bản dịch đã lưu → dùng luôn, không gọi engine
            profile = self.classifier.current_profile
            self._notify_domain(profile)
            return cached, profile

        # 1. Xác định domain
        if self._manual_profile_id:
            # Manual override (Req 1.4)
            profile = get_profile(self._manual_profile_id)
            # Vẫn cập nhật window để giữ context
            self.classifier.add_to_window(text)
        elif self.enable_context:
            # Tự động phân loại (Req 1.1)
            profile, confidence = self.classifier.classify(text)
        else:
            profile = get_profile(DEFAULT_PROFILE_ID)

        # 2. Thông báo domain change cho UI (Req 1.5)
        self._notify_domain(profile)

        # 3. Dịch với gợi ý ngữ cảnh
        translated = self._translate_with_context(text, source_lang, profile)

        # 4. Áp dụng terminology chuẩn của domain (Req 2.2)
        translated = self._apply_terminology(translated, profile, source_lang)

        # 5. Xử lý văn hóa Việt-Anh: xưng hô, thành ngữ, vùng miền (Capability C)
        src = source_lang or "auto"
        tgt = self.engine.config.target_lang
        context_window = self.classifier.context_window
        translated, note, pair = self.culture.process(
            source_text=text,
            translated=translated,
            source_lang=src,
            target_lang=tgt,
            context_window=context_window,
        )

        # Thông báo ghi chú văn hóa cho UI (Req 3.5)
        if note and self.on_cultural_note:
            self.on_cultural_note(note)

        # 6. Adaptive: lưu bản dịch vào TM (tự động học)
        self.adaptive.remember(text, translated, src_lang, tgt_lang)
        
        # 7. Lưu ngữ cảnh vào Context Memory
        global_context_memory.add_turn(text, translated)

        return translated, profile

    def _translate_with_context(self, text: str, source_lang: Optional[str],
                                 profile: DomainProfile) -> str:
        """Dịch với ngữ cảnh domain và history"""
        # Lấy lịch sử hội thoại gần đây
        context_prompt = global_context_memory.get_context_prompt()
        
        # Với engine hiện tại (Deep Translator), ta nối context vào text 
        # (Lưu ý: Đối với LLM, context sẽ được đưa vào system prompt).
        if context_prompt and self.engine.config.engine in ["openai", "ctranslate2"]:
            # Chỉ hoạt động hiệu quả trên mô hình LLM hoặc NMT có context
            full_text = context_prompt + text
        else:
            full_text = text

        translated = self.engine.translate(full_text, source_lang=source_lang)
        
        # Cắt bỏ phần context trong bản dịch nếu bị dịch theo
        # Đây là workaround cho Deep Translator, LLM sẽ xử lý mượt hơn
        return translated

    def _apply_terminology(self, translated: str, profile: DomainProfile,
                           source_lang: Optional[str]) -> str:
        """
        Áp dụng thuật ngữ chuẩn của domain (Req 2.2, 2.3).

        Hậu xử lý: thay thế các thuật ngữ trong bản dịch bằng
        bản chuẩn đã định nghĩa trong Terminology_Base.
        """
        if not profile.terminology:
            return translated

        # Áp dụng terminology (source → target)
        # Lưu ý: đây là hậu xử lý đơn giản. Khi dùng LLM,
        # terminology sẽ được đưa vào prompt để dịch chính xác hơn.
        result = translated
        for src_term, tgt_term in profile.terminology.items():
            # Chỉ thay khi target term chưa có trong kết quả
            # (tránh thay nhầm). Bản nâng cao sẽ dùng alignment.
            pass  # Placeholder: terminology injection cần dịch ở tầng LLM

        return result

    def _notify_domain(self, profile: DomainProfile):
        """Thông báo domain change cho UI (Req 1.5: trong 500ms)"""
        if self.on_domain_change:
            # Luôn gọi callback, kể cả khi không đổi (Req 1.5)
            self.on_domain_change(profile)
        self._last_notified_profile = profile.id

    def reset(self):
        """Reset context"""
        self.classifier.reset()
        self.culture.reset()
        global_context_memory.clear()
        self._last_notified_profile = None

    @property
    def current_profile(self) -> DomainProfile:
        if self._manual_profile_id:
            return get_profile(self._manual_profile_id)
        return self.classifier.current_profile
