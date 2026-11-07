// CDP smoke test for the English UI.
// Usage: node ui_smoke_lang.mjs [debugPort]
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
  async function shot(name) {
    const s = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
    fs.writeFileSync(name, Buffer.from(s.result.data, "base64"));
  }
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });

  await evalJs(`setLang('en',true)`);
  await new Promise((r) => setTimeout(r, 1800));
  const predict = await evalJs(`(()=>({
    lang:document.documentElement.lang,
    langTop:document.getElementById('langTop').value,
    setLang:document.getElementById('set_lang').value,
    nav:[...document.querySelectorAll('.navBtn .txt')].map(x=>x.textContent.trim()),
    title:document.getElementById('viewTitle').textContent,
    sub:document.getElementById('viewSub').textContent,
    condValue:document.getElementById('cond').value,
    condText:document.getElementById('cond').selectedOptions[0].textContent,
    cards:[...document.querySelectorAll('#view-predict .cardHead h2')].map(x=>x.textContent.trim()),
    zhVisible:[...new Set((document.body.innerText.match(/[\\u4e00-\\u9fff][^\\n]{0,40}/g)||[]))].slice(0,30)
  }))()`);
  await shot("reports/ui_en_predict.png");

  await evalJs(`setView('settings')`);
  await new Promise((r) => setTimeout(r, 300));
  const settings = await evalJs(`(()=>({
    title:document.getElementById('viewTitle').textContent,
    labels:[...document.querySelectorAll('#view-settings .field')].map(x=>x.childNodes[0].textContent.trim()),
    buttons:[...document.querySelectorAll('#view-settings button')].map(x=>x.textContent.trim())
  }))()`);
  await shot("reports/ui_en_settings.png");

  await evalJs(`setView('formula')`);
  await new Promise((r) => setTimeout(r, 300));
  const formula0 = await evalJs(`(()=>({
    title:document.getElementById('viewTitle').textContent,
    headers:[...document.querySelectorAll('#view-formula .cardHead h2')].map(x=>x.textContent.trim()),
    buttons:[...document.querySelectorAll('#view-formula button')].map(x=>x.textContent.trim()).slice(0,12)
  }))()`);
  await evalJs(`addFormulaRow('四君子汤')`);
  await new Promise((r) => setTimeout(r, 1200));
  const formula1 = await evalJs(`(()=>({
    status:document.getElementById('fxStatus').textContent.trim(),
    edit:document.getElementById('fxEditState').textContent.trim(),
    rows:document.querySelectorAll('.fxRow').length,
    versions:fxRows[0].versions.length,
    zhVisible:[...new Set((document.getElementById('view-formula').innerText.match(/[\\u4e00-\\u9fff][^\\n]{0,40}/g)||[]))].slice(0,30)
  }))()`);
  await shot("reports/ui_en_formula.png");

  await evalJs(`setLang('zh',true)`);
  await new Promise((r) => setTimeout(r, 1500));
  const zh = await evalJs(`({lang:document.documentElement.lang,title:document.getElementById('viewTitle').textContent,condValue:document.getElementById('cond').value})`);

  console.log(JSON.stringify({ predict, settings, formula0, formula1, backToZh: zh }, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
