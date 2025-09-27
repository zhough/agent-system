import json
import re
import logging
import log.log
from datetime import datetime
import uuid
from share import vector_db


def date2timestamp(date):
    date_obj = datetime.fromisoformat(date)
    return date_obj.timestamp()

def parse_json_robust(s):

    # 先尝试解析为单个JSON对象
    try:
        return [json.loads(s)]  # 统一返回列表格式，便于后续处理
    except json.JSONDecodeError:
        # 解析单个对象失败，尝试分割为多个对象
        pass

    json_objects = []
    start = 0
    stack = []
    
    for i, char in enumerate(s):
        if char == '{':
            if not stack:  # 记录第一个'{'的位置
                start = i
            stack.append(char)
        elif char == '}':
            if stack:
                stack.pop()
                # 当栈为空时，说明找到了一个完整的JSON对象
                if not stack:
                    json_str = s[start:i+1]
                    json_objects.append(json_str)
    
    # 解析提取到的JSON对象
    result = []
    for obj_str in json_objects:
        try:
            # 去除可能的空白字符
            obj_str = obj_str.strip()
            if obj_str:  # 确保不是空字符串
                obj = json.loads(obj_str)
                result.append(obj)
        except json.JSONDecodeError as e:
            logging.error(f"解析JSON片段失败: {e}，片段: {obj_str}")
    
    return result


def logging_decorator(func):
    def wrapper(*args,**kwargs):
        try:
            result = func(*args,**kwargs)
            logging.info(f'调用函数{func.__name__}成功，函数的返回是{result}')

            return result
        except Exception as e:
            logging.error(f'函数{func.__name__}调用失败,错误原因:{str(e)}')
    return wrapper


def get_weather(location:str):
    weather={'杭州':'24摄氏度','广州':'30摄氏度'}
    output = {location : weather.get(location)}
    return json.dumps(output) 


def save_full_turn_dialog(user_id: str, dialog_data: dict) -> None:
    """
    一轮对话结束后，一次性存储完整对话数据
    :param user_id: 用户ID
    :param dialog_data: 本轮对话结构化数据（current_turn）
    """
    # 1. 生成"检索摘要"（用于向量检索，捕捉核心语义）
    if dialog_data["tool_calls"]:
        # 有工具调用时，摘要包含工具信息
        tool_info = dialog_data["tool_calls"][0]
        tool_summary = f"调用工具[{tool_info['function_name']}]，结果：{tool_info['tool_result'][:50]}..."
        retrieval_summary = f"user：{dialog_data['user_input']} → {tool_summary} → assistant:{dialog_data['assistant_final_answer']}"
    else:
        # 无工具调用时，直接摘要对话
        retrieval_summary = f"user:{dialog_data['user_input']} → assistant:{dialog_data['assistant_final_answer']}"

    # 2. 生成"详细元数据"（存储完整对话结构，便于溯源）
    metadata = {
        "user_id": user_id,
        "timestamp": datetime.now().timestamp(),
        "memory_id": f"turn_{uuid.uuid4().hex[:10]}",  # 轮次唯一ID
        "full_dialog": json.dumps(dialog_data, ensure_ascii=False),  # 完整对话JSON
        "has_tool_call": len(dialog_data["tool_calls"]) > 0  # 标记是否有工具调用
    }

    # 3. 一次性写入向量库（摘要用于检索，元数据存完整信息）
    vector_db.add_texts(
        texts=[retrieval_summary],  # 检索用的摘要文本
        metadatas=[metadata]        # 详细元数据
    )

    # 调试提示（可注释）
    logging.info(f"\n[一轮对话已存储] 记忆ID：{metadata['memory_id']}")

