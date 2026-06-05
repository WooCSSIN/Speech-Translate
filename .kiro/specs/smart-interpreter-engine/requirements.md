# Requirements Document

## Introduction

**Smart Interpreter Engine** là bộ tính năng nâng cao cho dự án **Han Translate** — một ứng dụng phiên dịch AI realtime chạy trên desktop (Python + PyQt6, package `ai_interpreter/`). Mục tiêu của bộ tính năng này là tạo sự khác biệt rõ rệt so với các ứng dụng dịch phổ thông (Google Translate, DeepL, GPT) vốn giống nhau tới ~90%.

Chiến lược khác biệt hóa dựa trên ba trụ cột:

1. **Chuyên sâu theo lĩnh vực (deep domain focus)** thay vì dịch chung chung mọi thứ.
2. **Hiểu ngữ cảnh + văn hóa (context + culture awareness)** — hiểu được tình huống và yếu tố văn hóa.
3. **Thích ứng + offline + đa phương thức (adaptive + offline + multimodal)** — học từ người dùng, hoạt động ngoại tuyến, hỗ trợ AR/voice.

Tài liệu này mở rộng pipeline realtime hiện có của Han Translate (Audio Capture → Silero VAD → Faster-Whisper STT → Translation → Edge TTS → Audio Mixer) bằng sáu nhóm năng lực mới (A–F) cùng các yêu cầu xuyên suốt về độ trễ, UI/UX, bảo mật/quyền riêng tư, và vận hành ngoại tuyến.

**Thứ tự ưu tiên triển khai (theo tư vấn chuyên môn về phiên dịch):**

Cái khó nhất trong phiên dịch không phải từ vựng, mà là **ngữ cảnh ngầm hiểu**. Ví dụ cùng một câu "anh ấy đi rồi" — tùy tình huống có thể nghĩa là anh ấy ra ngoài, nghỉ việc, hoặc đã qua đời. Máy dịch và các app hiện tại đều bỏ qua điều này. Do đó thứ tự ưu tiên là:

1. **Ngữ cảnh (Capability A) — Quan trọng nhất.** Không có ngữ cảnh thì multimodal cũng vô nghĩa.
2. **Văn hóa (Capability C) — Đặc biệt với tiếng Việt:** cách xưng hô / tôn ti / vùng miền ảnh hưởng cực lớn đến nghĩa và sắc thái.
3. **Offline (Capability F):** người dùng thực tế ở Việt Nam hay mất mạng — yếu tố này quyết định khả năng được sử dụng rộng rãi (adoption).
4. **Chuyên ngành (Capability B):** làm theo từng domain riêng biệt, KHÔNG cố train một mô hình all-in-one.
5. **Adaptive (Capability E) + Multimodal/AR (Capability D):** triển khai sau cùng.

**Bối cảnh hệ thống hiện tại:**
- Pipeline realtime đã hoạt động, hỗ trợ 34 ngôn ngữ nguồn và 33 ngôn ngữ đích có giọng TTS.
- Điểm đau hiện tại: độ trễ cao (Edge TTS ~2.5s/câu), bản dịch chưa đồng bộ sát với lời nói, và cần thiết kế UI/UX cùng bảo mật khi đóng gói phân phối.
- Phần cứng mục tiêu: Windows 11, GPU RTX 3050 (4GB VRAM), Python 3.12.

## Glossary

