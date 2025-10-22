import os
from dotenv import load_dotenv
from openai import OpenAI,AsyncOpenAI 
from function.tools import tools,function_map
from function.utils import parse_json_robust,save_full_turn_dialog
import logging
from config import Config
from datetime import datetime   
from fastapi import FastAPI
from pydantic import BaseModel
from typing import AsyncGenerator,Dict,Any
import uvicorn
from fastapi.responses import StreamingResponse
import asyncio
import uuid
import base64
import io
from PIL import Image
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware


config = Config()
system_prompt = config.system_prompt.copy()
MAX_HISTORY_LENGTH = config.max_history_length

app = FastAPI(title='皮肤病诊断agent接口')
origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)

class QueryRequest(BaseModel):
    user_query: str  # 必须包含的参数
    ID : str = '0001'
    image_base64 : str = None
# 定义响应数据模型
class LLMResponse(BaseModel):
    result: str
    request_id: str  # 可用于追踪请求
    status: str = "success"
load_dotenv()


client = AsyncOpenAI(
    api_key=os.getenv('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com",
)


all_messages = {}

def get_user_messages(user_id:str) -> list[dict]:
    if user_id not in all_messages:
        all_messages[user_id] = [system_prompt]
    return all_messages[user_id]

def trim_conversation_history():
    """精简对话历史，避免上下文长度超限"""
    global messages
    if len(messages) > MAX_HISTORY_LENGTH:
        # 保留系统提示 + 最近19条对话
        messages = [messages[0]] + messages[-19:]
        print(f"\n[对话历史已精简] 当前长度：{len(messages)}")



async def generate_chat_stream(request: QueryRequest) -> AsyncGenerator[str, None]:
    user_query = request.user_query
    ID = request.ID
    global all_messages
    messages = get_user_messages(ID)
    messages.append({'role':'system','content':f'当前用户ID为{ID},当前时间为{datetime.now()}'})
    messages.append({"role": "user", "content": user_query})
    current_turn = {
        "user_input": user_query,
        "tool_calls": [],
        "assistant_final_answer": ""
    }

    while True:
        # 发起流式请求
        stream = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            stream=True
        )
        # 状态变量
        full_text = ""  # 拼接普通文本
        res = ''
        is_function_call = False  # 是否检测到工具调用
        full_tool_call = []
        #async def process_sync_stream():
        #nonlocal full_text, is_function_call, full_tool_call
        # 逐块处理流式响应
        async for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            # 检测工具调用（一旦发现工具调用，后续内容均视为工具指令）
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                is_function_call = True
                #current_tool = delta.tool_calls[0]
                # 初始化或更新完整工具调用数据
                for i,current_tool in enumerate(delta.tool_calls):
                    if not full_tool_call:
                        full_tool_call.append({
                            "id": current_tool.id,
                            'type':current_tool.type,
                            "function": {
                                "name": current_tool.function.name,
                                "arguments": current_tool.function.arguments  # 初始参数片段
                            }
                        }) 

                    else:
                        # 拼接后续的参数片段
                        full_tool_call[i]["function"]["arguments"] += current_tool.function.arguments
                        #yield '\n'
                        await asyncio.sleep(0)
                #logging.info(f'测试点1:{full_tool_call}')                

            # 普通文本处理（实时流式输出）
            elif hasattr(delta, "content") and delta.content is not None and not is_function_call:
                print(delta.content, end="", flush=True)  # 实时打印
                yield delta.content
                full_text += delta.content
                await asyncio.sleep(0)

            # 响应结束判断
            if choice.finish_reason in ["stop", "tool_calls"]:
                break
        # # 迭代处理同步流的结果（将同步生成器转为异步迭代）
        # async for chunk in process_sync_stream():
        #     yield chunk  # 将处理后的文本片段发送给前端
        # 3. 助手消息入队
        assistant_msg = {"role": "assistant", "content": full_text}

        if is_function_call and full_tool_call:
            assistant_msg["tool_calls"] = full_tool_call  # 补充工具调用信息
        messages.append(assistant_msg)



        # 4. 处理工具调用
        if is_function_call and full_tool_call:
            print("\n[检测到工具调用，开始执行...]")
            yield '\n'
            #logging.info('开始调用工具')
            try:
                for i in range(len(full_tool_call)):
                    function_name = full_tool_call[i]["function"]["name"]
                    
                    arguments = parse_json_robust(full_tool_call[i]["function"]["arguments"])
                    for argument in arguments:

                        #function_args = json.loads(argument)  # 解析完整参数
                        #测试点3

                        if function_name in function_map:
                            if function_name == 'send_request':
                                logging.info(f'多模态调用参数:{argument}')
                                argument['image'] = request.image_base64
                                argument['ID'] = ID   
                                #logging.info(f'函数调用的参数：{argument}')
                                sync_generator = function_map[function_name](**argument)
                                full_tool_response = ""
                                if request.image_base64 is not None:
                                    logging.info('接收到图像')
                                    name = f'{uuid.uuid4().hex}.png'
                                    save_dir = os.path.join(config.base_path,ID)
                                    save_dir1 = Path(save_dir)
                                    save_dir1.mkdir(parents=True, exist_ok=True)
                                    save_path = os.path.join(save_dir,name)
                                    img_bytes = base64.b64decode(request.image_base64)
                                    img_file_obj = io.BytesIO(img_bytes)
                                    image_pil = Image.open(img_file_obj)
                                    image_pil.save(save_path)
                                    full_tool_response = f'请在数据库中记录图像路径:{save_path}\n'
                                async for chunk in sync_generator:
                                    yield chunk
                                    full_tool_response += chunk
                                    #await asyncio.sleep(0)
                                res = full_tool_response
                            else:
                                logging.info(f'函数调用的参数:{argument}')
                                res = function_map[function_name](**argument)

                            logging.info(f'函数调用结果: {res[:50]}')
                            #logging.info(f'函数调用的结果：{res}')
                        # 工具结果入队
                    messages.append({
                        "role": "tool", 
                        'type':'function',
                        "tool_call_id": full_tool_call[i]["id"], 
                        "name": function_name,
                        "content": res
                    })
                    current_turn["tool_calls"].append({
                    "function_name": full_tool_call[i]["function"]["name"],
                    "arguments": full_tool_call[i]["function"]["arguments"],
                    "tool_result": res,
                    })

            except Exception as e:
                logging.error(f"[函数执行错误] {str(e)}")
        #如果没有再次调用函数，退出while
        else: 
            current_turn['assistant_final_answer'] = full_text
            save_full_turn_dialog(user_id=ID, dialog_data=current_turn)
            break

@app.post("/generate", response_model=str, description="调用LLM生成文本")
async def stream_chat(request: QueryRequest):
    """
    流式响应的入口。返回一个 StreamingResponse。
    StreamingResponse 的内容由 generate_chat_stream 生成器提供。
    """
    return StreamingResponse(
        generate_chat_stream(request), 
        media_type="text/event-stream"  # 使用 SSE (Server-Sent Events) 格式
        # 如果前端期望纯文本流，可以使用 media_type="text/plain"
    )

# 测试
if __name__ == "__main__":
    # while True:
    #     user_input = input('你：')
    #     if user_input in ['退出','exit']:
    #         break
    #     stream_chat(user_input)
    #     print("\n" + "-"*50)
    uvicorn.run(app, host="0.0.0.0", port=5000, workers=1)