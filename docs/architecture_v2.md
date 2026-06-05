# AI Realtime Interpreter - System Architecture V2

## Tầm nhìn sản phẩm

**AI Interpreter** — Phiên dịch viên AI realtime chạy trên desktop.
Người dùng nghe bất kỳ nội dung nước ngoài nào trên máy tính → Hệ thống tự động dịch và thuyết minh bằng giọng AI tiếng Việt.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER'S COMPUTER                               │
│                                                                      │
│  ┌──────────────┐     ┌──────────────────────────────────────────┐  │
│  │ Any App      │     │         AI INTERPRETER ENGINE             │  │
│  │ (YouTube,    │     │                                          │  │
│  │  Zoom,       │────▶│  Audio Capture ──▶ VAD ──▶ Chunker      │  │
│  │  Netflix,    │     │                              │           │  │
│  │  Game,       │     │                              ▼           │  │
│  │  Meeting...) │     │                     STT (Faster-Whisper) │  │
│  └──────────────┘     │                              │           │  │
│                       │                              ▼           │  │
│                       │                     Translation Engine    │  │
│                       │                              │           │  │
│                       │                    ┌─────────┴────────┐  │  │
│                       │                    ▼                  ▼  │  │
│                       │              TTS Vietnamese     Subtitle │  │
│                       │              (AI Voice)        (Optional)│  │
│                       │                    │                  │  │  │
│                       └────────────────────┼──────────────────┼──┘  │
│                                            ▼                  ▼     │
│                                   ┌──────────────┐   ┌───────────┐ │
│                                   │ Audio Output │   │  Overlay  │ │
│                                   │ (Speaker/    │   │  Window   │ │
│                                   │  Headphone)  │   │ (on top)  │ │
│                                   └──────────────┘   └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Streaming Pipeline (Realtime Flow)

```
Time ──────────────────────────────────────────────────────────▶

Audio In:    [chunk1][chunk2][chunk3][chunk4][chunk5]...
                │       │       │       │       │
VAD:         [speech✓] [silence✗] [speech✓][speech✓] [silence✗]
                │                    │       │
STT:         [text1]              [text2  ][text3]
                │                    │       │
Translation: [viet1]              [viet2  ][viet3]
                │                    │       │
TTS:         [audio1]             [audio2 ][audio3]
                │                    │       │
Output:      🔊 phát              🔊 phát  🔊 phát

Target Latency: 1.5 - 2.5 giây từ lúc nghe → lúc phát tiếng Việt
```

---

## 3. Core Components

### 3.1 Audio Capture Layer

```
┌─────────────────────────────────────────┐
│           AUDIO CAPTURE                  │
│                                          │
│  Mode 1: System Audio (WASAPI Loopback) │
│  → Bắt mọi âm thanh từ máy tính        │
│                                          │
│  Mode 2: App-specific capture           │
│  → Chỉ bắt audio từ 1 app cụ thể       │
│                                          │
│  Mode 3: Microphone                     │
│  → Bắt giọng người nói trực tiếp       │
│                                          │
│  Output: PCM 16kHz mono chunks          │
└─────────────────────────────────────────┘
```

**Technologies:** PyAudioWPatch (WASAPI), SoundDevice

---

### 3.2 Voice Activity Detection (VAD)

```
┌─────────────────────────────────────────┐
│              SILERO VAD                   │
│                                          │
│  Input: Audio chunks (30ms frames)       │
│                                          │
│  Logic:                                  │
│  - Detect speech vs silence              │
│  - Filter background noise/music         │
│  - Only pass human voice to STT          │
│                                          │
│  Output: Speech segments only            │
│  Benefit: Giảm 60-80% compute cho STT   │
└─────────────────────────────────────────┘
```

---

### 3.3 Smart Chunker (Adaptive Segmentation)