- **Han_Translate**: Toàn bộ ứng dụng phiên dịch AI realtime trên desktop, bao gồm tất cả các thành phần con bên dưới.
- **Pipeline_Orchestrator**: Thành phần điều phối luồng xử lý realtime đa giai đoạn (Capture → VAD → STT → Translation → TTS → Mixer).
- **Context_Classifier**: Thành phần phân loại tình huống hội thoại (ví dụ: nhà hàng, bệnh viện, họp kinh doanh, hội thoại hằng ngày, du lịch) từ nội dung văn bản và/hoặc tín hiệu âm thanh.
- **Implicit_Context**: Ngữ cảnh ngầm hiểu của một câu — ý nghĩa thực sự phụ thuộc vào tình huống mà không được nêu rõ trong câu (ví dụ "anh ấy đi rồi" có thể là ra ngoài, nghỉ việc, hoặc qua đời).
- **Context_Window**: Tập hợp các câu hội thoại gần nhất được Context_Classifier dùng làm bối cảnh để suy luận Implicit_Context, thay vì chỉ xét một câu đơn lẻ.
- **Translation_Router**: Thành phần chọn mô hình dịch, phong cách dịch và prompt theo lĩnh vực dựa trên kết quả của Context_Classifier hoặc lựa chọn của người dùng.
- **Domain_Profile**: Một cấu hình lĩnh vực bao gồm mô hình dịch, bộ thuật ngữ chuẩn, phong cách ngôn ngữ và prompt tương ứng (ví dụ: Medical, Legal, Technical, Fintech, Travel, Daily).
- **Terminology_Base**: Kho thuật ngữ chuẩn theo lĩnh vực, ánh xạ thuật ngữ nguồn sang thuật ngữ đích đã được phê duyệt.
- **Cultural_Insight_Module**: Thành phần phát hiện và giải thích tiếng lóng, thành ngữ và hàm ý văn hóa Việt–Anh, đồng thời đề xuất cách diễn đạt tự nhiên hơn.
- **Honorific_Resolver**: Thành phần xác định cách xưng hô và tôn ti tiếng Việt phù hợp (anh/chị/em/ông/bà/cháu...) dựa trên quan hệ, vai vế và tình huống, vì tiếng Anh không phân biệt các đại từ này.
- **Regional_Variant**: Biến thể vùng miền của tiếng Việt (Bắc/Trung/Nam) ảnh hưởng đến từ vựng và cách diễn đạt khi dịch.
- **AR_Overlay_Module**: Thành phần thu hình ảnh từ camera, nhận dạng văn bản (OCR) và hiển thị bản dịch chồng lên vật thể thực tế theo dạng thực tế tăng cường.
- **Voice_Cloning_Engine**: Thành phần tổng hợp giọng nói dịch theo kiểu speech-to-speech (S2ST), giữ lại đặc trưng giọng của người nói gốc.
- **Media_Export_Module**: Thành phần tạo bản ghi (transcript), tệp âm thanh hoặc video đã dịch sau buổi phiên dịch.
- **Adaptive_Learning_Module**: Thành phần học từ các chỉnh sửa, thuật ngữ tùy chỉnh và sổ tay cụm từ cá nhân của người dùng để cải thiện độ chính xác theo thời gian.
- **Translation_Memory**: Kho lưu trữ các cặp câu nguồn–đích đã được người dùng xác nhận hoặc chỉnh sửa, dùng để tái sử dụng và tinh chỉnh.
- **Personal_Phrasebook**: Sổ tay cụm từ cá nhân do người dùng tạo, gồm cặp cụm từ nguồn–đích và ghi chú.
- **Offline_Model_Manager**: Thành phần quản lý tải, nạp và chuyển đổi giữa các mô hình AI on-device (định dạng .onnx, TensorFlow Lite, CoreML) cho STT, dịch và TTS.
- **On_Device_Engine**: Tập hợp các mô hình AI chạy hoàn toàn trên thiết bị người dùng, có tăng tốc bằng GPU CUDA khi khả dụng.
- **Network_Monitor**: Thành phần phát hiện trạng thái kết nối mạng (online/offline) của thiết bị.
- **UI_Shell**: Lớp giao diện người dùng của Han_Translate gồm khay hệ thống, bảng điều khiển, lớp phủ phụ đề và các màn hình cấu hình.
- **Security_Module**: Thành phần chịu trách nhiệm lưu trữ an toàn thông tin nhạy cảm (khóa API, dữ liệu người dùng), kiểm tra tính toàn vẹn mô hình và bảo vệ dữ liệu khi phân phối ứng dụng.
- **Secure_Storage**: Vùng lưu trữ được mã hóa trên thiết bị dùng cho khóa API, thông tin xác thực và dữ liệu cá nhân của người dùng.
- **Configuration_Store**: Vùng lưu trữ cấu hình ứng dụng, hồ sơ lĩnh vực, và tùy chọn người dùng dưới dạng tệp có thể đọc/ghi.
- **End_To_End_Latency**: Khoảng thời gian tính từ thời điểm một đoạn lời nói kết thúc (được VAD xác nhận) đến thời điểm Han_Translate bắt đầu phát giọng dịch tương ứng.

