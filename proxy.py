from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

# 路由配置：外部访问路径 -> 内部服务地址
ROUTES = {
    "/main": "http://127.0.0.1:5000",        # 内部5000端口服务
    "/app": "http://127.0.0.1:8501",         # 内部8501端口Streamlit服务
    "/multimodal": "http://127.0.0.1:8080"   # 内部8080端口服务
}

class ProxyHandler(BaseHTTPRequestHandler):
    """代理请求处理器，支持GET和POST方法"""
    
    def do_GET(self):
        """处理GET请求"""
        self._proxy_request("GET")

    def do_POST(self):
        """处理POST请求"""
        self._proxy_request("POST")

    def _proxy_request(self, method):
        """
        通用代理逻辑：转发GET/POST请求到对应内部服务
        :param method: 请求方法（"GET" 或 "POST"）
        """
        # 匹配路由规则
        target_url = None
        for path_prefix, service_base in ROUTES.items():
            if self.path.startswith(path_prefix):
                # 拼接完整目标URL（内部服务地址 + 路径后缀）
                target_url = f"{service_base}{self.path[len(path_prefix):]}"
                break

        if not target_url:
            # 未匹配到路由，返回404
            self.send_response(404)
            self.end_headers()
            self.wfile.write("Not found: 未匹配到对应服务路由")
            return

        try:
            # 处理请求参数（POST需要读取请求体）
            headers = self._get_forward_headers()
            if method == "POST":
                # 读取POST请求体
                content_length = int(self.headers.get("Content-Length", 0))
                post_data = self.rfile.read(content_length) if content_length > 0 else None
                response = requests.post(
                    target_url,
                    data=post_data,
                    headers=headers,
                    timeout=15  # 超时时间15秒
                )
            else:  # GET请求
                response = requests.get(
                    target_url,
                    headers=headers,
                    timeout=15
                )

            # 转发响应给客户端
            self.send_response(response.status_code)
            self._send_forward_headers(response.headers)
            self.end_headers()
            self.wfile.write(response.content)

        except requests.exceptions.RequestException as e:
            # 代理过程出错（如连接失败、超时等）
            self.send_response(502)
            self.end_headers()
            error_msg = f"代理请求失败：{str(e)}".encode()
            self.wfile.write(error_msg)

    def _get_forward_headers(self):
        """提取需要转发的请求头（过滤掉代理不需要的头）"""
        forward_headers = {}
        for key, value in self.headers.items():
            # 过滤掉不适合转发的头（如主机名、连接控制等）
            if key.lower() not in ["host", "connection", "proxy-connection"]:
                forward_headers[key] = value
        return forward_headers

    def _send_forward_headers(self, response_headers):
        """转发响应头（过滤可能导致客户端连接异常的头）"""
        for key, value in response_headers.items():
            # 过滤掉 Connection 头，避免客户端提前关闭连接
            if key.lower() != "connection":
                self.send_header(key, value)
        # 显式设置连接为关闭（避免长连接导致的问题）
        self.send_header("Connection", "close")

    # 禁用默认日志（可选，减少终端输出干扰）
    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    # 代理服务绑定到所有网络接口的8000端口
    server_address = ("0.0.0.0", 8000)
    httpd = HTTPServer(server_address, ProxyHandler)
    print(f"代理服务已启动，监听地址：http://{server_address[0]}:{server_address[1]}")
    print(f"路由配置：{ROUTES}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n用户中断，代理服务停止")
        httpd.server_close()