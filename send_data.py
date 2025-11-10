from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
import uvicorn
import asyncio
import json
from database.memory_database import write_memory,delete_memory,query_memory
from config import Config
from fastapi.middleware.cors import CORSMiddleware
import re
app = FastAPI(title='数据库查询')
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境改为前端实际域名（如 "http://localhost:8080"）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

config = Config()

@app.post('/query')
async def query_database(user_id: str = Form(..., description="用户ID（必填）")):
    fact = query_memory(user_id=user_id,memory_type='FACT')
    diagnosis = query_memory(user_id=user_id,memory_type='DIAGNOSIS')
    important = query_memory(user_id=user_id,memory_type='IMPORTANT')
    path = query_memory(user_id=user_id,memory_type='PATH')
    pattern = r'\/images\/(.*)'
    
    res = {
        'fact': fact,
        'diagnosis': diagnosis,
        'important': important,
        'path': [re.search(pattern, p['content']).group(1) if re.search(pattern, p['content']) else '' for p in path]
    }
    return res

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=config.database_port, log_level="info")
