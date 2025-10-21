import torch
import asyncio
import base64
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
        device_map="cuda"  # 强制使用GPU
    )
    torch.cuda.empty_cache()  # 清理初始显存
    processor = AutoProcessor.from_pretrained(
        model_name,
        image_size=(512, 512)  # 降低图像分辨率，减少显存占用
    )
    # 确保tokenizer有pad和eos标记（避免生成时出错）
    if processor.tokenizer.pad_token is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
    logger.info("模型和处理器加载成功")
except Exception as e:
    logger.error(f"模型加载失败: {str(e)}")
    raise


async def process_request(
    question: str,
    ID: str = "0042",
    image: Optional[str] = None,  # base64编码的图像
    image1: Optional[str] = None  # 本地图像路径（或上传的临时路径）
) -> AsyncGenerator[str, None]:
    """处理请求并返回异步流式响应"""
    try:
        # --------------------------
        # 1. 构建多模态输入（文本+图像）
        # --------------------------
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": question.strip()}]  # 文本问题
            }
        ]

        # 添加base64图像（若有）
        if image:
            try:
                # 验证base64格式
                base64.b64decode(image)
                messages[0]["content"].insert(0, {
                    "type": "image",
                    "image": f"data:image/jpeg;base64,{image}"  # 转换为data URI
                })
                logger.info("已添加base64图像")
            except Exception as e:
                error = f"base64图像解析失败: {str(e)}"
                logger.error(error)
                yield f'{{"type":"error","message":"{error}"}}'
                return

        # 添加本地图像（若有）
        if image1 and os.path.exists(image1):
            try:
                messages[0]["content"].insert(0, {
                    "type": "image",
                    "image": image1  # 本地路径
                })
                logger.info(f"已添加本地图像: {image1}")
            except Exception as e:
                error = f"本地图像处理失败: {str(e)}"
                logger.error(error)
                yield f'{{"type":"error","message":"{error}"}}'
                return
        elif image1:
            warning = f"本地图像路径不存在: {image1}"
            logger.warning(warning)
            yield f'{{"type":"warning","message":"{warning}"}}'

        # --------------------------
        # 2. 同步推理函数（循环生成单个token模拟流式）
        # --------------------------
        def sync_inference():
            # 转换输入为模型格式
            inputs = processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt"
            ).to(model.device)

            generated_tokens = []  # 累积生成的token
            max_new_tokens = 512   # 最大生成长度
            eos_token_id = processor.tokenizer.eos_token_id  # 结束符ID

            for _ in range(max_new_tokens):
                # 每次生成1个token（避免stream参数）
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=1,  # 关键：每次只生成1个token
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    pad_token_id=processor.tokenizer.pad_token_id,
                    eos_token_id=eos_token_id
                )

                # 提取新生成的token（最后一个token）
                new_token = outputs[0, -1].item()
                # 若遇到结束符，停止生成
                if new_token == eos_token_id:
                    break
                generated_tokens.append(new_token)

                # 解码当前累积的token，返回片段
                current_text = processor.batch_decode(
                    [generated_tokens],
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False
                )[0]
                yield current_text

                # 更新输入：将已生成的token加入下一轮输入（保证上下文连贯）
                inputs = {
                    "input_ids": outputs,  # 包含历史token的新输入
                    "attention_mask": torch.ones_like(outputs)  # 全为1的注意力掩码
                }

        # --------------------------
        # 3. 异步包装同步推理结果
        # --------------------------
        loop = asyncio.get_event_loop()
        # 运行同步生成器并转换为列表（保持异步迭代）
        for chunk in await loop.run_in_executor(None, list, sync_inference()):
            yield chunk
            await asyncio.sleep(0.01)  # 控制流式输出速度

    except Exception as e:
        error_msg = f"推理失败: {str(e)}"
        logger.error(f"⚠️  {error_msg}")
        yield f'{{"type":"error","message":"{error_msg}"}}'


# --------------------------
# HTTP接口定义
# --------------------------
@app.post("/chat")
async def chat(
    question: str = Form(...),  # 必传：文本问题
    ID: str = Form("0042"),    # 可选：会话ID
    image: Optional[str] = Form(None),  # 可选：base64图像
    image1: Optional[UploadFile] = File(None)  # 可选：上传的图像文件
):
    """接收多模态请求，返回流式响应"""
    # 处理上传的图像文件（保存为临时文件）
    image1_path = None
    if image1:
        temp_dir = "./temp_images"
        os.makedirs(temp_dir, exist_ok=True)
        image1_path = f"{temp_dir}/{image1.filename}"
        with open(image1_path, "wb") as f:
            f.write(await image1.read())  # 读取上传的文件内容
        logger.info(f"上传图像已保存到: {image1_path}")

    # 返回流式响应
    return StreamingResponse(
        process_request(
            question=question,
            ID=ID,
            image=image,
            image1=image1_path
        ),
        media_type="text/event-stream"  # 流式响应的MIME类型
    )


# --------------------------
# 启动服务
# --------------------------
if __name__ == "__main__":
    import uvicorn
    # 启动服务：host=0.0.0.0允许外部访问，port=8000为端口
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)  # 单进程（模型不支持多进程共享）