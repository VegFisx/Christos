# 工具分工：什么时候用 Codex，什么时候用 DSH

> 2026-10-13 定（用户要求「写一个什么时候用 codex，什么时候用 DSH 的记录，加进项目报告里」）。
> 实测依据：本轮 Codex 首次独立复核（`reports\codex_runs\20261013-204124\`）。

## 〇、一句话

**DSH 负责「做」，Codex 负责「挑刺」。**
* **DSH**（本项目主 agent，有 37 轮上下文）：唯一能改生产文件、跑判卷器、写报告、跟用户对话的。
* **Codex**（外包，无项目历史）：只做**不需要历史**的独立活，**默认只读**。

---

## 一、白名单（这些活给 Codex）

| 场景 | 为什么适合 | 实测成本 |
|---|---|---|
| **对抗性复核交付物** | 它没有我的盲区。实例：一次复核第三十七轮简报，抓出 **4 处真错**（其中 2 处是数字/标签级） | 331 s · ≈¥0.28 |
| **独立复现数字** | 让它自己写脚本重算，结论不依赖我的口径 | 同上 |
| **从零写自包含工具/脚本** | 没有项目历史包袱，规格给清就干净 | 按规模 |
| **查外部文档/接口** | 省我的 web 往返（如 Codex/DeepSeek 接入方式） | 秒级 |

## 二、黑名单（这些活不给 Codex）

1. **需要项目历史的活**——它上下文里没有这 37 轮，我得写巨型 prompt，又贵又容易错。
2. **改核心化学逻辑**——原子映射安全、口径纪律它没有直觉（`AGENTS.md` 第七节那套）。
3. **抢资源的批量重活**——用户的爬虫在跑，我自己的 8 分钟训练也在排队。
4. **我 1 秒能做完的**（grep 一个字段、看目录结构、读一个 schema）。

## 三、纪律（每次必做，来自首次实测）

1. **范围写死 + 只读优先**：`tools\codex_worker.ps1` 默认 `--sandbox read-only`，并在每次任务里自动附加边界
   （不许碰 `D:\TCMAI`、尤其 `formula_db.*`；不许关/重启进程，尤其 VS Code 和爬虫；改代码必须自跑回归）。
2. **留证据**：每次调用落 `reports\codex_runs\<时间戳>\{prompt.md, stdout.jsonl, final.md, meta.txt}`。
3. **事后核指纹**：跑前跑后对 `reports\` + `tools\` 的源文件清单算 SHA256（首次实测：757 个文件前后一致）。
4. **它的结论必须经我复核才并入交付物**——首次实测 4 条发现复核后 4 条成立，但仍要走这一步。

---

## 四、环境事实（2026-10-13 实测）

| 项 | 事实 |
|---|---|
| 版本 | `codex-cli 0.162.1`，装在 `C:\Users\Vegfish\AppData\Roaming\npm\codex.ps1` |
| 认证 | **不需要 ChatGPT 账号**。DeepSeek 官方为 Codex 提供了 Responses API，一键脚本写入 `~/.codex/config.toml` + `models.json`；provider=`deepseek`，model=`deepseek-flash` |
| 备份 | `~/.codex/backup-deepseek`（重跑官方脚本选 9 可还原） |
| ★ 坑 | **Windows 上没有可用沙箱**：execpolicy 拒绝一切命令（连 `echo hello` / `Get-Location` 都拒，报 `blocked by policy`；openai/codex #43633、#43881）。`-s read-only` 与 `workspace-write` 一样被拒，**只有 `--dangerously-bypass-approvals-and-sandbox` 能跑** |
| 结论 | 因此**只给只读任务，写权限暂缓**；包装脚本里 bypass 是显式开关 `-Bypass`，默认关 |
| 计费 | deepseek-flash：输入(缓存命中) ¥0.02/M · 输入(未命中) ¥1/M · 输出 ¥4/M（**空闲时段**；高峰翻倍）。首次复核 1.18 M 输入（95% 命中缓存）+ 49 k 输出 = **≈¥0.28** |

## 五、建议节奏

**每轮交付物定稿前，让 Codex 做一次独立复核**（约 ¥0.3、5 分钟）——与 `AGENTS.md`「每 5 轮向用户汇报」互补：**它复核、用户拍板**。

## 六、复现命令

```powershell
cd D:\ProgramData\DSHNS\chemreact-staging
# 只读复核（Windows 上必须带 -Bypass，否则一条命令都跑不起来）
pwsh -NoProfile -File tools\codex_worker.ps1 -Bypass -Task "独立复核 <文件>，指出夸大/错误/无出处的断言"
# 跑完看：
#   reports\codex_runs\<时间戳>\final.md
```
