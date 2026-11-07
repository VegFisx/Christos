// Inspect the dedicated run-output window. Usage: node ui_smoke_runwindow.mjs [debugPort]
const port = process.argv[2] || "9223";
const base = `http://127.0.0.1:${port}`;

async function main() {
  const list = await (await fetch(base + "/json")).json();
  const page = list.find((x) => (x.url || "").includes("?run=")) || list[0];
  if (!page) throw new Error("no debuggable page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
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
  const r = await send("Runtime.evaluate", {
    expression: `(()=>({
      url:location.href,
      mode:document.body.classList.contains('runWindowMode'),
      title:document.getElementById('viewTitle').textContent,
      sub:document.getElementById('viewSub').textContent,
      status:document.getElementById('statusPill').textContent,
      stopDisplay:getComputedStyle(document.getElementById('stopBtn')).display,
      resultsHidden:document.getElementById('results').hidden,
      logHidden:document.getElementById('logWrap').hidden,
      sidebarDisplay:getComputedStyle(document.querySelector('.sidebar')).display
    }))()`,
    returnByValue: true,
  });
  if (r.error) throw new Error(JSON.stringify(r.error));
  if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
  console.log(JSON.stringify(r.result.result.value, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
