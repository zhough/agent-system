from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
import base64
import logging
from aiohttp import ClientSession, WSMsgType
from config import Config
import asyncio
config = Config()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WebSocket 皮肤病诊断应用")
templates = Jinja2Templates(directory="templates")

# 配置目标服务地址（main.py 的 WebSocket 接口，通过 proxy 转发）
# 格式：ws://proxy地址/api/ws（与 proxy.py 中 /api 路径的 WebSocket 转发对应）
TARGET_WS_URL = config.proxy_ws_url  # 需在 config.py 中配置 proxy_ws_url（如 ws://127.0.0.1:8000）


# 1. 前端页面路由
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("websocket.html", {"request": request})


# 2. WebSocket 核心接口（连接前端与 main.py 的 WebSocket）
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 接受前端连接
    await websocket.accept()
    logger.info("前端 WebSocket 连接已建立")

    # 与 main.py 的 WebSocket 建立连接（通过 proxy 转发）
    main_ws = None
    try:
        async with ClientSession() as session:
            # 连接到 proxy 转发的 main.py WebSocket 接口
            async with session.ws_connect(TARGET_WS_URL) as main_ws:
                logger.info(f"已连接到目标服务: {TARGET_WS_URL}")

                # 双向转发消息的任务
                async def forward_to_main():
                    """将前端消息转发给 main.py"""
                    while True:
                        # 接收前端消息（JSON 格式：包含 user_id、question、image_base64）
                        data = await websocket.receive_text()
                        logger.info(f"收到前端消息: {data[:100]}...")  # 打印前100字符
                        # 转发给 main.py
                        await main_ws.send_str(data)

                async def forward_to_frontend():
                    """将 main.py 的响应转发给前端"""
                    while True:
                        # 接收 main.py 的流式响应
                        msg = await main_ws.receive()
                        if msg.type == WSMsgType.TEXT:
                            # 转发响应转发给前端
                            await websocket.send_text(msg.data)
                        elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                            # 目标服务关闭，通知前端
                            await websocket.close(code=1001, reason="服务端断开连接")
                            break

                # 并发发执行双向转发
                await asyncio.gather(forward_to_main(), forward_to_frontend())

    except WebSocketDisconnect:
        logger.info("前端主动断开连接")
    except Exception as e:
        logger.error(f"WebSocket 错误: {str(e)}")
        if not websocket.closed:
            await websocket.close(code=1011, reason=f"服务错误: {str(e)}")
    finally:
        if main_ws and not main_ws.closed:
            await main_ws.close()
        logger.info("WebSocket 连接已关闭")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=config.web_port, log_level="info")