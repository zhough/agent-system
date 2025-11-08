from aiohttp import web, ClientSession, WSMsgType
import asyncio
from config import Config
import os # 新增：导入 os 模块用于处理静态文件路径

config = Config()

# 路径映射：前缀 -> 目标端口
PATH_TO_PORT = {
    "/multimodal": config.multimodal_port,
    "/api": config.main_port,
    "/webapp": config.web_port,
    '/database': config.database_port,
    '/web': config.web_port, # 假设你的前端Vite服务运行在 config.web_port (5002)
}

# 新增配置：前端静态文件目录 (如果是生产环境，请指向打包后的 dist 目录)
# 开发环境可以直接指向 Vite 的根目录，但更推荐使用 Vite 的开发服务器
# 这里我们假设你在生产环境，已将前端打包到 'frontend/dist' 目录
STATIC_WEB_ROOT = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')

# -------------------------- WebSocket 处理逻辑 (保持不变) --------------------------
async def handle_websocket_api(request):
    # ... (你的原始代码，无需修改)
    if not request.path.startswith("/api"):
        return web.Response(status=404, text="WebSocket 路径不支持")

    target_port = PATH_TO_PORT["/api"]
    target_path = request.path[len("/api"):] or "/ws"
    target_ws_url = f"ws://127.0.0.1:{target_port}{target_path}"

    proxy_ws = web.WebSocketResponse()
    await proxy_ws.prepare(request)
    print(f"[WebSocket] 小程序连接 /api 路径，转发目标：{target_ws_url}")

    async with ClientSession() as session:
        try:
            async with session.ws_connect(
                target_ws_url,
                headers=request.headers
            ) as main_ws:
                async def forward_from_main():
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

                await asyncio.gather(forward_from_main(), forward_to_main())

        except Exception as e:
            print(f"[WebSocket 转发失败] 连接 main.py 错误：{e}")
            if not proxy_ws.closed:
                await proxy_ws.close(code=1011, message="服务器连接失败")

    return proxy_ws

# -------------------------- HTTP 处理逻辑 (核心修改在这里) --------------------------
async def handle_http(request):
    """处理非 WebSocket 的 HTTP 请求"""
    target_port = None
    target_path = request.path

    # --- 核心修改开始 ---
    # 1. 优先处理 /web 路径的静态文件 (生产环境)
    if request.path.startswith("/web"):
        # 检查静态文件目录是否存在
        if os.path.exists(STATIC_WEB_ROOT) and os.path.isdir(STATIC_WEB_ROOT):
            # 构造相对于 dist 目录的文件路径
            relative_path = request.path[len("/web"):] or "index.html"
            full_path = os.path.join(STATIC_WEB_ROOT, relative_path.lstrip('/'))

            # 安全检查
            if not os.path.abspath(full_path).startswith(os.path.abspath(STATIC_WEB_ROOT)):
                return web.Response(status=403, text="Forbidden")

            # 如果文件存在，直接返回
            if os.path.exists(full_path) and os.path.isfile(full_path):
                return web.FileResponse(full_path)
            else:
                # 前端路由，返回 index.html
                index_file_path = os.path.join(STATIC_WEB_ROOT, "index.html")
                if os.path.exists(index_file_path):
                    return web.FileResponse(index_file_path)

        # 2. 如果静态文件目录不存在，或者在开发环境，则转发请求到 Vite 开发服务器
        # 确保 PATH_TO_PORT 中有 '/web' 的映射
        if '/web' in PATH_TO_PORT:
            target_port = PATH_TO_PORT['/web']
            # 关键点：不剥离 '/web' 前缀，完整转发
            target_path = request.path
            # --- 核心修改结束 ---

    # 3. 处理其他 API 路径 (保持原有的剥离前缀逻辑)
    if not target_port:
        for path_prefix, port in PATH_TO_PORT.items():
            # 确保 '/web' 不会进入这个循环，因为我们上面已经处理了
            if path_prefix != '/web' and request.path.startswith(path_prefix):
                target_port = port
                target_path = request.path[len(path_prefix):] or "/"
                break

    if not target_port:
        return web.Response(status=404, text="路径未配置")

    target_url = f"http://127.0.0.1:{target_port}{target_path}"
    print(f"[HTTP Proxy] {request.method} {request.path} -> {target_url}") # 新增：打印转发日志，方便调试

    # 转发 HTTP 请求 (保持不变)
    async with ClientSession() as session:
        try:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=request.headers,
                data=await request.content.read(),
                allow_redirects=False
            ) as upstream_resp:
                response_headers = dict(upstream_resp.headers)
                response_headers.pop('Connection', None) # 移除可能导致问题的头

                response = web.StreamResponse(
                    status=upstream_resp.status,
                    headers=response_headers
                )
                await response.prepare(request)

                async for data in upstream_resp.content.iter_any():
                    if data:
                        await response.write(data)
                        await response.drain()
                return response
        except Exception as e:
            print(f"[HTTP Proxy Error] Failed to connect to {target_url}: {e}")
            return web.Response(status=502, text="Bad Gateway: Could not connect to upstream service")

# -------------------------- 路由分发逻辑 (保持不变) --------------------------
async def handle_all(request):
    """统一入口：判断请求类型，分发到 WebSocket 或 HTTP 处理逻辑"""
    if request.headers.get("Upgrade", "").lower() == "websocket":
        if request.path.startswith("/api"):
            return await handle_websocket_api(request)
        else:
            return web.Response(status=400, text="仅 /api 路径支持 WebSocket")
    else:
        return await handle_http(request)

# 注册统一路由
app = web.Application()
app.router.add_route("*", "/{tail:.*}", handle_all)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=config.proxy_port)