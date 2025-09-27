

VECTOR_DB_PATH = "./full_turn_rag_db"  # 向量库本地存储路径
DEVICE='cpu'
ID = '0002'
MAX_HISTORY_LENGTH = 20

#多模态配置
API_URL = "http://134.175.128.138:6888/chat"
IMAGE_PATH = '14.png'
#端口转发
#ssh -L 8888:localhost:6888 ubuntu@	175.178.7.40
#password:  7|9YMzr?N-Hpx
#http://localhost:8888/chat
#C:/Users/z4538/miniconda3/envs/agent/Scripts/streamlit.exe run app.py

SYSTEM_PROMPT = {"role": "system", "content": f"1. 你是皮肤病诊断助手，普通对话直接回答，需工具时调用函数，一次可以调用多个工具。"+\
     "2. 你可以随时查询所有用户的信息，但是严格禁止透露用户的信息给其他用户。"+\
     f"3. 首轮对话先读取用户的个人信息"+\
     '4. 用户进行皮肤病相关诊断前先查一下他的过往的诊断记录，诊断后为他生成一个病历并保存下来'+\
        '5. 记录详细的用户个人信息,从他的对话中推断他的个性和爱好等,用于后续提供更加合理的回答'}