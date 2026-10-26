@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo   QQ 待办助手 · 启动
echo ========================================
echo.

rem 读看板端口（默认 8080）
set PORT=8080
for /f "delims=" %%p in ('powershell -NoProfile -Command "try { (Get-Content -LiteralPath config.json -Raw -Encoding UTF8 ^| ConvertFrom-Json).board_port } catch { 8080 }"') do set PORT=%%p
if not defined PORT set PORT=8080

rem 1) 写开关标志：看门狗看到它，才会在崩溃时自动拉起
echo on > enabled.flag

rem 2) 确保开机自启任务是启用状态
powershell -NoProfile -Command "Enable-ScheduledTask -TaskName QQTodoBot -ErrorAction SilentlyContinue | Out-Null"

rem 3) 已经在跑就不重复启动
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:%PORT%/api/status' | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
    echo [√] 后台服务已经在运行。
) else (
    echo [..] 正在后台启动服务（无黑窗口）...
    powershell -NoProfile -Command "Start-ScheduledTask -TaskName QQTodoBot"
    set /a tries=0
    :waitloop
    powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:%PORT%/api/status' | Out-Null; exit 0 } catch { exit 1 }"
    if %errorlevel%==0 goto ready
    set /a tries+=1
    if !tries! lss 15 ( timeout /t 1 >nul & goto waitloop )
    echo [!] 服务启动较慢，看板可能还在初始化，稍等几秒再刷新。
)

:ready
echo [√] 打开看板 http://127.0.0.1:%PORT%
start "" "http://127.0.0.1:%PORT%"

echo.
echo 已经在后台运行，关闭本窗口不影响。
echo 要停止并释放内存，双击 stop.bat。
timeout /t 3 >nul
endlocal