```
┌─────────────────────────────────────────┐
│           SMART CHUNKER                  │
│                                          │
│  Mục tiêu: Cắt audio thành câu/cụm     │
│  có nghĩa để dịch chính xác             │
│                                          │
│  Strategies:                             │
│  - Silence-based: cắt khi im > 500ms    │
│  - Time-based: max 5s per chunk          │
│  - Overlap: 200ms overlap giữa chunks   │
│                                          │
│  Output: Complete speech segments        │
│  ready for transcription                 │
└─────────────────────────────────────────┘
```

---

### 3.4 Speech-to-Text (STT)

```
┌─────────────────────────────────────────┐
│         FASTER-WHISPER STT               │
│                                          │
│  Engine: Faster-Whisper (CTranslate2)    │
│  Model: Small/Medium (tùy GPU)          │
│  Precision: FP16 (GPU) / INT8 (CPU)     │
│                                          │
│  Features:                               │
│  - Streaming transcription               │
│  - Auto language detection               │
│  - Multilingual support                  │
│  - GPU accelerated (CUDA)               │
│                                          │
│  Output: Text + timestamps               │
│  Latency: 300-800ms per chunk            │
└─────────────────────────────────────────┘
```

---

### 3.5 Translation Engine

```
┌─────────────────────────────────────────┐
│         TRANSLATION ENGINE               │
│                                          │
│  Strategy: Local-first, Cloud fallback   │
│                                          │
│  Option 1: NLLB (Local, offline)         │
│  - Facebook's No Language Left Behind    │
│  - 200+ languages                        │
│  - Chạy trên GPU local                  │
│                                          │
│  Option 2: Google Translate API          │
│  - Nhanh, chính xác                     │
│  - Cần internet                          │
│                                          │
│  Option 3: GPT/LLM Translation          │
│  - Context-aware, tự nhiên nhất         │
│  - Tốn API cost                          │
│                                          │
│  Output: Vietnamese text                 │
│  Latency: 100-300ms                      │
└─────────────────────────────────────────┘
```

---

### 3.6 TTS - AI Vietnamese Voice (Thuyết Minh)

```
┌─────────────────────────────────────────┐
│       VIETNAMESE TTS ENGINE              │
│                                          │
│  ★ CORE FEATURE: Giọng thuyết minh AI   │
│                                          │
│  Option 1: Edge TTS (Microsoft)          │
│  - Miễn phí, giọng Việt tự nhiên       │
│  - Cần internet                          │
│  - Latency thấp                          │
│                                          │
│  Option 2: Piper TTS (Offline)           │
│  - Chạy local, không cần mạng          │
│  - Giọng OK, tốc độ nhanh              │
│                                          │
│  Option 3: XTTS v2 (Voice Clone)        │
│  - Clone giọng speaker gốc             │
│  - Nặng GPU nhưng tự nhiên nhất        │
│                                          │
│  Features:                               │
│  - Adjustable speed (nhanh/chậm)        │
│  - Multiple voices (nam/nữ)             │
│  - Emotion preservation                  │
│                                          │
│  Output: Audio stream (PCM/WAV)          │
│  Latency: 200-500ms                      │
└─────────────────────────────────────────┘
```

---

### 3.7 Audio Mixer & Output

```
┌─────────────────────────────────────────┐
│          AUDIO MIXER                     │
│                                          │
│  Input 1: Original audio (from app)     │
│  Input 2: TTS Vietnamese voice          │
│                                          │
│  Mixing Modes:                           │
│                                          │
│  Mode 1: "Thuyết minh"                  │
│  → Giảm volume gốc 70%                 │
│  → Phát giọng Việt lên trên            │
│  (Giống xem phim thuyết minh)           │
│                                          │
│  Mode 2: "Lồng tiếng"                  │
│  → Mute giọng gốc hoàn toàn           │
│  → Chỉ phát giọng Việt                 │
│  (Giống phim lồng tiếng)               │
│                                          │
│  Mode 3: "Song ngữ"                    │
│  → Giữ nguyên audio gốc               │
│  → Phát giọng Việt qua tai nghe khác  │
│                                          │
│  Output: Mixed audio → Speaker/Headphone │
└─────────────────────────────────────────┘
```

---

### 3.8 Subtitle Overlay (Optional)

