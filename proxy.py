from aiohttp import web, ClientSession
import asyncio
from config import Config

config = Config()

# 路径映射：前缀 -> 目标端口
PATH_TO_PORT = {
    "/multimodal": config.multimodal_port,   
    "/api": config.main_port,
    "/webapp": config.web_port,
    '/database': config.database_port
}

# Vite开发服务器配置
VITE_DEV_SERVER = "http://127.0.0.1:5002"

async def handle_vite_dev_server(request):
    """专门处理Vite开发服务器的请求"""
    target_url = f"{VITE_DEV_SERVER}{request.path}"
    
    async with ClientSession() as session:
        try:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=request.headers,
                data=await request.content.read() if request.method in ['POST', 'PUT', 'PATCH'] else None,
                allow_redirects=False
            ) as upstream_resp:
                # 复制响应头，但移除一些可能冲突的头部
                headers = dict(upstream_resp.headers)
                headers.pop('Content-Encoding', None)
                headers.pop('Transfer-Encoding', None)
                
                response = web.StreamResponse(
                    status=upstream_resp.status,
                    headers=headers
                )
                await response.prepare(request)

                # 流式转发内容
                async for data in upstream_resp.content.iter_any():
                    if data:
                        await response.write(data)
                        await response.drain()
                return response
        except Exception as e:
            print(f"[Vite代理错误] 无法连接到Vite开发服务器: {e}")
            return web.Response(status=502, text="开发服务器未启动")

async def handle_backend_service(request, path_prefix, port):
    """处理后端服务的HTTP请求"""
    target_path = request.path[len(path_prefix):] or "/"
    target_url = f"http://127.0.0.1:{port}{target_path}"
    
    print(f"[代理] 转发 {request.method} {request.path} -> {target_url}")
    
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

            async for data in upstream_resp.content.iter_any():
                if data:
                    await response.write(data)
                    await response.drain()
            return response

async def handle_all(request):
    """统一入口：根据路径前缀分发请求"""
    # 根据路径前缀分发到对应的服务
    for path_prefix, port in PATH_TO_PORT.items():
        if request.path.startswith(path_prefix):
            return await handle_backend_service(request, path_prefix, port)
    
    # 没有匹配的路径前缀，转发到Vite开发服务器
    return await handle_vite_dev_server(request)

# 创建应用并配置路由
app = web.Application()
app.router.add_route("*", "/{tail:.*}", handle_all)

if __name__ == "__main__":
    print(f"启动代理服务器在端口 {config.proxy_port}")
    print("路径映射配置:")
    for path, port in PATH_TO_PORT.items():
        print(f"  {path} -> {port}")
    print(f"  其他路径 -> Vite开发服务器 (5002)")
    
    web.run_app(app, host="0.0.0.0", port=config.proxy_port)