"""
Context Classifier - Phân loại tình huống hội thoại.

Theo tư vấn chuyên môn: ngữ cảnh ngầm hiểu là cái khó nhất.
- Dùng Context_Window (nhiều câu gần nhất) thay vì 1 câu đơn lẻ (Req 1.7)
- Phân loại vào Domain_Profile với độ tin cậy (Req 1.1, 1.2)
- Fallback về "daily" nếu confidence < 0.6 (Req 1.3)
"""

from collections import deque
from typing import Deque, Tuple
from loguru import logger

from .domain_profiles import ALL_PROFILES, DEFAULT_PROFILE_ID, DomainProfile, get_profile


class ContextClassifier:
    """
    Phân loại ngữ cảnh hội thoại dựa trên keyword matching + context window.

    Đây là bản keyword-based nhẹ (chạy nhanh, offline).
    Có thể nâng cấp lên LLM-based classifier sau.
    """

    CONFIDENCE_THRESHOLD = 0.6
    WINDOW_SIZE = 5  # Số câu gần nhất làm context

    def __init__(self):
        # Context window: lưu các câu gần nhất
        self._window: Deque[str] = deque(maxlen=self.WINDOW_SIZE)
        self._current_profile_id = DEFAULT_PROFILE_ID
        # Sticky: profile hiện tại có "quán tính", tránh nhảy liên tục
        self._sticky_score = 0.0

    def add_to_window(self, text: str):
        """Thêm câu vào context window"""
        if text and text.strip():
            self._window.append(text.lower())

    def classify(self, text: str) -> Tuple[DomainProfile, float]:
        """
        Phân loại đoạn văn bản vào một Domain_Profile.

        Dùng cả câu hiện tại + context window với trọng số giảm dần
        (câu mới nhất quan trọng hơn câu cũ).

        Returns:
            (DomainProfile, confidence)
        """
        # Thêm câu mới vào window
        self.add_to_window(text)

        if not self._window:
            return get_profile(DEFAULT_PROFILE_ID), 1.0

        # Tính điểm cho mỗi profile với trọng số giảm dần theo độ cũ
        # Câu mới nhất (cuối window) có trọng số cao nhất
        scores: dict = {}
        window_list = list(self._window)
        n = len(window_list)

        for pid, profile in ALL_PROFILES.items():
            if pid == DEFAULT_PROFILE_ID:
                continue  # daily là fallback
            total_score = 0.0
            for i, sentence in enumerate(window_list):
                # Trọng số: câu mới nhất = 1.0, càng cũ càng giảm
                # i=n-1 (mới nhất) → weight 1.0; i=0 (cũ nhất) → weight thấp
                recency_weight = (i + 1) / n
                kw_score = self._score_profile(sentence, profile)
                total_score += kw_score * recency_weight
            if total_score > 0:
                scores[pid] = total_score

        if not scores:
            # Không match domain nào → daily
            self._current_profile_id = DEFAULT_PROFILE_ID
            return get_profile(DEFAULT_PROFILE_ID), 1.0

        # Profile điểm cao nhất
        best_pid = max(scores, key=scores.get)
        best_score = scores[best_pid]

        # Normalize confidence (0-1)
        total = sum(scores.values())
        confidence = best_score / total if total > 0 else 0.0

        # Sticky logic: chỉ đổi profile khi đủ tin cậy
        if best_pid != self._current_profile_id:
            if confidence < self.CONFIDENCE_THRESHOLD:
                # Chưa đủ tin cậy để đổi → giữ profile hiện tại
                if self._current_profile_id == DEFAULT_PROFILE_ID:
                    return get_profile(DEFAULT_PROFILE_ID), confidence
                return get_profile(self._current_profile_id), self._sticky_score

        self._current_profile_id = best_pid
        self._sticky_score = confidence

        profile = get_profile(best_pid)
        logger.debug(f"Context: '{text[:40]}...' → {profile.name} ({confidence:.2f})")

        return profile, confidence

    def _score_profile(self, text: str, profile: DomainProfile) -> float:
        """Tính điểm match của text với profile (số keyword xuất hiện)"""
        score = 0.0
        for kw in profile.keywords:
            if kw.lower() in text:
                score += 1.0
        return score

    def reset(self):
        """Reset context window"""
        self._window.clear()
        self._current_profile_id = DEFAULT_PROFILE_ID
        self._sticky_score = 0.0

    @property
    def context_window(self) -> list:
        return list(self._window)

    @property
    def current_profile(self) -> DomainProfile:
        return get_profile(self._current_profile_id)
