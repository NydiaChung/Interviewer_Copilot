"""FastAPI 应用入口：创建 App + 注册路由。"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.handlers.http_routes import router as http_router
from server.handlers.ws_handler import audio_websocket

# 加载 .env
_env_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".env"
)
load_dotenv(dotenv_path=_env_path)

app = FastAPI(title="Interview Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(http_router)
app.websocket("/ws/audio")(audio_websocket)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
