"""
Danh sách ngôn ngữ và mapping giọng TTS.

Hỗ trợ dịch từ mọi ngôn ngữ sang mọi ngôn ngữ.
- STT (Whisper): ~99 ngôn ngữ
- Translation (Google): ~130 ngôn ngữ
- TTS (Edge): ~70 ngôn ngữ với nhiều giọng
"""

# Ngôn ngữ Whisper STT hỗ trợ (code: tên hiển thị)
WHISPER_LANGUAGES = {
    "auto": "Auto Detect",
    "en": "English",
    "vi": "Vietnamese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "it": "Italian",
    "pt": "Portuguese",
    "th": "Thai",
    "id": "Indonesian",
    "ar": "Arabic",
    "hi": "Hindi",
    "nl": "Dutch",
    "tr": "Turkish",
    "pl": "Polish",
    "uk": "Ukrainian",
    "sv": "Swedish",
    "cs": "Czech",
    "el": "Greek",
    "he": "Hebrew",
    "da": "Danish",
    "fi": "Finnish",
    "no": "Norwegian",
    "ro": "Romanian",
    "hu": "Hungarian",
    "ms": "Malay",
    "fa": "Persian",
    "ta": "Tamil",
    "ur": "Urdu",
    "bn": "Bengali",
}

# Edge TTS voices - mapping ngôn ngữ → danh sách giọng
# Format: lang_code: [(voice_id, display_name, gender), ...]
EDGE_TTS_VOICES = {
    "vi": [
        ("vi-VN-HoaiMyNeural", "Hoài My (Nữ)", "Female"),
        ("vi-VN-NamMinhNeural", "Nam Minh (Nam)", "Male"),
    ],
    "en": [
        ("en-US-JennyNeural", "Jenny (US, Female)", "Female"),
        ("en-US-GuyNeural", "Guy (US, Male)", "Male"),
        ("en-US-AriaNeural", "Aria (US, Female)", "Female"),
        ("en-GB-SoniaNeural", "Sonia (UK, Female)", "Female"),
        ("en-GB-RyanNeural", "Ryan (UK, Male)", "Male"),
        ("en-AU-NatashaNeural", "Natasha (AU, Female)", "Female"),
    ],
    "zh": [
        ("zh-CN-XiaoxiaoNeural", "Xiaoxiao (Nữ)", "Female"),
        ("zh-CN-YunxiNeural", "Yunxi (Nam)", "Male"),
        ("zh-CN-XiaoyiNeural", "Xiaoyi (Nữ)", "Female"),
        ("zh-TW-HsiaoChenNeural", "HsiaoChen (TW, Nữ)", "Female"),
    ],
    "ja": [
        ("ja-JP-NanamiNeural", "Nanami (Nữ)", "Female"),
        ("ja-JP-KeitaNeural", "Keita (Nam)", "Male"),
    ],
    "ko": [
        ("ko-KR-SunHiNeural", "SunHi (Nữ)", "Female"),
        ("ko-KR-InJoonNeural", "InJoon (Nam)", "Male"),
    ],
    "fr": [
        ("fr-FR-DeniseNeural", "Denise (Nữ)", "Female"),
        ("fr-FR-HenriNeural", "Henri (Nam)", "Male"),
    ],
    "de": [
        ("de-DE-KatjaNeural", "Katja (Nữ)", "Female"),
        ("de-DE-ConradNeural", "Conrad (Nam)", "Male"),
    ],
    "es": [
        ("es-ES-ElviraNeural", "Elvira (Nữ)", "Female"),
        ("es-ES-AlvaroNeural", "Alvaro (Nam)", "Male"),
        ("es-MX-DaliaNeural", "Dalia (MX, Nữ)", "Female"),
    ],
    "ru": [
        ("ru-RU-SvetlanaNeural", "Svetlana (Nữ)", "Female"),
        ("ru-RU-DmitryNeural", "Dmitry (Nam)", "Male"),
    ],
    "it": [
        ("it-IT-ElsaNeural", "Elsa (Nữ)", "Female"),
        ("it-IT-DiegoNeural", "Diego (Nam)", "Male"),
    ],
    "pt": [
        ("pt-BR-FranciscaNeural", "Francisca (BR, Nữ)", "Female"),
        ("pt-BR-AntonioNeural", "Antonio (BR, Nam)", "Male"),
    ],
    "th": [
        ("th-TH-PremwadeeNeural", "Premwadee (Nữ)", "Female"),
        ("th-TH-NiwatNeural", "Niwat (Nam)", "Male"),
    ],
    "id": [
        ("id-ID-GadisNeural", "Gadis (Nữ)", "Female"),
        ("id-ID-ArdiNeural", "Ardi (Nam)", "Male"),
    ],
    "ar": [
        ("ar-SA-ZariyahNeural", "Zariyah (Nữ)", "Female"),
        ("ar-SA-HamedNeural", "Hamed (Nam)", "Male"),
    ],
    "hi": [
        ("hi-IN-SwaraNeural", "Swara (Nữ)", "Female"),
        ("hi-IN-MadhurNeural", "Madhur (Nam)", "Male"),
    ],
    "nl": [
        ("nl-NL-ColetteNeural", "Colette (Nữ)", "Female"),
        ("nl-NL-MaartenNeural", "Maarten (Nam)", "Male"),
    ],
    "tr": [
        ("tr-TR-EmelNeural", "Emel (Nữ)", "Female"),
        ("tr-TR-AhmetNeural", "Ahmet (Nam)", "Male"),
    ],
    "pl": [
        ("pl-PL-ZofiaNeural", "Zofia (Nữ)", "Female"),
        ("pl-PL-MarekNeural", "Marek (Nam)", "Male"),
    ],
    "uk": [
        ("uk-UA-PolinaNeural", "Polina (Nữ)", "Female"),
        ("uk-UA-OstapNeural", "Ostap (Nam)", "Male"),
    ],
    "sv": [
        ("sv-SE-SofieNeural", "Sofie (Nữ)", "Female"),
        ("sv-SE-MattiasNeural", "Mattias (Nam)", "Male"),
    ],
    "cs": [
        ("cs-CZ-VlastaNeural", "Vlasta (Nữ)", "Female"),
        ("cs-CZ-AntoninNeural", "Antonin (Nam)", "Male"),
    ],
    "el": [
        ("el-GR-AthinaNeural", "Athina (Nữ)", "Female"),
        ("el-GR-NestorasNeural", "Nestoras (Nam)", "Male"),
    ],
    "he": [
        ("he-IL-HilaNeural", "Hila (Nữ)", "Female"),
        ("he-IL-AvriNeural", "Avri (Nam)", "Male"),
    ],
    "da": [
        ("da-DK-ChristelNeural", "Christel (Nữ)", "Female"),
        ("da-DK-JeppeNeural", "Jeppe (Nam)", "Male"),
    ],
    "fi": [
        ("fi-FI-NooraNeural", "Noora (Nữ)", "Female"),
        ("fi-FI-HarriNeural", "Harri (Nam)", "Male"),
    ],
    "no": [
        ("nb-NO-PernilleNeural", "Pernille (Nữ)", "Female"),
        ("nb-NO-FinnNeural", "Finn (Nam)", "Male"),
    ],
    "ro": [
        ("ro-RO-AlinaNeural", "Alina (Nữ)", "Female"),
        ("ro-RO-EmilNeural", "Emil (Nam)", "Male"),
    ],
    "hu": [
        ("hu-HU-NoemiNeural", "Noemi (Nữ)", "Female"),
        ("hu-HU-TamasNeural", "Tamas (Nam)", "Male"),
    ],
    "ms": [
        ("ms-MY-YasminNeural", "Yasmin (Nữ)", "Female"),
        ("ms-MY-OsmanNeural", "Osman (Nam)", "Male"),
    ],
    "fa": [
        ("fa-IR-DilaraNeural", "Dilara (Nữ)", "Female"),
        ("fa-IR-FaridNeural", "Farid (Nam)", "Male"),
    ],
    "ta": [
        ("ta-IN-PallaviNeural", "Pallavi (Nữ)", "Female"),
        ("ta-IN-ValluvarNeural", "Valluvar (Nam)", "Male"),
    ],
    "ur": [
        ("ur-PK-UzmaNeural", "Uzma (Nữ)", "Female"),
        ("ur-PK-AsadNeural", "Asad (Nam)", "Male"),
    ],
    "bn": [
        ("bn-IN-TanishaaNeural", "Tanishaa (Nữ)", "Female"),
        ("bn-IN-BashkarNeural", "Bashkar (Nam)", "Male"),
    ],
}

