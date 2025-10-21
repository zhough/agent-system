import torch
import io
import logging
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from modelscope import Qwen3VLForConditionalGeneration, AutoProcessor
from threading import Thread
import uvicorn

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化FastAPI应用
app = FastAPI(title="Qwen-VL API服务")

# --------------------------
# 模型加载（Qwen-VL 4bit量化版）
# --------------------------
model_name = "unsloth/Qwen3-VL-4B-Instruct-bnb-4bit"
try:
    logger.info("开始加载Qwen-VL模型...")
    # 加载处理器（处理图像和文本输入）
    processor = AutoProcessor.from_pretrained(
        model_name,
        image_size=(512, 512)  # 降低图像分辨率，减少显存占用
    )
    # 加载模型（4bit量化，GPU部署）
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_name,
        dtype=torch.float16,
        device_map="cuda"
    )
    # 确保tokenizer有pad标记
    if processor.tokenizer.pad_token is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
    logger.info("Qwen-VL模型加载完成")
except Exception as e:
    logger.error(f"模型加载失败: {str(e)}", exc_info=True)
    raise

# --------------------------
# 图像处理（适配Qwen-VL输入格式）
# --------------------------
def process_images(image_files):
    """处理上传的图像文件，转换为Qwen-VL可接受的格式"""
    images = []
    for file in image_files:
        if file is None:
            continue
        try:
            # 读取图像字节并转换为PIL Image
            image_bytes = file.file.read()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            images.append(image)
            logger.info(f"处理图像成功: {file.filename}")
        except Exception as e:
            logger.error(f"图像处理失败 {file.filename}: {str(e)}")
            raise
    return images

# --------------------------
# 生成响应（流式输出）
# --------------------------
def generate_stream(question, images):
    """生成流式响应的核心函数"""
    try:
        # 构建Qwen-VL要求的输入格式（messages列表）
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": question}]
            }
        ]
        # 添加图像到输入（按顺序插入）
        for i, img in enumerate(images):
            messages[0]["content"].insert(i, {"type": "image", "image": img})

        # 转换为模型输入张量
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        ).to(model.device)

        # 流式生成（循环生成单个token）
        generated_tokens = []
        max_new_tokens = 512
        eos_token_id = processor.tokenizer.eos_token_id

        for _ in range(max_new_tokens):
            # 每次生成1个token
            outputs = model.generate(
                **inputs,
                max_new_tokens=1,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                pad_token_id=processor.tokenizer.pad_token_id,
                eos_token_id=eos_token_id
            )

            # 提取新生成的token
            new_token = outputs[0, -1].item()
            if new_token == eos_token_id:
                break  # 遇到结束符停止
            generated_tokens.append(new_token)

            # 解码当前片段并返回
            current_text = processor.batch_decode(
                [generated_tokens],
                skip_special_tokens=True
            )[0]
            yield current_text

            # 更新输入（包含历史token）
            inputs = {
                "input_ids": outputs,
                "attention_mask": torch.ones_like(outputs)
            }

    except Exception as e:
        error_msg = f"推理失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        yield f"\n⚠️  {error_msg}"

# --------------------------
# API接口定义（与原InternVL格式兼容）
# --------------------------
@app.post("/chat")
async def chat(
    question: str = Form(...),  # 必传：文本问题
    session_id: str = Form("default"),  # 保留参数，兼容原格式（无实际作用）
    image: UploadFile = File(None),  # 可选：第一张图像
    image1: UploadFile = File(None)  # 可选：第二张图像
):
    """Qwen-VL多模态推理接口（单轮，无历史）"""
    logger.info(f"收到请求 - session_id: {session_id}, 问题: {question[:50]}...")

    # 1. 处理图像（收集非空图像）
    images = process_images([image, image1])
    logger.info(f"共处理 {len(images)} 张图像")

    # 2. 定义流式响应生成器
    def response_generator():
        yield from generate_stream(question, images)

    # 3. 返回流式响应
    return StreamingResponse(response_generator(), media_type="text/plain")

# --------------------------
# 启动服务
# --------------------------
if __name__ == "__main__":
    # 单进程启动（模型不支持多进程共享）
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1, log_level="info")