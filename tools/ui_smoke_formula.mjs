// CDP smoke test for the Christos formula page (one row per formula).
// Usage: node ui_smoke_formula.mjs [debugPort]
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
    out.rows0=document.querySelectorAll('.fxRow').length;
    out.hasFind=!!document.querySelector('.fxRow .findBtn');
    out.hasDel=!!document.querySelector('.fxRow .delBtn');
    pickFormula(fxRows[0],'四君子汤');
    for(let i=0;i<60 && fxRows[0].versions.length===0;i++) await sleep(250);
    out.versions1=fxRows[0].versions.length;
    out.selOptions1=document.querySelector('.fxVerSel')?document.querySelector('.fxVerSel').options.length:-1;
    out.metaDisplay=getComputedStyle(document.querySelector('.fxRowMeta')).display;
    out.tbodyRows=document.querySelectorAll('#fxTbody tr').length;
    out.summary1=(document.querySelector('.fxRowSummary')||{}).textContent||'';
    const trs=[...document.querySelectorAll('#fxTbody tr')];
    const tr=trs.find(r=>r.textContent.includes('茯苓'));
    if(tr) tr.querySelector('.fxToggle').click();
    out.removedMult=fxRows[0].multiples['茯苓'];
    out.summary2=(document.querySelector('.fxRowSummary')||{}).textContent||'';
    document.getElementById('fxAddHerb').value='陈皮';
    document.getElementById('fxAddMult').value='1';
    addHerbToCurrent();
    out.added=fxRows[0].added.map(x=>x.herb+'x'+x.mult).join(',');
    out.summary3=(document.querySelector('.fxRowSummary')||{}).textContent||'';
    addFormulaRow('四物汤');
    for(let i=0;i<60 && fxRows[1].versions.length===0;i++) await sleep(250);
    out.rows2=document.querySelectorAll('.fxRow').length;
    out.versions2=fxRows[1].versions.length;
    out.selOptions2=document.querySelectorAll('.fxVerSel')[1]?document.querySelectorAll('.fxVerSel')[1].options.length:-1;
    out.summary4=(document.querySelectorAll('.fxRowSummary')[1]||{}).textContent||'';
    out.activeName=(fxRows.find(r=>r.id===fxActiveId)||{}).name||'';
    return out;
  })()`);
  console.log(JSON.stringify(out, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
