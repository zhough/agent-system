#!/bin/bash

# 定义需要创建的screen会话及对应的命令
# 格式："会话名 conda环境 执行命令"
sessions=(
    "main agent 'python main.py'"
    "proxy agent 'python proxy.py'"
    "web agent 'python web_app.py'"
    "multimodal multimodal 'python multimodal/infer.py'"
)

# 循环创建每个screen会话
for session in "${sessions[@]}"; do
    # 解析会话名、conda环境、执行命令
    read -r name env cmd <<< "$session"
    
    echo "创建screen会话: $name"
    
    # 1. 创建并后台启动screen会话
    screen -S "$name" -dm
    
    # 2. 向会话发送命令：激活conda环境（需先确保conda初始化完成）
    # 注意：如果是bash，可能需要先source ~/.bashrc加载conda；zsh则是~/.zshrc
    screen -S "$name" -X stuff "conda activate $env\n"
    
    # 3. 向会话发送执行命令
    screen -S "$name" -X stuff "$cmd\n"
    
    # 4. 自动发送Ctrl+A+D挂起会话
    screen -S "$name" -X stuff $'\001d'  # \001是Ctrl+A的ASCII码
    
    echo "会话 $name 已启动并挂起（环境：$env，命令：$cmd）"
done

echo "所有会话创建完成！"