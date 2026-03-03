import os
import json
import requests
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QFrame,
    QSpacerItem,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QColor
from user_settings_dialog import UserSettingsDialog


class ControlPanelUI(QWidget):
    start_interview_signal = pyqtSignal(str, str)
    end_interview_signal = pyqtSignal()
    interview_ended_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.records_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "server", "records"
        )
        # Ensure UI refresh after interview always runs on Qt main thread.
        self.interview_ended_signal.connect(self.interview_ended)
        self.init_ui()
        self.refresh_history()

    def init_ui(self):
        self.setWindowTitle("Interview Copilot")
        self.resize(1100, 750)

        # ChatGPT Style Palette
        # Sidebar: #202123
        # Main: #343541
        # Text: #ECECF1

        self.setStyleSheet(
            """
            QWidget {
                background-color: #343541;
                color: #ECECF1;
                font-family: 'Inter', 'Segoe UI', Arial;
            }
            #sidebar {
                background-color: #202123;
                border-right: 1px solid #4D4D4F;
                min-width: 280px;
                max-width: 280px;
            }
            QLabel#nav_header {
                color: #8E8EA0;
                font-size: 12px;
                font-weight: bold;
                text-transform: uppercase;
                margin-left: 12px;
                margin-top: 20px;
                margin-bottom: 8px;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 12px;
                border-radius: 6px;
                margin: 2px 8px;
                color: #ECECF1;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background-color: #2A2B32;
            }
            QListWidget::item:selected {
                background-color: #343541;
            }
            QPushButton#btn_new {
                background-color: transparent;
                border: 1px solid #4D4D4F;
                border-radius: 6px;
                color: #ECECF1;
                padding: 12px;
                text-align: left;
                margin: 8px;
                font-size: 14px;
            }
            QPushButton#btn_new:hover {
                background-color: #2A2B32;
            }
            QPushButton#btn_settings {
                background-color: transparent;
                border: none;
                border-top: 1px solid #4D4D4F;
                border-radius: 0px;
                padding: 15px;
                text-align: left;
                font-size: 14px;
            }
            QPushButton#btn_settings:hover {
                background-color: #2A2B32;
            }
            #main_content {
                background-color: #343541;
            }
            QTextEdit {
                background-color: #40414F;
                border: 1px solid #565869;
                border-radius: 8px;
                padding: 15px;
                font-size: 15px;
                color: #FFFFFF;
                selection-background-color: #2D69E0;
            }
            QPushButton#btn_start {
                background-color: #10A37F; /* ChatGPT Green */
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton#btn_start:hover {
                background-color: #1A7F64;
            }
            QLabel#huge_title {
                font-size: 32px;
                font-weight: 800;
                margin-bottom: 20px;
                color: #FFFFFF;
            }
        """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Sidebar ---
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 8, 0, 0)

        self.btn_new = QPushButton("＋ New Interview")
        self.btn_new.setObjectName("btn_new")
        self.btn_new.clicked.connect(self.show_new_interview)
        sidebar_layout.addWidget(self.btn_new)

        nav_header = QLabel("History")
        nav_header.setObjectName("nav_header")
        sidebar_layout.addWidget(nav_header)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_history_selected)
        sidebar_layout.addWidget(self.history_list)

        sidebar_layout.addStretch()

        self.btn_settings = QPushButton("⚙️  User Settings")
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.clicked.connect(self.open_settings)
        sidebar_layout.addWidget(self.btn_settings)

        layout.addWidget(sidebar)

        # --- Main Content ---
        self.main_stack = QStackedWidget()
        self.main_stack.setObjectName("main_content")

        # New Interview Page
        self.prep_page = QWidget()
        prep_layout = QVBoxLayout(self.prep_page)
        prep_layout.setContentsMargins(80, 60, 80, 60)
        prep_layout.setSpacing(20)

        huge_title = QLabel("How can I help you today?")
        huge_title.setObjectName("huge_title")
        huge_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prep_layout.addWidget(huge_title)

        instruction = QLabel("Paste the Job Description (JD) below to get started.")
        instruction.setStyleSheet("color: #8E8EA0; font-size: 14px;")
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prep_layout.addWidget(instruction)

        self.jd_input = QTextEdit()
        self.jd_input.setPlaceholderText("Enter JD here...")
        self.jd_input.setMinimumHeight(350)
        prep_layout.addWidget(self.jd_input)

        btn_container = QHBoxLayout()
        self.btn_start = QPushButton("Start Real-time Copilot")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self.on_start_clicked)
        btn_container.addStretch()
        btn_container.addWidget(self.btn_start)
        btn_container.addStretch()
        prep_layout.addLayout(btn_container)

        prep_layout.addStretch()  # Push everything up

        # History Detail Page
        self.detail_page = QWidget()
        detail_layout = QVBoxLayout(self.detail_page)
        detail_layout.setContentsMargins(60, 40, 60, 40)

        self.detail_title = QLabel("Report")
        self.detail_title.setObjectName("huge_title")
        detail_layout.addWidget(self.detail_title)

        detail_layout.addWidget(QLabel("Job Description"))
        self.detail_jd = QTextEdit()
        self.detail_jd.setReadOnly(True)
        self.detail_jd.setMaximumHeight(200)
        detail_layout.addWidget(self.detail_jd)

        detail_layout.addSpacing(20)
        detail_layout.addWidget(QLabel("AI Analysis & Feedback"))
        self.detail_analysis = QTextEdit()
        self.detail_analysis.setReadOnly(True)
        detail_layout.addWidget(self.detail_analysis)

        self.main_stack.addWidget(self.prep_page)
        self.main_stack.addWidget(self.detail_page)

        layout.addWidget(self.main_stack)

    def refresh_history(self):
        self.history_list.clear()
        if not os.path.exists(self.records_dir):
            return

        files = [f for f in os.listdir(self.records_dir) if f.endswith(".json")]
        files.sort(reverse=True)

        for f in files:
            parts = f.replace("session_", "").replace(".json", "").split("_")
            if len(parts) >= 2:
                date_str = f"{parts[0][0:4]}/{parts[0][4:6]}/{parts[0][6:8]} {parts[1][0:2]}:{parts[1][2:4]}"
                item = QListWidgetItem(f"💬 Session {date_str}")
                item.setData(Qt.ItemDataRole.UserRole, f)
                self.history_list.addItem(item)

    def show_new_interview(self):
        self.jd_input.clear()
        self.main_stack.setCurrentIndex(0)
        self.history_list.clearSelection()

    def on_history_selected(self, item):
        filename = item.data(Qt.ItemDataRole.UserRole)
        path = os.path.join(self.records_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.detail_jd.setPlainText(data.get("jd", "N/A"))
                self.detail_analysis.setPlainText(
                    data.get("analysis", "No feedback available.")
                )
                self.main_stack.setCurrentIndex(1)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", str(e))

    def open_settings(self):
        dialog = UserSettingsDialog(self)
        dialog.exec()

    def on_start_clicked(self):
        jd = self.jd_input.toPlainText().strip()
        resume = UserSettingsDialog.get_default_resume()
        extra_info = UserSettingsDialog.get_extra_info()

        if not jd:
            QMessageBox.warning(self, "提示", "请输入岗位 JD 后再开始面试。")
            return

        try:
            response = requests.post(
                "http://localhost:8000/set_context",
                json={"jd": jd, "resume": resume, "extra_info": extra_info},
            )
            if response.status_code == 200:
                self.start_interview_signal.emit(jd, resume)
                self.hide()
            else:
                QMessageBox.critical(self, "Server Error", response.text)
        except Exception as e:
            QMessageBox.critical(self, "Network Error", str(e))

    def interview_ended(self):
        self.show()
        self.refresh_history()
        if self.history_list.count() > 0:
            self.history_list.setCurrentRow(0)
            self.on_history_selected(self.history_list.item(0))
