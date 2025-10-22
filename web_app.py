from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio
import io
import base64
import logging
from aiohttp import ClientSession

# 配置日志（方便调试）
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化FastAPI
app = FastAPI(title="皮肤病诊断Web应用")
templates = Jinja2Templates(directory="templates")

# 5000端口agent的地址（服务器本地通信）
AGENT_URL = "http://127.0.0.1:5000/generate"


# 1. 首页路由
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# 2. 流式响应接口（适配5000端口的参数要求）
@app.post("/stream")
async def stream(
    question: str = Form(..., description="用户问题（不能为空）"),  # 强制必填
    image: UploadFile = File(None),
    user_id: str = Form("0001", description="用户ID（字符串类型）")  # 确保是字符串
):
    # 关键：确保user_query非空（即使只上传图片，也补充默认问题）
    user_query = question.strip()
    if not user_query:
        if image:
            user_query = "请分析我上传的图片"  # 只上传图片时的默认问题
        else:
            raise HTTPException(status_code=400, detail="请输入问题或上传图片")

    # 处理图像：转换为base64字符串（若有）
    image_base64 = None
    if image:
        try:
            img_bytes = await image.read()
            image_base64 = base64.b64encode(img_bytes).decode("utf-8")  # 确保是字符串
            logger.info(f"图像转换成功，base64长度：{len(image_base64)}")
        except Exception as e:
            logger.error(f"图像转换失败：{str(e)}")
            raise HTTPException(status_code=400, detail="图像处理失败，请重新上传")

    # 构造符合5000端口要求的JSON payload
    payload = {
        "user_query": user_query,  # 确保非空字符串
        "ID": user_id,  # 确保是字符串（默认'0001'）
        "image_base64": image_base64  # 要么是base64字符串，要么是None
    }
    logger.info(f"发送给5000端口的参数：{payload}")  # 打印日志，确认参数正确性

    # 转发5000端口的流式响应
    async def forward_stream():
        try:
            async with ClientSession() as session:
                async with session.post(
                    AGENT_URL,
                    json=payload,  # 发送JSON格式（自动设置Content-Type: application/json）
                    timeout=None
                ) as response:
                    if not response.ok:
                        error_detail = await response.text()
                        logger.error(f"5000端口返回错误：{response.status}，详情：{error_detail}")
                        yield f"服务错误（{response.status}）：{error_detail}"
                        return

                    # 逐块转发SSE流（5000端口返回text/event-stream）
                    async for chunk in response.content.iter_any():
                        if chunk:
                            yield chunk.decode("utf-8")  # 保持原始SSE格式

        except Exception as e:
            logger.error(f"连接5000端口失败：{str(e)}")
            yield f"连接服务失败：{str(e)}"

    # 返回SSE流（与5000端口一致的媒体类型）
    return StreamingResponse(forward_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="info")