
from aiohttp import web, ClientSession, WSMsgType
import asyncio
from config import Config

config = Config()

# 路径映射：前缀 -> 目标端口
PATH_TO_PORT = {
    "/multimodal": config.multimodal_port,   
    "/api": config.main_port,
    "/webapp": config.web_port,
    '/database':config.database_port,
    '/web':5002
}

# -------------------------- 新增：处理 /api 路径的 WebSocket 请求 --------------------------
async def handle_websocket_api(request):
    """专门处理 /api 路径的 WebSocket 请求，转发到 main.py 的 WebSocket 接口"""
    # 验证路径是否匹配 /api
    if not request.path.startswith("/api"):
        return web.Response(status=404, text="WebSocket 路径不支持")

    # 获取目标端口（main.py 的端口）
    target_port = PATH_TO_PORT["/api"]
    # 移除 /api 前缀，拼接实际 WebSocket 路径（假设 main.py 的 WebSocket 接口为 /ws）
    # 例如：小程序请求 /api/ws → 转发到 main.py 的 /ws
    target_path = request.path[len("/api"):] or "/ws"  # 默认为 /ws
    target_ws_url = f"ws://127.0.0.1:{target_port}{target_path}"

    # 与小程序建立 WebSocket 连接
    proxy_ws = web.WebSocketResponse()
    await proxy_ws.prepare(request)
    print(f"[WebSocket] 小程序连接 /api 路径，转发目标：{target_ws_url}")

    # 与 main.py 建立 WebSocket 连接
    async with ClientSession() as session:
        try:
            async with session.ws_connect(
                target_ws_url,
                headers=request.headers  # 转发原请求头（如认证信息）
            ) as main_ws:
                # 双向转发消息：小程序 ↔ main.py
                async def forward_from_main():
                    """将 main.py 的消息转发给小程序"""
                    async for msg in main_ws:
                        if msg.type == WSMsgType.TEXT:
                            await proxy_ws.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await proxy_ws.send_bytes(msg.data)
                        elif msg.type == WSMsgType.CLOSED:
                            await proxy_ws.close()
                            break
                        elif msg.type == WSMsgType.ERROR:
                            print(f"[main.py WebSocket 错误] {main_ws.exception()}")
                            break

                async def forward_to_main():
                    """将小程序的消息转发给 main.py"""
                    async for msg in proxy_ws:
                        if msg.type == WSMsgType.TEXT:
                            await main_ws.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await main_ws.send_bytes(msg.data)
                        elif msg.type == WSMsgType.CLOSED:
                            await main_ws.close()
                            break
                        elif msg.type == WSMsgType.ERROR:
                            print(f"[小程序 WebSocket 错误] {proxy_ws.exception()}")
                            break

                # 并发执行双向转发
                await asyncio.gather(forward_from_main(), forward_to_main())

        except Exception as e:
            print(f"[WebSocket 转发失败] 连接 main.py 错误：{e}")
            if not proxy_ws.closed:
                await proxy_ws.close(code=1011, message="服务器连接失败")

    return proxy_ws

# -------------------------- 原有 HTTP 处理逻辑（保持不变，兼容非 WebSocket 请求） --------------------------
async def handle_http(request):
    """处理非 WebSocket 的 HTTP 请求（如普通接口、SSE 等）"""
    target_port = None
    target_path = request.path
    # 匹配路径前缀，确定目标端口
    for path_prefix, port in PATH_TO_PORT.items():
        if request.path.startswith(path_prefix):
            target_port = port
            target_path = request.path[len(path_prefix):] or "/"
            break
    if not target_port:
        return web.Response(status=404, text="路径未配置")

    # 构建目标 URL
    target_url = f"http://127.0.0.1:{target_port}{target_path}"

    # 转发 HTTP 请求（支持流式响应）
    async with ClientSession() as session:
        async with session.request(
            method=request.method,
            url=target_url,
            headers=request.headers,
            data=await request.content.read(),
            allow_redirects=False
        ) as upstream_resp:
            response = web.StreamResponse(
                status=upstream_resp.status,
                headers=upstream_resp.headers
            )
            await response.prepare(request)

            # 流式转发内容
            async for data in upstream_resp.content.iter_any():
                if data:
                    await response.write(data)
                    await response.drain()
            return response

# -------------------------- 路由配置：优先处理 WebSocket 请求 --------------------------
async def handle_all(request):
    """统一入口：判断请求类型，分发到 WebSocket 或 HTTP 处理逻辑"""
    # 判断是否为 WebSocket 升级请求（通过 Upgrade 头）
    if request.headers.get("Upgrade", "").lower() == "websocket":
        # 仅 /api 路径走 WebSocket 转发
        if request.path.startswith("/api"):
            return await handle_websocket_api(request)
        else:
            return web.Response(status=400, text="仅 /api 路径支持 WebSocket")
    else:
        # 非 WebSocket 请求走 HTTP 转发
        return await handle_http(request)

# 注册统一路由
app = web.Application()
app.router.add_route("*", "/{tail:.*}", handle_all)  # 所有请求先经过 handle_all 分发

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=config.proxy_port)