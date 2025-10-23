# import os
# from dotenv import load_dotenv
# from openai import OpenAI,AsyncOpenAI 
# from function.tools import tools,function_map
# from function.utils import parse_json_robust,save_full_turn_dialog
# import logging
# from config import Config
# from datetime import datetime   
# from fastapi import FastAPI
# from pydantic import BaseModel
# from typing import AsyncGenerator,Dict,Any
# import uvicorn
# from fastapi.responses import StreamingResponse
# import asyncio
# import uuid
# import base64
# import io
# from PIL import Image
# from pathlib import Path
# from fastapi.middleware.cors import CORSMiddleware


# config = Config()
# system_prompt = config.system_prompt.copy()
# MAX_HISTORY_LENGTH = config.max_history_length

# app = FastAPI(title='皮肤病诊断agent接口')
# origins = [
#     "*",
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],  # 允许所有HTTP方法
#     allow_headers=["*"],  # 允许所有HTTP头
# )

# class QueryRequest(BaseModel):
#     user_query: str  # 必须包含的参数
#     ID : str = '0001'
#     image_base64 : str = None
# # 定义响应数据模型
# class LLMResponse(BaseModel):
#     result: str
#     request_id: str  # 可用于追踪请求
#     status: str = "success"
# load_dotenv()


# client = AsyncOpenAI(
#     api_key=os.getenv('DEEPSEEK_API_KEY'),
#     base_url="https://api.deepseek.com",
# )


# all_messages = {}

# def get_user_messages(user_id:str) -> list[dict]:
#     if user_id not in all_messages:
#         all_messages[user_id] = [system_prompt]
#     return all_messages[user_id]

# def trim_conversation_history():
#     """精简对话历史，避免上下文长度超限"""
#     global messages
#     if len(messages) > MAX_HISTORY_LENGTH:
#         # 保留系统提示 + 最近19条对话
#         messages = [messages[0]] + messages[-19:]
#         print(f"\n[对话历史已精简] 当前长度：{len(messages)}")


# async def generate_chat_stream(request: QueryRequest) -> AsyncGenerator[str, None]:
#     user_query = request.user_query
#     ID = request.ID
#     global all_messages
#     messages = get_user_messages(ID)
#     messages.append({'role':'system','content':f'当前用户ID为{ID},当前时间为{datetime.now()}'})
#     messages.append({"role": "user", "content": user_query})
#     current_turn = {
#         "user_input": user_query,
#         "tool_calls": [],
#         "assistant_final_answer": ""
#     }

#     try:  # 外层捕获总取消事件
#         while True:
#             # 发起流式请求
#             stream = await client.chat.completions.create(
#                 model="deepseek-chat",
#                 messages=messages,
#                 tools=tools,
#                 stream=True
#             )
            
#             # 状态变量
#             full_text = ""
#             res = ''
#             is_function_call = False
#             full_tool_call = []

#             try:  # 内层捕获API流的取消事件
#                 # 逐块处理流式响应
#                 async for chunk in stream:
#                     if not chunk.choices:
#                         continue
#                     choice = chunk.choices[0]
#                     delta = choice.delta

#                     # 检测工具调用
#                     if hasattr(delta, "tool_calls") and delta.tool_calls:
#                         is_function_call = True
#                         for i, current_tool in enumerate(delta.tool_calls):
#                             if not full_tool_call:
#                                 full_tool_call.append({
#                                     "id": current_tool.id,
#                                     'type': current_tool.type,
#                                     "function": {
#                                         "name": current_tool.function.name,
#                                         "arguments": current_tool.function.arguments
#                                     }
#                                 })
#                             else:
#                                 full_tool_call[i]["function"]["arguments"] += current_tool.function.arguments
#                                 await asyncio.sleep(0)

#                     # 普通文本处理
#                     elif hasattr(delta, "content") and delta.content is not None and not is_function_call:
#                         print(delta.content, end="", flush=True)
#                         yield delta.content
#                         full_text += delta.content
#                         await asyncio.sleep(0)

#                     # 响应结束判断
#                     if choice.finish_reason in ["stop", "tool_calls"]:
#                         break

#             except asyncio.CancelledError:
#                 # 客户端中断请求时，关闭API流并退出
#                 print(f"\n[用户中断请求] 关闭DeepSeek API流")
#                 await stream.aclose()  # 强制关闭API连接
#                 return  # 直接退出生成器，不传播错误
#             finally:
#                 # 确保流资源被释放（无论是否正常结束）
#                 if 'stream' in locals():
#                     try:
#                         await stream.aclose()
#                     except:
#                         pass

#             # 助手消息入队
#             assistant_msg = {"role": "assistant", "content": full_text}
#             if is_function_call and full_tool_call:
#                 assistant_msg["tool_calls"] = full_tool_call
#             messages.append(assistant_msg)

