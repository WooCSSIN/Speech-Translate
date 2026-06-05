"""
Domain Profiles - Cấu hình lĩnh vực độc lập.

Mỗi Domain_Profile là cấu hình riêng biệt (KHÔNG train all-in-one):
- keywords: từ khóa nhận diện tình huống
- style: phong cách dịch
- prompt_hint: gợi ý cho LLM/translator
- terminology: bộ thuật ngữ chuẩn (source → target)

Thứ tự ưu tiên theo tư vấn: ngữ cảnh là quan trọng nhất.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class DomainProfile:
    """Cấu hình một lĩnh vực dịch độc lập"""
    id: str
    name: str  # Tên hiển thị
    keywords: List[str] = field(default_factory=list)  # Từ khóa nhận diện
    style: str = "neutral"  # neutral, fast, formal, casual
    prompt_hint: str = ""  # Gợi ý ngữ cảnh cho dịch
    terminology: Dict[str, str] = field(default_factory=dict)  # source → target
    fast_mode: bool = False  # Ưu tiên tốc độ (Travel)
    basic_vocab: bool = False  # Từ vựng cơ bản (Travel)


# ============ DAILY (mặc định) ============
DAILY = DomainProfile(
    id="daily",
    name="Hằng ngày",
    keywords=[],  # fallback mặc định
    style="casual",
    prompt_hint="Dịch hội thoại hằng ngày, tự nhiên, thân thiện.",
)

# ============ TRAVEL ============
TRAVEL = DomainProfile(
    id="travel",
    name="Du lịch",
    keywords=[
        "hotel", "restaurant", "menu", "ticket", "airport", "taxi", "map",
        "tour", "booking", "check-in", "luggage", "khách sạn", "nhà hàng",
        "vé", "sân bay", "bản đồ", "đặt phòng", "hành lý", "tham quan",
    ],
    style="fast",
    prompt_hint="Dịch nhanh cho du lịch, dùng từ vựng cơ bản, dễ hiểu.",
    fast_mode=True,
    basic_vocab=True,
)

# ============ MEDICAL ============
MEDICAL = DomainProfile(
    id="medical",
    name="Y tế",
    keywords=[
        "doctor", "patient", "symptom", "diagnosis", "prescription", "medicine",
        "hospital", "pain", "fever", "blood", "surgery", "treatment", "dose",
        "bác sĩ", "bệnh nhân", "triệu chứng", "chẩn đoán", "đơn thuốc", "thuốc",
        "bệnh viện", "đau", "sốt", "máu", "phẫu thuật", "điều trị", "liều",
    ],
    style="formal",
    prompt_hint="Dịch chính xác thuật ngữ y tế, giữ nghĩa chuyên môn, không suy diễn.",
    terminology={
        "blood pressure": "huyết áp",
        "heart rate": "nhịp tim",
        "prescription": "đơn thuốc",
        "dosage": "liều lượng",
        "side effect": "tác dụng phụ",
        "diagnosis": "chẩn đoán",
        "symptom": "triệu chứng",
        "antibiotic": "kháng sinh",
    },
)

# ============ LEGAL ============
LEGAL = DomainProfile(
    id="legal",
    name="Pháp lý",
    keywords=[
        "contract", "agreement", "clause", "law", "legal", "court", "lawyer",
        "liability", "plaintiff", "defendant", "rights", "obligation",
        "hợp đồng", "thỏa thuận", "điều khoản", "pháp luật", "tòa án", "luật sư",
        "trách nhiệm", "nguyên đơn", "bị đơn", "quyền", "nghĩa vụ",
    ],
    style="formal",
    prompt_hint="Dịch chính xác thuật ngữ pháp lý, giữ tính chính xác và trang trọng.",
    terminology={
        "contract": "hợp đồng",
        "agreement": "thỏa thuận",
        "clause": "điều khoản",
        "liability": "trách nhiệm pháp lý",
        "plaintiff": "nguyên đơn",
        "defendant": "bị đơn",
        "breach of contract": "vi phạm hợp đồng",
        "terms and conditions": "điều khoản và điều kiện",
    },
)

# ============ TECHNICAL / IT ============
TECHNICAL = DomainProfile(
    id="technical",
    name="Kỹ thuật / IT",
    keywords=[
        "code", "function", "api", "server", "database", "algorithm", "bug",
        "deploy", "framework", "variable", "compile", "runtime", "library",
        "hàm", "máy chủ", "cơ sở dữ liệu", "thuật toán", "lỗi", "triển khai",
        "biến", "biên dịch", "thư viện",
    ],
    style="neutral",
    prompt_hint="Dịch tài liệu kỹ thuật, giữ nguyên thuật ngữ tiếng Anh phổ biến khi cần.",
    terminology={
        "database": "cơ sở dữ liệu",
        "algorithm": "thuật toán",
        "deploy": "triển khai",
        "runtime": "thời gian chạy",
        "compile": "biên dịch",
    },
)

# ============ FINTECH ============
FINTECH = DomainProfile(
    id="fintech",
    name="Tài chính",
    keywords=[
        "bank", "account", "transaction", "investment", "stock", "loan",
        "interest", "payment", "credit", "currency", "balance", "tax",
        "ngân hàng", "tài khoản", "giao dịch", "đầu tư", "cổ phiếu", "khoản vay",
        "lãi suất", "thanh toán", "tín dụng", "tiền tệ", "số dư", "thuế",
    ],
    style="formal",
    prompt_hint="Dịch chính xác thuật ngữ tài chính - ngân hàng.",
    terminology={
        "interest rate": "lãi suất",
        "transaction": "giao dịch",
        "investment": "đầu tư",
        "balance": "số dư",
        "credit score": "điểm tín dụng",
        "exchange rate": "tỷ giá",
    },
)

# ============ BUSINESS / MEETING ============
BUSINESS = DomainProfile(
    id="business",
    name="Kinh doanh",
    keywords=[
        "meeting", "project", "deadline", "report", "client", "strategy",
        "revenue", "team", "presentation", "proposal", "budget", "kpi",
        "cuộc họp", "dự án", "báo cáo", "khách hàng", "chiến lược",
        "doanh thu", "nhóm", "thuyết trình", "đề xuất", "ngân sách",
    ],
    style="formal",
    prompt_hint="Dịch ngôn ngữ kinh doanh, trang trọng và chuyên nghiệp.",
)


# Registry tất cả profiles
ALL_PROFILES: Dict[str, DomainProfile] = {
    p.id: p for p in [DAILY, TRAVEL, MEDICAL, LEGAL, TECHNICAL, FINTECH, BUSINESS]
}

DEFAULT_PROFILE_ID = "daily"


def get_profile(profile_id: str) -> DomainProfile:
    """Lấy profile theo id, fallback về daily"""
    return ALL_PROFILES.get(profile_id, DAILY)


def list_profiles() -> List[DomainProfile]:
    """Danh sách tất cả profiles"""
    return list(ALL_PROFILES.values())
