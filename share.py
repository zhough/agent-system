from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import logging
from config import Config
import os   

config = Config()

embedding_model = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",  # 轻量768维模型
    model_kwargs={"device": config.device} 
)
logging.info('成功加载word2vec模型')


vector_db = Chroma(
    persist_directory=config.vector_db_path,  # 数据存储路径
    embedding_function=embedding_model,  # 绑定向量化模型
    collection_name="full_turn_conversations"  # 集合名（类似数据库表）
)

if not os.path.exists(config.base_path):
    os.makedirs(config.base_path)