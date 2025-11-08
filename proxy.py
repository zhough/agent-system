import os
from aiohttp import web, ClientSession, WSMsgType
import asyncio
from config import Config

config = Config()

# 路径映射：前缀 -> 目标端口
PATH_TO_PORT = {
    "/multimodal": config.multimodal_port,
    "/api": config.main_port,
    "/webapp": config.web_port,
    '/database': config.database_port,
    # '/web':5002  # 我们不再需要这个转发规则了
}

# 前端静态文件目录 (假设你的 Vue 项目打包后的 dist 目录路径是这个)
# 请根据你的实际目录结构修改！
STATIC_WEB_ROOT = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist') 

async def handle_http(request):
    """处理非 WebSocket 的 HTTP 请求"""
    # --- 新增逻辑：优先处理 /web 路径的静态文件 ---
    if request.path.startswith("/web"):
        # 构造相对于 dist 目录的文件路径
        # 例如: /web/index.html -> dist/index.html
        #      /web/assets/app.js -> dist/assets/app.js
        file_path = request.path[len("/web"):] or "index.html"
        full_path = os.path.abspath(os.path.join(STATIC_WEB_ROOT, file_path.lstrip('/')))

        # 安全检查：防止路径穿越攻击
        if not full_path.startswith(os.path.abspath(STATIC_WEB_ROOT)):
            return web.Response(status=403, text="Forbidden")

        # 如果文件存在，直接返回文件
        if os.path.exists(full_path) and os.path.isfile(full_path):
            return web.FileResponse(full_path)
        else:
            # 如果文件不存在，很可能是 Vue 的路由路径，返回 index.html 让 Vue Router 处理
            # 例如: /web/about -> dist/index.html
            index_path = os.path.join(STATIC_WEB_ROOT, "index.html")
            if os.path.exists(index_path):
                return web.FileResponse(index_path)
            else:
                return web.Response(status=404, text="Frontend file not found")

    # --- 原有逻辑：处理 API 路径转发 ---
    target_port = None
    target_path = request.path
    # 匹配路径前缀，确定目标端口
    for path_prefix, port in PATH_TO_PORT.items():
        if request.path.startswith(path_prefix):
            target_port = port
            # 对于所有 API 路径，都剥离前缀后转发
            target_path = request.path[len(path_prefix):] or "/"
            break
    if not target_port:
        return web.Response(status=404, text="Path not configured")

    # 构建目标 URL
    target_url = f"http://127.0.0.1:{target_port}{target_path}"

    # 转发 HTTP 请求
    async with ClientSession() as session:
        async with session.request(
            method=request.method,
            url=target_url,
            headers=request.headers,
            data=await request.content.read(),
            allow_redirects=False
        ) as upstream_resp:
            # 复制响应头
            response_headers = dict(upstream_resp.headers)
            # 移除可能导致问题的 Connection 头
            response_headers.pop('Connection', None)

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

# ... (handle_websocket_api, handle_all, app 定义等其他代码保持不变) ...

# 注册统一路由
app = web.Application()
app.router.add_route("*", "/{tail:.*}", handle_all)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=config.proxy_port)