#             # 处理工具调用
#             if is_function_call and full_tool_call:
#                 print("\n[检测到工具调用，开始执行...]")
#                 yield '\n'
#                 try:
#                     for i in range(len(full_tool_call)):
#                         function_name = full_tool_call[i]["function"]["name"]
#                         arguments = parse_json_robust(full_tool_call[i]["function"]["arguments"])
#                         for argument in arguments:
#                             if function_name in function_map:
#                                 if function_name == 'send_request':
#                                     logging.info(f'多模态调用参数:{argument}')
#                                     argument['image'] = request.image_base64
#                                     argument['ID'] = ID   
#                                     sync_generator = function_map[function_name](**argument)
#                                     full_tool_response = ""
#                                     if request.image_base64 is not None:
#                                         logging.info('接收到图像')
#                                         name = f'{uuid.uuid4().hex}.png'
#                                         save_dir = os.path.join(config.base_path,ID)
#                                         save_dir1 = Path(save_dir)
#                                         save_dir1.mkdir(parents=True, exist_ok=True)
#                                         save_path = os.path.join(save_dir,name)
#                                         img_bytes = base64.b64decode(request.image_base64)
#                                         img_file_obj = io.BytesIO(img_bytes)
#                                         image_pil = Image.open(img_file_obj)
#                                         image_pil.save(save_path)
#                                         full_tool_response = f'请在数据库中记录图像路径:{save_path}\n'
#                                     async for chunk in sync_generator:
#                                         yield chunk
#                                         full_tool_response += chunk
#                                     res = full_tool_response
#                                 else:
#                                     logging.info(f'函数调用的参数:{argument}')
#                                     res = function_map[function_name](** argument)
#                                 logging.info(f'函数调用结果: {res[:50]}')
#                         messages.append({
#                             "role": "tool", 
#                             'type':'function',
#                             "tool_call_id": full_tool_call[i]["id"], 
#                             "name": function_name,
#                             "content": res
#                         })
#                         current_turn["tool_calls"].append({
#                             "function_name": full_tool_call[i]["function"]["name"],
#                             "arguments": full_tool_call[i]["function"]["arguments"],
#                             "tool_result": res,
#                         })
#                 except Exception as e:
#                     logging.error(f"[函数执行错误] {str(e)}")
#             else: 
#                 current_turn['assistant_final_answer'] = full_text
#                 save_full_turn_dialog(user_id=ID, dialog_data=current_turn)
#                 break

#     except asyncio.CancelledError:
#         # 最外层捕获取消事件，确保程序不崩溃
#         print(f"\n[请求被中断] 已清理资源")
#         return
#     except Exception as e:
#         logging.error(f"[生成器异常] {str(e)}")
#         yield f"服务异常：{str(e)}"


# @app.post("/generate", response_model=str, description="调用LLM生成文本")
# async def stream_chat(request: QueryRequest):
#     return StreamingResponse(
#         generate_chat_stream(request), 
#         media_type="text/event-stream"
#     )


# # 测试
# if __name__ == "__main__":
#     # while True:
#     #     user_input = input('你：')
#     #     if user_input in ['退出','exit']:
#     #         break
#     #     stream_chat(user_input)
#     #     print("\n" + "-"*50)
#     uvicorn.run(app, host="0.0.0.0", port=config.main_port, workers=1)


from dotenv import load_dotenv
from openai import OpenAI,AsyncOpenAI 
from function.tools import tools,function_map
from function.utils import parse_json_robust,save_full_turn_dialog
import logging
from config import Config
from datetime import datetime   
from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # 1. 新增：导入WebSocket相关
from pydantic import BaseModel
from typing import AsyncGenerator,Dict,Any
import uvicorn
from fastapi.responses import StreamingResponse
import asyncio
import uuid
import base64
import io
import json  # 2. 新增：用于解析WebSocket接收的JSON消息
from pathlib import Path
import os
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image


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
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    user_query: str  # 必须包含的参数
    ID : str = '0001'
    image_base64 : str = None

# 定义响应数据模型（原有，未改动）
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
        messages = [messages[0]] + messages[-19:]
        print(f"\n[对话历史已精简] 当前长度：{len(messages)}")

