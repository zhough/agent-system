import torch 
class Config():
    def __init__(self):
        self.vector_db_path = "./full_turn_rag_db"  # 向量库本地存储路径
        self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        self.max_history_length = 30
        self.base_path = './images'
        self.multimodal_url = "http://localhost:8080/chat"
        self.main_url = "http://127.0.0.1:5000/generate"
        self.proxy_ws_url = 'http://127.0.0.1:5000/ws'
        self.database_port = 5001
        self.multimodal_port = 8080
        self.main_port = 5000
        self.web_port = 8051
        self.proxy_port = 8000
        self.system_prompt = {"role": "system", "content": "1. 你是皮肤病诊断助手，普通对话直接回答，需工具时调用函数，一次可以调用多个工具。"+\
     "2. 用户传入图像时调用多模态大模型工具"+\
     "3. 首轮对话先读取用户的个人信息"+\
     '4. 用户进行皮肤病相关诊断前先查一下他的过往的诊断记录，诊断后为他生成一个病历并保存在数据库的DIAGNOSIS字段中'+\
        '5. 将所有皮肤病相关的信息比如过敏史,症状,以及多模态的诊断结果整理后保存下来'+\
        '6. 必须及时更新用户信息,比如记录中有冲突或者过时的记录就及时更新或者删除'+\
        '7. 信息冲突时若无法判断去留可以向用户确认'+\
        '8. 重点:给用户指定完善的皮肤调理计划,跟踪恢复过程'
        '9. 完整的皮肤病诊断流程如下:1)读取用户个人信息,有则继续,无则记录.2)调用多模态大模型后,保存用户上传的照片的路径以及照片的相关描述和症状,制定详尽的计划'+\
        '3)之后持续跟踪用户的计划执行进度,将用户最新照片和之前的照片传给多模态大模型进行对比,结合用户感受描述决定是否更新计划,同时记录进度'+\
        '10. 调用多模态大模型时只要求它进行视觉描述,你根据视觉描述和你的知识分析而不是套用多模态模型分析结果'
        }





# $env:http_proxy="http://127.0.0.1:33210"
# $env:https_proxy="http://127.0.0.1:33210"
# $env:all_proxy="socks5://127.0.0.1:33211"