import torch
import io
import logging
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from transformers import TextIteratorStreamer
from modelscope import Qwen3VLForConditionalGeneration,AutoProcessor
from threading import Thread
import uvicorn
import sys
import os

current_file_path = os.path.abspath(__file__)
multimodal_dir = os.path.dirname(current_file_path)
home_dir = os.path.dirname(multimodal_dir)
sys.path.append(home_dir)
from config import Config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化FastAPI应用
app = FastAPI(title="Qwen-VL API服务")
config = Config()
# --------------------------
# 模型加载
# --------------------------
model_name = "Qwen/Qwen3-VL-2B-Instruct"
try:
    logger.info("开始加载Qwen-VL模型...")
    processor = AutoProcessor.from_pretrained(
        model_name,
        image_size=(512, 512)
    )
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_name,
        dtype=torch.float16,
        device_map="cuda:1"
    )
    if processor.tokenizer.pad_token is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
    logger.info("Qwen-VL模型加载完成")
except Exception as e:
    logger.error(f"模型加载失败: {str(e)}", exc_info=True)
    raise

# --------------------------
# 图像处理
# --------------------------
def process_images(image_files):
    images = []
    for file in image_files:
        if file is None:
            continue
        try:
            image_bytes = file.file.read()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            images.append(image)
            logger.info(f"处理图像成功: {file.filename}")
        except Exception as e:
            logger.error(f"图像处理失败 {file.filename}: {str(e)}")
            raise
    return images

# --------------------------
# 流式生成核心逻辑
# --------------------------
def generate_stream(question, images):
    try:
        # 1. 构建Qwen-VL输入（messages格式）
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": question}]
            }
        ]
        for i, img in enumerate(images):
            messages[0]["content"].insert(i, {"type": "image", "image": img})

        # 2. 转换为模型输入张量
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        ).to(model.device)

        # 3. 初始化TextIteratorStreamer
        streamer = TextIteratorStreamer(
            processor.tokenizer,
            skip_prompt=True,  # 跳过提示词部分
            skip_special_tokens=True,
            timeout=30  # 超时时间
        )

        # 4. 生成配置
        generation_config = {
            "max_new_tokens": 1024,
            "do_sample": False,
            "pad_token_id": processor.tokenizer.pad_token_id,
            "eos_token_id": processor.tokenizer.eos_token_id,
            "streamer": streamer
        }

        # 5. 多线程生成
        def generate_task():
            model.generate(** inputs, **generation_config)

        thread = Thread(target=generate_task)
        thread.start()

        # 6. 从streamer获取增量文本
        for new_text in streamer:
            yield new_text  # 直接返回增量，无累积重复

        thread.join()

    except Exception as e:
        error_msg = f"推理失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        yield f"\n⚠️  {error_msg}"

# --------------------------
# API接口
# --------------------------
@app.post("/chat")
async def chat(
    question: str = Form(...),
    session_id: str = Form("default"),
    image: UploadFile = File(None),
    image1: UploadFile = File(None)
):
    logger.info(f"收到请求 - session_id: {session_id}, 问题: {question[:50]}...")
    images = process_images([image, image1])
    logger.info(f"共处理 {len(images)} 张图像")

    # 直接返回streamer的增量文本生成器
    return StreamingResponse(generate_stream(question, images), media_type="text/plain")

# --------------------------
# 启动服务
# --------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.multimodal_port, workers=1, log_level="info")