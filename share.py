from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import logging
from config import VECTOR_DB_PATH,DEVICE


embedding_model = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",  # 轻量768维模型，平衡速度与效果
    model_kwargs={"device": DEVICE}  # 无GPU时用"cpu"，有GPU可改为"cuda"
)
logging.info('成功加载word2vec模型')


vector_db = Chroma(
    persist_directory=VECTOR_DB_PATH,  # 数据存储路径
    embedding_function=embedding_model,  # 绑定向量化模型
    collection_name="full_turn_conversations"  # 集合名（类似数据库表）
)