#!/bin/bash

# 解决conda在screen中无法识别的问题：先加载bash配置（根据你的终端类型选择）
# 如果你用的是bash，用这行；如果是zsh，替换为source ~/.zshrc
BASH_PROFILE="source ~/.bashrc"

# 定义会话：会话名、conda环境、执行命令（命令不要加单引号！）
sessions=(
    "main agent 'python main.py'"  # 这里的单引号是为了脚本解析，实际执行时会去掉
    "proxy agent 'python proxy.py'"
    "web agent 'python web_app.py'"
    "multimodal multimodal 'python multimodal/infer.py'"
)

for session in "${sessions[@]}"; do
    # 解析会话名、环境、命令（注意：命令外的单引号会被自动去除）
    read -r name env cmd <<< "$(echo "$session" | sed "s/'//g")"  # 关键：去掉命令的单引号
    
    echo "创建会话: $name"
    
    # 1. 创建screen会话并后台运行
    screen -S "$name" -dm
    
    # 2. 加载bash配置（确保conda可用）
    screen -S "$name" -X stuff "$BASH_PROFILE\n"
    
    # 3. 激活conda环境
    screen -S "$name" -X stuff "conda activate $env\n"
    
    # 4. 执行命令（此时cmd已经没有单引号了）
    screen -S "$name" -X stuff "$cmd\n"
    
    # 5. 自动挂起会话（Ctrl+A+D）
    screen -S "$name" -X stuff $'\001d'
    
    echo "会话 $name 启动完成（环境：$env，命令：$cmd）"
done

echo "所有会话创建成功！"