/* BrightSmile chat widget. Kisi bhi website mein ye ek line daalo:
   <script src="https://YOUR-SERVER/widget/widget.js" data-api="https://YOUR-SERVER"></script>
   Shadow DOM use hota hai, is liye host website ki CSS se takrao nahi hota. */
(function () {
  var script = document.currentScript;
  // API address: data-api attribute, warna jis server se widget.js load hui wohi server
  var API = script && script.getAttribute("data-api");
  if (!API) {
    try { API = new URL(script.src).origin; } catch (e) { API = "http://localhost:8000"; }
  }
  var TITLE = (script && script.getAttribute("data-title")) || "BrightSmile Assistant";
  var GREETING =
    "Assalam o Alaikum! Main BrightSmile Dental Clinic ka assistant hoon. " +
    "Fees, timings, treatments ya appointment ke bare mein pooch sakte hain.";
  var history = [];
  var busy = false;

  var host = document.createElement("div");
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  root.innerHTML =
    "<style>" +
    ":host{all:initial}" +
    "*{box-sizing:border-box;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}" +
    "#bubble{position:fixed;right:20px;bottom:20px;width:58px;height:58px;border-radius:50%;border:0;" +
    "background:#0f766e;color:#fff;font-size:26px;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.25);z-index:2147483646}" +
    "#panel{position:fixed;right:20px;bottom:90px;width:360px;max-width:calc(100vw - 24px);height:520px;" +
    "max-height:calc(100vh - 110px);background:#fff;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.25);" +
    "display:none;flex-direction:column;overflow:hidden;z-index:2147483647}" +
    "#panel.open{display:flex}" +
    "#head{background:#0f766e;color:#fff;padding:14px 16px;font-weight:600;display:flex;justify-content:space-between;align-items:center}" +
    "#close{background:none;border:0;color:#fff;font-size:20px;cursor:pointer}" +
    "#msgs{flex:1;overflow-y:auto;padding:14px;background:#f4f7f7;display:flex;flex-direction:column;gap:8px}" +
    ".m{max-width:85%;padding:9px 12px;border-radius:14px;font-size:14px;line-height:1.45;white-space:pre-wrap;word-wrap:break-word}" +
    ".bot{background:#fff;color:#1f2937;align-self:flex-start;border-bottom-left-radius:4px}" +
    ".user{background:#0f766e;color:#fff;align-self:flex-end;border-bottom-right-radius:4px}" +
    ".typing{opacity:.6;font-style:italic}" +
    "#form{display:flex;gap:8px;padding:10px;border-top:1px solid #e5e7eb;background:#fff}" +
    "#input{flex:1;border:1px solid #d1d5db;border-radius:20px;padding:9px 14px;font-size:14px;outline:none}" +
    "#input:focus{border-color:#0f766e}" +
    "#send{border:0;background:#0f766e;color:#fff;border-radius:20px;padding:0 16px;cursor:pointer;font-size:14px}" +
    "#send:disabled{opacity:.5;cursor:default}" +
    "</style>" +
    '<button id="bubble" aria-label="Chat kholein">&#128172;</button>' +
    '<div id="panel" role="dialog" aria-label="Chat">' +
    '<div id="head"><span></span><button id="close" aria-label="Band karein">&times;</button></div>' +
    '<div id="msgs"></div>' +
    '<form id="form"><input id="input" type="text" maxlength="500" placeholder="Apna sawal likhein..." autocomplete="off">' +
    '<button id="send" type="submit">Send</button></form></div>';

  var $ = function (id) { return root.getElementById(id); };
  $("head").firstChild.textContent = TITLE;
  var msgs = $("msgs"), input = $("input"), send = $("send"), panel = $("panel");

  function addMsg(text, who, extraClass) {
    var el = document.createElement("div");
    el.className = "m " + who + (extraClass ? " " + extraClass : "");
    el.textContent = text; // textContent: HTML injection se safe
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
    return el;
  }

  function toggle(open) {
    panel.classList.toggle("open", open);
    if (open) {
      if (!msgs.children.length) addMsg(GREETING, "bot");
      input.focus();
    }
  }
  $("bubble").onclick = function () { toggle(!panel.classList.contains("open")); };
  $("close").onclick = function () { toggle(false); };

  $("form").onsubmit = function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text || busy) return;
    input.value = "";
    addMsg(text, "user");
    busy = true;
    send.disabled = true;
    var typing = addMsg("Typing...", "bot", "typing");

    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, 90000); // 90 second se zyada intezar nahi
    fetch(API + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: history.slice(-6) }),
      signal: ctrl.signal,
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        var reply = res.ok ? res.d.answer : (res.d.detail || "Kuch masla ho gaya.");
        typing.remove();
        addMsg(reply, "bot");
        if (res.ok) {
          history.push({ role: "user", content: text });
          history.push({ role: "assistant", content: reply });
        }
      })
      .catch(function () {
        typing.remove();
        addMsg("Jawab dene mein der lag rahi hai ya connection ka masla hai. Dobara try karein, ya clinic ko 0300-1234567 par call karein.", "bot");
      })
      .finally(function () {
        clearTimeout(timer);
        busy = false;
        send.disabled = false;
        input.focus();
      });
  };
})();