"""
OverlayUI — 面试助手悬浮窗
置顶策略：纯 Qt 方案（WindowStaysOnTopHint + Tool + 500ms 定时 raise）
完全移除 PyObjC / Cocoa 调用，避免 Segfault 崩溃
"""

import os
import requests
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QTextEdit,
    QPushButton,
    QFileDialog,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QShortcut, QKeySequence


class OverlayUI(QWidget):
    update_signal = pyqtSignal(str, str)
    end_session_signal = pyqtSignal()
    send_text_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # ── 窗口标志：无边框、始终置顶、工具窗口 ──
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # ── 外层布局 ──
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── 毛玻璃卡片 ──
        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setStyleSheet(
            """
            #card {
                background-color: rgba(18, 18, 18, 192);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 16px;
            }
        """
        )
        outer.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(8)

        # 1. 实时 ASR 文本（暗灰色）
        self.asr_label = QLabel("🎤 正在倾听面试官...")
        self.asr_label.setFont(QFont("SF Pro Text", 12))
        self.asr_label.setStyleSheet(
            "color: rgba(255,255,255,85); background: transparent;"
        )
        self.asr_label.setWordWrap(True)
        layout.addWidget(self.asr_label)

        # 2. 标题 / 状态
        self.outline_label = QLabel("等待开启面试")
        self.outline_label.setFont(QFont("SF Pro Text", 16, QFont.Weight.Bold))
        self.outline_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        self.outline_label.setWordWrap(True)
        layout.addWidget(self.outline_label)

        # 3. 答案滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet("background: transparent; border: none;")
        self.answer_label = QLabel("")
        self.answer_label.setFont(QFont("SF Pro Text", 14))
        self.answer_label.setStyleSheet(
            "color: rgba(255,255,255,210); background: transparent; padding: 2px 0;"
        )
        self.answer_label.setWordWrap(True)
        self.answer_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.answer_label)
        layout.addWidget(scroll)

        # ── 分隔线 ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            "background: rgba(255,255,255,15); border: none; max-height: 1px;"
        )
        layout.addWidget(sep)

        # 4. 输入行
        row = QHBoxLayout()
        row.setSpacing(8)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("手动输入提问，Ctrl+Enter 发送...")
        self.text_input.setMaximumHeight(70)
        self.text_input.setStyleSheet(
            """
            QTextEdit {
                background: rgba(255,255,255,8);
                border: 1px solid rgba(255,255,255,16);
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 13px;
                padding: 6px 10px;
            }
        """
        )
        row.addWidget(self.text_input)

        col = QVBoxLayout()
        col.setSpacing(6)

        self.btn_img = QPushButton("🖼")
        self.btn_img.setFixedSize(34, 34)
        self.btn_img.setToolTip("上传图片")
        self.btn_img.setStyleSheet(self._btn_css())
        self.btn_img.clicked.connect(self.send_image)
        col.addWidget(self.btn_img)

        self.btn_send = QPushButton("↑")
        self.btn_send.setFixedSize(34, 34)
        self.btn_send.setFont(QFont("SF Pro Text", 16, QFont.Weight.Bold))
        self.btn_send.setStyleSheet(self._btn_css(primary=True))
        self.btn_send.clicked.connect(self.send_text)
        col.addWidget(self.btn_send)

        row.addLayout(col)
        layout.addLayout(row)

        # 5. 底部提示
        hint = QLabel("Option+E 结束并复盘")
        hint.setStyleSheet(
            "color: rgba(255,255,255,38); font-size: 11px; background: transparent;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(hint)

        self.setFixedWidth(520)
        self.adjustSize()
        self.move(80, 80)

        # ── 快捷键 ──
        QShortcut(QKeySequence("Alt+E"), self).activated.connect(
            self.end_session_signal.emit
        )
        QShortcut(QKeySequence("Meta+E"), self).activated.connect(
            self.end_session_signal.emit
        )
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.send_text)

        self.update_signal.connect(self.update_text)

    def _qt_raise(self):
        """纯 Qt 置顶：raise_() 将窗口提到所有同级窗口的最前面"""
        self.raise_()

    # ── 内容更新 ──
    def update_text(self, msg_type: str, text: str):
        if msg_type == "incremental":
            self.asr_label.setText(f"🎤 {text}")
        elif msg_type == "outline":
            self.outline_label.setText(f"💡 {text}")
            self.answer_label.setText("正在生成回答...")
        elif msg_type == "answer":
            self.asr_label.setText("🎤 正在倾听...")
            self.outline_label.setText("💡 AI 参考回答")
            self.answer_label.setText(text)
        elif msg_type == "analysis":
            self.asr_label.hide()
            self.outline_label.setText("📊 面试复盘报告")
            self.answer_label.setText(text)
            self.setFixedWidth(680)
            self.adjustSize()

    # ── 文本发送 ──
    def send_text(self):
        text = self.text_input.toPlainText().strip()
        if text:
            self.send_text_signal.emit(text)
            self.text_input.clear()
            self.outline_label.setText(f"📨 {text[:60]}")
            self.answer_label.setText("正在生成回答...")

    # ── 图片发送 ──
    def send_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                resp = requests.post(
                    "http://localhost:8000/parse_resume",
                    files={"file": (os.path.basename(path), f)},
                )
            if resp.status_code == 200:
                extracted = resp.json().get("text", "[图片内容]")
                self.send_text_signal.emit(f"[图片] {extracted}")
                self.answer_label.setText("图片已发送，正在分析...")
        except Exception as e:
            self.answer_label.setText(f"图片上传失败: {e}")

    # ── 拖动 ──
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    @staticmethod
    def _btn_css(primary=False):
        if primary:
            return (
                "QPushButton { background: #10A37F; border: none; border-radius: 8px; "
                "color: white; } QPushButton:hover { background: #0D8A69; }"
            )
        return (
            "QPushButton { background: rgba(255,255,255,10); border: 1px solid "
            "rgba(255,255,255,16); border-radius: 8px; color: white; } "
            "QPushButton:hover { background: rgba(255,255,255,20); }"
        )
