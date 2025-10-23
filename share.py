from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
import logging
from ..config import Config
import os   
from modelscope.hub.snapshot_download import snapshot_download
from huggingface_hub import snapshot_download as hf_snapshot_download

config = Config()
#os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

modelscope_model_id = "sentence-transformers/all-MiniLM-L6-v2"
local_model_dir = "./local_models" 
os.makedirs(local_model_dir, exist_ok=True)
local_model_path = os.path.join(local_model_dir, modelscope_model_id.replace("/", "_"))
if not os.path.exists(local_model_path):
    logging.info(f"模型未在本地发现，正在从 ModelScope 下载到 {local_model_path} ...")
    # 使用 ModelScope 的 snapshot_download 函数下载模型
    # 这个函数会返回下载后的本地路径
    local_model_path = snapshot_download(
        model_id=modelscope_model_id,
        cache_dir=local_model_dir,
        revision="master"
    )
    logging.info("模型下载完成！")
else:
    logging.info(f"模型已在本地存在: {local_model_path}")

embedding_model = HuggingFaceEmbeddings(
    model_name=local_model_path,  # 轻量768维模型
    model_kwargs={"device": config.device} 
)
logging.info('成功加载word2vec模型')

if not os.path.exists(config.vector_db_path):
    os.makedirs(config.vector_db_path)
    
vector_db = Chroma(
    persist_directory=config.vector_db_path,  # 数据存储路径
    embedding_function=embedding_model,  # 绑定向量化模型
    collection_name="full_turn_conversations"  # 集合名（类似数据库表）
)

if not os.path.exists(config.base_path):
    os.makedirs(config.base_path)


# eval "$(ssh-agent -s)"
# ssh-add ~/zhou/.ssh/id_ed25519
# ssh-add -l