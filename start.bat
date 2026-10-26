@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ========================================
echo   QQ 待办助手
echo ========================================
echo.

rem 先看后台服务是不是已经常驻在跑
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:8080/api/status' | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
    echo 服务已在后台常驻运行，直接打开看板...
    start "" http://127.0.0.1:8080
    timeout /t 2 >nul
    exit /b 0
)

echo 后台服务没在跑。本次以前台方式临时启动，适合调试用。
echo 想让它开机自启、挂掉自愈，运行 install.ps1 注册计划任务即可；平时不要用这个 bat。
echo.
echo [1/2] 检查依赖...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    python -m pip install -q requests
)
echo.
echo [2/2] 启动助手（保持窗口开着）...
python main.py
echo.
pause