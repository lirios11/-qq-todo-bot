# QQ 待办助手 · 看门狗
#
# 由计划任务每 2 分钟调一次：
#   - 看板无响应 且 用户没有主动停用（enabled.flag 存在）→ 把主任务重新拉起来
#   - 用户主动停用（enabled.flag 不存在）→ 什么都不做，安静退出
#
# Windows 计划任务自带的「失败后重启」在进程被强杀时不触发，所以需要这一层。
# 但用户想关的时候（stop.bat 删了 enabled.flag），这一层绝不能再复活它。

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "QQTodoBot"
$LogPath = Join-Path $Root "logs\watchdog.log"
$FlagPath = Join-Path $Root "enabled.flag"

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

if ($alive) { exit 0 }

New-Item -ItemType Directory -Path (Join-Path $Root "logs") -Force | Out-Null

if (Test-Path -LiteralPath $FlagPath) {
    Start-ScheduledTask -TaskName $TaskName
    ("{0} 看板无响应，已重新拉起 {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $TaskName) |
        Out-File -LiteralPath $LogPath -Append -Encoding utf8
} else {
    ("{0} 看板无响应，但用户已停用（无 enabled.flag），跳过拉起" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) |
        Out-File -LiteralPath $LogPath -Append -Encoding utf8
}
