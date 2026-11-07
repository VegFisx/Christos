// End-to-end: start a run, wait for the auto-opened run window, stop it.
// Usage: node ui_smoke_runstop.mjs [debugPort]
const port = process.argv[2] || "9223";
const base = `http://127.0.0.1:${port}`;

async function connect(url) {
  const ws = new WebSocket(url);
  let seq = 0;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      pending.get(m.id)(m);
      pending.delete(m.id);
    }
  };
  await new Promise((res, rej) => {
    ws.onopen = res;
    ws.onerror = rej;
  });
  function send(method, params = {}) {
    return new Promise((res) => {
      const id = ++seq;
      pending.set(id, res);
      ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async function evalJs(expression) {
    const r = await send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (r.error) throw new Error(JSON.stringify(r.error));
    if (r.result.exceptionDetails) {
      const d = r.result.exceptionDetails;
      throw new Error(d.exception?.description || JSON.stringify(d));
    }
    return r.result.result.value;
  }
  await send("Runtime.enable");
  return { ws, evalJs };
}

async function pages() {
  return (await (await fetch(base + "/json")).json());
}

async function main() {
  let list = await pages();
  const mainPage = list.find((x) => (x.url || "").includes("127.0.0.1:8765") && !(x.url || "").includes("?run="));
  if (!mainPage) throw new Error("main page not found");
  const main = await connect(mainPage.webSocketDebuggerUrl);
  await main.evalJs(`(()=>{
    const rows=document.querySelectorAll('.hrow .herbInput');
    rows[0].value='党参';
    addRow('甘草');
    addRow('白术');
    document.getElementById('limit').value='6';
    document.getElementById('go').click();
  })()`);

  let runPage = null;
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 500));
    list = await pages();
    runPage = list.find((x) => (x.url || "").includes("?run="));
    if (runPage) break;
  }
  if (!runPage) throw new Error("auto run window did not open");
  const run = await connect(runPage.webSocketDebuggerUrl);
  await new Promise((r) => setTimeout(r, 1500));
  const before = await run.evalJs(`(()=>({
    url:location.href,
    mode:document.body.classList.contains('runWindowMode'),
    status:document.getElementById('statusPill').textContent,
    stop:getComputedStyle(document.getElementById('stopBtn')).display,
    log:document.getElementById('log').textContent.slice(-160)
  }))()`);
  await run.evalJs(`window.confirm=()=>true;document.getElementById('stopBtn').click()`);
  let after = null;
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 500));
    after = await run.evalJs(`(()=>({
      status:document.getElementById('statusPill').textContent,
      stop:getComputedStyle(document.getElementById('stopBtn')).display,
      log:document.getElementById('log').textContent.slice(-160)
    }))()`);
    if (after.status.includes("已终止") || after.status.includes("Stopped")) break;
  }
  console.log(JSON.stringify({ windowOpened: true, before, after }, null, 2));
  main.ws.close();
  run.ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
