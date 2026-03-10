"""
OverlayUI — 面试助手悬浮窗（双栏布局版）
左栏：实时字幕（微信式气泡分离说话人）
右栏：AI 回答（一问一答卡片）

置顶策略：纯 Qt 方案（WindowStaysOnTopHint + Tool + 500ms 定时 raise）
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
    QSizePolicy,
    QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QColor


# ── 样式常量 ──
CARD_BG = "rgba(18, 18, 18, 192)"
INTERVIEWER_BUBBLE_BG = "rgba(59, 130, 246, 0.22)"  # 蓝色半透明
CANDIDATE_BUBBLE_BG = "rgba(34, 197, 94, 0.18)"  # 绿色半透明
HIGHLIGHT_BG = "rgba(250, 204, 21, 0.25)"  # 黄色高亮
QA_CARD_BG = "rgba(255, 255, 255, 6)"
FONT_FAMILY = "SF Pro Text"


def _bubble_widget(
    role: str,
    text: str,
    question_id: int | None,
    truncate_callback,
    highlighted: bool = False,
) -> QWidget:
    """创建一个包含说话人气泡和截断按钮的容器。"""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)  # 间距设为0，通过内部组件控制位置

    is_interviewer = role == "interviewer"

    # 截断按钮及其固定容器
    btn_container = QWidget()
    btn_container.setFixedWidth(50)  # 固定宽度，确保按钮纵向对齐
    btn_layout = QHBoxLayout(btn_container)
    btn_layout.setContentsMargins(0, 0, 0, 0)
    btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    truncate_btn = QPushButton("🔘")
    truncate_btn.setFixedSize(30, 30)
    truncate_btn.setFont(QFont(FONT_FAMILY, 10))
    truncate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    truncate_btn.setStyleSheet(
        """
        QPushButton {
            background: rgba(255, 255, 255, 10);
            border: 1px solid rgba(255, 255, 255, 20);
            border-radius: 4px;
            color: rgba(255, 255, 255, 120);
        }
        QPushButton:hover {
            background: rgba(244, 63, 94, 0.4);
            color: white;
            border-color: rgba(244, 63, 94, 0.6);
        }
    """
    )
    if question_id is not None:
        truncate_btn.clicked.connect(
            lambda checked=False, q=question_id: truncate_callback(q)
        )
    else:
        truncate_btn.setEnabled(False)
        truncate_btn.hide()
    btn_layout.addWidget(truncate_btn)

    # 实际的气泡卡片
    bubble = QFrame()
    bubble.setObjectName("bubble")
    bg = INTERVIEWER_BUBBLE_BG if is_interviewer else CANDIDATE_BUBBLE_BG
    highlight_css = (
        f"border-left: 3px solid rgba(250, 204, 21, 0.7); background: {HIGHLIGHT_BG};"
        if highlighted
        else ""
    )

    bubble.setStyleSheet(
        f"""
        QFrame#bubble {{
            background: {bg};
            border-radius: 12px;
            padding: 8px 12px;
            {highlight_css}
        }}
    """
    )

    bubble_layout = QVBoxLayout(bubble)
    bubble_layout.setContentsMargins(0, 0, 0, 0)
    bubble_layout.setSpacing(2)

    prefix = "🔵 面试官" if is_interviewer else "🟢 我"
    role_label = QLabel(prefix)
    role_label.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
    role_label.setStyleSheet(
        f"color: {'rgba(96, 165, 250, 0.9)' if is_interviewer else 'rgba(74, 222, 128, 0.9)'}; "
        "background: transparent;"
    )
    bubble_layout.addWidget(role_label)

    text_label = QLabel(text)
    text_label.setFont(QFont(FONT_FAMILY, 13))
    text_label.setStyleSheet("color: rgba(255,255,255,200); background: transparent;")
    text_label.setWordWrap(True)
    text_label.setTextFormat(Qt.TextFormat.PlainText)
    bubble_layout.addWidget(text_label)

    if is_interviewer:
        # 面试官：气泡居左，按钮固定在中间/右侧对齐
        layout.addWidget(bubble)
        layout.addStretch()
        layout.addWidget(btn_container)
    else:
        # 候选人：按钮固定在中间/左侧对齐，气泡居右
        layout.addWidget(btn_container)
        layout.addStretch()
        layout.addWidget(bubble)

    container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    return container


def _qa_card_widget(question: str, answer: str, streaming: bool = False) -> QFrame:
    """创建一个一问一答卡片。"""
    card = QFrame()
    card.setObjectName("qacard")
    card.setStyleSheet(
        f"""
        QFrame#qacard {{
            background: {QA_CARD_BG};
            border: 1px solid rgba(255,255,255,8);
            border-radius: 10px;
            padding: 10px 12px;
            margin-bottom: 6px;
        }}
    """
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    q_label = QLabel(f"❓ {question}")
    q_label.setFont(QFont(FONT_FAMILY, 11))
    q_label.setStyleSheet("color: rgba(255,255,255,100); background: transparent;")
    q_label.setWordWrap(True)
    layout.addWidget(q_label)

    status = "⏳" if streaming else "✅"
    a_label = QLabel(f"{status} {answer}")
    a_label.setObjectName("answer_text")
    a_label.setFont(QFont(FONT_FAMILY, 13))
    a_label.setStyleSheet("color: rgba(255,255,255,210); background: transparent;")
    a_label.setWordWrap(True)
    layout.addWidget(a_label)

    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    return card


class OverlayUI(QWidget):
    # 信号定义
    update_signal = pyqtSignal(str, str)  # (msg_type, json_payload)
    end_session_signal = pyqtSignal()  # 结束并复盘信号 (Option+E)
    close_window_signal = pyqtSignal()  # 仅关闭窗口信号 (❌, Cmd+\)
    send_text_signal = pyqtSignal(str)
    truncate_signal = pyqtSignal(int)  # 手动截断信号 (question_id)
    highlight_signal = pyqtSignal(int)  # 高亮信号 (question_id)

    def __init__(self):
        super().__init__()
        # 状态追踪
        self._bubbles: list[dict] = (
            []
        )  # [{role, text, widget, question_id, highlighted}]
        self._qa_cards: dict[int, QFrame] = {}  # question_id -> card widget
        self._current_bubble_qid: int | None = (
            None  # 当前正在更新的气泡对应的 question_id
        )
        self._current_bubble_role: str = "unknown"
        self._current_bubble_text_base: str = (
            ""  # 当前气泡中已固定的文本前缀（用于多轮合并）
        )
        self._is_input_full: bool = False
        self.init_ui()

    def init_ui(self):
        # ── 窗口标志 ──
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # ── 外层 ──
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # ── 毛玻璃卡片 ──
        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setStyleSheet(
            f"""
            #card {{
                background-color: {CARD_BG};
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 16px;
            }}
        """
        )
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 12, 14, 10)
        card_layout.setSpacing(6)

        # ── 标题栏 ──
        title_row = QHBoxLayout()
        self.title_label = QLabel("🎙️ 面试助手")
        self.title_label.setFont(QFont(FONT_FAMILY, 14, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #FFFFFF; background: transparent;")
        # 确保标题位置固定
        self.title_label.setFixedWidth(120)
        title_row.addWidget(self.title_label)

        title_row.addStretch()

        self.status_label = QLabel("正在倾听...")
        self.status_label.setFont(QFont(FONT_FAMILY, 11))
        self.status_label.setStyleSheet(
            "color: rgba(255,255,255,60); background: transparent;"
        )
        title_row.addWidget(self.status_label)

        # 增加间距
        title_row.addSpacing(12)

        # 增加关闭按钮
        self.btn_close = QPushButton("❌")
        self.btn_close.setFixedSize(34, 34)
        self.btn_close.setFont(QFont(FONT_FAMILY, 12))
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 12);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 4px;
                color: rgba(255, 255, 255, 180);
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 20);
                color: #FFFFFF;
            }
        """
        )
        self.btn_close.clicked.connect(self.close_window_signal.emit)
        title_row.addWidget(self.btn_close)
        card_layout.addLayout(title_row)

        # ── 分割线 ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            "background: rgba(255,255,255,12); border: none; max-height: 1px;"
        )
        card_layout.addWidget(sep)

        # ── 双栏主体 ──
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet(
            "QSplitter::handle { background: rgba(255,255,255,8); width: 2px; }"
        )

        # 左栏：字幕
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        left_title = QLabel("💬 实时字幕")
        left_title.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        left_title.setStyleSheet(
            "color: rgba(255,255,255,60); background: transparent; padding: 4px 0;"
        )
        left_layout.addWidget(left_title)

        self.subtitle_scroll = QScrollArea()
        self.subtitle_scroll.setWidgetResizable(True)
        self.subtitle_scroll.setMinimumHeight(260)
        self.subtitle_scroll.setStyleSheet("background: transparent; border: none;")
        self.subtitle_container = QWidget()
        self.subtitle_layout = QVBoxLayout(self.subtitle_container)
        self.subtitle_layout.setContentsMargins(4, 4, 4, 4)
        self.subtitle_layout.setSpacing(6)
        self.subtitle_layout.addStretch()  # 气泡从底部向上堆叠
        self.subtitle_scroll.setWidget(self.subtitle_container)
        left_layout.addWidget(self.subtitle_scroll)

        # 右栏：回答
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_title = QLabel("🤖 AI 回答")
        right_title.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Bold))
        right_title.setStyleSheet(
            "color: rgba(255,255,255,60); background: transparent; padding: 4px 0;"
        )
        right_layout.addWidget(right_title)

        self.answer_scroll = QScrollArea()
        self.answer_scroll.setWidgetResizable(True)
        self.answer_scroll.setMinimumHeight(260)
        self.answer_scroll.setStyleSheet("background: transparent; border: none;")
        self.answer_container = QWidget()
        self.answer_layout = QVBoxLayout(self.answer_container)
        self.answer_layout.setContentsMargins(4, 4, 4, 4)
        self.answer_layout.setSpacing(6)
        self.answer_layout.addStretch()
        self.answer_scroll.setWidget(self.answer_container)
        right_layout.addWidget(self.answer_scroll)

        self.splitter.addWidget(left_frame)
        self.splitter.addWidget(right_frame)
        self.splitter.setSizes([540, 360])
        # 将中间主体添加进布局，并设置伸缩因子为 1，确保其占据所有剩余空间
        card_layout.addWidget(self.splitter, 1)

        # ── 分隔线 ──
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(
            "background: rgba(255,255,255,12); border: none; max-height: 1px;"
        )
        card_layout.addWidget(sep2)

        # ── 输入行 ──
        row = QHBoxLayout()
        row.setSpacing(8)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("手动输入提问，Ctrl+Enter 发送...")
        self.text_input.setMaximumHeight(60)
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
        self.btn_send.setFont(QFont(FONT_FAMILY, 16, QFont.Weight.Bold))
        self.btn_send.setStyleSheet(self._btn_css(primary=True))
        self.btn_send.clicked.connect(self.send_text)
        col.addWidget(self.btn_send)

        self.btn_full = QPushButton("🔲")
        self.btn_full.setFixedSize(34, 34)
        self.btn_full.setToolTip("全屏/常规切换")
        self.btn_full.setStyleSheet(self._btn_css())
        self.btn_full.clicked.connect(self._toggle_input_expand)
        col.addWidget(self.btn_full)

        row.addLayout(col)
        # 输入行设置伸缩因子为 0，确保其不随界面拉伸而变高
        card_layout.addLayout(row, 0)

        # ── 底部提示 ──
        hint = QLabel("Option+E 结束并复盘")
        hint.setStyleSheet(
            "color: rgba(255,255,255,38); font-size: 11px; background: transparent;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        card_layout.addWidget(hint)

        # ── 窗口尺寸 ──
        self.setFixedWidth(920)
        self.setMinimumHeight(420)
        self.adjustSize()
        self.move(40, 60)

        # ── 快捷键 ──
        QShortcut(QKeySequence("Alt+E"), self).activated.connect(
            self.end_session_signal.emit
        )
        QShortcut(QKeySequence("Meta+E"), self).activated.connect(
            self.end_session_signal.emit
        )
        # Cmd+\ 快捷键 -> 仅关闭窗口
        QShortcut(QKeySequence("Ctrl+\\"), self).activated.connect(
            self.close_window_signal.emit
        )
        QShortcut(QKeySequence("Meta+\\"), self).activated.connect(
            self.close_window_signal.emit
        )

        # ── 信号连接 ──
        self.update_signal.connect(self._on_update)
        self.highlight_signal.connect(self._highlight_question)

    # ════════════════════════════════════════════════════
    # 核心更新逻辑
    # ════════════════════════════════════════════════════

    def _on_update(self, msg_type: str, payload: str):
        """统一处理后端推送消息。payload 为 JSON 字符串。"""
        import json

        try:
            data = (
                json.loads(payload)
                if payload.startswith("{")
                else {"text": payload, "answer": payload}
            )
        except Exception:
            data = {"text": payload, "answer": payload}

        if msg_type == "incremental":
            self._handle_incremental(data)
        elif msg_type == "outline":
            self._handle_outline(data)
        elif msg_type == "answer":
            self._handle_answer(data)
        elif msg_type == "analysis":
            self._handle_analysis(data)

    def _handle_incremental(self, data: dict):
        """处理实时字幕增量更新。"""
        text = data.get("text", "")
        question_id = data.get("question_id")
        role = data.get("speaker_role", "unknown")
        # 归一化角色
        if role == "interviewer":
            display_role = "interviewer"
        elif role == "candidate":
            display_role = "candidate"
        else:
            display_role = "interviewer"  # 默认视为面试官

        self.status_label.setText("正在倾听...")

        # 逻辑：如果角色没变且已有气泡，则尝试在当前气泡中更新或追加内容
        if display_role == self._current_bubble_role and self._bubbles:
            last = self._bubbles[-1]
            text_label = last["widget"].findChildren(QLabel)[-1]

            # 如果 question_id 变了（开启了新轮次），需要把上一轮的最终结果固定到 base 中
            if question_id != self._current_bubble_qid and question_id is not None:
                # 将上一轮的内容存入 base（加上空格分隔）
                self._current_bubble_text_base = last["text"].strip() + " "
                self._current_bubble_qid = question_id

            # 拼接显示文本：已固定的内容 + 当前正在演变的文本
            full_text = self._current_bubble_text_base + text
            text_label.setText(full_text)
            last["text"] = full_text
        else:
            # 角色变化或首次启动：创建新气泡
            bubble = _bubble_widget(
                display_role, text, question_id, self.truncate_signal.emit
            )
            self._bubbles.append(
                {
                    "role": display_role,
                    "text": text,
                    "widget": bubble,
                    "question_id": question_id,
                    "highlighted": False,
                }
            )
            # 插入到 stretch 之前
            idx = self.subtitle_layout.count() - 1
            self.subtitle_layout.insertWidget(idx, bubble)

            # 更新追踪状态
            self._current_bubble_qid = question_id
            self._current_bubble_role = display_role
            self._current_bubble_text_base = ""  # 新气泡，重置 base

        # 自动滚动到底部
        QTimer.singleShot(
            50,
            lambda: self.subtitle_scroll.verticalScrollBar().setValue(
                self.subtitle_scroll.verticalScrollBar().maximum()
            ),
        )

    def _handle_outline(self, data: dict):
        """处理要点草稿。"""
        answer = data.get("answer", data.get("text", ""))
        question_id = data.get("question_id")
        self.status_label.setText("⚡ 草稿生成中...")
        self._upsert_qa_card(question_id, "（识别中…）", answer, streaming=True)

    def _handle_answer(self, data: dict):
        """处理正式回答。"""
        answer = data.get("answer", "")
        question = data.get("question", "")
        question_id = data.get("question_id")
        streaming = data.get("streaming", False)

        self.status_label.setText(
            "正在倾听..." if not streaming else "⏳ 回答生成中..."
        )
        self._upsert_qa_card(question_id, question, answer, streaming=streaming)

        # 高亮对应的字幕气泡
        if question_id is not None and not streaming:
            self._highlight_question(question_id)

    def _handle_analysis(self, data: dict):
        """处理复盘报告——特殊全屏展示。"""
        answer = data.get("answer", data.get("text", ""))
        self.status_label.setText("📊 复盘已完成")
        # 清空右栏，放复盘内容
        self._clear_layout(self.answer_layout)
        self.answer_layout.addStretch()
        report = QLabel(answer)
        report.setFont(QFont(FONT_FAMILY, 13))
        report.setStyleSheet("color: rgba(255,255,255,210); background: transparent;")
        report.setWordWrap(True)
        report.setTextFormat(Qt.TextFormat.MarkdownText)
        idx = self.answer_layout.count() - 1
        self.answer_layout.insertWidget(idx, report)
        self.setFixedWidth(960)
        self.adjustSize()

    # ════════════════════════════════════════════════════
    # 辅助方法
    # ════════════════════════════════════════════════════

    def _upsert_qa_card(
        self, question_id, question: str, answer: str, streaming: bool = False
    ):
        """创建或更新一问一答卡片。"""
        if question_id is not None and question_id in self._qa_cards:
            card = self._qa_cards[question_id]
            # 更新答案文本
            a_label = card.findChild(QLabel, "answer_text")
            if a_label:
                status = "⏳" if streaming else "✅"
                a_label.setText(f"{status} {answer}")
        else:
            card = _qa_card_widget(question, answer, streaming)
            if question_id is not None:
                self._qa_cards[question_id] = card
            idx = self.answer_layout.count() - 1
            self.answer_layout.insertWidget(idx, card)

        # 自动滚动
        QTimer.singleShot(
            50,
            lambda: self.answer_scroll.verticalScrollBar().setValue(
                self.answer_scroll.verticalScrollBar().maximum()
            ),
        )

    def _highlight_question(self, question_id: int):
        """高亮指定 question_id 对应的字幕气泡。"""
        for entry in self._bubbles:
            if entry.get("question_id") == question_id and not entry.get("highlighted"):
                entry["highlighted"] = True
                role = entry["role"]
                bg = (
                    INTERVIEWER_BUBBLE_BG
                    if role == "interviewer"
                    else CANDIDATE_BUBBLE_BG
                )
                margin = (
                    "margin-right: 40px;"
                    if role == "interviewer"
                    else "margin-left: 40px;"
                )
                entry["widget"].setStyleSheet(
                    f"""
                    QFrame#bubble {{
                        background: {bg};
                        border-radius: 10px;
                        padding: 8px 12px;
                        {margin}
                        border-left: 3px solid rgba(250, 204, 21, 0.7);
                        background: {HIGHLIGHT_BG};
                    }}
                """
                )

    def _clear_layout(self, layout):
        """递归清空布局中的所有 Widget。"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # ════════════════════════════════════════════════════
    # 输入与交互
    # ════════════════════════════════════════════════════

    def send_text(self):
        text = self.text_input.toPlainText().strip()
        if text:
            self.send_text_signal.emit(text)
            self.text_input.clear()
            # 在字幕区添加候选人气泡 (手动输入的问题，QID 可以设为特殊的，或者 None)
            bubble = _bubble_widget(
                "candidate", f"📨 {text}", None, self.truncate_signal.emit
            )
            idx = self.subtitle_layout.count() - 1
            self.subtitle_layout.insertWidget(idx, bubble)

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
        except Exception as e:
            self.status_label.setText(f"图片上传失败: {e}")

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

    def _toggle_input_expand(self):
        """切换输入框全屏模式。"""
        self._is_input_full = not self._is_input_full
        if self._is_input_full:
            self.btn_full.setText("↙️")
            self.splitter.hide()  # 隐藏中间的主体
            self.text_input.setMaximumHeight(2000)  # 允许填充纵向
        else:
            self.btn_full.setText("🔲")
            self.splitter.show()
            self.text_input.setMaximumHeight(60)

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
