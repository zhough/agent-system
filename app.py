import requests
import streamlit as st
import base64
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_image = None
# 1. 初始化Session State（新增标记位确保重绘）
if "messages" not in st.session_state:
    st.session_state.messages = []  # 存储所有历史消息（旧→新）
if "is_streaming" not in st.session_state:
    st.session_state.is_streaming = False  # 是否正在流式传输
if "current_stream_response" not in st.session_state:
    st.session_state.current_stream_response = ""  # 当前流式临时内容
if "stream_complete" not in st.session_state:
    st.session_state.stream_complete = False  # 标记流式是否已完成
if "user_id" not in st.session_state:
    st.session_state.user_id = "0042"  # 给一个默认ID
ANSWER = False
with st.sidebar:

    st.text_input(
        "请输入你的ID",
        key="user_id",  # 关键：将输入框的值与 session_state.user_id 绑定
        placeholder="例如: 0006"
    )
    #上传图像
    uploaded_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption="上传的图片",width=150)
        if not ANSWER:
            st.session_state.uploaded_image = uploaded_file
    else:
        ANSWER = False


# 2. 核心：st.chat_input实现回车发送
if prompt := st.chat_input("请输入你的问题："):
    if st.session_state.uploaded_image is not None:
        prompt = '<image>'+ prompt
    # 重置上一次的流式完成标记（避免影响新请求）
    st.session_state.stream_complete = False
    # 立即添加用户输入到历史消息（实时显示）
    st.session_state.messages.append({"role": "user", "content": prompt})
    # 初始化当前流式状态
    st.session_state.is_streaming = True
    st.session_state.current_stream_response = ""

# 3. 先渲染所有历史消息（旧→新，确保上一次完整响应能显示）
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # if msg["role"] == "user" and st.session_state.uploaded_image:
        #     st.image(st.session_state.uploaded_image, caption="上传的图片",width=150)
            # 上传后可以清空，避免重复显示
            #st.session_state.uploaded_image = None
# 4. 处理流式传输：关键优化“不提前清空占位符，直到历史消息重绘”
if st.session_state.is_streaming:
    # 获取最新用户输入
    latest_user_query = st.session_state.messages[-1]["content"]
    # 创建流式占位符（固定在历史消息下方）
    stream_placeholder = st.empty()
    url = "http://127.0.0.1:5000/generate"
    #url = 'http://172.30.154.81:5000/generate'
    payload = {"user_query": latest_user_query, "ID": st.session_state.user_id}
    # 如果有上传的图片，转为 Base64 传到后端
    if st.session_state.uploaded_image:
        img_bytes = st.session_state.uploaded_image.getvalue()
        #print(f'img_bytes{img_bytes}')
        payload["image_base64"] = base64.b64encode(img_bytes).decode("utf-8")

    try:
        with requests.post(url, json=payload, stream=True) as response:
            response.raise_for_status()
            # 逐段接收并更新流式内容
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    st.session_state.current_stream_response += chunk
                    # 实时渲染流式内容（带助手头像）
                    with stream_placeholder.chat_message("assistant"):
                        st.markdown(st.session_state.current_stream_response)
        
        # 🌟 流式结束：先添加完整响应到历史消息，再标记“流式完成”
        st.session_state.messages.append({
            "role": "assistant", 
            "content": st.session_state.current_stream_response
        })
        st.session_state.stream_complete = True  # 标记完成，触发后续重绘
        st.session_state.is_streaming = False    # 关闭流式状态
        st.session_state.current_stream_response = ""  # 重置临时内容
        st.session_state.uploaded_image = None
        ANSWER = True

    except requests.exceptions.RequestException as e:
        # 异常处理：同样先添加错误信息到历史，再标记完成
        error_msg = f"请求失败：{str(e)}"
        with stream_placeholder.chat_message("assistant"):
            st.markdown(error_msg)
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        st.session_state.stream_complete = True
        st.session_state.is_streaming = False
        st.session_state.current_stream_response = ""

# 🌟 关键修复：流式完成后，强制触发页面重绘（显示刚添加的完整响应）
if st.session_state.stream_complete:
    # 通过更新一个“无意义”的Session State键，触发Streamlit重绘
    st.session_state["_force_rerun"] = st.session_state.get("_force_rerun", 0) + 1
    # 重置完成标记，避免重复重绘
    st.session_state.stream_complete = False