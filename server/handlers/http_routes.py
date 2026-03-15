"""HTTP 路由：/set_context、/parse_resume、/health。"""

import io

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from server.handlers.ws_handler import get_default_session

router = APIRouter()


class ContextInput(BaseModel):
    jd: str
    resume: str = ""
    extra_info: str = ""


@router.post("/set_context")
async def set_context(context: ContextInput):
    """设置职位描述和简历上下文。"""
    session = get_default_session()

    parts = []
    if context.resume:
        parts.append(f"【个人简历】\n{context.resume}")
    if context.extra_info:
        parts.append(f"【其他补充信息】\n{context.extra_info}")

    combined_resume = "\n\n".join(parts)
    session.set_context(jd=context.jd, resume=combined_resume)

    return {"status": "ok", "message": "Context saved in session"}


@router.post("/parse_resume")
async def parse_resume(file: UploadFile = File(...)):
    """解析简历文件（PDF / Docx / 图片）。"""
    filename = file.filename.lower()
    content = await file.read()
    text = ""

    try:
        if filename.endswith(".pdf"):
            try:
                import fitz
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="Missing dependency: PyMuPDF.",
                )
            doc = fitz.open(stream=content, filetype="pdf")
            for page in doc:
                text += page.get_text()

        elif filename.endswith((".docx", ".doc")):
            try:
                from docx import Document
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="Missing dependency: python-docx.",
                )
            doc = Document(io.BytesIO(content))
            text = "\n".join([para.text for para in doc.paragraphs])

        elif filename.endswith((".png", ".jpg", ".jpeg")):
            text = "[图片简历解析需调用 Vision 模型，暂未实现具体 OCR 逻辑]"
        else:
            raise HTTPException(
                status_code=400, detail="Unsupported file format"
            )

        return {"status": "ok", "text": text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Parsing error: {str(e)}"
        )


@router.get("/health")
async def health():
    """健康检查端点。"""
    return {"status": "ok"}