## Requirements

### Requirement 1: Phân loại ngữ cảnh và chọn mô hình theo tình huống (Capability A)

**User Story:** As a người dùng phiên dịch realtime, I want ứng dụng tự nhận diện tình huống hội thoại và chọn phong cách dịch phù hợp, so that bản dịch phản ánh đúng bối cảnh (y tế, du lịch, kinh doanh, hằng ngày) mà tôi không phải cấu hình thủ công.

#### Acceptance Criteria

1. WHEN một đoạn văn bản đã được STT chuyển đổi, THE Context_Classifier SHALL phân loại đoạn văn bản vào đúng một Domain_Profile trong tập các Domain_Profile đã đăng ký.
2. WHEN Context_Classifier xác định một Domain_Profile với độ tin cậy lớn hơn hoặc bằng 0.6, THE Translation_Router SHALL chọn mô hình dịch, bộ thuật ngữ và prompt tương ứng với Domain_Profile đó.
3. IF Context_Classifier xác định Domain_Profile với độ tin cậy nhỏ hơn 0.6, THEN THE Translation_Router SHALL sử dụng Domain_Profile "Daily" làm mặc định.
4. WHERE người dùng chọn thủ công một Domain_Profile, THE Translation_Router SHALL sử dụng Domain_Profile do người dùng chọn và bỏ qua kết quả của Context_Classifier.
5. WHEN Translation_Router xác định Domain_Profile cho một đoạn văn bản, THE UI_Shell SHALL hiển thị tên Domain_Profile hiện hành cho người dùng trong vòng 500 mili-giây, kể cả khi Domain_Profile không thay đổi so với đoạn trước.
6. WHERE Domain_Profile "Travel" đang được áp dụng, THE Translation_Router SHALL áp dụng đồng thời cả cấu hình dịch tốc độ cao và từ vựng cơ bản.
7. WHEN Context_Classifier phân loại một đoạn văn bản, THE Context_Classifier SHALL sử dụng Context_Window gồm các câu hội thoại gần nhất làm bối cảnh thay vì chỉ xét câu hiện tại đơn lẻ.
8. WHEN một câu nguồn có nhiều cách hiểu khác nhau tùy ngữ cảnh (Implicit_Context), THE Translation_Router SHALL chọn bản dịch phù hợp với Domain_Profile và Context_Window hiện hành.
9. WHERE một câu nguồn vẫn còn mơ hồ về Implicit_Context sau khi xét Context_Window, THE Translation_Router SHALL tạo bản dịch khả dĩ nhất và đánh dấu câu đó là mơ hồ để UI_Shell có thể hiển thị cảnh báo cho người dùng.

### Requirement 2: Dịch chuyên sâu theo lĩnh vực (Capability B)

**User Story:** As a người dùng làm việc trong lĩnh vực chuyên môn (y tế, pháp lý, kỹ thuật, tài chính), I want bản dịch sử dụng thuật ngữ chuẩn của lĩnh vực đó, so that bản dịch chính xác hơn và đáng tin cậy hơn so với công cụ dịch phổ thông.

#### Acceptance Criteria

