# 运行期间阻止系统休眠（长跑基准用）。
# 用法： pwsh -NoProfile -File tools\keep_awake.ps1 -Minutes 240
param([int]$Minutes = 240)
Add-Type -Name Pwr -Namespace Win -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError=true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
$ES_CONTINUOUS = 0x80000000
$ES_SYSTEM_REQUIRED = 0x00000001
$ES_DISPLAY_REQUIRED = 0x00000002
$flags = $ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_DISPLAY_REQUIRED
$end = (Get-Date).AddMinutes($Minutes)
while ((Get-Date) -lt $end) {
    [void][Win.Pwr]::SetThreadExecutionState($flags)
    Start-Sleep -Seconds 30
}
[void][Win.Pwr]::SetThreadExecutionState($ES_CONTINUOUS)
