"""纯文本工具函数 — 不含业务逻辑。"""

from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    """小写 + 合并空白。"""
    return " ".join((text or "").strip().lower().split())


def text_similarity(a: str, b: str) -> float:
    """基于 SequenceMatcher 的文本相似度（0‒1）。"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def chunk_answer_text(text: str) -> list[str]:
    """将回答文本按标点切分为适合流式推送的片段。"""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    buf = ""
    split_chars = set("，。！？；,.!?\n")
    for ch in text:
        buf += ch
        if (ch in split_chars and len(buf) >= 6) or len(buf) >= 20:
            chunks.append(buf)
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks
