import torch
from modelscope import Qwen3VLForConditionalGeneration, AutoProcessor

# --------------------------
# 1. 加载模型和处理器（已确保无报错）
# --------------------------
model_name = "unsloth/Qwen3-VL-4B-Instruct-bnb-4bit"
#cache_dir = "/home/zhangzy/zhou/hf_cache"  # 替换为你的缓存路径（可选）

# 加载模型（4bit量化，自动分配到GPU）
model = Qwen3VLForConditionalGeneration.from_pretrained("unsloth/Qwen3-VL-4B-Instruct-bnb-4bit",
                                                        dtype="auto",device_map='auto')


# 加载处理器（处理图像和文本输入）
processor = AutoProcessor.from_pretrained(
    model_name
)

# 验证模型是否在GPU上
print(f"模型设备：{model.device}")  # 应输出 cuda:0 或类似GPU设备
print(f"当前GPU显存占用：{torch.cuda.memory_allocated() / (1024**2):.2f} MB")


# --------------------------
# 2. 准备输入（图像+文本）
# --------------------------
# 示例1：图像描述（输入图像URL或本地路径，文本查询为"描述这张图片"）
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                # 可以替换为本地图像路径（如"./test.jpg"）或网络URL
                "image": "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg",
            },
            {"type": "text", "text": "描述这张图片的内容，包括物体、场景和细节。"},
        ],
    }
]

# 示例2：视觉问答（询问图像中的具体问题，取消注释即可使用）
# messages = [
#     {
#         "role": "user",
#         "content": [
#             {"type": "image", "image": "本地图像路径或URL"},
#             {"type": "text", "text": "图中有几个人？他们在做什么？"},
#         ],
#     }
# ]


# --------------------------
# 3. 处理输入并推理
# --------------------------
# 将消息转换为模型输入格式（tokenize + 构造输入张量）
inputs = processor.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,  # 自动添加生成提示（如"Assistant:"）
    return_dict=True,
    return_tensors="pt"  # 返回PyTorch张量
).to(model.device)  # 确保输入在GPU上

# 推理生成（控制生成长度等参数）
generated_ids = model.generate(
    **inputs,
    max_new_tokens=512,  # 最大生成 tokens 数（根据需求调整，越大回答越长）
    do_sample=True,      # 启用采样（生成更自然的回答）
    temperature=0.7,     # 采样温度（0-1，越小越确定，越大越多样）
    top_p=0.9            # 核采样参数
)

# 修剪生成结果（去掉输入部分，只保留模型生成的内容）
generated_ids_trimmed = [
    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]

# 解码为自然语言文本
output_text = processor.batch_decode(
    generated_ids_trimmed,
    skip_special_tokens=True,
    clean_up_tokenization_spaces=False
)[0]  # 取第一个结果（batch_size=1）


# --------------------------
# 4. 输出结果
# --------------------------
print("\n===== 模型回答 =====")
print(output_text)
print("\n===== 推理完成 =====")
print(f"推理后GPU显存占用：{torch.cuda.memory_allocated() / (1024**2):.2f} MB")