# Google Translate language codes (subset phổ biến, deep-translator hỗ trợ ~130)
# Whisper code → Google Translate code (đa số giống nhau)
GOOGLE_LANG_MAP = {
    "auto": "auto",
    "en": "en", "vi": "vi", "zh": "zh-CN", "ja": "ja", "ko": "ko",
    "fr": "fr", "de": "de", "es": "es", "ru": "ru", "it": "it",
    "pt": "pt", "th": "th", "id": "id", "ar": "ar", "hi": "hi",
    "nl": "nl", "tr": "tr", "pl": "pl", "uk": "uk", "sv": "sv",
    "cs": "cs", "el": "el", "he": "iw", "da": "da", "fi": "fi",
    "no": "no", "ro": "ro", "hu": "hu", "ms": "ms", "fa": "fa",
    "ta": "ta", "ur": "ur", "bn": "bn",
}


def get_source_languages() -> list:
    """Danh sách ngôn ngữ nguồn (cho STT) - bao gồm Auto Detect"""
    return [(code, name) for code, name in WHISPER_LANGUAGES.items()]


def get_target_languages() -> list:
    """
    Danh sách ngôn ngữ đích (cho Translation + TTS).
    Chỉ các ngôn ngữ có TTS voice (để đọc được).
    """
    result = []
    for code, name in WHISPER_LANGUAGES.items():
        if code == "auto":
            continue
        if code in EDGE_TTS_VOICES:
            result.append((code, name))
    return result


def get_voices_for_language(lang_code: str) -> list:
    """Lấy danh sách giọng TTS cho 1 ngôn ngữ"""
    return EDGE_TTS_VOICES.get(lang_code, [])


def get_default_voice(lang_code: str) -> str:
    """Lấy giọng mặc định cho ngôn ngữ"""
    voices = EDGE_TTS_VOICES.get(lang_code, [])
    if voices:
        return voices[0][0]
    return "en-US-JennyNeural"


def get_google_code(whisper_code: str) -> str:
    """Convert Whisper lang code sang Google Translate code"""
    return GOOGLE_LANG_MAP.get(whisper_code, whisper_code)
