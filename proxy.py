from aiohttp import web, ClientSession
import asyncio
from config import Config
import mimetypes

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
    
    print(f"[Vite代理] 转发: {request.method} {request.path} -> {target_url}")
    
    async with ClientSession() as session:
        try:
            # 准备请求数据
            request_data = await request.read() if request.method in ['POST', 'PUT', 'PATCH'] else None
            
            async with session.request(
                method=request.method,
                url=target_url,
                headers=dict(request.headers),
                data=request_data,
                allow_redirects=False
            ) as upstream_resp:
                
                # 获取内容类型
                content_type = upstream_resp.headers.get('Content-Type', '')
                
                # 处理静态资源 - 确保正确的内容类型
                if request.path.endswith('.css'):
                    content_type = 'text/css; charset=utf-8'
                elif request.path.endswith('.js'):
                    content_type = 'application/javascript; charset=utf-8'
                elif request.path.endswith('.png'):
                    content_type = 'image/png'
                elif request.path.endswith('.jpg') or request.path.endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif request.path.endswith('.svg'):
                    content_type = 'image/svg+xml'
                
                # 复制响应头
                headers = dict(upstream_resp.headers)
                
                # 更新内容类型
                if content_type:
                    headers['Content-Type'] = content_type
                
                # 确保有正确的内容长度
                if 'Content-Length' not in headers:
                    content = await upstream_resp.read()
                    headers['Content-Length'] = str(len(content))
                    response = web.Response(
                        body=content,
                        status=upstream_resp.status,
                        headers=headers
                    )
                else:
                    response = web.StreamResponse(
                        status=upstream_resp.status,
                        headers=headers
                    )
                    await response.prepare(request)
                    
                    # 流式转发内容
                    async for data in upstream_resp.content.iter_any():
                        if data:
                            await response.write(data)
                            
                return response
                        
        except Exception as e:
            print(f"[Vite代理错误] 无法连接到Vite开发服务器: {e}")
            return web.Response(
                status=502, 
                text=f"开发服务器连接失败: {str(e)}"
            )

async def handle_backend_service(request, path_prefix, port):
    """处理后端服务的HTTP请求"""
    target_path = request.path[len(path_prefix):] or "/"
    target_url = f"http://127.0.0.1:{port}{target_path}"
    
    print(f"[后端代理] 转发 {request.method} {request.path} -> {target_url}")
    
    async with ClientSession() as session:
        request_data = await request.read()
        
        async with session.request(
            method=request.method,
            url=target_url,
            headers=dict(request.headers),
            data=request_data,
            allow_redirects=False
        ) as upstream_resp:
            response = web.StreamResponse(
                status=upstream_resp.status,
                headers=dict(upstream_resp.headers)
            )
            await response.prepare(request)

            async for data in upstream_resp.content.iter_any():
                if data:
                    await response.write(data)
            return response

async def handle_all(request):
    """统一入口：根据路径前缀分发请求"""
    path = request.path
    
    # 根据路径前缀分发到对应的服务
    for path_prefix, port in PATH_TO_PORT.items():
        if path.startswith(path_prefix):
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
    print(f"  访问地址: http://0.0.0.0:{config.proxy_port}")
    
    web.run_app(app, host="0.0.0.0", port=config.proxy_port)