```
┌─────────────────────────────────────────┐
│        SUBTITLE OVERLAY                  │
│                                          │
│  - Transparent window, always on top     │
│  - Hiện text gốc + text dịch           │
│  - Drag & drop position                 │
│  - Auto-hide khi không có text          │
│  - Customizable: font, size, color      │
│                                          │
│  Có thể bật/tắt độc lập với TTS        │
└─────────────────────────────────────────┘
```

---

## 4. System Orchestration

```
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE ORCHESTRATOR                      │
│                                                              │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   │
│  │ Audio   │──▶│  VAD    │──▶│  STT    │──▶│ Transl. │   │
│  │ Queue   │   │ Queue   │   │ Queue   │   │ Queue   │   │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘   │
│                                                    │         │
│                                              ┌─────┴─────┐  │
│                                              ▼           ▼  │
│                                        ┌─────────┐ ┌──────┐│
│                                        │TTS Queue│ │ Sub  ││
│                                        └─────────┘ │Queue ││
│                                              │     └──────┘│
│                                              ▼       ▼      │
│                                        ┌──────────────────┐ │
│                                        │   Output Queue   │ │
│                                        └──────────────────┘ │
│                                                              │
│  Engine: AsyncIO + Threading                                 │
│  Communication: Queue-based pipeline                         │
│  Error handling: Auto-retry, graceful degradation            │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. User Interface

```
┌─────────────────────────────────────────────────────────────┐
│                     UI LAYERS                                 │
│                                                              │
│  Layer 1: System Tray (luôn chạy background)                │
│  ┌─────────────────────────────────────┐                    │
│  │ 🎙️ AI Interpreter                   │                    │
│  │ ├── Start/Stop (Ctrl+Shift+I)       │                    │
│  │ ├── Mode: Thuyết minh ▼            │                    │
│  │ ├── Language: EN → VI              │                    │
│  │ ├── Settings                        │                    │
│  │ └── Exit                            │                    │
│  └─────────────────────────────────────┘                    │
│                                                              │
│  Layer 2: Control Panel (mở khi cần settings)               │
│  ┌─────────────────────────────────────┐                    │
│  │ Audio source | Model | Voice | Mix  │                    │
│  └─────────────────────────────────────┘                    │
│                                                              │
│  Layer 3: Subtitle Overlay (optional, floating)             │
│  ┌─────────────────────────────────────┐                    │
│  │ [Original text]                      │                    │
│  │ [Bản dịch tiếng Việt]              │                    │
│  └─────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Performance Targets

| Component | Target Latency | Note |
|-----------|---------------|------|
| Audio Capture | < 50ms | Realtime buffer |
| VAD | < 30ms | Per 30ms frame |
| Chunker | 500-2000ms | Chờ đủ câu |
| STT | 300-800ms | Tùy model size |
| Translation | 100-300ms | API hoặc local |
| TTS | 200-500ms | Streaming synthesis |
| **Total Pipeline** | **1.5 - 3.0s** | **Acceptable for interpretation** |

> So sánh: Phiên dịch viên con người thường delay 3-5 giây. Hệ thống này nhanh hơn.

---

## 7. Audio Routing Diagram

