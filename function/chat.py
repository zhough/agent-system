
import requests
import logging
from config import ID,API_URL,IMAGE_PATH
import io
import base64
from typing import Generator,AsyncGenerator
import asyncio
async def send_request(question, image_path=IMAGE_PATH,image=None)-> AsyncGenerator[str, None]:
    """发送单轮请求到API服务"""
    # 构建请求数据（必传：question、session_id）
    data = {
        "question": question.strip(),
        "session_id": ID
    }

    # 构建文件（若有图像）
    files = None
    # if image_path and image_path.strip():
    #     try:
    #         files = {"image": open(image_path.strip(), "rb")}
    #         logging.info(f"[已附加图像: {image_path.strip()}]")
    #     except Exception as e:
    #         logging.error(f"⚠️  图像加载失败: {str(e)}，将以纯文本提问")
    if image is not None:
        img_bytes = base64.b64decode(image)
        img_file_obj = io.BytesIO(img_bytes)
        files = {"image": img_file_obj}
    # 发送POST请求（stream=True保持流式响应）
    try:
        response = requests.post(
            API_URL,
            data=data,
            files=files,
            stream=True,
            timeout=30  # 超时时间（根据模型响应速度调整）
        )
        response.raise_for_status()  # 捕获HTTP错误（如404、500）
        
        # 流式接收并打印回答
        #print("模型回答：", end="", flush=True)
        full_response = ''
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                #print(chunk, end="", flush=True)
                yield chunk
                full_response+=chunk
                await asyncio.sleep(0)
        #print("\n" + "-"*50 + "\n")
        
        # 关闭图像文件（若打开）
        # if files:
        #     files["image"].close()
        #return full_response
    except requests.exceptions.RequestException as e:
        yield {'status':f'请求失败{str(e)}'} 
        logging.error(f"⚠️  请求失败: {str(e)}\n" + "-"*50 + "\n")

# function/tools.py
# import httpx
# import logging
# from config import ID, API_URL
# import io
# import base64
# from typing import AsyncGenerator  # 类型提示改为异步生成器

# # 🌟 改为异步函数，返回 AsyncGenerator
# async def send_request(question, image=None) -> AsyncGenerator[str, None]:
#     """异步发送单轮请求到API服务，返回流式响应"""
#     data = {
#         "question": question.strip(),
#         "session_id": ID
#     }
#     files = None

#     # 处理图像：Base64 转 BytesIO（逻辑不变，同步操作不影响，因为在异步函数内）
#     if image is not None:
#         try:
#             img_bytes = base64.b64decode(image)
#             img_file_obj = io.BytesIO(img_bytes)
#             # 注意：httpx 处理 files 时，需指定文件名和 MIME 类型
#             files = {"image": ("uploaded_image.png", img_file_obj, "image/png")}
#             logging.info(f"[已附加Base64图像]")
#         except Exception as e:
#             error_msg = f"\n⚠️ 图像解码失败: {str(e)}"
#             yield error_msg
#             logging.error(error_msg)
#             return

#     # 🌟 异步发送流式请求
#     try:
#         async with httpx.AsyncClient(timeout=30) as client:
#             # 用 client.stream 发起异步流式 POST 请求
#             async with client.stream(
#                 "POST",
#                 API_URL,
#                 data=data,
#                 files=files  # httpx 支持异步处理 files
#             ) as response:
#                 response.raise_for_status()  # 捕获 HTTP 错误
#                 full_response = ""
#                 # 🌟 异步迭代响应内容（关键：不阻塞事件循环）
#                 async for chunk in response.aiter_text():  # aiter_text() 异步获取文本流
#                     if chunk:
#                         yield chunk
#                         full_response += chunk
#                 # 迭代结束，无需手动关闭文件（httpx 会自动处理）
#     except httpx.RequestError as e:
#         error_msg = f"\n⚠️ 请求失败: {str(e)}"
#         yield error_msg
#         logging.error(error_msg)