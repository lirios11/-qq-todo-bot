# QQ 待办助手 · 看门狗
#
# 由计划任务每 2 分钟调一次：探测看板是否还活着，没响应就把主任务重新拉起来。
# Windows 计划任务自带的「失败后重启」在进程被强杀时经常不触发，所以需要这一层。

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "QQTodoBot"
$LogPath = Join-Path $Root "logs\watchdog.log"

$port = 8080
$cfgPath = Join-Path $Root "config.json"
if (Test-Path -LiteralPath $cfgPath) {
    try {
        $cfg = Get-Content -LiteralPath $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($cfg.board_port) { $port = [int]$cfg.board_port }
    } catch {}
}

$alive = $false
try {
    $resp = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/api/status" -f $port) -UseBasicParsing -TimeoutSec 3
    $alive = ($resp.StatusCode -eq 200)
} catch {
    $alive = $false
}

if (-not $alive) {
    New-Item -ItemType Directory -Path (Join-Path $Root "logs") -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    ("{0} 看板无响应，已重新拉起 {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $TaskName) |
        Out-File -LiteralPath $LogPath -Append -Encoding utf8
}
