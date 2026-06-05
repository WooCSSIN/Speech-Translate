"""
AI Realtime Interpreter - Desktop Application

Ứng dụng desktop phiên dịch AI realtime.
Double-click mở → bấm Start → nghe tiếng Việt.
"""

import sys
import os
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSlider, QTextEdit, QGroupBox,
    QSystemTrayIcon, QMenu, QFrame, QCheckBox, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, pyqtProperty, QPropertyAnimation, QRectF, QVariantAnimation
from PyQt6.QtGui import QIcon, QAction, QFont, QColor, QPalette, QKeySequence, QShortcut, QPixmap, QPainter, QPen
from loguru import logger

from .config import InterpreterConfig
from .pipeline.orchestrator import InterpreterPipeline

# Đường dẫn assets
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PNG = os.path.join(ASSETS_DIR, "logo.png")
LOGO_ICO = os.path.join(ASSETS_DIR, "logo.ico")


def add_shadow(widget, color_alpha=30, blur_radius=20, y_offset=5):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    shadow.setColor(QColor(0, 0, 0, color_alpha))
    shadow.setOffset(0, y_offset)
    widget.setGraphicsEffect(shadow)

class AnimatedButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._bg_color = QColor("#4CAF50")
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(300)
        self.anim.valueChanged.connect(self._on_color_changed)
        self.is_active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_color_changed(self._bg_color)

    def _on_color_changed(self, color):
        self._bg_color = color
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color.name()};
                color: white;
                border: none;
                border-radius: 12px;
                padding: 14px;
                font-weight: bold;
                font-size: 16px;
                letter-spacing: 1px;
            }}
            QPushButton:disabled {{
                background-color: #a5d6a7;
            }}
        """)

    def set_active_state(self, active):
        self.is_active = active
        self.anim.stop()
        if active:
            self.setText("⏹  DỪNG PHIÊN DỊCH")
            self.anim.setStartValue(self._bg_color)
            self.anim.setEndValue(QColor("#f44336"))
        else:
            self.setText("▶  BẮT ĐẦU PHIÊN DỊCH")
            self.anim.setStartValue(self._bg_color)
            self.anim.setEndValue(QColor("#4CAF50"))
        self.anim.start()

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(QColor("#da190b") if self.is_active else QColor("#3d8b40"))
        self.anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._bg_color)
        self.anim.setEndValue(QColor("#f44336") if self.is_active else QColor("#4CAF50"))
        self.anim.start()
        super().leaveEvent(event)


class AnimatedToggle(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._position = 2
        self.animation = QPropertyAnimation(self, b"position")
        self.animation.setDuration(200)
        self.stateChanged.connect(self.setup_animation)

    @pyqtProperty(float)
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        self._position = pos
        self.update()

    def setup_animation(self, value):
        self.animation.stop()
        if value:
            self.animation.setEndValue(26)
        else:
            self.animation.setEndValue(2)
        self.animation.start()

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        rect = QRectF(0, 0, self.width(), self.height())
        if self.isChecked():
            painter.setBrush(QColor("#f3b519")) # Vàng cam khi bật
        else:
            painter.setBrush(QColor("#e8e8e8")) # Xám khi tắt
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 12, 12)
        
        # Knob
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#d5d5d5"), 1))
        painter.drawEllipse(QRectF(self._position, 2, 20, 20))


class SignalBridge(QObject):
    """Bridge để gửi signal từ thread khác về UI thread"""
    transcription_signal = pyqtSignal(str, str, bool)  # text, lang, is_final
    translation_signal = pyqtSignal(str, bool)  # translated text, is_final
    status_signal = pyqtSignal(str)  # status message
    error_signal = pyqtSignal(str)  # error message
    domain_signal = pyqtSignal(str, str)  # domain_id, domain_name
    cultural_note_signal = pyqtSignal(str, str)  # phrase, meaning
    offline_signal = pyqtSignal(bool, str)  # is_offline, reason


class InterpreterApp(QMainWindow):
    """Main Application Window"""

    def __init__(self):
        super().__init__()
        self.config = InterpreterConfig()
        self.pipeline = None
        self.is_running = False
        self.is_dark_mode = False
        
        # State tracking cho partial text
        self._last_transcription_was_partial = False
        self._last_translation_was_partial = False

        # Signal bridge for thread-safe UI updates
        self.signals = SignalBridge()
        self.signals.transcription_signal.connect(self._on_transcription)
        self.signals.translation_signal.connect(self._on_translation)
        self.signals.status_signal.connect(self._on_status)
        self.signals.error_signal.connect(self._on_error)
        self.signals.domain_signal.connect(self._on_domain_change)
        self.signals.cultural_note_signal.connect(self._on_cultural_note)
        self.signals.offline_signal.connect(self._on_offline_change)

        self._init_ui()
        self._init_tray()

    def _init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("Han Translate")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(self._get_stylesheet())

        # Window icon
        if os.path.exists(LOGO_ICO):
            self.setWindowIcon(QIcon(LOGO_ICO))
        elif os.path.exists(LOGO_PNG):
            self.setWindowIcon(QIcon(LOGO_PNG))

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # === Header với logo ===
        header_layout = QHBoxLayout()
        header_layout.addStretch()

        # Logo image
        if os.path.exists(LOGO_PNG):
            logo_label = QLabel()
            pixmap = QPixmap(LOGO_PNG).scaled(
                48, 48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label.setPixmap(pixmap)
            header_layout.addWidget(logo_label)

        header = QLabel("Han Translate")
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        # Nút chuyển đổi Dark/Light mode
        theme_container = QHBoxLayout()
        theme_container.addWidget(QLabel("🌙 Mode:"))
        self.theme_toggle = AnimatedToggle()
        self.theme_toggle.toggled.connect(self._toggle_theme)
        theme_container.addWidget(self.theme_toggle)
        header_layout.addLayout(theme_container)

        layout.addLayout(header_layout)

        subtitle = QLabel("Phiên dịch viên AI - Dịch realtime mọi ngôn ngữ sang mọi ngôn ngữ")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # === Controls ===
        controls_group = QGroupBox("CẤU HÌNH HỆ THỐNG")
        add_shadow(controls_group, color_alpha=15)
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(15)
        controls_layout.setContentsMargins(20, 30, 20, 20)

        # Row 1: Audio source + Language
        row1 = QHBoxLayout()

        row1.addWidget(QLabel("Nguồn âm:"))
        self.combo_source = QComboBox()
        self.combo_source.addItems(["🔊 System Audio (Loa)", "🎤 Microphone"])
        self.combo_source.currentIndexChanged.connect(self._on_source_changed)
        row1.addWidget(self.combo_source)

        row1.addWidget(QLabel("Từ:"))
        self.combo_lang_from = QComboBox()
        from .languages import get_source_languages, get_target_languages
        self._source_langs = get_source_languages()
        for code, name in self._source_langs:
            self.combo_lang_from.addItem(name, code)
        # Default English
        idx = next((i for i, (c, _) in enumerate(self._source_langs) if c == "en"), 0)
        self.combo_lang_from.setCurrentIndex(idx)
        row1.addWidget(self.combo_lang_from)

        row1.addWidget(QLabel("Sang:"))
        self.combo_lang_to = QComboBox()
        self._target_langs = get_target_languages()
        for code, name in self._target_langs:
            self.combo_lang_to.addItem(name, code)
        # Default Vietnamese
        idx = next((i for i, (c, _) in enumerate(self._target_langs) if c == "vi"), 0)
        self.combo_lang_to.setCurrentIndex(idx)
        self.combo_lang_to.currentIndexChanged.connect(self._on_target_lang_changed)
        row1.addWidget(self.combo_lang_to)

        controls_layout.addLayout(row1)

        # Row 2: Mode + Voice
        row2 = QHBoxLayout()

        row2.addWidget(QLabel("Chế độ:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["🎬 Thuyết minh", "🎭 Lồng tiếng", "📖 Song ngữ"])
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        row2.addWidget(self.combo_mode)

        row2.addWidget(QLabel("Giọng đọc:"))
        self.combo_voice = QComboBox()
        self._populate_voices("vi")  # default Vietnamese voices
        row2.addWidget(self.combo_voice)

        row2.addWidget(QLabel("Tốc độ:"))
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(50, 150)
        self.slider_speed.setValue(100)
        self.slider_speed.setMaximumWidth(100)
        row2.addWidget(self.slider_speed)
        self.lbl_speed = QLabel("1.0x")
        row2.addWidget(self.lbl_speed)
        self.slider_speed.valueChanged.connect(
            lambda v: self.lbl_speed.setText(f"{v/100:.1f}x")
        )

        controls_layout.addLayout(row2)

        # Row 3: Domain / Ngữ cảnh (Capability A)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Lĩnh vực:"))
        self.combo_domain = QComboBox()
        # "Tự động" = context classifier tự nhận diện
        self.combo_domain.addItem("🤖 Tự động (AI nhận diện)", None)
        from .context.domain_profiles import list_profiles
        for profile in list_profiles():
            self.combo_domain.addItem(profile.name, profile.id)
        self.combo_domain.currentIndexChanged.connect(self._on_domain_selected)
        row3.addWidget(self.combo_domain)
        row3.addStretch()
        controls_layout.addLayout(row3)

        # Row 4: Văn hóa Việt (Capability C) + Offline (Capability F)
        row4 = QHBoxLayout()

        # Vùng miền (Req 3.8)
        row4.addWidget(QLabel("Vùng miền:"))
        self.combo_region = QComboBox()
        from .culture.regional import RegionalVariant
        for r in RegionalVariant.list_regions():
            self.combo_region.addItem(r["name"], r["id"])
        self.combo_region.currentIndexChanged.connect(self._on_region_changed)
        row4.addWidget(self.combo_region)

        # Xưng hô (Req 3.6)
        row4.addWidget(QLabel("Xưng hô:"))
        self.combo_honorific = QComboBox()
        self.combo_honorific.addItem("Tự động (AI)", None)
        from .culture.honorifics import HonorificResolver
        for pair in HonorificResolver().list_pairs():
            self.combo_honorific.addItem(pair.label, pair.id)
        self.combo_honorific.currentIndexChanged.connect(self._on_honorific_changed)
        row4.addWidget(self.combo_honorific)

        # Offline mode (Capability F)
        row4.addWidget(QLabel("  "))  # spacer
        self.combo_offline = QComboBox()
        self.combo_offline.addItems(["🌐 Auto (tự chuyển)", "📴 Luôn offline", "☁️ Luôn online"])
        self.combo_offline.currentIndexChanged.connect(self._on_offline_mode_changed)
        row4.addWidget(self.combo_offline)

        controls_layout.addLayout(row4)

        layout.addWidget(controls_group)

        # === Start/Stop Button ===
        self.btn_start = AnimatedButton("▶  BẮT ĐẦU PHIÊN DỊCH")
        self.btn_start.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.btn_start.setMinimumHeight(60)
        add_shadow(self.btn_start, color_alpha=25, blur_radius=15, y_offset=4)
        self.btn_start.clicked.connect(self._toggle_interpreter)
        layout.addWidget(self.btn_start)
        
        # Spacer for breathing room
        layout.addSpacing(10)

        # === Output Display ===
        output_group = QGroupBox("KẾT QUẢ PHIÊN DỊCH")
        add_shadow(output_group, color_alpha=15)
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(15)
        output_layout.setContentsMargins(20, 30, 20, 20)

        # Status bar with domain badge
        status_row = QHBoxLayout()

        self.lbl_status = QLabel("⏸️ Sẵn sàng")
        self.lbl_status.setObjectName("status")
        status_row.addWidget(self.lbl_status)

        status_row.addStretch()

        # Domain badge - hiển thị ngữ cảnh đang nhận diện (Capability A)
        domain_label = QLabel("Ngữ cảnh:")
        domain_label.setObjectName("domain_label")
        status_row.addWidget(domain_label)

        self.lbl_domain = QLabel("Hằng ngày")
        self.lbl_domain.setStyleSheet(self._domain_badge_style("daily"))
        status_row.addWidget(self.lbl_domain)

        output_layout.addLayout(status_row)

        # Transcription + Translation display
        text_layout = QHBoxLayout()

        # Original text
        left_frame = QVBoxLayout()
        left_frame.addWidget(QLabel("Nguyên bản:"))
        self.text_original = QTextEdit()
        self.text_original.setReadOnly(True)
        self.text_original.setMaximumHeight(150)
        self.text_original.setPlaceholderText("Text gốc sẽ hiện ở đây...")
        left_frame.addWidget(self.text_original)
        text_layout.addLayout(left_frame)

        # Translated text
        right_frame = QVBoxLayout()
        self.lbl_translated_title = QLabel("Bản dịch:")
        right_frame.addWidget(self.lbl_translated_title)
        self.text_translated = QTextEdit()
        self.text_translated.setReadOnly(True)
        self.text_translated.setMaximumHeight(150)
        self.text_translated.setPlaceholderText("Bản dịch sẽ hiện ở đây...")
        self.text_translated.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_frame.addWidget(self.text_translated)
        text_layout.addLayout(right_frame)

        output_layout.addLayout(text_layout)

        # Cultural note area (Capability C - Req 3.5)
        self.lbl_cultural_note = QLabel("")
        self.lbl_cultural_note.setWordWrap(True)
        self.lbl_cultural_note.setStyleSheet(
            "background-color: #FFF3E0; border: 1px solid #FFB74D; "
            "border-radius: 6px; padding: 8px; font-size: 12px; color: #E65100;"
        )
        self.lbl_cultural_note.setVisible(False)
        output_layout.addWidget(self.lbl_cultural_note)

        layout.addWidget(output_group)

        # === Footer ===
        footer = QLabel("Ctrl+Shift+I: Bật/Tắt nhanh  |  Ctrl+Q: Thoát")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        # === Shortcuts ===
        QShortcut(QKeySequence("Ctrl+Shift+I"), self, self._toggle_interpreter)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)

    def _init_tray(self):
        """Khởi tạo system tray"""
        self.tray = QSystemTrayIcon(self)
        # Logo icon
        if os.path.exists(LOGO_ICO):
            self.tray.setIcon(QIcon(LOGO_ICO))
        elif os.path.exists(LOGO_PNG):
            self.tray.setIcon(QIcon(LOGO_PNG))
        self.tray.setToolTip("Han Translate")

        tray_menu = QMenu()
        action_show = QAction("Mở", self)
        action_show.triggered.connect(self.show)
        tray_menu.addAction(action_show)

        action_toggle = QAction("Bật/Tắt phiên dịch", self)
        action_toggle.triggered.connect(self._toggle_interpreter)
        tray_menu.addAction(action_toggle)

        tray_menu.addSeparator()

        action_quit = QAction("Thoát", self)
        action_quit.triggered.connect(self._quit_app)
        tray_menu.addAction(action_quit)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _toggle_interpreter(self):
        """Bật/tắt phiên dịch"""
        if self.is_running:
            self._stop_interpreter()
        else:
            self._start_interpreter()

    def _start_interpreter(self):
        """Bắt đầu phiên dịch"""
        self.lbl_status.setText("⏳ Đang khởi động...")
        self.btn_start.setEnabled(False)
        QApplication.processEvents()

        # Update config from UI
        self._apply_config()

        # Create pipeline
        self.pipeline = InterpreterPipeline(self.config)
        self.pipeline.on_transcription = lambda t, l, is_final: self.signals.transcription_signal.emit(t, l, is_final)
        self.pipeline.on_translation = lambda t, is_final: self.signals.translation_signal.emit(t, is_final)
        self.pipeline.on_domain_change = lambda p: self.signals.domain_signal.emit(p.id, p.name)

        # Cultural note callback (Req 3.5)
        self.pipeline.router.on_cultural_note = lambda note: self.signals.cultural_note_signal.emit(
            note.phrase, note.meaning
        )

        # Áp dụng lựa chọn lĩnh vực thủ công nếu có (Req 1.4)
        manual_domain = self.combo_domain.currentData()
        self.pipeline.router.set_manual_profile(manual_domain)

        # Áp dụng vùng miền + xưng hô (Capability C)
        region_id = self.combo_region.currentData()
        if region_id:
            self.pipeline.router.culture.set_region(region_id)
        honorific_id = self.combo_honorific.currentData()
        self.pipeline.router.culture.set_manual_honorific(honorific_id)

        # FIX: Start trong background thread
        # is_running chỉ được set True SAU KHI pipeline.start() thành công
        # tránh UI hiển thị sai trạng thái nếu start() thất bại
        def start_pipeline():
            try:
                self.pipeline.start()
                # Chỉ báo thành công nếu không có exception
                self.signals.status_signal.emit("🟢 Đang phiên dịch...")
            except Exception as e:
                logger.error(f"Pipeline start failed: {e}")
                self.signals.error_signal.emit(str(e))
                # Reset trạng thái UI về Dừng nếu khởi động thất bại
                self.is_running = False
                self.btn_start.set_active_state(False)
                self.btn_start.setEnabled(True)

        threading.Thread(target=start_pipeline, daemon=True).start()

        # Đặt is_running = True ngay để UI phản hồi nhanh,
        # nhưng nếu start() thất bại thì thread trên sẽ reset lại về False
        self.is_running = True
        self.btn_start.set_active_state(True)
        self.btn_start.setEnabled(True)

    def _stop_interpreter(self):
        """Dừng phiên dịch"""
        if self.pipeline:
            threading.Thread(target=self.pipeline.stop, daemon=True).start()
            self.pipeline = None

        self.is_running = False
        self.lbl_status.setText("⏸️ Đã dừng")
        self.btn_start.set_active_state(False)

    def _apply_config(self):
        """Áp dụng config từ UI"""
        # Audio source
        if self.combo_source.currentIndex() == 0:
            self.config.audio.mode = "system"
        else:
            self.config.audio.mode = "mic"

        # Source language (từ combo data)
        src_code = self.combo_lang_from.currentData() or "en"
        self.config.translation.source_lang = src_code
        self.config.stt.language = src_code

        # Target language (từ combo data)
        tgt_code = self.combo_lang_to.currentData() or "vi"
        self.config.translation.target_lang = tgt_code

        # Mode
        mode_map = {0: "narration", 1: "dubbing", 2: "bilingual"}
        self.config.mixer.mode = mode_map.get(self.combo_mode.currentIndex(), "narration")

        # Voice (từ combo data)
        voice_id = self.combo_voice.currentData()
        if voice_id:
            self.config.tts.voice = voice_id

        # Speed
        self.config.tts.speed = self.slider_speed.value() / 100.0

        # FIX: Áp dụng offline_mode vào config
        # _offline_mode được set trong _on_offline_mode_changed()
        offline_mode = getattr(self, '_offline_mode', 'auto')
        if hasattr(self.config, 'offline_mode'):
            self.config.offline_mode = offline_mode
        # Nếu config chưa có field offline_mode, lưu tạm để pipeline/router dùng
        self._resolved_offline_mode = offline_mode
        logger.debug(f"Config applied: {src_code}→{tgt_code}, offline={offline_mode}")

    def _populate_voices(self, lang_code: str):
        """Load danh sách giọng TTS theo ngôn ngữ đích"""
        from .languages import get_voices_for_language
        self.combo_voice.clear()
        voices = get_voices_for_language(lang_code)
        for voice_id, display_name, gender in voices:
            self.combo_voice.addItem(display_name, voice_id)

    def _on_target_lang_changed(self, index):
        """Khi đổi ngôn ngữ đích → cập nhật danh sách giọng"""
        lang_code = self.combo_lang_to.currentData()
        if lang_code:
            self._populate_voices(lang_code)

    def _on_transcription(self, text, lang, is_final):
        """Callback khi có transcription mới"""
        from PyQt6.QtGui import QTextCursor
        
        cursor = self.text_original.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_original.setTextCursor(cursor)
        
        if self._last_transcription_was_partial:
            # Xóa dòng partial cuối cùng
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            # Xóa thêm block format empty nếu có
            cursor.deletePreviousChar()

        if not is_final:
            # Hiển thị màu xám cho partial
            color = "#aaaaaa" if self.is_dark_mode else "#888888"
            self.text_original.append(f"<span style='color: {color};'>[{lang}] {text} (đang dịch...)</span>")
        else:
            color = "#ffffff" if self.is_dark_mode else "#000000"
            self.text_original.append(f"<span style='color: {color};'>[{lang}] {text}</span>")
            
        self._last_transcription_was_partial = not is_final

        # Auto scroll
        self.text_original.verticalScrollBar().setValue(
            self.text_original.verticalScrollBar().maximum()
        )

    def _on_translation(self, text, is_final):
        """Callback khi có translation mới"""
        from PyQt6.QtGui import QTextCursor
        
        cursor = self.text_translated.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_translated.setTextCursor(cursor)
        
        if self._last_translation_was_partial:
            # Xóa dòng partial cuối cùng
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()

        if not is_final:
            color = "#ffcc00" if self.is_dark_mode else "#d35400"
            self.text_translated.append(f"<span style='color: {color}; font-style: italic;'>{text}</span>")
        else:
            color = "#ffffff" if self.is_dark_mode else "#000000"
            self.text_translated.append(f"<span style='color: {color};'>{text}</span>")
            
        self._last_translation_was_partial = not is_final

        self.text_translated.verticalScrollBar().setValue(
            self.text_translated.verticalScrollBar().maximum()
        )

    def _on_status(self, status):
        """Update status"""
        self.lbl_status.setText(status)

    def _domain_badge_style(self, domain_id):
        """Style cho domain badge theo từng lĩnh vực (màu khác nhau)"""
        colors = {
            "daily": "#607D8B",      # xám xanh
            "travel": "#FF9800",     # cam
            "medical": "#E91E63",    # hồng đỏ
            "legal": "#3F51B5",      # xanh tím
            "technical": "#009688",  # teal
            "fintech": "#4CAF50",    # xanh lá
            "business": "#9C27B0",   # tím
        }
        color = colors.get(domain_id, "#607D8B")
        return (
            f"background-color: {color}; color: white; "
            f"font-size: 12px; font-weight: bold; "
            f"padding: 3px 12px; border-radius: 10px;"
        )

    def _on_domain_change(self, domain_id, domain_name):
        """Callback khi ngữ cảnh thay đổi (Capability A)"""
        self.lbl_domain.setText(domain_name)
        self.lbl_domain.setStyleSheet(self._domain_badge_style(domain_id))

    def _on_domain_selected(self, index):
        """Khi người dùng chọn lĩnh vực thủ công (manual override - Req 1.4)"""
        domain_id = self.combo_domain.currentData()
        # domain_id = None nghĩa là Tự động
        if self.pipeline and self.pipeline.is_running:
            self.pipeline.router.set_manual_profile(domain_id)
        # Cập nhật badge ngay nếu chọn manual
        if domain_id:
            from .context.domain_profiles import get_profile
            profile = get_profile(domain_id)
            self.lbl_domain.setText(profile.name)
            self.lbl_domain.setStyleSheet(self._domain_badge_style(domain_id))

    def _on_error(self, error):
        """Handle error"""
        self.lbl_status.setText(f"❌ Lỗi: {error}")
        self._stop_interpreter()

    def _on_source_changed(self, index):
        """Khi đổi nguồn audio"""
        pass

    def _on_mode_changed(self, index):
        """Khi đổi chế độ"""
        pass

    def _on_region_changed(self, index):
        """Khi đổi vùng miền (Req 3.8)"""
        region_id = self.combo_region.currentData()
        if self.pipeline and self.pipeline.is_running:
            self.pipeline.router.culture.set_region(region_id)

    def _on_honorific_changed(self, index):
        """Khi đổi cặp xưng hô (Req 3.6)"""
        pair_id = self.combo_honorific.currentData()  # None = tự động
        if self.pipeline and self.pipeline.is_running:
            self.pipeline.router.culture.set_manual_honorific(pair_id)

    def _on_offline_mode_changed(self, index):
        """Khi đổi chế độ offline (Capability F)"""
        modes = {0: "auto", 1: "always_offline", 2: "always_online"}
        mode = modes.get(index, "auto")
        self._offline_mode = mode

        # FIX: Áp dụng ngay vào pipeline nếu đang chạy (hot-reload)
        if self.pipeline and self.pipeline.is_running:
            if hasattr(self.pipeline, 'set_offline_mode'):
                self.pipeline.set_offline_mode(mode)
        logger.debug(f"Offline mode changed to: {mode}")

    def _on_cultural_note(self, phrase, meaning):
        """Hiển thị ghi chú văn hóa (Req 3.5)"""
        self.lbl_cultural_note.setText(f"💡 \"{phrase}\" — {meaning}")
        self.lbl_cultural_note.setVisible(True)
        # Tự ẩn sau 10 giây
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10000, lambda: self.lbl_cultural_note.setVisible(False))

    def _on_offline_change(self, is_offline, reason):
        """Khi chế độ online/offline thay đổi"""
        if is_offline:
            self.lbl_status.setText(f"📴 Offline: {reason}")
        else:
            self.lbl_status.setText(f"🌐 Online: {reason}")
        pass

    def _tray_activated(self, reason):
        """Khi click tray icon"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()

    def _quit_app(self):
        """Thoát app"""
        if self.is_running:
            self._stop_interpreter()
        QApplication.quit()

    def closeEvent(self, event):
        """Ẩn vào tray thay vì thoát"""
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Han Translate",
            "Ứng dụng vẫn chạy ở system tray. Click đúp để mở lại.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def _toggle_theme(self, checked):
        """Chuyển đổi giao diện Sáng/Tối"""
        self.is_dark_mode = checked
        self.setStyleSheet(self._get_stylesheet())

    def _get_stylesheet(self):
        # Thiết kế Floating Title cho QGroupBox và các ô input siêu mịn
        if hasattr(self, 'is_dark_mode') and self.is_dark_mode:
            return """
                QMainWindow { background-color: #121212; color: #ffffff; font-family: 'Segoe UI', Inter, sans-serif; }
                QLabel { color: #e0e0e0; font-size: 13px; font-weight: 500; }
                QLabel#subtitle { color: #999; font-size: 12px; }
                QLabel#status { color: #bbb; font-size: 14px; padding: 4px; font-weight: 600; }
                QLabel#domain_label { color: #888; font-size: 12px; }
                QLabel#footer { color: #666; font-size: 11px; }
                
                QGroupBox {
                    background-color: #1e1e1e;
                    border: none;
                    border-radius: 12px;
                    margin-top: 28px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top center; 
                    padding: 6px 16px;
                    background-color: #f3b519;
                    color: #121212;
                    font-size: 13px;
                    font-weight: bold;
                    border-radius: 12px;
                    top: 4px;
                }
                
                QComboBox {
                    padding: 8px 14px;
                    border: 1px solid #333;
                    border-radius: 8px;
                    background-color: #2a2a2a;
                    color: #ffffff;
                    min-width: 100px;
                    font-size: 13px;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 30px;
                }
                QComboBox:hover {
                    border: 1px solid #f3b519;
                }
                QComboBox QAbstractItemView {
                    background-color: #2a2a2a;
                    color: #ffffff;
                    selection-background-color: #f3b519;
                    selection-color: #121212;
                    border-radius: 8px;
                    border: 1px solid #333;
                    outline: none;
                }
                
                QTextEdit {
                    border: 1px solid #333;
                    border-radius: 10px;
                    padding: 12px;
                    background-color: #2a2a2a;
                    color: #ffffff;
                    font-size: 14px;
                    line-height: 1.5;
                }
                QTextEdit:focus {
                    border: 1px solid #f3b519;
                }
            """
        else:
            return """
                QMainWindow { background-color: #f0f2f5; color: #2c3e50; font-family: 'Segoe UI', Inter, sans-serif; }
                QLabel { color: #2c3e50; font-size: 13px; font-weight: 500; }
                QLabel#subtitle { color: #7f8c8d; font-size: 12px; }
                QLabel#status { color: #34495e; font-size: 14px; padding: 4px; font-weight: 600; }
                QLabel#domain_label { color: #7f8c8d; font-size: 12px; }
                QLabel#footer { color: #95a5a6; font-size: 11px; }
                
                QGroupBox {
                    background-color: #ffffff;
                    border: none;
                    border-radius: 12px;
                    margin-top: 28px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top center; 
                    padding: 6px 16px;
                    background-color: #4CAF50;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                    border-radius: 12px;
                    top: 4px;
                }
                
                QComboBox {
                    padding: 8px 14px;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    background-color: #f8f9fa;
                    color: #2c3e50;
                    min-width: 100px;
                    font-size: 13px;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 30px;
                }
                QComboBox:hover {
                    border: 1px solid #4CAF50;
                    background-color: #ffffff;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #2c3e50;
                    selection-background-color: #e8f5e9;
                    selection-color: #2c3e50;
                    border-radius: 8px;
                    border: 1px solid #e0e0e0;
                    outline: none;
                }
                
                QTextEdit {
                    border: 1px solid #e0e0e0;
                    border-radius: 10px;
                    padding: 12px;
                    background-color: #f9fbfc;
                    color: #2c3e50;
                    font-size: 14px;
                    line-height: 1.5;
                }
                QTextEdit:focus {
                    border: 1px solid #4CAF50;
                    background-color: #ffffff;
                }
            """


def run_app():
    """Entry point cho desktop app"""
    # Setup logging
    logger.remove()
    logger.add(sys.stderr, format="{time:HH:mm:ss} | {level: <7} | {message}", level="INFO")

    # First-run security setup: mỗi máy tự sinh API key riêng (Req 11.7)
    try:
        from .packaging_security import first_run_setup
        first_run_setup()
    except Exception as e:
        logger.warning(f"First-run setup gặp lỗi (bỏ qua): {e}")

    app = QApplication(sys.argv)
    app.setApplicationName("Han Translate")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # App icon
    if os.path.exists(LOGO_ICO):
        app.setWindowIcon(QIcon(LOGO_ICO))
    elif os.path.exists(LOGO_PNG):
        app.setWindowIcon(QIcon(LOGO_PNG))

    window = InterpreterApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
