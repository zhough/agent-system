from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

ROUTES = {
    "/main": "http://127.0.0.1:5000/generate",
    "/app": "http://127.0.0.1:8501",
    "/multimodal": "http://127.0.0.1:8080/chat"
}

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._proxy_request("GET")

    def do_POST(self):
        self._proxy_request("POST")

    def _proxy_request(self, method):
        target_url = None
        for path_prefix, service_base in ROUTES.items():
            if self.path.startswith(path_prefix):
                target_url = f"{service_base}{self.path[len(path_prefix):]}"
                break

        if not target_url:
            self.send_response(404)
            self.end_headers()
            self.wfile.write("Not found: 未匹配到对应服务路由")
            return

        try:
            headers = self._get_forward_headers()
            if method == "POST":
                content_length = int(self.headers.get("Content-Length", 0))
                post_data = self.rfile.read(content_length) if content_length > 0 else None
                response = requests.post(
                    target_url,
                    data=post_data,
                    headers=headers,
                    stream=True,  # 启用流式响应，关键！
                    timeout=15
                )
            else:
                response = requests.get(
                    target_url,
                    headers=headers,
                    stream=True,  # 启用流式响应，关键！
                    timeout=15
                )

            # 转发响应状态码和头（保留分块编码头）
            self.send_response(response.status_code)
            for key, value in response.headers.items():
                # 不删除 Transfer-Encoding 头，保留分块编码信息
                if key.lower() != "connection":
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()

            # 逐块转发内容（保留分块格式）
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:  # 忽略空块（但通常不会有）
                    self.wfile.write(chunk)

        except requests.exceptions.RequestException as e:
            self.send_response(502)
            self.end_headers()
            error_msg = f"代理请求失败：{str(e)}".encode()
            self.wfile.write(error_msg)

    def _get_forward_headers(self):
        forward_headers = {}
        for key, value in self.headers.items():
            if key.lower() not in ["host", "connection", "proxy-connection"]:
                forward_headers[key] = value
        return forward_headers

    def log_message(self, format, *args):
        return  # 禁用日志

if __name__ == "__main__":
    server_address = ("0.0.0.0", 8000)
    httpd = HTTPServer(server_address, ProxyHandler)
    print(f"代理服务已启动，监听：http://{server_address[0]}:{server_address[1]}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n代理服务停止")
        httpd.server_close()