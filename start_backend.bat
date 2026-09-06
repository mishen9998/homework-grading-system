@echo off
chcp 65001 >nul
echo ========================================
echo    简化启动脚本（仅启动后端）
echo ========================================
echo.

echo [1/3] 检查Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python
    echo 请先安装Python 3.8+ 并添加到PATH
    pause
    exit /b 1
)
echo [OK] Python已安装
echo.

echo [2/3] 初始化数据库和测试账号...
cd backend
python init_test_accounts.py
if %errorlevel% neq 0 (
    echo [警告] 数据库初始化可能失败，继续启动...
) else (
    echo [OK] 数据库和测试账号已创建
)
echo.

echo [3/3] 启动后端服务...
echo 正在启动Flask服务器...
echo.
echo ========================================
echo    服务信息
echo ========================================
echo 后端地址：http://localhost:5000
echo 测试账号：
echo   老师：teacher1 / 123456
echo   学生：student1 / 123456
echo.
echo 按Ctrl+C停止服务
echo ========================================
echo.

python run.py

pause