1. THE Han_Translate SHALL cung cấp tối thiểu bốn Domain_Profile chuyên sâu: Medical, Legal, Technical, và Fintech.
2. WHEN một Domain_Profile chuyên sâu đang được áp dụng và văn bản nguồn chứa một thuật ngữ có trong Terminology_Base của Domain_Profile đó, THE Translation_Router SHALL dịch thuật ngữ đó theo bản dịch chuẩn đã được định nghĩa trong Terminology_Base.
3. WHERE Domain_Profile "Medical" đang được áp dụng, THE Translation_Router SHALL áp dụng bộ thuật ngữ y tế chuẩn cho hồ sơ bệnh án, triệu chứng và chỉ định thuốc, kể cả khi không phát hiện thuật ngữ y tế nào trong văn bản nguồn.
4. WHERE Domain_Profile "Legal" đang được áp dụng, THE Translation_Router SHALL áp dụng bộ thuật ngữ pháp lý chuẩn cho hợp đồng và văn bản pháp lý.
5. IF một thuật ngữ trong văn bản nguồn không tồn tại trong Terminology_Base của Domain_Profile đang áp dụng, THEN THE Translation_Router SHALL dịch thuật ngữ đó bằng mô hình dịch chung của Domain_Profile.
6. THE Han_Translate SHALL cho phép người dùng thêm, chỉnh sửa và xóa các mục trong Terminology_Base của từng Domain_Profile.
7. THE Han_Translate SHALL quản lý mỗi Domain_Profile như một cấu hình độc lập (mô hình, Terminology_Base, prompt riêng), KHÔNG gộp các lĩnh vực vào một mô hình all-in-one duy nhất.
8. WHERE người dùng cài đặt thêm một Domain_Profile mới, THE Han_Translate SHALL nạp Domain_Profile đó mà không yêu cầu thay đổi các Domain_Profile hiện có.

### Requirement 3: Hiểu văn hóa Việt–Anh (Capability C)

**User Story:** As a người dùng dịch giữa tiếng Việt và tiếng Anh, I want ứng dụng nhận biết tiếng lóng, thành ngữ và hàm ý văn hóa, so that tôi hiểu đúng ý nghĩa thực sự thay vì bản dịch sát nghĩa từng từ.

#### Acceptance Criteria

1. WHEN một câu nguồn chứa một thành ngữ hoặc tiếng lóng có trong cơ sở dữ liệu văn hóa, THE Cultural_Insight_Module SHALL tạo một ghi chú giải thích ý nghĩa văn hóa kèm theo bản dịch và lưu ghi chú đó để truy cập sau, kể cả khi việc hiển thị tách biệt thất bại.
2. WHEN Cultural_Insight_Module tạo một bản dịch sát nghĩa cho một thành ngữ, THE Cultural_Insight_Module SHALL đề xuất ít nhất một cách diễn đạt tự nhiên hơn ở ngôn ngữ đích.
3. WHERE người dùng yêu cầu xem ví dụ sử dụng cho một từ hoặc cụm từ, THE Cultural_Insight_Module SHALL hiển thị ít nhất một ví dụ thực tế kèm bản dịch của ví dụ đó.
4. IF cặp ngôn ngữ nguồn–đích không phải là Việt–Anh hoặc Anh–Việt, THEN THE Cultural_Insight_Module SHALL bỏ qua việc tạo ghi chú văn hóa.
5. WHEN Cultural_Insight_Module tạo ghi chú văn hóa, THE UI_Shell SHALL hiển thị ghi chú đó tách biệt với bản dịch chính.
6. WHEN dịch từ tiếng Anh sang tiếng Việt một câu có đại từ nhân xưng (ví dụ "you", "he", "she"), THE Honorific_Resolver SHALL chọn cách xưng hô tiếng Việt phù hợp (anh/chị/em/ông/bà/cháu...) dựa trên Context_Window và quan hệ giữa người nói.
7. WHERE Context_Window chưa đủ thông tin để xác định tôn ti, THE Honorific_Resolver SHALL chọn cách xưng hô trung lập và đánh dấu để người dùng có thể điều chỉnh.
8. WHERE người dùng chọn một Regional_Variant (Bắc/Trung/Nam), THE Cultural_Insight_Module SHALL ưu tiên từ vựng và cách diễn đạt của vùng miền đó trong bản dịch sang tiếng Việt.
9. WHEN người dùng chỉnh sửa cách xưng hô do Honorific_Resolver đề xuất, THE Adaptive_Learning_Module SHALL ghi nhớ lựa chọn đó để áp dụng cho các câu tương tự trong cùng phiên.

### Requirement 4: Lớp phủ thực tế tăng cường (AR) cho văn bản hình ảnh (Capability D)

