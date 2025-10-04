from .utils import get_time
from database.memory_database import database_operation
from .chat import send_request
import requests
from database.vector_database import query_user_memory
tools = [
    #天气查询
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前时间.",
            "parameters": {
                "type": "object",
                "properties": {
                    'time':{
                        'type':'string',
                        "description": "占位用,固定传入字母a即可",
                    },
                },
                "required": ['time']
            },
        }
    },
    #数据库操作集合
    {
        "type": "function",
        "function": {
            "name": "database_operation",
            "description": "用户详细的个人信息的写入和查询，调用时给出具体的操作类型，写入时给出写入的内容,删除时要给出要删除的memory_id."+\
            "用户的个人信息和病情相关信息都应该在这里写入或者查询"+\
                '第一次对话之前无论用户说什么都先读取一遍个人信息,及时删除或更新过时或者矛盾的信息',
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "提炼后需要写入的信息",
                    },
                    "memory_type":{
                        'type':'string',
                        'description':'记忆的类型',
                        'enum':['FACT','PREFERENCE','EMOTION','TASK','IMPORTANT']
                    },
                    'operation_type':{
                        'type':'string',
                        'description':'操作的类型',
                        'enum':['write','query','delete']
                    },
                    'user_id':{
                        'type':'string',
                        'description':'用户的id'
                    },
                    'memory_id':{
                        'type':'string',
                        'description':'删除时所需的memory唯一标识'
                    }
                },
                "required": ['operation_type',"user_id"]
            },
        }
    },
    #调用多模态大模型
    {
        "type": "function",
        "function": {
            "name": "send_request",
            "description": "1.调用多模态大模型，当用户输出的开头带<image>的时候证明传入图像，这时候请你先调用这个工具分析."+\
            "2.返回的结果中有图像的保存路径,请在数据库中记下图像保存的路径."+\
            "3.用户能看到多模态的输出,不必复述",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "向多模态大模型提出的文本要求，可以让它描述图像之类的,对于皮肤病诊断,要求提供详细的病变描述和分析",
                    },
                    'image1':{
                        'type':'string',
                        'description': '如果需要两张图作对比,传入被对比图的路径,如果没有要对比的图,不用传任何东西'
                    }
                },
                "required": ["question"]
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_user_memory",
            "description": "查询或者删除当前用户的历史完整对话轮次，包含用户输入、助手回答、工具调用记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "当前用户id"
                    },
                    "method": {
                        "type": "string",
                        "description": "检索的方法，关键字检索或者元数据检索,还包括删除的方法",
                        'enum':['keywords','metadata','delete']
                    },
                    'keywords':{
                        'type':'string',
                        'description':'关键字检索时的关键字'
                    },
                    'k':{
                        'type': 'string',
                        'description':'查询时用，需要查询的对话轮次，默认是100，如果有需要你可以修改'
                    },
                    'memory_ids':{
                        'type':'string',
                        'description':'元数据检索或者删除时的一条或者多条记忆id'
                    },
                    'start_time':{
                        'type':'string',
                        'description':'元数据查询时要查询的的起始时间，格式为"2025-09-20T13:17:33.308716"'
                    },
                    'end_time':{
                        'type':'string',
                        'description':'元数据查询时的结束时间，格式同起始时间'
                    }

                },
                "required": ["user_id"]  # 必传参数
            }
        }
    },
]




function_map={
    'get_time':get_time,
    'database_operation':database_operation,
    'send_request':send_request,
    'query_user_memory':query_user_memory,
}