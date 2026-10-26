@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   QQ 待办助手 · 停止
echo ========================================
echo.

rem 1) 删开关标志：看门狗看到没有这个，就不会再把程序拉起来
if exist enabled.flag del enabled.flag

rem 2) 停后台主进程（只停命令行里含 main.py 的 python，不误杀其他 Python 程序）
echo [..] 停止后台主进程...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'pythonw.exe' -or $_.Name -eq 'python.exe') -and $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

rem 3) 停掉 NapCat（QQ 机器人下线，内存一起释放）
echo [..] 停止 NapCat...
powershell -NoProfile -Command "Get-Process NapCatWinBootMain -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"

rem 4) 取消开机自启（看门狗任务保留，但它会因没有 enabled.flag 而保持沉默）
powershell -NoProfile -Command "Disable-ScheduledTask -TaskName QQTodoBot -ErrorAction SilentlyContinue | Out-Null"

echo.
echo [√] 已停止：后台进程、NapCat 都已退出，开机也不会再自动启动。
echo     数据不会丢（todos.json 都在），下次用双击 start.bat 即可。
timeout /t 4 >nul
