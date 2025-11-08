from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
import uvicorn
import asyncio
import json
from database.memory_database import write_memory,delete_memory,query_memory
from config import Config

config = Config()

app = FastAPI(title='数据库查询')

@app.post('/query')
async def query_database(user_id: str = Form(..., description="用户ID（必填）")):
    fact = query_memory(user_id=user_id,memory_type='FACT')
    preference = query_memory(user_id=user_id,memory_type='PREFERENCE')
    important = query_memory(user_id=user_id,memory_type='IMPORTANT')

    res = {'fact': [f['content'] for f in fact],
           'preference': [p['content'] for p in preference],
           'important': [i['content'] for i in important]}
    return res

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=config.database_port, log_level="info")
