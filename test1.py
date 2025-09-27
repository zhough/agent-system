import requests
from time import sleep
def stream_chat_test_sync(user_query):
    url = "http://127.0.0.1:5000/generate"
    
    payload = {
        "user_query": user_query,
        "ID": "0007"
    }

    try:
        # stream=True 参数
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()

            print("--- 开始接收流式响应 ---")
            # 遍历 response.iter_content() 或 response.iter_lines()
            # iter_content 提供字节流，需要解码
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    print(chunk, end="", flush=True)
            
            print("\n--- 流式响应结束 ---")

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")

if __name__ == "__main__":
    while True:
        user_query = input('你: ')

        stream_chat_test_sync(user_query)