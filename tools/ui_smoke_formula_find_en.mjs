// CDP smoke test for the English version of the formula add-area finder.
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
  await evalJs(`setLang('en',true)`);
  await new Promise((r) => setTimeout(r, 1800));
  const out = await evalJs(`(async()=>{
    const sleep=ms=>new Promise(r=>setTimeout(r,ms));
    const wait=async(fn,ms=9000)=>{const t=Date.now();while(Date.now()-t<ms){if(fn())return true;await sleep(200);}return false;};
    const row=fxRows[0];
    pickFormula(row,'四君子汤');
    await wait(()=>row.versions.length>0);
    document.getElementById('fxAddHerb').value='Glycyrrhiza';
    document.getElementById('fxAddFindBtn').click();
    await wait(()=>document.getElementById('fxAddFind').querySelectorAll('.fbox').length>0);
    const fb=document.getElementById('fxAddFind');
    return {
      btn:document.getElementById('fxAddFindBtn').textContent.trim(),
      text:fb.textContent.trim().slice(0,500),
      hasSourcePlant:fb.textContent.includes('[Source plant]'),
      hasAddSelected:fb.textContent.includes('Add selected'),
      hasMulti:fb.textContent.includes('select multiple')
    };
  })()`);
  console.log(JSON.stringify(out, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
