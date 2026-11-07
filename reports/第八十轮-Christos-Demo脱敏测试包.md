# 第八十轮 · Christos-Demo 脱敏测试包

日期：2026-10-18

> 2026-10-18 后续已扩展为 100 味中药 / 50 个方剂 / 150 个预计算条目；
> 最新版本见 `reports\第八十一轮-Christos-Demo-100味50方.md`。

## 一、用途

这是给外部测试者看**界面和工作流**的脱敏演示包，不是完整 Christos 引擎。

包含：

- 一个 COCONUT 物种示例（`Glycyrrhiza uralensis`）的极小静态结果片段；
- 一个乙酸小分子阳性对照；
- 方剂工作区的版式预览。

不包含：

- `tcm.db`、`coconut.db`、`formula_db.json`、异名表或用户数据库；
- 任意目标输入框；
- routes / 逆合成；
- 自由辅助试剂；
- 可购砌块、供应商或采购信息；
- 药典成方库或正式方剂组成。

## 二、产物

目录：

`reports\desktop-build\demo-v090\Christos-Demo-0.9.0-beta-demo.zip`

大小与校验：

- zip：8.4 MB
- SHA-256：`2f8ca5af1a43e653de126056391f44b443e80801839660811e6f3020ef386cac`

解压后双击：

`Christos-Demo\Christos-Demo.exe`

程序只监听 `127.0.0.1`；页面右下角有「退出演示」。

## 三、验收证据

### 静态服务器

```text
HTTP=200
examples=3
has_routes=False
has_reagents=False
```

### 打包 exe

最终 `Christos-Demo.exe` 以 `--no-browser` 启动后实测：

```text
http=200
examples=3
has_routes=False
has_reagents=False
```

双击启动（Edge app 模式）再次实测：`http=200`，页面正常加载；测试进程已关闭。

zip 内包含：

- `Christos-Demo.exe`
- `_internal\demo_page.html`
- `_internal\demo_data.json`
- `_internal\README.md`
- `_internal\TEST-AGREEMENT.md`
- `_internal\FEEDBACK-TEMPLATE.md`

zip 扫描未发现 `tcm.db`、`coconut.db`、`formula_db`、`herb_aliases`、
`purchasable`、`vendor`、`supplier`、`routes` 或 `reagents` 工件。
演示页面也扫描确认没有 `<input>`、`<textarea>` 或 `contenteditable` 输入区。

### 病毒扫描

Windows Defender 服务在本机未启用；改用已注册的 Kaspersky 21.27 做只报告扫描。
病毒库日期：2026-10-18。

扫描对象：

- `Christos-Demo-0.9.0-beta-demo.zip`
- 已解压的 `Christos-Demo` 目录

结果：

```text
Processed objects: 504
Total detected: 0
Suspicions: 0
Errors: 0
Password protected: 0
Corrupted: 0
```

报告：`reports\desktop-build\demo-v090\KASPERSKY_SCAN_REPORT.txt`

代码审计只发现本地 `127.0.0.1` HTTP 服务、启动独立 Edge 窗口、写 `runtime\app.log`
和专用 Edge profile；没有外部 URL 请求、删除、注册表修改或后台开机项。

## 四、使用边界

1. 只发给明确的测试对象，不放到公开网盘或公开下载页；
2. 随包发送 `TEST-AGREEMENT.md`，测试者填写 `FEEDBACK-TEMPLATE.md`；
3. 只用于界面、流程和可用性反馈，不作为医学、药学或合成建议；
4. 不要尝试把示例扩展为受控物质或真实数据库操作；
5. 这不是完整软件的替代品；真实引擎测试仍需受控环境和正式数据授权。