**User Story:** As a người dùng đang ở môi trường thực tế (du lịch, đọc menu, biển báo), I want hướng camera vào văn bản và thấy bản dịch hiển thị trực tiếp trên vật thể, so that tôi hiểu nội dung mà không cần gõ lại văn bản.

#### Acceptance Criteria

1. WHEN người dùng kích hoạt chế độ AR và camera thu được khung hình chứa văn bản, THE AR_Overlay_Module SHALL nhận dạng văn bản trong khung hình bằng OCR.
2. WHEN AR_Overlay_Module nhận dạng được văn bản, THE AR_Overlay_Module SHALL hiển thị bản dịch chồng lên vị trí của văn bản gốc trong khung hình.
3. WHILE chế độ AR đang hoạt động, THE AR_Overlay_Module SHALL cập nhật hình ảnh camera hiển thị với tốc độ tối thiểu 5 khung hình mỗi giây, kể cả khi không có lớp phủ dịch nào được hiển thị.
4. IF AR_Overlay_Module không nhận dạng được văn bản nào trong khung hình, THEN THE AR_Overlay_Module SHALL hiển thị khung hình camera mà không có lớp phủ dịch.
5. IF camera trở nên không khả dụng hoặc bị từ chối quyền truy cập trong khi chế độ AR đang hoạt động, THEN THE AR_Overlay_Module SHALL tiếp tục hiển thị khung hình gần nhất kèm lớp phủ đồng thời hiển thị một thông báo lỗi mô tả nguyên nhân cho người dùng.

### Requirement 5: Phiên dịch giọng nói realtime giữ giọng gốc (Capability D)

**User Story:** As a người dùng nghe nội dung nước ngoài, I want giọng dịch giữ được đặc trưng giọng của người nói gốc, so that trải nghiệm tự nhiên hơn và tôi phân biệt được người nói.

#### Acceptance Criteria

1. WHERE chế độ voice cloning được bật, THE Voice_Cloning_Engine SHALL tổng hợp giọng dịch giữ lại đặc trưng giọng của người nói gốc.
2. WHEN Voice_Cloning_Engine tổng hợp giọng dịch cho một câu, THE End_To_End_Latency cho câu đó SHALL nhỏ hơn hoặc bằng 3 giây.
3. IF mẫu giọng người nói gốc chưa đủ để nhân bản, THEN THE Voice_Cloning_Engine SHALL giữ engine voice cloning ở trạng thái kích hoạt nhưng sử dụng giọng TTS mặc định của ngôn ngữ đích.
4. WHERE chế độ voice cloning bị tắt, THE Pipeline_Orchestrator SHALL sử dụng engine TTS tiêu chuẩn đã cấu hình.
5. IF tài nguyên GPU không đủ để chạy Voice_Cloning_Engine, THEN THE Pipeline_Orchestrator SHALL chuyển sang engine TTS tiêu chuẩn và ghi lại sự kiện chuyển đổi.

### Requirement 6: Tạo bản ghi và media đã dịch sau buổi phiên dịch (Capability D)

**User Story:** As a người dùng sau một buổi họp hoặc xem nội dung, I want nhận được bản ghi và tệp âm thanh/video đã dịch, so that tôi có thể xem lại và lưu trữ nội dung.

#### Acceptance Criteria

1. WHEN một phiên phiên dịch kết thúc, THE Media_Export_Module SHALL tạo một bản ghi (transcript) chứa văn bản gốc và văn bản dịch kèm dấu thời gian cho từng câu.
2. WHERE người dùng yêu cầu xuất âm thanh đã dịch, THE Media_Export_Module SHALL tạo một tệp âm thanh chứa toàn bộ giọng dịch của phiên.
3. THE Media_Export_Module SHALL hỗ trợ xuất bản ghi ở định dạng văn bản và định dạng SRT.
4. FOR ALL bản ghi được xuất ra định dạng SRT rồi nạp lại, THE Media_Export_Module SHALL tạo ra một bản ghi tương đương với bản ghi gốc (thuộc tính round-trip).
5. IF không có câu nào được xử lý trong phiên, THEN THE Media_Export_Module SHALL thông báo cho người dùng rằng không có nội dung để xuất.

