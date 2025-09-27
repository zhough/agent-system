import json
from sqlalchemy import create_engine, Column, String, Text, Float, Boolean, Integer, DateTime
from sqlalchemy.orm import sessionmaker,declarative_base
from datetime import datetime
import uuid
from function.utils import logging_decorator


Base = declarative_base()

class Memory(Base):
    __tablename__ = "memories"  # 表名

    # 字段定义（与之前的表结构一致）
    memory_id = Column(String, primary_key=True, default=lambda: f"mem_{uuid.uuid4()}")
    user_id = Column(String,nullable=False)
    content = Column(Text, nullable=False)
    memory_type = Column(String, nullable=False)  # FACT/PREFERENCE 等
    create_timestamp = Column(DateTime, default=datetime.now)
    update_timestamp = Column(DateTime, default=datetime.now, onupdate=datetime.now)


engine = create_engine("sqlite:///memory_orm.db")  # 支持 SQLite/PostgreSQL/MySQL
Base.metadata.create_all(engine)  # 自动创建表
Session = sessionmaker(bind=engine)
session = Session()

@logging_decorator
def write_memory(user_id,content,memory_type):
    new_memory=Memory(
        user_id=user_id,
        content=content,
        memory_type=memory_type
    )
    session.add(new_memory)
    session.commit()
    return {"status": "success", "memory_id": new_memory.memory_id}

@logging_decorator
def query_memory(user_id,memory_type=None):
    query = session.query(Memory).filter(Memory.user_id == user_id)
    if memory_type:
        query = query.filter(Memory.memory_type == memory_type)
    results = query.all()
    return [{"memory_id": mem.memory_id,"content": mem.content, "type": mem.memory_type,
             'update_timestamp':mem.update_timestamp.isoformat()} for mem in results]

@logging_decorator
def delete_memory(memory_id,user_id):
    query = session.query(Memory).filter(Memory.user_id == user_id)
    if memory_id:
        memory_id_list = [i.strip() for i in memory_id.split(',')]
        query = query.filter(Memory.memory_id.in_(memory_id_list))
    query_list = query.all()
    if query_list:
        for f in query_list:
            session.delete(f)
        session.commit()
        return {'status':'success'}
    else: 
        return {'status':'没有相关记录'}
    
@logging_decorator
def database_operation(operation_type:str,user_id:str,memory_type:str=None,content:str=None,memory_id:str=None):
    if operation_type == 'write':
        write = write_memory(user_id=user_id,content=content,memory_type=memory_type)
        return json.dumps(write) 
    elif operation_type == 'query':
        query = query_memory(user_id=user_id,memory_type=memory_type)
        return json.dumps(query)
    elif operation_type == 'delete':
        delete=delete_memory(memory_id=memory_id,user_id=user_id)
        return json.dumps(delete)