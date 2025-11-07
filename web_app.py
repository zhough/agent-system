from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio
import io
import base64
import logging
from aiohttp import ClientSession
from config import Config

config = Config()
# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化FastAPI
app = FastAPI(title="皮肤病诊断Web应用")
templates = Jinja2Templates(directory="templates")

# 5000端口agent的地址
#AGENT_URL = "http://127.0.0.1:5000/generate"
AGENT_URL = config.main_url

# 1. 首页路由（显示Web界面）
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# 2. 流式响应接口（核心逻辑）
@app.post("/stream")
async def stream(
    user_id: str = Form(..., description="用户ID（必填）"),  # 强制用户输入ID
    question: str = Form("", description="用户问题"),
    image: UploadFile = File(None)
):
    # 处理<image>前缀：有图像时自动添加
    user_query = question.strip()
    if image:
        # 即使没有输入问题，也确保基础文本存在（避免空字符串）
        user_query = f"<image>{user_query}" if user_query else "<image>请分析上传的图片"

    # 验证user_query非空（无图像时必须有文字）
    if not user_query:
        raise HTTPException(status_code=400, detail="请输入问题或上传图片")

    # 处理图像：转换为base64（仅当有图像时）
    image_base64 = None
    if image:
        try:
            img_bytes = await image.read()
            image_base64 = base64.b64encode(img_bytes).decode("utf-8")
            logger.info(f"用户{user_id}上传图像，base64长度：{len(image_base64)}")
        except Exception as e:
            logger.error(f"图像处理失败：{str(e)}")
            raise HTTPException(status_code=400, detail="图像处理失败，请重新上传")


    payload = {
        "user_query": user_query,
        "ID": user_id
    }
    if image_base64 is not None:
        payload["image_base64"] = image_base64

    logger.info(f"发送给5000端口的参数：{payload}")

    # 转发5000端口的流式响应
    async def forward_stream():
        try:
            async with ClientSession() as session:
                async with session.post(
                    AGENT_URL,
                    json=payload,
                    timeout=None
                ) as response:
                    if not response.ok:
                        error_detail = await response.text()
                        logger.error(f"5000端口错误：{response.status}，详情：{error_detail}")
                        yield f"服务错误（{response.status}）：{error_detail}"
                        return

                    # 逐块转发SSE流
                    async for chunk in response.content.iter_any():
                        if chunk:
                            yield chunk.decode("utf-8")

        except Exception as e:
            logger.error(f"连接5000端口失败：{str(e)}")
            yield f"连接服务失败：{str(e)}"

    return StreamingResponse(forward_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=config.web_port, log_level="info")