# -------------------------- 原有核心流式逻辑（完全未改动） --------------------------
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

    try:  # 外层捕获总取消事件
        while True:
            # 发起流式请求
            stream = await client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=tools,
                stream=True
            )
            
            # 状态变量
            full_text = ""
            res = ''
            is_function_call = False
            full_tool_call = []

            try:  # 内层捕获API流的取消事件
                # 逐块处理流式响应
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    delta = choice.delta

                    # 检测工具调用
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        is_function_call = True
                        for i, current_tool in enumerate(delta.tool_calls):
                            if not full_tool_call:
                                full_tool_call.append({
                                    "id": current_tool.id,
                                    'type': current_tool.type,
                                    "function": {
                                        "name": current_tool.function.name,
                                        "arguments": current_tool.function.arguments
                                    }
                                })
                            else:
                                full_tool_call[i]["function"]["arguments"] += current_tool.function.arguments
                                await asyncio.sleep(0)

                    # 普通文本处理
                    elif hasattr(delta, "content") and delta.content is not None and not is_function_call:
                        print(delta.content, end="", flush=True)
                        yield delta.content
                        full_text += delta.content
                        await asyncio.sleep(0)

                    # 响应结束判断
                    if choice.finish_reason in ["stop", "tool_calls"]:
                        break

            except asyncio.CancelledError:
                # 客户端中断请求时，关闭API流并退出
                print(f"\n[用户中断请求] 关闭DeepSeek API流")
                await stream.aclose()  # 强制关闭API连接
                return  # 直接退出生成器，不传播错误
            finally:
                # 确保流资源被释放（无论是否正常结束）
                if 'stream' in locals():
                    try:
                        await stream.aclose()
                    except:
                        pass

            # 助手消息入队
            assistant_msg = {"role": "assistant", "content": full_text}
            if is_function_call and full_tool_call:
                assistant_msg["tool_calls"] = full_tool_call
            messages.append(assistant_msg)

            # 处理工具调用
            if is_function_call and full_tool_call:
                print("\n[检测到工具调用，开始执行...]")
                yield '\n'
                try:
                    for i in range(len(full_tool_call)):
                        function_name = full_tool_call[i]["function"]["name"]
                        arguments = parse_json_robust(full_tool_call[i]["function"]["arguments"])
                        for argument in arguments:
                            if function_name in function_map:
                                if function_name == 'send_request':
                                    logging.info(f'多模态调用参数:{argument}')
                                    argument['image'] = request.image_base64
                                    argument['ID'] = ID   
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
                                    res = full_tool_response
                                else:
                                    logging.info(f'函数调用的参数:{argument}')
                                    res = function_map[function_name](** argument)
                                logging.info(f'函数调用结果: {res[:50]}')
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
            else: 
                current_turn['assistant_final_answer'] = full_text
                save_full_turn_dialog(user_id=ID, dialog_data=current_turn)
                break

    except asyncio.CancelledError:
        # 最外层捕获取消事件，确保程序不崩溃
        print(f"\n[请求被中断] 已清理资源")
        return
    except Exception as e:
        logging.error(f"[生成器异常] {str(e)}")
        yield f"服务异常：{str(e)}"

# -------------------------- 原有HTTP接口（完全未改动，保留Web前端SSE支持） --------------------------
@app.post("/generate", response_model=str, description="调用LLM生成文本")
async def stream_chat(request: QueryRequest):
    return StreamingResponse(
        generate_chat_stream(request), 
        media_type="text/event-stream"
    )

# -------------------------- 3. 新增：WebSocket接口（适配proxy.py转发） --------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket接口：接收proxy.py转发的请求，复用generate_chat_stream生成流式响应
    客户端（proxy.py）需发送JSON格式消息：{"user_query": "xxx", "ID": "xxx", "image_base64": "xxx"}
    """
    # 1. 接受WebSocket连接（来自proxy.py）
    await websocket.accept()
    print(f"[WebSocket] 新连接建立")

    try:
        # 2. 接收proxy.py转发的消息（小程序的请求参数）
        # 消息格式：JSON字符串，包含user_query、ID、image_base64（可选）
        data = await websocket.receive_text()
        req_data = json.loads(data)  # 解析JSON为字典

        # 3. 构造QueryRequest对象（复用原有生成逻辑的入参格式）
        # 若参数缺失，用默认值（如ID默认0001，image_base64默认None）
        query_request = QueryRequest(
            user_query=req_data.get("user_query", ""),
            ID=req_data.get("ID", "0001"),
            image_base64=req_data.get("image_base64", None)
        )

        # 4. 调用核心流式生成逻辑，逐段通过WebSocket发送结果
        async for chunk in generate_chat_stream(query_request):
            await websocket.send_text(chunk)  # 把生成的文本块转发给proxy.py（再给小程序）

        # 5. 流式生成结束后，主动关闭WebSocket连接
        await websocket.close(code=1000, reason="响应完成")
        print(f"[WebSocket] 连接正常关闭（响应完成）")

    except WebSocketDisconnect:
        # 处理客户端（proxy.py）主动断开连接
        print(f"[WebSocket] 客户端主动断开连接")
    except json.JSONDecodeError:
        # 处理JSON解析失败（参数格式错误）
        await websocket.send_text("错误：请求参数必须是JSON格式")
        await websocket.close(code=1007, reason="参数格式错误")
        print(f"[WebSocket] 错误：请求参数非JSON格式")
    except Exception as e:
        # 处理其他未知错误
        error_msg = f"服务错误：{str(e)}"
        await websocket.send_text(error_msg)
        await websocket.close(code=1011, reason=error_msg)
        logging.error(f"[WebSocket] 未知错误：{str(e)}")

# -------------------------- 原有测试入口（未改动） --------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.main_port, workers=1)