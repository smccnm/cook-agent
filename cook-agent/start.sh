#!/bin/bash
# 美食排菜 Agent 启动脚本（Linux/Mac）

echo ""
echo "====================================="
echo "  🍳 美食排菜 Agent 启动脚本"
echo "====================================="
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "🔧 虚拟环境不存在，正在创建..."
    python3 -m venv venv
    echo "✅ 虚拟环境创建完成"
fi

# 激活虚拟环境
echo "🚀 激活虚拟环境..."
source venv/bin/activate

# 检查依赖
echo "📦 检查依赖..."
if ! pip list | grep -q "fastapi"; then
    echo "📥 安装依赖..."
    pip install -r requirements.txt
    echo "✅ 依赖安装完成"
else
    echo "✅ 依赖已齐全"
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件"
    echo "📋 正在复制 .env.example -> .env"
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，填入您的 API Key"
    echo ""
    read -p "按 Enter 键继续..."
fi

# 启动后端和前端
echo ""
echo "🌐 启动后端服务 (FastAPI)..."
echo "📍 API 地址: http://localhost:8000"
echo "📚 文档地址: http://localhost:8000/docs"
echo ""

# 在后台启动后端
python main.py &
BACKEND_PID=$!

# 等待后端启动
sleep 3

echo ""
echo "🎨 启动前端应用 (Streamlit)..."
echo "🌐 页面地址: http://localhost:8501"
echo ""

# 前台启动前端
streamlit run app.py

# 清理后端进程
kill $BACKEND_PID 2>/dev/null || true
