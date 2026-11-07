<#
codex_worker.ps1 —— 受控调用 Codex CLI（非交互）给本项目干活。

设计原则（见 AGENTS.md 第四/六节）：
  * 默认 --sandbox read-only：先只读复核，确认质量后再显式 -Sandbox workspace-write
  * 每次调用留证据：reports\codex_runs\<时间戳>\prompt.md + stdout.jsonl + final.md + meta.txt
  * prompt 里写死边界：不许碰 D:\TCMAI、不许碰用户的 VS Code 和正在跑的爬虫进程

用法示例：
  pwsh -File tools\codex_worker.ps1 -Task "独立复核 reports\第三十七轮-条件层决策简报.md 的数字"
  pwsh -File tools\codex_worker.ps1 -TaskFile tmp\task.md -Sandbox workspace-write -Scope "tools\" -TimeoutSec 900
#>
param(
  [string]$Task = "",
  [string]$TaskFile = "",
  [string]$WorkDir = "D:\ProgramData\DSHNS\chemreact-staging",
  [ValidateSet("read-only","workspace-write","danger-full-access")]
  [string]$Sandbox = "read-only",
  [string]$Scope = "",
  [string]$Model = "",
  [int]$TimeoutSec = 600,
  [switch]$Bypass   # ★ Windows 上 Codex 的沙箱/execpolicy 会拒绝一切命令（已知 issue），
                    #   只有加 --dangerously-bypass-approvals-and-sandbox 才能跑起来。
                    #   仅在"任务本身只读 + 我事后核对文件未变"时才用。
)

$ErrorActionPreference = "Stop"

if ($TaskFile) { $Task = Get-Content -Raw -Encoding UTF8 $TaskFile }
if (-not $Task.Trim()) { Write-Error "必须给 -Task 或 -TaskFile"; exit 2 }

$scopeLabel = "(read-only，不要改任何文件)"
if ($Scope) { $scopeLabel = $Scope }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $WorkDir ("reports\codex_runs\" + $stamp)
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$guard = @"
【本次任务的边界（必须遵守）】
1. 只改这个范围：$scopeLabel
2. 绝对不要碰 D:\TCMAI（用户原始项目，只读）；尤其不要碰 D:\TCMAI\data\formula_db.json / .csv。
3. 不要关闭、重启、结束任何进程，尤其不要碰 VS Code 和正在运行的 python 爬虫。
4. 若改动了代码，必须自己跑：tools\audit_mapped_safety.py 与 tools\query_engine.py selftest。
5. 结论必须标"实测"或"推断"；关键数字给出出处文件路径。

【任务】
$Task
"@

$guard | Set-Content -Encoding UTF8 (Join-Path $runDir "prompt.md")

$codexArgs = @("exec", "--cd", $WorkDir, "--sandbox", $Sandbox, "--skip-git-repo-check",
               "--json", "-o", (Join-Path $runDir "final.md"))
if ($Model) { $codexArgs += @("--model", $Model) }
if ($Bypass) { $codexArgs += "--dangerously-bypass-approvals-and-sandbox" }
$codexArgs += $guard

Write-Host ("[codex_worker] run dir : " + $runDir)
Write-Host ("[codex_worker] sandbox : " + $Sandbox)
Write-Host ("[codex_worker] scope   : " + $scopeLabel)

$sw = [System.Diagnostics.Stopwatch]::StartNew()
& codex @codexArgs 2>&1 | Tee-Object -FilePath (Join-Path $runDir "stdout.jsonl")
$code = $LASTEXITCODE
$sw.Stop()

@(
  "exit_code=$code",
  ("seconds=" + [math]::Round($sw.Elapsed.TotalSeconds,1)),
  "sandbox=$Sandbox",
  ("bypass=" + $Bypass),
  "workdir=$WorkDir",
  ("scope=" + $scopeLabel),
  ("model=" + $(if ($Model) { $Model } else { "(default)" }))
) | Set-Content -Encoding UTF8 (Join-Path $runDir "meta.txt")

Write-Host ("[codex_worker] exit=" + $code + "  " + [math]::Round($sw.Elapsed.TotalSeconds,1) + "s")
Write-Host ("[codex_worker] final: " + (Join-Path $runDir "final.md"))
exit $code
