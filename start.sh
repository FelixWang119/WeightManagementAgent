#!/bin/bash

# 体重管理助手 - 快速启动脚本

APP_NAME="weight_management"
PID_FILE="/tmp/${APP_NAME}.pid"
LOG_FILE="logs/app.log"

# 检查是否已运行
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "应用已在运行中 (PID: $PID)"
            exit 0
        fi
    fi
}

# 停止应用
stop_app() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "正在停止应用 (PID: $PID)..."
            kill "$PID"
            rm -f "$PID_FILE"
            echo "✅ 应用已停止"
        else
            echo "应用未在运行"
            rm -f "$PID_FILE"
        fi
    else
        echo "未找到PID文件，应用可能未运行"
    fi
}

# 根据命令行参数执行
case "${1:-start}" in
    start)
        echo "🚀 体重管理助手 - 启动脚本"
        echo "============================"

        check_running

        # 检查 Python 版本
        echo "📍 检查 Python 环境..."
        python3 --version || { echo "❌ 未找到 Python3"; exit 1; }

        # 检查并创建虚拟环境（如果需要）
        if [ ! -d "venv" ]; then
            echo "📦 创建虚拟环境..."
            python3 -m venv venv
        fi

        # 激活虚拟环境
        echo "🔄 激活虚拟环境..."
        source venv/bin/activate || . venv/bin/activate

        # 安装依赖
        echo "📥 安装依赖..."
        pip install -q -r requirements.txt --only-binary :all:

        # 检查 .env 文件
        if [ ! -f ".env" ]; then
            echo "⚠️  未找到 .env 文件，复制示例文件..."
            cp .env.example .env
            echo "⚠️  请编辑 .env 文件，填入 OPENAI_API_KEY 等必要配置"
        fi

        # 创建必要的目录
        echo "📁 创建必要目录..."
        mkdir -p logs uploads

        # 启动应用（后台运行）
        echo ""
        echo "✅ 准备就绪，正在启动 FastAPI 应用..."
        echo "📍 访问地址: http://localhost:8000"
        echo "📚 API 文档: http://localhost:8000/docs"
        echo ""

        nohup python main.py > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        echo "✅ 应用已启动 (PID: $(cat $PID_FILE))"
        echo "📝 日志文件: $LOG_FILE"
        ;;

    stop)
        stop_app
        ;;

    restart)
        stop_app
        sleep 1
        $0 start
        ;;

    status)
        check_running
        echo "应用未运行"
        ;;

    log)
        tail -f "$LOG_FILE"
        ;;

    *)
        echo "用法: $0 {start|stop|restart|status|log}"
        exit 1
        ;;
esac
