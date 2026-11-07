// CDP smoke test for the two Christos color themes.
// Usage: node ui_smoke_theme.mjs [debugPort]
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
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });

  const probe = `(()=>({
    theme:document.documentElement.getAttribute('data-theme'),
    bodyBg:getComputedStyle(document.body).backgroundColor,
    bodyColor:getComputedStyle(document.body).color,
    cardBg:getComputedStyle(document.querySelector('.card')).backgroundColor,
    top:document.getElementById('themeTop').value,
    set:document.getElementById('set_theme').value
  }))()`;

  await evalJs(`setTheme('default',true)`);
  const def = await evalJs(probe);
  const s1 = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
  fs.writeFileSync("reports/theme_default.png", Buffer.from(s1.result.data, "base64"));

  await evalJs(`setTheme('night',true)`);
  const night = await evalJs(probe);
  const s2 = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
  fs.writeFileSync("reports/theme_night.png", Buffer.from(s2.result.data, "base64"));

  await send("Page.reload", { ignoreCache: true });
  await new Promise((r) => setTimeout(r, 1800));
  const after = await evalJs(`(()=>({
    theme:document.documentElement.getAttribute('data-theme'),
    top:document.getElementById('themeTop').value,
    set:document.getElementById('set_theme').value,
    saved:(JSON.parse(localStorage.getItem('chemreact.settings')||'{}').theme||'')
  }))()`);

  await evalJs(`setTheme('default',true)`);
  console.log(JSON.stringify({ default: def, night, afterReload: after }, null, 2));
  ws.close();
}

main().catch((e) => {
  console.error("SMOKE_FAIL:", e.message);
  process.exit(1);
});
