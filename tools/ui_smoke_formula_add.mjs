// CDP smoke test for formula add-herb validation (Chinese UI).
// Usage: node ui_smoke_formula_add.mjs [debugPort]
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
    out.loaded=row.versions.length;

    document.getElementById('fxAddHerb').value='枸杞';
    document.getElementById('fxAddMult').value='1';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>fxRows[0].added.some(x=>x.herb==='枸杞'));
    out.herbAdded=fxRows[0].added.map(x=>x.herb);
    out.hintHerb=document.getElementById('fxAddHint').textContent;

    document.getElementById('fxAddHerb').value='Glycyrrhiza uralensis';
    document.getElementById('fxAddMult').value='2';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>fxRows[0].added.some(x=>x.herb==='Glycyrrhiza uralensis'));
    out.speciesAdded=fxRows[0].added.map(x=>x.herb+'x'+x.mult);

    document.getElementById('fxAddHint').textContent='';
    document.getElementById('fxAddHerb').value='Ranuncula';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>document.getElementById('fxAddHint').textContent.includes('未收录'));
    out.ranunculaHint=document.getElementById('fxAddHint').textContent.trim();
    out.ranunculaInAdded=fxRows[0].added.some(x=>/^ranuncula$/i.test(x.herb));

    document.getElementById('fxAddHint').textContent='';
    document.getElementById('fxAddHerb').value='屎';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>document.getElementById('fxAddHint').textContent.includes('未收录'));
    out.shiHint=document.getElementById('fxAddHint').textContent.trim();
    out.shiInAdded=fxRows[0].added.some(x=>x.herb==='屎');

    document.getElementById('fxAddHint').textContent='';
    document.getElementById('fxAddHerb').value='丹皮';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>fxRows[0].added.some(x=>x.herb==='牡丹皮'||x.herb==='丹皮'));
    out.aliasAdded=fxRows[0].added.map(x=>x.herb);

    document.getElementById('fxAddHint').textContent='';
    document.getElementById('fxAddHerb').value='拾荒';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>document.getElementById('fxAddHint').textContent.includes('未收录'));
    out.unknownHint=document.getElementById('fxAddHint').textContent.trim();
    out.unknownInAdded=fxRows[0].added.some(x=>x.herb==='拾荒');
    out.inputAfterUnknown=document.getElementById('fxAddHerb').value;

    document.getElementById('fxAddHerb').value='蒋介石内裤';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>document.getElementById('fxAddHint').textContent.includes('根本没有'));
    out.eggHint=document.getElementById('fxAddHint').textContent.trim();
    out.eggInAdded=fxRows[0].added.some(x=>x.herb==='蒋介石内裤');

    document.getElementById('fxAddHerb').value='四君子汤';
    document.getElementById('fxAddHerbBtn').click();
    await wait(()=>document.getElementById('fxAddHint').textContent.includes('这是方剂'));
    out.formulaHint=document.getElementById('fxAddHint').textContent.trim();

    const r2=addFormulaRow();
    pickFormula(r2,'枸杞');
    await wait(()=>document.getElementById('fxStatus').textContent.includes('药材/物种'));
    out.guide=document.getElementById('fxStatus').textContent.trim();
    out.hasGo=!!document.getElementById('fxGoAdd');
    if(document.getElementById('fxGoAdd'))document.getElementById('fxGoAdd').click();
    await sleep(300);
    out.focusAfterGo=document.activeElement?document.activeElement.id:'';

    fxAdded=[{herb:'Ranuncula',mult:1},{herb:'屎',mult:1},{herb:'陈皮',mult:1}];
    renderComposition();sanitizeFxAdded();
    await wait(()=>fxAdded.length===1&&fxAdded[0].herb==='陈皮');
    out.afterSanitize=fxAdded.map(x=>x.herb);
    out.sanitizeHint=document.getElementById('fxAddHint').textContent.trim();
    return out;
  })()`);
  console.log(JSON.stringify(out, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
