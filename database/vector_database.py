import os
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import logging
from share import vector_db
from function.utils import logging_decorator,date2timestamp


current_turn = {
    "user_input": "",          # 用户本轮输入
    "tool_calls": [],          # 本轮工具调用记录（含参数+结果）
    "assistant_final_answer": ""  # 助手本轮最终回答
}

@logging_decorator
def query_by_keywords(user_id: str, keywords: str,k:str) -> str:
    """
    从向量库检索用户相似的历史对话轮次
    :param user_id: 用户ID（确保数据隔离）
    :param query: 检索关键词（语义匹配）
    :return: 格式化的检索结果（JSON字符串）
    """
    # 核心：按用户ID过滤 + 语义相似性检索
    search_results = vector_db.similarity_search(
        query=keywords,
        k=int(k),  
        filter={"user_id": user_id}  # 仅查询当前用户的数据
    )
    return search_results


@logging_decorator
def query_by_metadata(
    user_id=None,
    memory_id=None,  # 新增：支持单一memory_id（字符串）
    start_time=None,
    end_time=None,
    limit='10'
):
    #where_clause={}
    where_list=[]
    # 处理user_id筛选
    if user_id is not None:
        #where_clause["user_id"] = user_id
        where_list.append({'user_id':user_id})
    # 处理memory_id筛选（同时支持单一ID和列表）
    if memory_id is not None:
        memory_id = [i.strip() for i in memory_id.split(',')]
        #where_clause["memory_id"] = {"$in": memory_id}
        where_list.append({'memory_id':{'$in':memory_id}})
    # 处理时间范围筛选
    if start_time is not None or end_time is not None:
        time_conditions = []
        
        if start_time is not None:
            time_conditions.append({'timestamp':{'$gte':date2timestamp(start_time)}})
        if end_time is not None:
            time_conditions.append({'timestamp':{'$lte':date2timestamp(end_time)}})
        #where_clause["timestamp"] = time_conditions
        where_list.extend(time_conditions)
    # 可省略include参数，使用数据库默认返回字段
    if len(where_list)<=1:
        return vector_db.get(where=where_list[0],include=['metadatas','documents'],limit=int(limit))
    else:
        return vector_db.get(where={'$and':where_list},include=['metadatas','documents'],limit=int(limit))

@logging_decorator
def delete_memory(user_id,memory_ids):
    if memory_ids is not None:
        memory_id = [i.strip() for i in memory_ids.split(',')]
        memory_ids1 = {'$in':memory_id}
        vector_db.delete(where={'$and':[{'memory_id':memory_ids1},{'user_id':user_id}]})
    else: 
        vector_db.delete(where={'user_id':user_id})
    return json.dumps({'status':'success'})
    
@logging_decorator
def query_user_memory(method:str,user_id:str,keywords:str=None,
                      memory_ids:str=None,start_time:str=None,end_time:str=None,k:str='100'):
    if method == 'delete':
        return delete_memory(user_id=user_id,memory_ids=memory_ids)  
    else:
        history_memories = []
        if method == 'keywords':
            search_results = query_by_keywords(user_id=user_id,keywords=keywords,k=k) 
            for result in search_results:
                # 还原元数据中存储的完整对话结构
                full_dialog = json.loads(result.metadata["full_dialog"])
                history_memories.append({
                    'memory_id':result.metadata['memory_id'],
                    "轮次时间": result.metadata["timestamp"],
                    "用户输入": full_dialog["user_input"],
                    "助手最终回答": full_dialog["assistant_final_answer"],
                    "是否调用工具": "是" if full_dialog["tool_calls"] else "否"
                })

        elif method == 'metadata':
            search_results = query_by_metadata(user_id=user_id,memory_id=memory_ids,
                                            start_time=start_time,end_time=end_time,limit=k)
            metadatas = search_results.get('metadatas',[])
            for metadata in metadatas:
                full_dialog = json.loads(metadata.get('full_dialog',[]))
                history_memories.append({
                    'memory_id':metadata.get('memory_id',[]),
                    '轮次时间':metadata.get('timestamp',[]),
                    '是否调用工具':'是'if metadata.get('has_tool_call',[]) else '否',
                    '用户输入':full_dialog['user_input'],
                    '助手最终回答':full_dialog['assistant_final_answer'],
                })


        # 返回JSON格式结果（模型可解析）
        return json.dumps({
            "status": "success",
            "user_id": user_id,
            "memories": history_memories
        }, ensure_ascii=False)