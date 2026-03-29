@echo off
REM 美食排菜 Agent 启动脚本（Windows）

echo.
echo =====================================
echo   🍳 美食排菜 Agent 启动脚本
echo =====================================
echo.

REM 检查虚拟环境
if not exist "venv" (
    echo 🔧 虚拟环境不存在，正在创建...
    python -m venv venv
    echo ✅ 虚拟环境创建完成
)

REM 激活虚拟环境
echo 🚀 激活虚拟环境...
call venv\Scripts\activate.bat

REM 检查依赖
echo 📦 检查依赖...
pip list | find "fastapi" > nul
if errorlevel 1 (
    echo 📥 安装依赖...
    pip install -r requirements.txt
    echo ✅ 依赖安装完成
) else (
    echo ✅ 依赖已齐全
)

REM 检查 .env 文件
if not exist ".env" (
    echo ⚠️  未找到 .env 文件
    echo 📋 正在复制 .env.example -> .env
    copy .env.example .env
    echo ⚠️  请编辑 .env 文件，填入您的 API Key
    echo.
    pause
)

REM 启动后端
echo.
echo 🌐 启动后端服务 (FastAPI)...
echo 📍 API 地址: http://localhost:8000
echo 📚 文档地址: http://localhost:8000/docs
echo.
start "" python main.py

REM 等待后端启动
timeout /t 3 /nobreak

REM 启动前端
echo.
echo 🎨 启动前端应用 (Streamlit)...
echo 🌐 页面地址: http://localhost:8501
echo.
streamlit run app.py

pause
