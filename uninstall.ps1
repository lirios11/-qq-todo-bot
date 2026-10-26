# QQ 待办助手 · 卸载「登录自启」
#
# 作用：
#   1. 删除登录自启的计划任务
#   2. 结束正在后台运行的看板进程（只结束本项目 main.py 的进程）
#
# 数据文件（todos.json / seen.json）不会被删。

$ErrorActionPreference = "Continue"
$TaskName = "QQTodoBot"
$WatchdogTask = "QQTodoBot-Watchdog"

Write-Host "== QQ 待办助手 · 卸载登录自启 ==" -ForegroundColor Cyan

foreach ($name in @($WatchdogTask, $TaskName)) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "已删除计划任务：$name" -ForegroundColor Green
    } else {
        Write-Host "没有找到计划任务：$name（可能已经卸载过）" -ForegroundColor Yellow
    }
}

Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match "main\.py" -and $_.CommandLine -match "qq-todo-bot" } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host ("已结束后台进程 PID {0}" -f $_.ProcessId)
    }

Write-Host ""
Write-Host "卸载完成。想临时运行，仍可双击 start.bat。"
