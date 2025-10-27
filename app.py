import requests
import streamlit as st
import base64
from config import Config
config = Config()
# 1. 初始化Session State（新增image_used跟踪图像是否已使用）
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_image = None
if "messages" not in st.session_state:
    st.session_state.messages = []  # 存储所有历史消息（旧→新）
if "is_streaming" not in st.session_state:
    st.session_state.is_streaming = False  # 是否正在流式传输
if "current_stream_response" not in st.session_state:
    st.session_state.current_stream_response = ""  # 当前流式临时内容
if "stream_complete" not in st.session_state:
    st.session_state.stream_complete = False  # 标记流式是否已完成
if "user_id" not in st.session_state:
    st.session_state.user_id = "0042"  # 默认ID
if "image_used" not in st.session_state:  # 新增：标记当前图像是否已用过
    st.session_state.image_used = False  


with st.sidebar:
    # 用户ID输入
    st.text_input(
        "请输入你的ID",
        key="user_id",
        placeholder="例如: 0006"
    )
    
    # 上传图像逻辑
    uploaded_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="上传的图片", width=150)
        # 新上传图像时：更新图像并重置“已使用”标记（关键）
        st.session_state.uploaded_image = uploaded_file
        st.session_state.image_used = False  # 新图像未使用过
    else:
        # 未上传/清除图像时：重置图像和“已使用”标记
        st.session_state.uploaded_image = None
        st.session_state.image_used = False  


# 2. 处理用户输入（chat_input回车发送）
if prompt := st.chat_input("请输入你的问题："):
    # 仅当“存在图像且未使用过”时，才添加<image>标记（核心逻辑）
    if st.session_state.uploaded_image is not None and not st.session_state.image_used:
        prompt = '<image>' + prompt
        st.session_state.image_used = True  # 标记为已使用，后续对话不再添加
    
    # 重置流式状态
    st.session_state.stream_complete = False
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.is_streaming = True
    st.session_state.current_stream_response = ""


# 3. 渲染所有历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# 4. 处理流式传输
if st.session_state.is_streaming:
    latest_user_query = st.session_state.messages[-1]["content"]
    stream_placeholder = st.empty()
    #url = "http://127.0.0.1:5000/generate"
    url = config.main_url
    payload = {"user_query": latest_user_query, "ID": st.session_state.user_id}
    
    # 若有图像，携带Base64（即使已使用，仍传给后端但不加<image>标记）
    if st.session_state.uploaded_image:
        img_bytes = st.session_state.uploaded_image.getvalue()
        payload["image_base64"] = base64.b64encode(img_bytes).decode("utf-8")

    try:
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    st.session_state.current_stream_response += chunk
                    with stream_placeholder.chat_message("assistant"):
                        st.markdown(st.session_state.current_stream_response)
        
        # 流式结束：更新历史消息
        st.session_state.messages.append({
            "role": "assistant", 
            "content": st.session_state.current_stream_response
        })
        st.session_state.stream_complete = True
        st.session_state.is_streaming = False
        st.session_state.current_stream_response = ""

    except requests.exceptions.RequestException as e:
        error_msg = f"请求失败：{str(e)}"
        with stream_placeholder.chat_message("assistant"):
            st.markdown(error_msg)
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        st.session_state.stream_complete = True
        st.session_state.is_streaming = False
        st.session_state.current_stream_response = ""


# 5. 强制重绘
if st.session_state.stream_complete:
    st.session_state["_force_rerun"] = st.session_state.get("_force_rerun", 0) + 1
    st.session_state.stream_complete = False



