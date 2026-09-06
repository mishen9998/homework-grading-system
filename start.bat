@echo off
echo ========================================
echo    作业管理系统 - 一键启动脚本
echo ========================================
echo.

echo [1/4] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)
echo Python环境正常
echo.

echo [2/4] 检查并安装后端依赖...
cd backend
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

echo 激活虚拟环境...
call venv\Scripts\activate

echo 安装依赖包...
pip install -q Flask==3.0.0 Flask-SQLAlchemy==3.1.1 Flask-CORS==4.0.0 Flask-JWT-Extended==4.6.0 python-dotenv==1.0.0 SQLAlchemy==2.0.23
echo 后端依赖安装完成
echo.

echo [3/4] 启动后端服务...
start "Backend Server" cmd /k "cd /d %cd% && venv\Scripts\activate && python run.py"
echo 后端服务正在启动，请等待几秒...
timeout /t 5 /nobreak >nul
echo.

echo [4/4] 启动前端服务...
cd ..\frontend
if not exist "node_modules" (
    echo 安装前端依赖...
    call npm install
)

start "Frontend Server" cmd /k "cd /d %cd% && npm run dev"
echo 前端服务正在启动...
timeout /t 3 /nobreak >nul
echo.

echo ========================================
echo    启动完成！
echo ========================================
echo.
echo 后端地址：http://localhost:5000
echo 前端地址：http://localhost:3000
echo.
echo 测试账号：
echo 老师 - 用户名: teacher1  密码: 123456
echo 学生 - 用户名: student1  密码: 123456
echo.
echo 按任意键关闭此窗口（服务器将继续运行）...
pause >nul
