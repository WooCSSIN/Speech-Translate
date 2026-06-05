# Bảo mật - Han Translate API

## Tổng quan các lớp bảo mật đã triển khai (Ưu tiên 1)

| Lớp | Cơ chế | File |
|-----|--------|------|
| **Authentication** | API key qua header `X-API-Key` | `security.py`, `api_server.py` |
| **CORS** | Chỉ cho phép localhost + n8n (không dùng `*`) | `api_server.py` |
| **Rate limiting** | 60 request / 60 giây mỗi IP | `security.py` (RateLimiter) |
| **Input validation** | Giới hạn độ dài text (5000 ký tự) | `security.py`, pydantic models |
| **Safe logging** | Ẩn/cắt nội dung nhạy cảm trong log | `security.py` (redact) |
| **Key storage** | Windows Credential Manager (keyring) | `security.py` |

## API Key

### Cách hệ thống lấy key (theo thứ tự ưu tiên)
1. Biến môi trường `HAN_TRANSLATE_API_KEY`
2. Windows Credential Manager (service=`han_translate`, username=`api_key`)

Nếu chưa có, server **tự tạo key mới** và lưu vào Credential Manager khi khởi động.

### Lấy key hiện tại
```powershell
.\venv\Scripts\python.exe -c "from ai_interpreter import security; print(security.get_api_key())"
```

### Đặt key thủ công (khuyến nghị cho production)
```powershell
# Cách 1: Biến môi trường (phiên hiện tại)
$env:HAN_TRANSLATE_API_KEY = "your-secret-key"

# Cách 2: Lưu vĩnh viễn vào Credential Manager
.\venv\Scripts\python.exe -c "import keyring; keyring.set_password('han_translate','api_key','your-secret-key')"
```

## Chạy API server

```powershell
# Chỉ localhost (an toàn nhất - chỉ máy local gọi được)
.\venv\Scripts\python.exe -m uvicorn ai_interpreter.api_server:app --host 127.0.0.1 --port 8000

# Cho phép Docker/n8n gọi vào (cần khi dùng n8n)
.\venv\Scripts\python.exe -m uvicorn ai_interpreter.api_server:app --host 0.0.0.0 --port 8000
```

> Lưu ý: dùng `0.0.0.0` mở port ra toàn mạng LAN. Vì đã có API key + rate limit nên an toàn, nhưng nếu chỉ test local thì dùng `127.0.0.1`.

## Gọi API

```powershell
$headers = @{ "X-API-Key" = "your-key"; "Content-Type" = "application/json" }
$body = '{"text":"The patient needs surgery","target_lang":"vi"}'
Invoke-RestMethod -Uri "http://localhost:8000/translate" -Method Post -Body $body -Headers $headers
```

## Cấu hình n8n

Trong n8n, đặt biến môi trường `HAN_TRANSLATE_API_KEY` để workflow tự gửi key:

```powershell
# Restart n8n với env var chứa key
docker rm -f n8n
docker run -d --name n8n --restart unless-stopped -p 5678:5678 `
  -e GENERIC_TIMEZONE=Asia/Ho_Chi_Minh -e TZ=Asia/Ho_Chi_Minh `
  -e N8N_DIAGNOSTICS_ENABLED=false -e N8N_SECURE_COOKIE=false `
  -e HAN_TRANSLATE_API_KEY="your-key" `
  -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n:latest
```

## Nguyên tắc chống IDOR (cho tương lai)

Khi triển khai các tính năng per-user (Translation Memory, Personal Phrasebook, Terminology Base, Media Export), PHẢI áp dụng:

1. **Ownership check** — mọi truy cập object verify `object.owner_id == current_user.id`
2. **Scoped query** — query luôn lọc theo user (`WHERE owner_id = ?`)
3. **UUID** thay vì ID tuần tự (khó enumerate)
4. **Deny by default** — không thuộc về user → trả 404 (không lộ sự tồn tại)

## CHƯA làm (roadmap bảo mật)

