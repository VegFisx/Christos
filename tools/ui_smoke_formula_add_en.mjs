// CDP smoke test for formula add-herb validation (English UI).
// Usage: node ui_smoke_formula_add_en.mjs [debugPort]
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
    const out={};
    out.placeholder=document.getElementById('fxAddHerb').placeholder;
    out.label=document.getElementById('fxAddHerb').closest('label').textContent.trim();
    out.defaultHint=document.getElementById('fxAddHint').textContent.trim();
    const row=fxRows[0];
    pickFormula(row,'四君子汤');
    await wait(()=>row.versions.length>0);
    document.getElementById('fxAddHerb').value='Glycyrrhiza uralensis';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>row.added.some(x=>/^glycyrrhiza uralensis$/i.test(x.herb)));
    out.speciesAdded=row.added.map(x=>x.herb);
    out.speciesHint=document.getElementById('fxAddHint').textContent.trim();
    document.getElementById('fxAddHerb').value='拾荒';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>/not found|not added/i.test(document.getElementById('fxAddHint').textContent));
    out.unknownHint=document.getElementById('fxAddHint').textContent.trim();
    document.getElementById('fxAddHerb').value='蒋介石内裤';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>document.getElementById('fxAddHint').textContent.includes('根本没有'));
    out.eggHint=document.getElementById('fxAddHint').textContent.trim();
    const r2=addFormulaRow();
    pickFormula(r2,'枸杞');
    await wait(()=>/herb\\/species/i.test(document.getElementById('fxStatus').textContent));
    out.guide=document.getElementById('fxStatus').textContent.trim();
    out.goLabel=document.getElementById('fxGoAdd')?document.getElementById('fxGoAdd').textContent.trim():'';
    return out;
  })()`);
  console.log(JSON.stringify(out, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
