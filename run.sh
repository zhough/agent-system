#!/bin/bash


source ~/.bashrc


sessions=(
    "main agent python main.py"
    "proxy agent python proxy.py"
    "web agent python web_app.py"
    "multimodal multimodal python multimodal/infer.py"
)

# 3. 循环创建会话
for session in "${sessions[@]}"; do
    read -r name env cmd <<< "$session"  # 直接解析，无引号
    
    echo "创建screen会话: $name"
    
    # 创建会话并后台运行
    screen -S "$name" -dm
    
    # 发送命令：加载配置 → 激活环境 → 执行脚本
    screen -S "$name" -X stuff "source ~/.bashrc\n"  # 确保conda生效
    screen -S "$name" -X stuff "conda activate $env\n"
    screen -S "$name" -X stuff "$cmd\n"  # 执行命令（无引号）
    
    # 自动挂起（Ctrl+A+D）
    screen -S "$name" -X stuff $'\001d'
    
    echo "会话 $name 已启动"
done

echo "所有会话创建完成！"