- [x] Model integrity check (verify checksum trước khi load) - Req 11.3, 11.4 → `model_integrity.py`
- [x] Input sanitization (control chars, null byte, lang injection) → `security.py`
- [x] Xóa dữ liệu cá nhân - Req 11.6 → `privacy.py`
- [x] n8n hardening (encryption key, bind localhost, inject API key)
- [x] Không nhúng credential dev vào file .exe khi build - Req 11.7 → `packaging_security.py`
- [ ] HTTPS/TLS cho API (khi deploy ngoài localhost)

## Ưu tiên 4 - Bảo mật đóng gói & phân phối (đã làm)

| Lớp | Cơ chế | File |
|-----|--------|------|
| **Pre-build secret scan** | Quét hardcoded secret, CHẶN build nếu phát hiện | `packaging_security.py` |
| **First-run setup** | Mỗi máy tự sinh API key riêng (không dùng key dev) | `packaging_security.py` |
| **Distribution filter** | Loại file nhạy cảm (.env, *.key, .han_translate) khỏi bản build | `packaging_security.py` |
| **Secure build script** | Build .exe có scan + verify dist sạch | `build_app.py` |

### Build app an toàn
```powershell
.\venv\Scripts\pip.exe install pyinstaller
.\venv\Scripts\python.exe build_app.py
```

Quy trình build:
1. Quét secret → chặn nếu phát hiện (Req 11.7)
2. Build .exe bằng PyInstaller
3. Verify bản dist không chứa file nhạy cảm

> Mỗi máy người dùng cài về sẽ TỰ SINH API key riêng ở lần chạy đầu (first-run setup). Key của dev KHÔNG bao giờ nằm trong bản phân phối.

## Ưu tiên 3 - n8n & Docker hardening (đã làm)

| Lớp | Cơ chế | Cấu hình |
|-----|--------|----------|
| **Bind localhost** | n8n chỉ truy cập từ máy local (không lộ LAN) | `-p 127.0.0.1:5678:5678` |
| **Encryption key cố định** | Bảo vệ credentials lưu trong n8n, không mất khi recreate | `N8N_ENCRYPTION_KEY` |
| **API key injection** | Workflow tự gửi key qua `$env.HAN_TRANSLATE_API_KEY` | `HAN_TRANSLATE_API_KEY` |
| **User management** | n8n 2.x có sẵn login owner (đã tạo lúc setup) | built-in |
| **Tắt telemetry** | Không gửi dữ liệu ra ngoài | `N8N_DIAGNOSTICS_ENABLED=false` |

### Khởi động n8n an toàn
```powershell
.\n8n_workflows\start_n8n_secure.ps1
```

Script tự động:
- Lấy Han Translate API key từ Credential Manager
- Recreate n8n với encryption key cố định (giữ data)
- Bind chỉ localhost (127.0.0.1)
- Inject API key cho workflow

> Lưu ý: encryption key được đọc động từ file local `~/.han_translate/n8n_encryption_key.txt` (gitignored) hoặc từ container đang chạy. GIỮ NGUYÊN key để không mất credentials đã lưu. KHÔNG commit key lên git.

## Ưu tiên 2 - Bảo mật dữ liệu & lưu trữ (đã làm)

| Lớp | Cơ chế | File |
|-----|--------|------|
| **Input sanitization** | Loại control chars, null byte | `security.py` (sanitize_text) |
| **Lang code validation** | Chặn injection qua tham số ngôn ngữ | `security.py` (is_safe_lang_code) |
| **Model integrity** | SHA-256 checksum verify trước khi load, deny by default | `model_integrity.py` |
| **Privacy / xóa dữ liệu** | Xóa Translation Memory, Phrasebook, API key theo yêu cầu | `privacy.py` |

### Model integrity - cách dùng
```python
from ai_interpreter import model_integrity

# Đăng ký model lần đầu (từ nguồn tin cậy)
model_integrity.register_model("models/whisper", "model.bin")

# Verify trước khi load (Req 11.3)
ok, msg = model_integrity.verify_model("models/whisper", "model.bin")
if not ok:
    raise RuntimeError(f"Model không an toàn: {msg}")  # Req 11.4: từ chối load
```

### Xóa dữ liệu cá nhân - cách dùng
```python
from ai_interpreter import privacy

# Xem dữ liệu hiện có
privacy.list_user_data()

# Xóa toàn bộ (tùy chọn xóa cả API key)
privacy.delete_user_data(include_api_key=False)
```
