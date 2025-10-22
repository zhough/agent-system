from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio
import io
import base64
from aiohttp import ClientSession  # 用于异步调用5000端口接口

# 初始化FastAPI
app = FastAPI(title="皮肤病诊断Web应用")
templates = Jinja2Templates(directory="templates")

# 5000端口agent的地址（服务器本地通信，无需代理）
AGENT_URL = "http://127.0.0.1:5000/generate"


# 1. 首页路由（显示Web界面）
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# 2. 流式响应接口（转发请求到5000端口，并返回实时结果）
@app.post("/stream")
async def stream(
    question: str = Form(""),
    image: UploadFile = File(None),
    user_id: str = Form("default_user")  # 可从前端传递用户ID，这里默认值
):
    # 步骤1：处理图像（转换为base64，适配5000端口的参数要求）
    image_base64 = None
    if image:
        # 读取图像文件并转换为base64字符串
        img_bytes = await image.read()
        image_base64 = base64.b64encode(img_bytes).decode("utf-8")

    # 步骤2：构造发送给5000端口的请求参数
    payload = {
        "user_query": question,
        "ID": user_id,
        "image_base64": image_base64  # 5000端口需要的图像参数
    }

    # 步骤3：异步调用5000端口的接口，并流式返回结果
    async def forward_stream():
        try:
            # 建立异步会话，发送POST请求到5000端口
            async with ClientSession() as session:
                async with session.post(
                    AGENT_URL,
                    json=payload,  # 发送JSON格式数据
                    timeout=None  # 流式响应不设超时
                ) as response:
                    if not response.ok:
                        yield f"错误：5000端口服务返回异常（状态码：{response.status}）"
                        return

                    # 逐块读取5000端口的流式响应，并转发给前端
                    async for chunk in response.content.iter_any():
                        if chunk:
                            yield chunk.decode("utf-8")  # 转换为字符串后返回

        except Exception as e:
            # 捕获连接错误（如5000端口未启动）
            yield f"错误：无法连接到5000端口服务 - {str(e)}"

    # 返回流式响应给前端
    return StreamingResponse(forward_stream(), media_type="text/plain")


# 启动服务（绑定本地回环，8501端口）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="info")