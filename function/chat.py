
import requests
import logging
from config import Config
import io
import base64
from typing import Generator,AsyncGenerator
import asyncio
from .utils import logging_decorator
import json
import os
config = Config()
async def send_request(question, ID='0042',image=None,image1=None)-> AsyncGenerator[str, None]:
    """发送单轮请求到API服务"""
    data = {
        "question": question.strip(),
        "session_id": ID
    }
    files = None
    if image is not None:
        img_bytes = base64.b64decode(image)
        img_file_obj = io.BytesIO(img_bytes)
        files = {"image": img_file_obj}
        if image1 is not None:
            image1_path = image1
            logging.info(f'image1_path: {image1_path}')
            if os.path.exists(image1_path):
                logging.info('打开image1成功')
                with open(image1_path, 'rb') as f:
                    img_bytes_from_file = f.read()
                    img_file_obj_from_file = io.BytesIO(img_bytes_from_file)
                    files['image1'] = img_file_obj_from_file 
        else:
            logging.info('image1加载失败')
    # 发送POST请求（stream=True保持流式响应）
    try:
        response = requests.post(
            config.api_url,
            data=data,
            files=files,
            stream=True,
            timeout=30  
        )
        response.raise_for_status()  # 捕获HTTP错误（如404、500）
        
        full_response = ''
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                yield chunk
                full_response+=chunk
                await asyncio.sleep(0)

    except requests.exceptions.RequestException as e:
        error_message = json.dumps({
            "type": "error",
            "message": f"请求失败: {str(e)}"
        })
        yield error_message
        logging.error(f"⚠️  请求失败: {str(e)}\n" + "-"*50 + "\n")

