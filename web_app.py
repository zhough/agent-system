from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncio
import io
from PIL import Image  # 用于处理图像（可选）

# 初始化FastAPI
app = FastAPI(title="替代Streamlit的Web应用")
templates = Jinja2Templates(directory="templates")  # 指向存放index.html的文件夹


# 1. 首页路由（显示Web界面）
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# 2. 流式响应接口（处理文本和图像）
@app.post("/stream")
async def stream(
    question: str = Form(""),
    image: UploadFile = File(None)
):
    # 模拟处理图像（实际场景可调用你的模型）
    image_info = ""
    if image:
        # 读取图像（示例：获取尺寸）
        img = Image.open(io.BytesIO(await image.read()))
        image_info = f"（已接收图像，尺寸：{img.size[0]}x{img.size[1]}）"

    # 模拟流式响应生成（实际场景替换为你的模型调用）
    async def generate_response():
        # 第一部分：确认接收
        yield f"已收到您的请求：{question or '无文本'}{image_info}\n\n正在分析..."
        await asyncio.sleep(1)

        # 第二部分：流式返回结果（模拟模型推理过程）
        analysis = [
            "根据您提供的信息，初步判断可能是...\n",
            "1. 症状特征：...\n",
            "2. 建议措施：...\n",
            "3. 注意事项：..."
        ]
        for part in analysis:
            for char in part:
                yield char
                await asyncio.sleep(0.05)  # 控制流式速度
        await asyncio.sleep(0.5)
        yield "\n\n如果症状持续，请及时就医。"

    return StreamingResponse(generate_response(), media_type="text/plain")


# 启动服务（绑定本地回环，8501端口）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8501, log_level="info")