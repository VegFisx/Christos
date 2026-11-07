// Collect Chinese UI text nodes/attributes from the running page via CDP.
// Usage: node collect_ui_zh.mjs [debugPort]
import fs from "node:fs";

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
  const texts = await evalJs(`(()=>{
    const out=new Set();
    const skip=new Set(['SCRIPT','STYLE','PRE','CODE']);
    const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{acceptNode(n){
      return skip.has(n.parentElement&&n.parentElement.tagName)?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT;
    }});
    let n;
    while((n=w.nextNode())){
      const t=n.nodeValue.replace(/\\s+/g,' ').trim();
      if(t&&/[\\u4e00-\\u9fff]/.test(t)) out.add(t);
    }
    document.querySelectorAll('input[placeholder],textarea[placeholder],[title]').forEach(el=>{
      ['placeholder','title'].forEach(a=>{
        const v=el.getAttribute(a);
        if(v&&/[\\u4e00-\\u9fff]/.test(v)) out.add(v);
      });
    });
    return [...out];
  })()`);
  texts.sort((a, b) => a.length - b.length || a.localeCompare(b, "zh"));
  fs.writeFileSync("reports/ui_zh_texts.json", JSON.stringify(texts, null, 2), "utf8");
  console.log("count", texts.length);
  for (const t of texts) console.log(t);
  ws.close();
}

main().catch((e) => {
  console.error("COLLECT_FAIL:", e.message);
  process.exit(1);
});
