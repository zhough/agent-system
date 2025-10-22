from aiohttp import web, ClientSession, WSMsgType
import asyncio

# 配置：路径前缀 -> 目标端口（根据你的应用修改）
# 三个应用的路径映射，避免冲突
# 正确的PATH_TO_PORT配置（重点改第一个应用的映射）
PATH_TO_PORT = {
    "/multimodal": 8080,   # 第一个应用：前缀为/multimodal，转发到8080端口
    "/api": 5000,    # 第二个应用：前缀为/api，转发到5000端口
    "/webapp": 8501  # Streamlit：前缀为/webapp，转发到8501端口
}

async def handle_http(request):
    """处理HTTP请求（包括流式响应和SSE）"""
    target_port = None
    target_path = request.path
    # 匹配路径前缀，确定目标端口
    for path_prefix, port in PATH_TO_PORT.items():
        if request.path.startswith(path_prefix):
            target_port = port
            # 移除路径前缀，拼接实际请求路径
            target_path = request.path[len(path_prefix):] or "/"
            break
    if not target_port:
        return web.Response(status=404, text="路径未配置")

    # 构建目标URL
    target_url = f"http://127.0.0.1:{target_port}{target_path}"

    # 转发HTTP请求（包括headers、方法、body）
    async with ClientSession() as session:
        async with session.request(
            method=request.method,
            url=target_url,
            headers=request.headers,
            data=await request.content.read(),
            allow_redirects=False
        ) as upstream_resp:
            # 构建响应对象，复制状态码和headers
            response = web.StreamResponse(
                status=upstream_resp.status,
                headers=upstream_resp.headers
            )
            await response.prepare(request)

            # 流式转发响应内容（核心：边接收边返回）
            async for data in upstream_resp.content.iter_any():
                if data:
                    await response.write(data)
                    await response.drain()  # 强制刷新，确保实时性
            return response

async def handle_websocket(request):
    """处理WebSocket请求（专门用于Streamlit）"""
    # 仅处理Streamlit路径的WebSocket
    if not request.path.startswith("/streamlit"):
        return web.Response(status=404)

    target_port = PATH_TO_PORT["/streamlit"]
    target_path = request.path[len("/streamlit"):] or "/"
    target_ws_url = f"ws://127.0.0.1:{target_port}{target_path}"

    # 升级为WebSocket连接
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # 连接到目标服务器的WebSocket
    async with ClientSession() as session:
        async with session.ws_connect(
            target_ws_url,
            headers=request.headers
        ) as upstream_ws:
            # 双向转发消息（客户端 <-> 目标服务器）
            async def forward_upstream():
                async for msg in upstream_ws:
                    if msg.type == WSMsgType.TEXT:
                        await ws.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws.send_bytes(msg.data)
                    elif msg.type == WSMsgType.CLOSED:
                        await ws.close()
                        break
                    elif msg.type == WSMsgType.ERROR:
                        break

            async def forward_client():
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        await upstream_ws.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await upstream_ws.send_bytes(msg.data)
                    elif msg.type == WSMsgType.CLOSED:
                        await upstream_ws.close()
                        break
                    elif msg.type == WSMsgType.ERROR:
                        break

            # 并发执行双向转发
            await asyncio.gather(forward_upstream(), forward_client())

    return ws

# 路由配置：WebSocket优先，其余HTTP请求走handle_http
app = web.Application()
app.router.add_route("*", "/{tail:.*}", handle_http)  # 匹配所有HTTP请求
app.router.add_route("GET", "/streamlit/{tail:.*}", handle_websocket)  # WebSocket专用

if __name__ == "__main__":
    # 监听8000端口，绑定公网接口（允许外网访问）
    web.run_app(app, host="0.0.0.0", port=8000)