```
┌──────────────────────────────────────────────────────────┐
│                                                           │
│   App (YouTube/Zoom/...)                                 │
│        │                                                  │
│        ▼                                                  │
│   System Audio ─────────┬──────────────────────────┐     │
│                         │                          │     │
│                         ▼                          ▼     │
│                  AI Interpreter              Original    │
│                  (capture & process)         Playback    │
│                         │                   (reduced     │
│                         ▼                    volume)     │
│                  Vietnamese TTS                  │       │
│                         │                       │       │
│                         ▼                       ▼       │
│                    Audio Mixer ◄─────────────────┘       │
│                         │                                │
│                         ▼                                │
│                  🎧 User hears:                          │
│                  - Giọng Việt (loud)                     │
│                  - Giọng gốc (quiet background)          │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

---

## 8. Tech Stack

| Layer | Technology | Lý do |
|-------|-----------|-------|
| Audio Capture | PyAudioWPatch (WASAPI) | Capture system audio trên Windows |
| VAD | Silero VAD | Nhẹ, chính xác, chạy CPU |
| STT | Faster-Whisper | Nhanh 4x so với Whisper gốc, GPU |
| Translation | Google Translate / NLLB | Nhanh + offline option |
| TTS | Edge TTS / Piper TTS | Giọng Việt tự nhiên |
| Audio Output | SoundDevice / PyAudio | Low-latency playback |
| Pipeline | AsyncIO + Queue | Non-blocking, streaming |
| UI | Electron + React (hoặc PyQt6) | Modern, overlay support |
| Backend | FastAPI + WebSocket | Streaming communication |

---

## 9. Folder Structure (New)

```
ai-interpreter/
│
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Settings & configuration
│   │
│   ├── audio/
│   │   ├── capture.py          # System audio capture
│   │   ├── vad.py              # Voice activity detection
│   │   ├── chunker.py          # Smart audio segmentation
│   │   ├── mixer.py            # Audio mixing (original + TTS)
│   │   └── output.py           # Audio playback
│   │
│   ├── stt/
│   │   ├── engine.py           # Faster-Whisper STT
│   │   └── streaming.py        # Streaming transcription
│   │
│   ├── translation/
│   │   ├── engine.py           # Translation router
│   │   ├── google_tl.py        # Google Translate
│   │   └── nllb.py             # NLLB local translation
│   │
│   ├── tts/
│   │   ├── engine.py           # TTS router
│   │   ├── edge_tts.py         # Microsoft Edge TTS
│   │   ├── piper_tts.py        # Piper offline TTS
│   │   └── voice_manager.py    # Voice selection & config
│   │
│   ├── pipeline/
│   │   ├── orchestrator.py     # Pipeline management
│   │   ├── queue_manager.py    # Queue-based streaming
│   │   └── websocket.py        # WebSocket streaming
│   │
│   └── utils/
│       ├── gpu.py              # GPU/CUDA utilities
│       └── logger.py           # Logging
│
├── frontend/                   # Electron + React
│   ├── src/
│   │   ├── App.tsx             # Main app
│   │   ├── components/
│   │   │   ├── ControlPanel.tsx
│   │   │   ├── SubtitleOverlay.tsx
│   │   │   └── Settings.tsx
│   │   └── hooks/
│   │       └── useWebSocket.ts
│   ├── electron/
│   │   └── main.ts             # Electron main process
│   └── package.json
│
├── models/                     # Downloaded AI models
├── docs/                       # Documentation
└── README.md
```

---

## 10. Development Phases

### Phase 1: Core Pipeline (MVP)
- [ ] Audio capture (system audio)
- [ ] VAD + Chunker
- [ ] STT (Faster-Whisper)
- [ ] Translation (Google Translate)
- [ ] TTS (Edge TTS)
- [ ] Audio output (play Vietnamese voice)
- [ ] Simple CLI interface

### Phase 2: Desktop App
- [ ] System tray
- [ ] Global hotkey (start/stop)
- [ ] Audio mixer (original + TTS)
- [ ] Settings UI
- [ ] Subtitle overlay

### Phase 3: Polish & Advanced
- [ ] Voice selection (nam/nữ/clone)
- [ ] Offline mode (NLLB + Piper)
- [ ] App-specific audio capture
- [ ] OBS integration
- [ ] Performance optimization

---

## 11. Điểm khác biệt với các sản phẩm khác

| Feature | YouTube Sub | Google Translate | AI Interpreter (Ours) |
|---------|------------|-----------------|----------------------|
| Realtime | ❌ (pre-made) | ❌ | ✅ |
| Mọi nguồn audio | ❌ YouTube only | ❌ | ✅ |
| Giọng thuyết minh | ❌ | ❌ | ✅ |
| Offline | ❌ | ❌ | ✅ (optional) |
| Custom voice | ❌ | ❌ | ✅ |
| Zoom/Meet support | ❌ | ❌ | ✅ |
| Game/Livestream | ❌ | ❌ | ✅ |
| Audio mixing | ❌ | ❌ | ✅ |
