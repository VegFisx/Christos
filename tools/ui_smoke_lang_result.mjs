// CDP smoke test: run one SMILES prediction in English mode and audit the result card.
// Usage: node ui_smoke_lang_result.mjs [debugPort]
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
  await evalJs(`(()=>{
    document.querySelectorAll('.hrow .herbInput').forEach(x=>x.value='');
    document.getElementById('smiles').value='CC(=O)Oc1ccccc1C(=O)O';
    document.getElementById('limit').value='6';
    document.getElementById('go').click();
  })()`);
  let done = false;
  for (let i = 0; i < 80; i++) {
    await new Promise((r) => setTimeout(r, 500));
    done = await evalJs(`!document.getElementById('results').hidden`);
    if (done) break;
  }
  const out = await evalJs(`(()=>{
    const r=document.getElementById('results');
    const text=r.innerText;
    const zh=[...new Set((text.match(/[\\u4e00-\\u9fff][^\\n]{0,60}/g)||[]))];
    return {
      done:!r.hidden,
      status:document.getElementById('statusPill').textContent,
      elapsed:document.getElementById('elapsed').textContent,
      text:text.slice(0,2500),
      zh
    };
  })()`);
  console.log(JSON.stringify(out, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
