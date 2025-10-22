import socket
import threading

def listen_port(port):
    try:
        # 创建TCP套接字
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 绑定到所有网络接口（允许外网访问）和指定端口
        sock.bind(('0.0.0.0', port))
        # 开始监听（最多允许5个等待连接）
        sock.listen(5)
        print(f"端口 {port} 已启动监听（进程ID：{threading.get_ident()}）")
        # 保持监听状态（不处理连接，仅维持端口监听）
        while True:
            client_sock, addr = sock.accept()  # 阻塞等待连接（无需处理）
            client_sock.close()  # 收到连接后立即关闭（仅用于测试）
    except Exception as e:
        print(f"端口 {port} 监听失败：{e}")

if __name__ == "__main__":
    # 定义要监听的端口范围（例如8001-8010）
    start_port = 8000
    end_port = 8020
    # 为每个端口启动一个线程监听
    for port in range(start_port, end_port + 1):
        thread = threading.Thread(target=listen_port, args=(port,), daemon=True)
        thread.start()
    # 保持主程序运行（避免脚本退出）
    input("按任意键停止所有监听...\n")