#!/bin/bash

# 体重管理助手 - 快速启动脚本

echo "🚀 体重管理助手 - 启动脚本"
echo "============================"

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

# 启动应用
echo ""
echo "✅ 准备就绪，正在启动 FastAPI 应用..."
echo "📍 访问地址: http://localhost:8000"
echo "📚 API 文档: http://localhost:8000/docs"
echo ""

python main.py
