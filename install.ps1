# QQ 待办助手 · 一键安装「登录即启动」
#
# 作用：把程序注册成一个 Windows 计划任务
#   - 你登录桌面时自动在后台启动，没有黑窗口
#   - 关掉窗口、关掉浏览器都不影响；开机就在
#   - 进程异常退出，任务会自动重启
#
# 用法（在项目目录里）：
#   powershell -ExecutionPolicy Bypass -File install.ps1
# 卸载：
#   powershell -ExecutionPolicy Bypass -File uninstall.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "QQTodoBot"
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

function Find-RealPython {
    $candidates = @()

    # 1) 本机 Python 官方安装位（Windows Store 版 / 绿色版 / pythoncore）
    foreach ($dir in Get-ChildItem -Path $env:LOCALAPPDATA -Filter "pythoncore-*" -Directory -ErrorAction SilentlyContinue) {
        $candidates += (Join-Path $dir.FullName "python.exe")
    }
    $candidates += (Join-Path $env:LOCALAPPDATA "Python\bin\python.exe")

    # 2) 注册表里登记的安装路径
    foreach ($hive in @("HKLM:\SOFTWARE\Python\PythonCore", "HKCU:\SOFTWARE\Python\PythonCore")) {
        if (-not (Test-Path $hive)) { continue }
        foreach ($ver in Get-ChildItem $hive -ErrorAction SilentlyContinue) {
            $installKey = Join-Path $ver.PSPath "InstallPath"
            $props = Get-ItemProperty -Path $installKey -ErrorAction SilentlyContinue
            if ($props -and $props.ExecutablePath) { $candidates += $props.ExecutablePath }
            elseif ($props -and $props.'(default)') { $candidates += (Join-Path $props.'(default)' "python.exe") }
        }
    }

    # 3) PATH 里的 python
    foreach ($name in @("python", "python3")) {
        foreach ($cmd in (Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if ($cmd.Source) { $candidates += $cmd.Source }
        }
    }

    foreach ($path in $candidates) {
        if (-not $path) { continue }
        $lower = $path.ToLower()
        # 排除商店占位符和沙箱里的临时解释器，它们不能给计划任务长期使用
        if ($lower -like "*\windowsapps\*") { continue }
        if ($lower -like "*sandbox_runtime*") { continue }
        if ($lower -like "*\doubao\*") { continue }
        if (-not (Test-Path -LiteralPath $path)) { continue }
        return $path
    }
    return $null
}

Write-Host "== QQ 待办助手 · 安装登录自启 ==" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath (Join-Path $Root "main.py"))) {
    Write-Host "[失败] 没在这个目录找到 main.py：$Root" -ForegroundColor Red
    exit 1
}

$python = Find-RealPython
if (-not $python) {
    Write-Host "[失败] 没找到 Python。请先安装 Python 并勾选 Add Python to PATH。" -ForegroundColor Red
    exit 1
}

# 后台运行看不到报错，所以依赖先在这里补齐
$reqOk = $false
try {
    $check = & $python -c "import requests;print('ok')" 2>$null
    $reqOk = ($check -eq "ok")
} catch {}
if (-not $reqOk) {
    Write-Host "缺少 requests，正在安装依赖…"
    & $python -m pip install -r (Join-Path $Root "requirements.txt")
}

# 有的安装目录里放的是启动器壳子（shim），先问出真实解释器路径，
# 免得计划任务跑在一个包装器上（包装器退出后任务会误判为已结束）
$realPython = $python
try {
    $resolved = & $python -c "import sys;print(sys.executable)" 2>$null
    if ($resolved -and (Test-Path -LiteralPath $resolved)) { $realPython = $resolved }
} catch {}

# 优先用 pythonw.exe：它不会弹黑窗口；找不到就退回 python.exe
$pythonDir = Split-Path -Parent $realPython
$pythonw = Join-Path $pythonDir "pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw)) { $pythonw = $realPython }

Write-Host "Python : $realPython"
Write-Host "启动器 : $pythonw"
Write-Host "项目   : $Root"

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$Root\main.py`" --background" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -Hidden
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "QQ 待办助手：看板常驻 + NapCat 掉线自动重连（登录时启动）" -Force | Out-Null

Write-Host "计划任务已注册：$TaskName" -ForegroundColor Green

# 看门狗：每 2 分钟探一次端口。计划任务自带的「失败后重启」在进程被强杀时不触发，
# 这一层才是真正的兜底。
$watchdogTask = "QQTodoBot-Watchdog"
$wAction = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument ("-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"{0}`"" -f (Join-Path $Root "watchdog.ps1"))
$wTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 2) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$wSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -Hidden
Register-ScheduledTask -TaskName $watchdogTask -Action $wAction -Trigger $wTrigger `
    -Settings $wSettings -Principal $principal `
    -Description "QQ 待办助手看门狗：每 2 分钟探测看板，挂掉就自动拉起" -Force | Out-Null

Write-Host "看门狗任务已注册：$watchdogTask" -ForegroundColor Green

Start-ScheduledTask -TaskName $TaskName
Start-ScheduledTask -TaskName $watchdogTask
Start-Sleep -Seconds 3

$port = 8080
try {
    $cfg = Get-Content -LiteralPath (Join-Path $Root "config.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($cfg.board_port) { $port = [int]$cfg.board_port }
} catch {}

$url = "http://127.0.0.1:$port"
$ok = $false
foreach ($i in 1..15) {
    try {
        $r = Invoke-WebRequest -Uri "$url/api/status" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { Start-Sleep -Seconds 1 }
}

if ($ok) {
    Write-Host "看板已在后台运行：$url" -ForegroundColor Green
    Write-Host "以后开机登录就会自动启动，不需要再双击 start.bat。"
} else {
    Write-Host "任务已注册，但看板暂时没响应。请查看 logs\app.log 排查。" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "常用命令："
Write-Host "  查看日志   Get-Content '$Root\logs\app.log' -Tail 50"
Write-Host "  重启       Restart-ScheduledTask -TaskName $TaskName"
Write-Host "  卸载       powershell -ExecutionPolicy Bypass -File uninstall.ps1"
