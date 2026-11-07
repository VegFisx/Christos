// CDP smoke test for the formula add-area "Find similar" feature.
// Usage: node ui_smoke_formula_findadd.mjs [debugPort]
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
    const wait=async(fn,ms=9000)=>{const t=Date.now();while(Date.now()-t<ms){if(fn())return true;await sleep(200);}return false;};
    const out={};
    const row=fxRows[0];
    pickFormula(row,'四君子汤');
    await wait(()=>row.versions.length>0);
    const inp=document.getElementById('fxAddHerb');
    const fb=document.getElementById('fxAddFind');
    async function find(q){
      inp.value=q;
      document.getElementById('fxAddFindBtn').click();
      await wait(()=>fb.querySelectorAll('.fbox').length>0||/没有找到/.test(fb.textContent)||/这是方剂/.test(fb.textContent));
      return fb.textContent.trim();
    }
    out.btn=document.getElementById('fxAddFindBtn').textContent.trim();
    out.speciesFind=await find('Glycyrrhiza');
    out.speciesCount=fb.querySelectorAll('.fbox').length;
    const speciesBox=[...fb.querySelectorAll('.fbox')].find(x=>x.parentElement.textContent.toLowerCase().includes('glycyrrhiza uralensis'));
    if(speciesBox)speciesBox.checked=true;
    fb.querySelector('.fillBtn').click();
    await wait(()=>row.added.some(x=>/^glycyrrhiza uralensis$/i.test(x.herb)));
    out.speciesAdded=row.added.map(x=>x.herb);
    out.speciesHint=document.getElementById('fxAddHint').textContent.trim();

    out.shiFind=await find('屎');
    out.shiCount=fb.querySelectorAll('.fbox').length;
    const shiBox=fb.querySelector('.fbox');
    if(shiBox)shiBox.checked=true;
    if(fb.querySelector('.fillBtn'))fb.querySelector('.fillBtn').click();
    await wait(()=>row.added.length>=2);
    out.afterShi=row.added.map(x=>x.herb);

    out.badFind=await find('Ranuncula');
    out.badBoxes=fb.querySelectorAll('.fbox').length;

    out.aliasFind=await find('丹皮');
    out.aliasHas=fb.textContent.includes('牡丹皮');
    const aliasBox=[...fb.querySelectorAll('.fbox')].find(x=>x.parentElement.textContent.includes('牡丹皮'));
    if(aliasBox)aliasBox.checked=true;
    if(fb.querySelector('.fillBtn'))fb.querySelector('.fillBtn').click();
    await wait(()=>row.added.some(x=>x.herb==='牡丹皮'));
    out.aliasAdded=row.added.map(x=>x.herb);

    out.formulaFind=await find('四君子汤');
    out.formulaBoxes=fb.querySelectorAll('.fbox').length;
    return out;
  })()`);
  console.log(JSON.stringify(out, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
