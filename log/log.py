import logging


# 配置日志
def setup_logging():
    # 设置日志级别为DEBUG，这样所有DEBUG及以上级别的日志都会被记录
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 移除所有已存在的处理器（防止默认的控制台输出）
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # 创建文件处理器，将日志写入文件
    file_handler = logging.FileHandler('app.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)  # 设置文件处理器的日志级别
    
    # 定义日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # 为日志器添加文件处理器
    logger.addHandler(file_handler)

setup_logging()

