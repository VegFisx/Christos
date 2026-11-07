// CDP smoke test: ambiguous formula names must show suggestions, not auto-load.
// Usage: node ui_smoke_formula_suggest.mjs [debugPort]
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
    pickFormula(row,'牛黄清心片');
    for(let i=0;i<60 && row.versions.length===0 && !document.getElementById('fxStatus').textContent.includes('相似方名');i++) await sleep(250);
    out.input0=row.el.querySelector('.fxInputRow').value;
    out.versions0=row.versions.length;
    out.status=document.getElementById('fxStatus').textContent.trim().slice(0,220);
    out.sugBtns=[...document.querySelectorAll('#fxStatus .fxSug')].map(b=>b.textContent);
    const b=[...document.querySelectorAll('#fxStatus .fxSug')].find(x=>x.textContent==='醒脑牛黄清心片');
    out.hasTargetBtn=!!b;
    if(b){
      b.click();
      for(let i=0;i<60 && row.versions.length===0;i++) await sleep(250);
    }
    out.name1=row.name;
    out.versions1=row.versions.length;
    out.selOptions=document.querySelector('.fxVerSel')?document.querySelector('.fxVerSel').options.length:-1;
    return out;
  })()`);
  console.log(JSON.stringify(out, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
