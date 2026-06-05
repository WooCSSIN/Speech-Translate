"""Translation Engine - Dịch text sang tiếng Việt"""

import threading
from typing import Optional
from loguru import logger

from ..config import TranslationConfig


class TranslationEngine:
    """
    Translation Engine hỗ trợ nhiều backend:
    - Google Translate (online, nhanh)
    - NLLB (offline, local)
    - GPT (context-aware, tốn API)
    """

    def __init__(self, config: TranslationConfig):
        self.config = config
        self._lock = threading.Lock()

    def translate(self, text: str, source_lang: Optional[str] = None) -> str:
        """
        Dịch text sang target language.
        
        Args:
            text: Text cần dịch
            source_lang: Ngôn ngữ nguồn (override config)
            
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return ""

        src = source_lang or self.config.source_lang
        tgt = self.config.target_lang

        # Không dịch nếu cùng ngôn ngữ
        if src == tgt:
            return text

        with self._lock:
            try:
                if self.config.engine == "google":
                    return self._translate_google(text, src, tgt)
                elif self.config.engine == "nllb":
                    return self._translate_nllb(text, src, tgt)
                elif self.config.engine == "gpt":
                    return self._translate_gpt(text, src, tgt)
                else:
                    return self._translate_google(text, src, tgt)
            except Exception as e:
                logger.error(f"Translation error ({self.config.engine}): {e}")
                # Fallback tự động: Bậc 1 là Google, Bậc 2 là MyMemory
                if self.config.engine != "google":
                    try:
                        logger.warning(f"Translation failed on {self.config.engine}, falling back to Google Translate...")
                        return self._translate_google(text, src, tgt)
                    except Exception as e2:
                        logger.error(f"Google fallback failed: {e2}")
                        
                # Nếu chính Google cũng chết (hoặc fallback Google chết), dùng MyMemory
                try:
                    logger.warning("Falling back to MyMemory Translator...")
                    return self._translate_mymemory(text, src, tgt)
                except Exception as e3:
                    logger.error(f"Ultimate fallback (MyMemory) failed: {e3}. Returning original text.")
                    return text

    def _translate_google(self, text: str, src: str, tgt: str) -> str:
        """Google Translate via deep-translator"""
        from deep_translator import GoogleTranslator
        from ..languages import get_google_code

        # Convert Whisper codes → Google Translate codes
        g_src = get_google_code(src)
        g_tgt = get_google_code(tgt)

        translator = GoogleTranslator(source=g_src, target=g_tgt)
        result = translator.translate(text)
        logger.debug(f"Translate [{g_src}→{g_tgt}]: {text} → {result}")
        return result or text

    def _translate_mymemory(self, text: str, src: str, tgt: str) -> str:
        """Fallback Translator (MyMemory API)"""
        from deep_translator import MyMemoryTranslator
        from ..languages import get_google_code
        
        # MyMemory dùng chung mã với Google đa số trường hợp
        g_src = get_google_code(src)
        g_tgt = get_google_code(tgt)
        
        translator = MyMemoryTranslator(source=g_src, target=g_tgt)
        result = translator.translate(text)
        logger.debug(f"MyMemory Fallback [{g_src}→{g_tgt}]: {text} → {result}")
        return result or text

    def _translate_nllb(self, text: str, src: str, tgt: str) -> str:
        """Facebook NLLB local translation"""
        # NLLB language codes
        nllb_lang_map = {
            "en": "eng_Latn",
            "vi": "vie_Latn",
            "zh": "zho_Hans",
            "ja": "jpn_Jpan",
            "ko": "kor_Hang",
            "fr": "fra_Latn",
            "de": "deu_Latn",
            "es": "spa_Latn",
        }

        src_code = nllb_lang_map.get(src, "eng_Latn")
        tgt_code = nllb_lang_map.get(tgt, "vie_Latn")

        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(self.config.nllb_model)
        model = AutoModelForSeq2SeqLM.from_pretrained(self.config.nllb_model)

        tokenizer.src_lang = src_code
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)

        translated_tokens = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_code),
            max_new_tokens=256,
        )

        result = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        logger.debug(f"NLLB [{src}→{tgt}]: {text} → {result}")
        return result

    def _translate_gpt(self, text: str, src: str, tgt: str) -> str:
        """GPT/LLM translation (placeholder)"""
        # TODO: Implement GPT translation
        logger.warning("GPT translation not implemented, falling back to Google")
        return self._translate_google(text, src, tgt)
