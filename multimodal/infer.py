import torch
import asyncio
import base64
import io
import os
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import StreamingResponse
from modelscope import Qwen3VLForConditionalGeneration, AutoProcessor
from typing import AsyncGenerator, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化FastAPI应用
app = FastAPI(title="Qwen3-VL 多模态推理服务")

# 全局加载模型和处理器（仅启动时加载一次）
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
model_name = "unsloth/Qwen3-VL-4B-Instruct-bnb-4bit"

# 加载模型和处理器
try:
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_name,
        dtype=torch.float16,
        device_map="cuda"
    )
    torch.cuda.empty_cache()
    processor = AutoProcessor.from_pretrained(
        model_name,
        image_size=(512, 512)  # 控制图像分辨率，减少显存
    )
    logger.info("模型和处理器加载成功")
except Exception as e:
    logger.error(f"模型加载失败: {str(e)}")
    raise


async def process_request(
    question: str,
    ID: str = "0042",
    image: Optional[str] = None,  # base64编码的图像
    image1: Optional[str] = None  # 本地图像路径（或上传的文件内容）
) -> AsyncGenerator[str, None]:
    """模型推理逻辑（复用之前的处理函数）"""
    try:
        # 构建多模态输入
        messages = [
            {"role": "user", "content": [{"type": "text", "text": question.strip()}]}
        ]

        # 处理base64图像
        if image:
            try:
                base64.b64decode(image)  # 验证base64格式
                messages[0]["content"].insert(0, {
                    "type": "image",
                    "image": f"data:image/jpeg;base64,{image}"
                })
                logger.info("已添加base64图像")
            except Exception as e:
                yield f'{{"type":"error","message":"base64图像解析失败: {str(e)}"}}'
                return

        # 处理本地图像路径或上传的图像
        if image1:
            try:
                messages[0]["content"].insert(0, {
                    "type": "image",
                    "image": image1  # 若为上传文件，这里是临时路径
                })
                logger.info(f"已添加图像: {image1}")
            except Exception as e:
                yield f'{{"type":"error","message":"图像处理失败: {str(e)}"}}'
                return

        # 同步推理函数（流式生成）
        def sync_inference():
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt"
            ).to(model.device)

            generated_tokens = []
            for token in model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                stream=True
            ):
                if token[0, -1] != processor.tokenizer.pad_token_id:
                    generated_tokens.append(token[0, -1].item())
                    current_text = processor.batch_decode(
                        [generated_tokens],
                        skip_special_tokens=True
                    )[0]
                    yield current_text

        # 异步包装同步生成器
        loop = asyncio.get_event_loop()
        for chunk in await loop.run_in_executor(None, list, sync_inference()):
            yield chunk
            await asyncio.sleep(0.01)

    except Exception as e:
        error_msg = f"推理失败: {str(e)}"
        logger.error(error_msg)
        yield f'{{"type":"error","message":"{error_msg}"}}'


@app.post("/chat")  # 定义HTTP接口路径
async def chat(
    question: str = Form(...),  # 文本问题（必传）
    ID: str = Form("0042"),    # 会话ID（可选，默认0042）
    image: Optional[str] = Form(None),  # base64图像（可选）
    image1: Optional[UploadFile] = File(None)  # 上传的图像文件（可选）
):
    """HTTP接口：接收问题和图像，返回流式响应"""
    # 处理上传的图像文件（保存为临时文件）
    image1_path = None
    if image1:
        # 保存上传的图像到临时路径
        temp_dir = "./temp_images"
        os.makedirs(temp_dir, exist_ok=True)
        image1_path = f"{temp_dir}/{image1.filename}"
        with open(image1_path, "wb") as f:
            f.write(await image1.read())
        logger.info(f"上传的图像已保存到: {image1_path}")

    # 返回流式响应（将process_request的生成器包装为HTTP流）
    return StreamingResponse(
        process_request(question=question, ID=ID, image=image, image1=image1_path),
        media_type="text/event-stream"  # 流式响应的MIME类型
    )


if __name__ == "__main__":
    # 启动服务：默认地址 http://localhost:8000，允许外部访问（host="0.0.0.0"）
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)  # 单进程（模型不支持多进程共享）