### Requirement 7: Học thích ứng từ người dùng (Capability E)

**User Story:** As a người dùng thường xuyên, I want ứng dụng học từ các chỉnh sửa và thuật ngữ riêng của tôi, so that bản dịch ngày càng chính xác và phù hợp với cách dùng của tôi.

#### Acceptance Criteria

1. WHEN người dùng chỉnh sửa một bản dịch, THE Adaptive_Learning_Module SHALL thêm một mục mới chứa cặp câu nguồn–đích đã chỉnh sửa vào Translation_Memory, bất kể nội dung hiện có trong Translation_Memory.
2. WHEN một câu nguồn trùng khớp với một mục trong Translation_Memory, THE Translation_Router SHALL sử dụng bản dịch đã lưu trong Translation_Memory thay cho kết quả của mô hình dịch.
3. THE Han_Translate SHALL cho phép người dùng thêm, chỉnh sửa và xóa các mục trong Personal_Phrasebook.
4. WHEN người dùng thêm một mục vào Personal_Phrasebook, THE Translation_Router SHALL áp dụng cặp cụm từ đó cho các bản dịch tiếp theo trong vòng 1 giây.
5. WHERE một mục trong Translation_Memory mâu thuẫn với một mục trong Personal_Phrasebook cho cùng một câu nguồn, THE Translation_Router SHALL ưu tiên mục trong Personal_Phrasebook.
6. FOR ALL mục được lưu vào Translation_Memory rồi truy xuất lại, THE Adaptive_Learning_Module SHALL trả về cặp câu nguồn–đích bằng với mục đã lưu (thuộc tính round-trip).

### Requirement 8: Vận hành ngoại tuyến với mô hình on-device (Capability F)

**User Story:** As a người dùng ở nơi không có mạng hoặc cần bảo mật dữ liệu, I want ứng dụng dịch hoàn toàn trên thiết bị, so that tôi vẫn dùng được khi offline và dữ liệu không rời khỏi máy.

#### Acceptance Criteria

1. WHERE chế độ offline được bật, THE Pipeline_Orchestrator SHALL thực hiện STT, dịch và TTS chỉ bằng On_Device_Engine.
2. WHILE chế độ offline được bật, THE Han_Translate SHALL không gửi văn bản nguồn, văn bản dịch hoặc dữ liệu âm thanh tới bất kỳ dịch vụ mạng bên ngoài nào.
3. WHEN Network_Monitor phát hiện mất kết nối mạng trong khi Pipeline_Orchestrator đang sử dụng dịch vụ mạng bên ngoài, THE Pipeline_Orchestrator SHALL chuyển sang On_Device_Engine và thông báo việc chuyển đổi cho người dùng.
4. THE Offline_Model_Manager SHALL hỗ trợ nạp các mô hình ở định dạng ONNX cho STT, dịch và TTS.
5. WHERE GPU CUDA khả dụng, THE On_Device_Engine SHALL sử dụng tăng tốc GPU cho việc suy luận mô hình.
6. IF việc nạp một mô hình on-device thất bại, THEN THE Offline_Model_Manager SHALL hiển thị thông báo lỗi nêu rõ mô hình bị lỗi và giữ engine ở trạng thái trước đó.
7. WHILE chế độ offline được bật trên phần cứng RTX 3050 với 4GB VRAM, THE On_Device_Engine SHALL giữ tổng mức sử dụng VRAM không vượt quá 4GB.

### Requirement 9: Độ trễ thấp và độ mượt realtime (Cross-cutting)

**User Story:** As a người dùng phiên dịch realtime, I want độ trễ thấp và bản dịch đồng bộ sát với lời nói, so that cuộc hội thoại diễn ra tự nhiên mà không bị ngắt quãng khó chịu.

#### Acceptance Criteria

