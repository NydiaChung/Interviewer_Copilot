# Prompt 配置指南

本项目使用 3 个 Prompt 模板，均定义在 `server/prompt.py` 中。你可以直接编辑该文件来调整 AI 的回答风格和行为。

---

## 模板一览

| 模板名称 | 触发时机 | 作用 |
|---------|---------|------|
| `INTERVIEW_PROMPT` | 面试官问题被确认后 | 生成**正式回答**（20秒内可说完的口语化答案） |
| `OUTLINE_PROMPT` | 问题尚在进行中（早期） | 生成**要点草稿**（3-5 条短句提纲，帮你先开口） |
| `ANALYSIS_PROMPT` | 用户点击「结束面试」后 | 生成**复盘报告**（评价+改进建议） |

---

## 可用变量

每个模板使用 Python `str.format()` 语法，支持以下占位变量：

| 变量 | 说明 | 来源 |
|------|------|------|
| `{jd}` | 岗位 JD 文本 | 用户在控制面板填写 |
| `{resume}` | 简历 + 补充信息 | 用户上传/填写 |
| `{question}` | 当前面试官的问题 | ASR 实时识别 |
| `{history}` | 完整面试对话记录 | 仅 `ANALYSIS_PROMPT` 使用 |

---

## 修改方法

1. 打开 `server/prompt.py`
2. 找到对应模板（如 `INTERVIEW_PROMPT`）
3. 修改三引号内的文本
4. 保持 `{jd}` `{resume}` `{question}` 占位符不要删除
5. 重启后端服务即可生效

### 示例：修改回答风格为更正式

```python
INTERVIEW_PROMPT = \"\"\"你是求职者的面试辅助AI。

【岗位JD】
{jd}

【求职者简历】
{resume}

面试官问题：
{question}

要求：
- 用第一人称回答
- 使用专业、正式的语气
- 30秒内可说完
- 必须结合简历真实经历
- 用 STAR 法则组织回答
- 不要解释，只输出答案

直接输出回答：\"\"\"
```

---

## LLM 提供商配置

在 `.env` 中配置：

```bash
# 提供商选择：auto / openai / dashscope / gemini
LLM_PROVIDER=auto

# auto 模式下的优先级顺序
LLM_AUTO_ORDER=dashscope,openai,gemini

# 各提供商 API Key
DASHSCOPE_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
GEMINI_API_KEY=xxx
```

`auto` 模式会按 `LLM_AUTO_ORDER` 顺序尝试，第一个成功的结果即返回。
