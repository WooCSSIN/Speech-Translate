"""
Han Translate - Translation API Server (cho n8n và tích hợp ngoài).

API nhe chi expose phan DICH CONTEXT-AWARE (Capability A) - khong gom
audio/STT/TTS (von la realtime, khong phu hop goi qua HTTP).

Day la diem khac biet cua Han Translate ma n8n co the tan dung:
dich tu nhan dien ngu canh/chuyen nganh.

BAO MAT (Uu tien 1):
- API key authentication (header X-API-Key)
- CORS gioi han (chi localhost + Docker)
- Rate limiting per-IP (chong spam/DoS)
- Input validation (gioi han do dai)
- Safe logging (an noi dung nhay cam)

Chay:
    .\\venv\\Scripts\\python.exe -m uvicorn ai_interpreter.api_server:app --host 127.0.0.1 --port 8000

Bien moi truong:
    HAN_TRANSLATE_API_KEY = <key>   (neu khong set, server tu tao va luu vao Credential Manager)
    HAN_TRANSLATE_CORS_ORIGINS = http://localhost:5678,...  (tuy chon)

n8n (trong Docker) goi toi: http://host.docker.internal:8000/translate
voi header: X-API-Key: <key>
"""

import os
from typing import Optional, List

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator
from loguru import logger

from .translation.engine import TranslationEngine
from .config import TranslationConfig
from .context.classifier import ContextClassifier
from .context.domain_profiles import list_profiles, get_profile
from . import security

# ---------- Khoi tao bao mat ----------
# Dam bao co API key (tao moi neu chua co)
API_KEY = security.ensure_api_key()

# Rate limiter: 60 request / 60 giay moi IP
rate_limiter = security.RateLimiter(max_requests=60, window_seconds=60)

# CORS: chi cho phep localhost + n8n Docker (KHONG dung "*")
_default_origins = [
    "http://localhost:5678",
    "http://127.0.0.1:5678",
    "http://localhost",
    "http://127.0.0.1",
]
_env_origins = os.environ.get("HAN_TRANSLATE_CORS_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins
)

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


app = FastAPI(
    title="Han Translate API",
    description="API dich context-aware - tu nhan dien ngu canh chuyen nganh",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)


# ---------- Dependencies (auth + rate limit) ----------
async def require_api_key(provided: Optional[str] = Depends(api_key_header)):
    """Xac thuc API key. Thieu/sai -> 401 (deny by default)."""
    if not security.verify_api_key(provided):
        logger.warning("Tu choi request: API key thieu hoac sai")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return True


async def check_rate_limit(request: Request):
    """Gioi han so request theo IP."""
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit vuot nguong: {security.hash_id(client_ip)}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down.",
        )
    return True


# Translation engine (Google Translate - nhe, khong can GPU)
_tl_config = TranslationConfig()
_engine = TranslationEngine(_tl_config)


# ---------- Request/Response models ----------
class TranslateRequest(BaseModel):
    text: str = Field(..., description="Van ban can dich", max_length=security.MAX_TEXT_LENGTH)
    source_lang: str = Field("auto", description="Ngon ngu nguon (auto/en/vi/ja...)", max_length=10)
    target_lang: str = Field("vi", description="Ngon ngu dich", max_length=10)
    domain: Optional[str] = Field(
        None,
        description="Linh vuc thu cong (medical/legal/technical/fintech/travel/business/daily). "
        "None = tu dong nhan dien.",
        max_length=20,
    )

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("text khong duoc rong")
        return v


class TranslateResponse(BaseModel):
    original: str
    translated: str
    source_lang: str
    target_lang: str
    domain_id: str
    domain_name: str
    domain_confidence: float
    auto_detected: bool


class DomainInfo(BaseModel):
    id: str
    name: str
    keywords_count: int


# ---------- Endpoints ----------
@app.get("/")
def root():
    """Endpoint cong khai - khong lo thong tin nhay cam."""
    return {
        "service": "Han Translate API",
        "version": "1.0.0",
        "auth": "required (X-API-Key header)",
        "endpoints": ["/translate", "/domains", "/health"],
    }


@app.get("/health")
def health():
    """Health check - cong khai cho Docker/monitoring."""
    return {"status": "healthy"}


@app.get("/domains", response_model=List[DomainInfo], dependencies=[Depends(require_api_key)])
def domains():
    """Danh sach cac linh vuc ho tro (yeu cau API key)."""
    return [
        DomainInfo(id=p.id, name=p.name, keywords_count=len(p.keywords))
        for p in list_profiles()
    ]


@app.post(
    "/translate",
    response_model=TranslateResponse,
    dependencies=[Depends(require_api_key), Depends(check_rate_limit)],
)
def translate(req: TranslateRequest):
    """
    Dich van ban voi nhan dien ngu canh chuyen nganh.

    - domain=None: AI tu nhan dien linh vuc
    - domain="medical"/...: ep dung linh vuc cu the

    Yeu cau header: X-API-Key
    """
    # Validate them do dai (pydantic da chan, day la lop phong thu thu 2)
    if not security.validate_text_length(req.text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"text qua dai (max {security.MAX_TEXT_LENGTH} ky tu)",
        )

    # Validate ma ngon ngu (chong injection qua tham so lang)
    if not security.is_safe_lang_code(req.source_lang) or not security.is_safe_lang_code(req.target_lang):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ma ngon ngu khong hop le",
        )

    # Sanitize input (loai control chars, null byte)
    clean_text = security.sanitize_text(req.text)
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="text rong sau khi lam sach",
        )

    # Cap nhat cau hinh ngon ngu theo request
    _engine.config.source_lang = req.source_lang
    _engine.config.target_lang = req.target_lang

    # Xac dinh domain: thu cong hoac tu dong (moi request 1 classifier de stateless)
    if req.domain:
        profile = get_profile(req.domain)
        confidence = 1.0
        auto = False
    else:
        clf = ContextClassifier()
        profile, confidence = clf.classify(clean_text)
        auto = True

    # Dich
    translated = _engine.translate(clean_text, source_lang=req.source_lang)

    # Safe logging: KHONG log toan bo noi dung (Req 11.2)
    logger.info(f"[{profile.id}] {security.redact(clean_text)} -> {security.redact(translated)}")

    return TranslateResponse(
        original=clean_text,
        translated=translated,
        source_lang=req.source_lang,
        target_lang=req.target_lang,
        domain_id=profile.id,
        domain_name=profile.name,
        domain_confidence=round(confidence, 2),
        auto_detected=auto,
    )
