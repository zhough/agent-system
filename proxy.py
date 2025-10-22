from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

# 配置：外部路径 -> 内部端口（根据你的应用修改）
# 例如：访问 http://你的IP:8000/app1 → 转发到内部 5000 端口
#       访问 http://你的IP:8000/app2 → 转发到内部 8501 端口
ROUTES = {
    "/main": "http://127.0.0.1:5000",  # 内部5000端口的应用
    "/app": "http://127.0.0.1:8501" ,  # 内部8501端口的Streamlit应用
    "/multimodal": "http://127.0.0.1:8080"
}

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 匹配路由，转发请求
        for path, target in ROUTES.items():
            if self.path.startswith(path):
                target_url = target + self.path[len(path):]
                try:
                    response = requests.get(target_url, timeout=10)
                    self.send_response(response.status_code)
                    for k, v in response.headers.items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(response.content)
                    return
                except Exception as e:
                    self.send_response(502)
                    self.end_headers()
                    self.wfile.write(f"Proxy error: {str(e)}".encode())
                    return
        # 未匹配到路由
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not found")

if __name__ == "__main__":
    # 代理服务运行在 8000 端口（已被防火墙允许）
    server = HTTPServer(("0.0.0.0", 8000), ProxyHandler)
    print("Proxy running on http://0.0.0.0:8000")
    server.serve_forever()