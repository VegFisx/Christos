// CDP smoke test for the formula page's "查找相似" button.
// Usage: node ui_smoke_formula_find.mjs [debugPort]
const port = process.argv[2] || "9223";
const base = `http://127.0.0.1:${port}`;

async function main() {
  const list = await (await fetch(base + "/json")).json();
  const page = list.find((x) => (x.url || "").includes("127.0.0.1:8765")) || list[0];
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
  const out = await evalJs(`(async()=>{
    const sleep=ms=>new Promise(r=>setTimeout(r,ms));
    const out={};
    const row=fxRows[0];
    const inp=row.el.querySelector('.fxInputRow');
    const fb=row.el.querySelector('.findBox');
    inp.value='四君子汤';
    row.el.querySelector('.findBtn').click();
    for(let i=0;i<40 && !fb.textContent.includes('方剂候选');i++) await sleep(250);
    out.box1=fb.textContent.trim().slice(0,200);
    out.checks1=fb.querySelectorAll('.fbox').length;
    inp.value='常凯申';
    row.el.querySelector('.findBtn').click();
    for(let i=0;i<40 && !fb.textContent.includes('根本没有');i++) await sleep(250);
    out.box2=fb.textContent.trim().slice(0,100);
    inp.value='甘草';
    row.el.querySelector('.findBtn').click();
    for(let i=0;i<40 && !fb.textContent.includes('未收录该方剂');i++) await sleep(250);
    out.box3=fb.textContent.trim().slice(0,120);
    return out;
  })()`);
  console.log(JSON.stringify(out, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
