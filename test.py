
# import requests

# def call_generate_api(user_query: str) -> str:
#     # 接口地址（替换为你的服务端IP和端口）
#     url = 'http://localhost:5000/generate' 
#     try:
#         # 发送POST请求，参数放在json中
#         response = requests.post(
#             url,
#             json={"user_query": user_query,'ID':'0007'},  # 键名必须与接口参数名一致
#             timeout=1000  # 超时时间（根据LLM生成速度调整）
#         )
        
#         # 检查请求是否成功（HTTP状态码200）
#         response.raise_for_status()
        
#         # 接口返回的是字符串，直接获取text
#         return response.text
    
#     except Exception as e:
#         return f"请求失败：{str(e)}"

# # 测试
# if __name__ == "__main__":
#     while True:
#         user_input = input('你：')
#         result = call_generate_api(user_input)
#         print("\nLLM返回结果：", result)

import asyncio
import httpx

async def stream_chat_test(user_query):
    # 你的 FastAPI 服务地址
    url = "http://127.0.0.1:8000/generate"
    
    # 要发送的数据
    payload = {
        "user_query": user_query,
        "ID": "0007"
    }

    try:
        async with httpx.AsyncClient() as client:
            # stream=True 参数告诉 httpx 这是一个流式响应
            async with client.post(url, json=payload, stream=True) as response:
                response.raise_for_status()  # 如果状态码不是 2xx, 则抛出异常

                print("--- 开始接收流式响应 ---")
                # 异步迭代响应内容
                async for chunk in response.aiter_text():
                    # aiter_text() 会自动解码，并逐块提供文本
                    print(chunk, end="", flush=True)
                
                print("\n--- 流式响应结束 ---")

    except httpx.RequestError as e:
        print(f"请求失败: {e}")
    except httpx.HTTPStatusError as e:
        print(f"HTTP 错误: {e.response.status_code} - {e.response.text}")

# 运行异步函数
if __name__ == "__main__":
    while True:
        user_query = input('你: ')

        asyncio.run(stream_chat_test(user_query))