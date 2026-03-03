# Interview Copilot

实时面试辅助工具：捕获面试音频 → ASR 转文字 → LLM 生成回答 → 悬浮窗展示。

## 快速开始

### 1. 配置环境变量

在 `server/` 目录创建 `.env` 文件：

```bash
# 二选一（或两个都配置）
OPENAI_API_KEY=sk-your-openai-key
DEEPGRAM_API_KEY=your-deepgram-key
```

- **OPENAI_API_KEY**: 必需，用于 LLM 生成回答，也可作为 ASR 备选
- **DEEPGRAM_API_KEY**: 可选，用于更快的 ASR

### 2. 启动后端服务

```bash
cd server
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

验证：访问 http://localhost:8000/health 应返回 `{"status": "ok"}`

### 3. 加载 Chrome 插件

1. 打开 Chrome → `chrome://extensions/`
2. 开启「开发者模式」
3. 点击「加载已解压的扩展程序」
4. 选择 `extension/` 文件夹

### 4. 使用

1. 点击插件图标
2. 输入 JD 和简历 → 点击「保存」
3. 打开会议页面（如 Google Meet / Zoom Web）
4. 点击「开始捕获」
5. 面试官说话后，答案将在悬浮窗中显示

### 快捷键

- `Alt + Q` : 显示/隐藏悬浮窗

## 项目结构

```
interview-copilot/
├── server/
│   ├── main.py         # FastAPI 主应用
│   ├── asr.py          # 语音识别模块
│   ├── llm.py          # LLM 回答生成
│   ├── prompt.py       # 提示词模板
│   └── requirements.txt
│
├── extension/
│   ├── manifest.json   # 插件配置
│   ├── background.js   # 音频捕获 + WebSocket
│   ├── content.js      # 悬浮窗
│   ├── popup.html/js   # 设置界面
│   └── styles.css
│
└── README.md
```

## 性能指标

| 项目 | 目标 |
|------|------|
| ASR 延迟 | < 2s |
| 答案生成 | < 3s |
| 总延迟 | < 5s |

## 注意事项

- 仅支持本地单用户使用
- 需要 Chrome 浏览器
- 需要麦克风权限（如有问题检查浏览器权限设置）