1. WHEN một đoạn lời nói được VAD xác nhận kết thúc, THE Pipeline_Orchestrator SHALL bắt đầu phát giọng dịch tương ứng với End_To_End_Latency nhỏ hơn hoặc bằng 3 giây.
2. WHERE chế độ độ trễ thấp được bật và đang dùng engine online, THE Pipeline_Orchestrator SHALL đạt End_To_End_Latency trung bình nhỏ hơn hoặc bằng 1.5 giây trên mỗi câu trong một phiên.
3. WHILE Pipeline_Orchestrator đang xử lý, THE Pipeline_Orchestrator SHALL xử lý các giai đoạn STT, dịch và TTS song song để các câu liên tiếp không bị xử lý tuần tự.
4. WHEN một giai đoạn xử lý có hàng đợi đầy, THE Pipeline_Orchestrator SHALL ghi lại sự kiện quá tải và tiếp tục xử lý các câu tiếp theo mà không dừng pipeline.
5. THE Pipeline_Orchestrator SHALL hiển thị độ trễ trung bình của phiên cho người dùng khi phiên kết thúc.

### Requirement 10: Chất lượng thiết kế UI/UX cho người dùng cuối (Cross-cutting)

**User Story:** As a người dùng cuối cài đặt ứng dụng, I want giao diện rõ ràng, dễ dùng và phản hồi trực quan, so that tôi sử dụng được ngay mà không cần hướng dẫn kỹ thuật.

#### Acceptance Criteria

1. THE UI_Shell SHALL cung cấp điều khiển bắt đầu và dừng phiên phiên dịch có thể truy cập từ khay hệ thống.
2. WHERE người dùng bật bảng trạng thái, THE UI_Shell SHALL hiển thị trạng thái hiện hành gồm Domain_Profile đang áp dụng, cặp ngôn ngữ và trạng thái online/offline trong khi một phiên phiên dịch đang chạy.
3. WHEN người dùng thay đổi một tùy chọn cấu hình, THE UI_Shell SHALL áp dụng và phản ánh thay đổi đó trong vòng 500 mili-giây.
4. WHEN Pipeline_Orchestrator tạo một bản dịch, THE UI_Shell SHALL hiển thị văn bản gốc và văn bản dịch trên lớp phủ phụ đề.
5. WHERE người dùng bật lớp phủ phụ đề, THE UI_Shell SHALL cho phép người dùng điều chỉnh vị trí, cỡ chữ và màu chữ của lớp phủ.
6. IF một thao tác của người dùng dẫn đến lỗi, THEN THE UI_Shell SHALL hiển thị một thông báo lỗi mô tả nguyên nhân bằng ngôn ngữ người dùng.

### Requirement 11: Bảo mật và quyền riêng tư khi đóng gói và phân phối (Cross-cutting)

**User Story:** As a người dùng cài đặt ứng dụng được phân phối, I want dữ liệu và thông tin nhạy cảm của tôi được xử lý an toàn cục bộ, so that thông tin của tôi không bị rò rỉ và ứng dụng đáng tin cậy.

#### Acceptance Criteria

1. WHEN Han_Translate lưu trữ khóa API hoặc thông tin xác thực, THE Security_Module SHALL lưu chúng trong Secure_Storage ở dạng đã mã hóa.
2. THE Security_Module SHALL không ghi khóa API, thông tin xác thực hoặc nội dung dữ liệu người dùng ở dạng văn bản thuần vào tệp nhật ký.
3. WHEN Han_Translate nạp một mô hình AI từ đĩa, THE Security_Module SHALL xác minh tính toàn vẹn của tệp mô hình trước khi nạp.
4. IF việc xác minh tính toàn vẹn của một tệp mô hình thất bại, THEN THE Security_Module SHALL từ chối nạp mô hình đó không có ngoại lệ và thông báo cho người dùng.
5. WHEN Han_Translate xử lý văn bản nguồn, văn bản dịch hoặc dữ liệu âm thanh ở chế độ offline, THE Security_Module SHALL giữ toàn bộ dữ liệu đó trên thiết bị cục bộ.
6. WHERE người dùng yêu cầu xóa dữ liệu cá nhân, THE Security_Module SHALL xóa Translation_Memory, Personal_Phrasebook và các mục trong Secure_Storage theo yêu cầu của người dùng.
7. WHEN gói cài đặt được tạo, THE Security_Module SHALL không bao gồm khóa API hoặc thông tin xác thực của nhà phát triển trong gói phân phối.
