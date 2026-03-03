import json
import os
import requests
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt


class UserSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("用户设置")
        self.setMinimumSize(680, 680)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #343541;
            }
            QFrame#card {
                background-color: #40414F;
                border: 1px solid #565869;
                border-radius: 10px;
                padding: 4px;
            }
            QLabel.section_label {
                color: #8E8EA0;
                font-size: 12px;
                font-weight: bold;
                padding: 12px 16px 4px 16px;
            }
            QTextEdit {
                background-color: transparent;
                border: none;
                color: #ECECF1;
                font-size: 14px;
                padding: 8px 16px;
            }
            QTextEdit:focus {
                outline: none;
            }
            QPushButton {
                background-color: #40414F;
                border: 1px solid #565869;
                border-radius: 6px;
                padding: 8px 14px;
                color: #ECECF1;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2A2B32;
            }
            QPushButton#btn_save {
                background-color: #10A37F;
                border: none;
                font-weight: bold;
            }
            QPushButton#btn_save:hover {
                background-color: #0E8A6C;
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("用户设置")
        title.setStyleSheet("color: #ECECF1; font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # --- Card 1: Resume ---
        card1 = QFrame()
        card1.setObjectName("card")
        card1_layout = QVBoxLayout(card1)
        card1_layout.setContentsMargins(0, 0, 0, 0)
        card1_layout.setSpacing(0)

        header1 = QHBoxLayout()
        label1 = QLabel("用户简历信息")
        label1.setProperty("class", "section_label")
        label1.setStyleSheet(
            "color: #8E8EA0; font-size: 12px; font-weight: bold; padding: 12px 16px 4px 16px;"
        )
        self.btn_upload = QPushButton("📎 上传文件")
        self.btn_upload.setFixedHeight(32)
        self.btn_upload.clicked.connect(self.upload_file)
        header1.addWidget(label1)
        header1.addStretch()
        header1.addWidget(self.btn_upload)
        header1.setContentsMargins(0, 0, 12, 0)
        card1_layout.addLayout(header1)

        self.resume_edit = QTextEdit()
        self.resume_edit.setPlaceholderText(
            "在此输入或粘贴您的简历内容。也可从上方上传 PDF/Word/图片文件自动解析。"
        )
        self.resume_edit.setMinimumHeight(180)
        card1_layout.addWidget(self.resume_edit)

        layout.addWidget(card1)

        # --- Card 2: Supplemental Info ---
        card2 = QFrame()
        card2.setObjectName("card")
        card2_layout = QVBoxLayout(card2)
        card2_layout.setContentsMargins(0, 0, 0, 0)
        card2_layout.setSpacing(0)

        label2 = QLabel("用户其他补充信息")
        label2.setStyleSheet(
            "color: #8E8EA0; font-size: 12px; font-weight: bold; padding: 12px 16px 4px 16px;"
        )
        card2_layout.addWidget(label2)

        self.extra_edit = QTextEdit()
        self.extra_edit.setPlaceholderText(
            "例如：期待薪资范围、目标公司、个人优势与劣势、面试偏好、个人兴趣等任何希望 AI 在回答时考虑到的背景信息。"
        )
        self.extra_edit.setMinimumHeight(220)
        card2_layout.addWidget(self.extra_edit)

        layout.addWidget(card2)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("保存设置")
        self.save_btn.setObjectName("btn_save")
        self.save_btn.clicked.connect(self.save_settings)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

    def upload_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择简历文件", "", "简历文件 (*.pdf *.docx *.doc *.jpg *.jpeg *.png)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    "http://localhost:8000/parse_resume",
                    files={"file": (os.path.basename(file_path), f)},
                )
            if resp.status_code == 200:
                self.resume_edit.setPlainText(resp.json().get("text", ""))
                QMessageBox.information(
                    self, "解析成功", "简历内容已自动提取到下方输入框，请确认后保存。"
                )
            else:
                QMessageBox.critical(self, "解析失败", resp.text)
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"无法连接到后端：{e}")

    def load_settings(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.resume_edit.setPlainText(data.get("resume", ""))
                    self.extra_edit.setPlainText(data.get("extra_info", ""))
            except Exception:
                pass

    def save_settings(self):
        data = {
            "resume": self.resume_edit.toPlainText().strip(),
            "extra_info": self.extra_edit.toPlainText().strip(),
        }
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    # --- Static helpers used by control_panel.py ---
    @staticmethod
    def _load() -> dict:
        path = os.path.join(os.path.dirname(__file__), "settings.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @staticmethod
    def get_default_resume() -> str:
        return UserSettingsDialog._load().get("resume", "")

    @staticmethod
    def get_extra_info() -> str:
        return UserSettingsDialog._load().get("extra_info", "")
