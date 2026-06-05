# Kế Hoạch Triển Khai: Realtime Streaming & Context-Aware Translation (Chuẩn YouTube)

Bản kế hoạch này mô tả các bước để nâng cấp hệ thống **Speech-Translate** từ cơ chế **"Chờ nói xong mới dịch" (Chunking/VAD-based)** sang cơ chế **"Dịch đuổi theo thời gian thực" (Continuous Streaming & Partial Results)** kết hợp với khả năng hiểu ngữ cảnh.

## 🎯 Mục tiêu
1. **Độ trễ (Latency) gần như bằng 0**: Chữ hiện lên ngay khi người dùng vừa phát âm xong 1-2 từ (giống YouTube/Google Meet).
2. **Tự động sửa lỗi (Auto-correction)**: Chữ hiển thị tạm thời có thể thay đổi để chuẩn ngữ pháp khi có nhiều từ hơn.
3. **Dịch theo ngữ cảnh (Context-Aware)**: Nhớ các câu trước đó để dịch đúng đại từ nhân xưng (anh ấy, cô ấy, nó) thay vì dịch độc lập từng câu.

---

## 🛠️ Phase 1: Nâng cấp STT (Speech-to-Text) trả về Partial Results
Hiện tại, `stt/engine.py` đang dùng hàm `transcribe` và đợi vòng lặp `for segment in segments` chạy xong toàn bộ đoạn âm thanh mới trả về kết quả. 

**Công việc:**
1. **Sliding Window Audio**: Ở `server.py`, thay vì chờ VAD ngắt một đoạn dài, ta sẽ đẩy audio buffer vào STT theo từng chu kỳ ngắn (vd: 0.5 giây hoặc 1 giây).
2. **Partial Transcription**: 
   - Nếu VAD chưa xác nhận ngắt câu, ta vẫn gọi Faster-Whisper để nhận text tạm thời (Partial).
   - Nếu VAD xác nhận ngắt câu, ta gọi Faster-Whisper lần cuối để lấy text chuẩn xác nhất (Final).

## 🌍 Phase 2: Nâng cấp Context-Aware Translation
Hiện tại, `ContextMemory` và `TranslationRouter` đang nối chuỗi ngữ cảnh vào bản dịch. Việc này làm `deep-translator` (Google Translate) bị bối rối vì nó không hiểu prompt.

**Công việc:**
1. **Sử dụng LLM cho Partial/Final Context**: Tích hợp GPT-3.5/4o-mini hoặc một local LLM (ví dụ: Qwen, Llama 3) vào hàm `_translate_gpt` trong `translation/engine.py`.
2. **Cấu trúc Prompt chuẩn**: 
   - *System Message*: "Bạn là phiên dịch viên cabin realtime. Lịch sử hội thoại: [Context]. Hãy dịch tiếp câu chưa hoàn chỉnh sau đây sang Tiếng Việt..."
   - Bằng cách này, khi người dùng nói "It is..." -> LLM dựa vào câu trước ("This is an apple") để dịch là "Nó là..." thay vì "Đó là...".
3. Dịch Partial không cần lưu vào `ContextMemory`, chỉ lưu kết quả **Final** để làm ngữ cảnh cho câu tiếp theo.

## ⚡ Phase 3: Cập nhật WebSocket Server (`server.py`)
Định nghĩa lại cấu trúc JSON trả về cho Client. Thêm cờ `is_final`.

**Công việc:**
```json
// Trạng thái đang nói (Partial) - Gửi liên tục mỗi 0.5s
{
    "type": "interpretation",
    "original": "I am looking for...",
    "translated": "Tôi đang tìm...",
    "is_final": false,
    "latency_ms": 150
}

// Trạng thái đã nói xong câu (Final) - Do VAD quyết định ngắt câu
{
    "type": "interpretation",
    "original": "I am looking for a restaurant.",
    "translated": "Tôi đang tìm một nhà hàng.",
    "is_final": true,
    "audio": "base64_tts_audio..." // Chỉ gọi TTS khi is_final = true để tránh đọc ngắc ngứ
}
```

## 🎨 Phase 4: Điều chỉnh Frontend (UI)
Cần cập nhật UI để hiển thị hiệu ứng "Dịch đuổi".

**Công việc:**
1. UI nhận WebSocket payload.
2. Nếu `is_final == false`: 
   - Render dòng chữ màu xám, hoặc thêm hiệu ứng mờ/nhấp nháy ở cuối (giống YouTube).
   - Cập nhật đè (overwrite) lên dòng hiển thị hiện tại.
3. Nếu `is_final == true`:
   - Đổi màu chữ thành trắng/đen bình thường (chốt kết quả).
   - Xuống dòng hoặc tạo một box hội thoại mới.
   - Phát âm thanh TTS (nếu có).

---
## 🚀 Đề xuất bước tiếp theo
Bạn có muốn tôi bắt tay vào lập trình **Phase 1 & Phase 3** bằng cách sửa file `server.py` và `stt/engine.py` để hỗ trợ cơ chế trả về `is_final` ngay bây giờ không?
