"""
resetrelay.py  -  automatic key reset through a Telegram account (userbot).

Flow:  reseller/user presses Reset (or calls /api/v1/reset)
       -> server checks the key belongs to him and is still valid
       -> a Telegram ACCOUNT (not a bot) sends the key to the reset bot
       -> the bot's answer is read -> "Reset Successful" / "Not successful" is shown.
The reseller never sees which bot or account is used.

Needs:  pip install telethon      (add "telethon>=1.36" to requirements.txt)
Setup:  Admin > Reset Relay -> API ID + API HASH (my.telegram.org) + reset bot username
        -> phone number -> login code (-> 2FA password). The session is stored in the settings table
        (so it is also inside the normal Backup).  Use a SEPARATE Telegram number, not your main one.
"""
import asyncio, re, threading, time

H = {}                       # helpers handed over by app.py
_loop = None
_client = None               # authorised client
_pending = None              # client waiting for the login code
_lock_async = None
_state_lock = threading.Lock()
_last_call = {}              # reseller_id -> time (cooldown)

KEY_RE = re.compile(r"[A-Za-z0-9_\-]{4,64}")
FAIL_WORDS = ("limit", "invalid", "not found", "expired", "no resets", "0 resets", "failed",
              "error", "wrong", "banned", "blocked", "not active", "denied")


# ------------------------------------------------------------------ db
def init_table():
    H["q"]("CREATE TABLE IF NOT EXISTS reset_log(id INTEGER PRIMARY KEY, reseller_id INTEGER, key TEXT,"
           " ok INTEGER, detail TEXT, ts INTEGER)", commit=True)


def _cfg(k, d=""):
    return H["get_setting"]("rr_" + k, d)


def _set(k, v):
    H["set_setting"]("rr_" + k, v)


# ------------------------------------------------------------------ telethon loop
def _ensure_loop():
    global _loop, _lock_async
    if _loop and _loop.is_running():
        return
    _loop = asyncio.new_event_loop()
    _lock_async = None
    t = threading.Thread(target=_loop.run_forever, daemon=True, name="reset-relay-loop")
    t.start()
    while not _loop.is_running():
        time.sleep(0.01)


def _run(coro, timeout=75):
    _ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(timeout)


def _new_client(session=""):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    api_id, api_hash = int(_cfg("api_id") or 0), _cfg("api_hash")
    if not api_id or not api_hash:
        raise RuntimeError("API ID / API HASH not set")
    return TelegramClient(StringSession(session), api_id, api_hash, loop=_loop)


async def _get_client():
    global _client
    if _client and _client.is_connected():
        return _client
    sess = _cfg("session")
    if not sess:
        raise RuntimeError("Relay account not logged in")
    c = _new_client(sess)
    await c.connect()
    if not await c.is_user_authorized():
        raise RuntimeError("Relay session expired - log in again")
    _client = c
    return c


# ------------------------------------------------------------------ login (admin)
async def _send_code(phone):
    global _pending
    if _pending:
        try:
            await _pending.disconnect()
        except Exception:
            pass
    c = _new_client("")
    await c.connect()
    sent = await c.send_code_request(phone)
    _pending = c
    _set("phone", phone)
    _set("phone_hash", sent.phone_code_hash)


async def _sign_in(code, password):
    global _pending, _client
    from telethon.errors import SessionPasswordNeededError
    c = _pending
    if not c:
        raise RuntimeError("Send the code first")
    try:
        if code:
            await c.sign_in(phone=_cfg("phone"), code=code, phone_code_hash=_cfg("phone_hash"))
        else:
            await c.sign_in(password=password)
    except SessionPasswordNeededError:
        return "2fa"
    _set("session", c.session.save())
    _client, _pending = c, None
    me = await c.get_me()
    _set("me", (me.first_name or "") + " (@" + (me.username or "-") + ")")
    return "ok"


async def _logout():
    global _client, _pending
    for c in (_client, _pending):
        if c:
            try:
                await c.disconnect()
            except Exception:
                pass
    _client = _pending = None
    _set("session", "")
    _set("me", "")


# ------------------------------------------------------------------ the reset itself
async def _reset(key):
    global _lock_async
    if _lock_async is None:
        _lock_async = asyncio.Lock()
    bot = _cfg("bot").strip().lstrip("@")
    if not bot:
        return False, "reset bot not set"
    async with _lock_async:                                   # one reset at a time -> replies never mix
        c = await _get_client()
        async with c.conversation(bot, timeout=25, total_timeout=50, exclusive=False) as conv:
            await conv.send_message(key)
            last = ""
            while True:
                try:
                    msg = await conv.get_response()
                except asyncio.TimeoutError:
                    return False, ("no usable answer from the bot. last: " + last)[:300]
                text = (msg.raw_text or "").strip()
                low = text.lower()
                last = text.replace("\n", " ")[:300]
                if "reset successful" in low and key.lower() in low:
                    return True, last
                if any(w in low for w in FAIL_WORDS) and "reset successful" not in low:
                    return False, last
                # otherwise: a "processing..." style message -> wait for the next one


def do_reset(rid, key, *, is_admin_check=False):
    """returns (ok: bool, public_message: str).  Raw bot text only goes to reset_log / admin."""
    key = (key or "").strip()
    if not KEY_RE.fullmatch(key):
        return False, "Invalid key format."
    if _cfg("enabled", "0") != "1":
        return False, "Reset is temporarily unavailable."
    now = int(time.time())
    row = H["q"]("SELECT id FROM license_keys WHERE reseller_id=? AND key=? AND expires>? LIMIT 1",
                 (rid, key, now), one=True)
    if not row:
        return False, "This key is not in your history or it has expired."
    if now - _last_call.get(rid, 0) < 6:
        return False, "Please wait a few seconds."
    _last_call[rid] = now
    day0 = now - (now % 86400)
    used = H["q"]("SELECT COUNT(*) FROM reset_log WHERE key=? AND ok=1 AND ts>=?", (key, day0), one=True)[0]
    per_key = int(H["get_setting"]("rr_daily_per_key", "2") or 2)
    if used >= per_key:
        return False, "Daily reset limit reached for this key."
    try:
        ok, detail = _run(_reset(key))
    except Exception as e:                                    # network, login expired, timeout ...
        ok, detail = False, "relay error: %s" % str(e)[:200]
    H["q"]("INSERT INTO reset_log(reseller_id,key,ok,detail,ts) VALUES(?,?,?,?,?)",
           (rid, key, 1 if ok else 0, detail, now), commit=True)
    if not ok:
        try:
            H["notify_admin"]("\u26a0\ufe0f <b>RESET FAILED</b>\nKey: <code>%s</code>\n%s" % (key, H["esc"](detail)))
        except Exception:
            pass
        return False, "Reset not successful. Try again later."
    return True, "Reset Successful"


# ------------------------------------------------------------------ pages
RESET_HTML = """{% extends 'rbase.html' %}{% block c %}
<div class=card><h3>{{ic('key',22)}} KEY RESET</h3>
<p style="opacity:.8">Paste your key and press Reset.</p>
<input id=k placeholder="Your key" style="width:100%;margin:8px 0" autocomplete=off>
<button id=b onclick="go()">Reset</button>
<div id=o style="margin-top:14px;font-weight:700"></div></div>
<script>
async function go(){
  const k=document.getElementById('k').value.trim(), o=document.getElementById('o'), b=document.getElementById('b');
  if(!k){return}
  b.disabled=true; o.style.color=''; o.textContent='Resetting...';
  try{
    const r=await fetch('/reset/do',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'key='+encodeURIComponent(k)});
    const d=await r.json();
    o.style.color=d.ok?'#22c55e':'#ef4444';
    o.textContent=(d.ok?'\\u2705 ':'\\u274c ')+d.message;
  }catch(e){o.style.color='#ef4444';o.textContent='\\u274c Reset not successful. Try again later.'}
  b.disabled=false;
}
</script>{% endblock %}"""

ADMIN_HTML = """{% extends 'abase.html' %}{% block c %}
<div class=card><h3>{{ic('bot',22)}} Reset Relay</h3>
{% for m in msgs %}<p><b>{{m}}</b></p>{% endfor %}
<p>Status: <b>{{ 'LOGGED IN as ' + me if me else 'not logged in' }}</b> &nbsp; | &nbsp; Reset: <b>{{ 'ON' if enabled else 'OFF' }}</b></p>
<form method=post><input type=hidden name=a value=save>
<p>API ID <input name=api_id value="{{api_id}}"> API HASH <input name=api_hash value="{{api_hash}}" style="width:320px"></p>
<p>Reset bot username <input name=bot value="{{bot}}" placeholder="@something_bot"> &nbsp; Max resets per key per day <input name=per_key value="{{per_key}}" size=3></p>
<p><label><input type=checkbox name=enabled value=1 {{'checked' if enabled}}> Reset ON for everybody</label></p>
<button>Save</button></form></div>
<div class=card><h3>Telegram login (use a separate number)</h3>
<form method=post><input type=hidden name=a value=code><input name=phone placeholder="+91..."> <button>Send code</button></form>
<form method=post style="margin-top:8px"><input type=hidden name=a value=signin><input name=code placeholder="login code"> <input name=password placeholder="2FA password (if any)" type=password> <button>Confirm</button></form>
<form method=post style="margin-top:8px"><input type=hidden name=a value=logout><button class=r>Log out relay</button></form></div>
<div class=card><h3>Test</h3>
<form method=post><input type=hidden name=a value=test><input name=key placeholder="a key sold by this site"> <button>Test reset</button></form></div>
<div class=card><h3>Last resets</h3><table><tr><th>Time</th><th>Reseller</th><th>Key</th><th>OK</th><th>Bot answer</th></tr>
{% for x in log %}<tr><td>{{x.ts|int|ts}}</td><td>{{x.reseller_id}}</td><td>{{x.key}}</td><td>{{'\\u2705' if x.ok else '\\u274c'}}</td><td style="font-size:12px">{{x.detail}}</td></tr>{% endfor %}
</table></div>{% endblock %}"""


def setup(app, **helpers):
    H.update(helpers)
    init_table()
    from flask import request, jsonify, render_template, session
    from templates_ui7 import TEMPLATES as T
    reseller_required, admin_required, api_guard = H["reseller_required"], H["admin_required"], H["api_guard"]

    T["reset.html"] = RESET_HTML
    T["admin_reset.html"] = ADMIN_HTML
    a_link = '<a href="/admin/bots" class="{{\'on\' if page==\'bots\'}}">Bots</a>'
    if a_link in T["abase.html"] and "/admin/reset-relay" not in T["abase.html"]:
        T["abase.html"] = T["abase.html"].replace(
            a_link, a_link + '<a href="/admin/reset-relay" class="{{\'on\' if page==\'resetrelay\'}}">Reset Relay</a>', 1)
    r_link = '<a href="/history" class="{{\'on\' if page==\'history\'}}">{{ic(\'history\')}} Key History</a>'
    if r_link in T["rbase.html"] and 'href="/reset"' not in T["rbase.html"]:
        T["rbase.html"] = T["rbase.html"].replace(
            r_link, r_link + '<a href="/reset" class="{{\'on\' if page==\'reset\'}}">{{ic(\'key\')}} Key Reset</a>', 1)

    @app.template_filter("ts")
    def _ts(v):
        return time.strftime("%d %b %H:%M:%S", time.gmtime(int(v) + int(H.get("tz_offset", 0) or 0)))

    @app.route("/reset")
    @reseller_required
    def reset_page():
        return render_template("reset.html", r=request.r, page="reset")

    @app.route("/reset/do", methods=["POST"])
    @reseller_required
    def reset_do():
        ok, msg = do_reset(request.r["id"], request.form.get("key", ""))
        return jsonify(ok=ok, message=msg)

    @app.route("/api/v1/reset", methods=["POST"])
    @api_guard
    def api_reset():
        d = request.get_json(silent=True) or request.form
        ok, msg = do_reset(request.r["id"], d.get("key", ""))
        return jsonify(success=ok, status=("success" if ok else "failed"), message=msg), (200 if ok else 400)

    @app.route("/admin/reset-relay", methods=["GET", "POST"])
    @admin_required
    def admin_reset_relay():
        msgs = []
        if request.method == "POST":
            a, f = request.form.get("a"), request.form
            try:
                if a == "save":
                    _set("api_id", f.get("api_id", "").strip())
                    _set("api_hash", f.get("api_hash", "").strip())
                    _set("bot", f.get("bot", "").strip().lstrip("@"))
                    _set("enabled", "1" if f.get("enabled") else "0")
                    H["set_setting"]("rr_daily_per_key", str(int(f.get("per_key") or 2)))
                    msgs.append("Saved.")
                elif a == "code":
                    _run(_send_code(f.get("phone", "").strip()))
                    msgs.append("Code sent to Telegram. Enter it below.")
                elif a == "signin":
                    res = _run(_sign_in(f.get("code", "").strip(), f.get("password", "")))
                    msgs.append("Logged in." if res == "ok" else "2FA password needed - enter it and press Confirm.")
                elif a == "logout":
                    _run(_logout())
                    msgs.append("Logged out.")
                elif a == "test":
                    key = f.get("key", "").strip()
                    row = H["q"]("SELECT reseller_id FROM license_keys WHERE key=? ORDER BY id DESC LIMIT 1", (key,), one=True)
                    if not row:
                        msgs.append("That key was not sold by this site.")
                    else:
                        ok, m = do_reset(row["reseller_id"], key)
                        last = H["q"]("SELECT detail FROM reset_log ORDER BY id DESC LIMIT 1", one=True)
                        msgs.append(("SUCCESS - " if ok else "FAILED - ") + (last["detail"] if last else m))
            except Exception as e:
                msgs.append("Error: %s" % str(e)[:300])
        log = H["q"]("SELECT * FROM reset_log ORDER BY id DESC LIMIT 50")
        return render_template("admin_reset.html", msgs=msgs, me=_cfg("me"), enabled=_cfg("enabled", "0") == "1",
                               api_id=_cfg("api_id"), api_hash=_cfg("api_hash"), bot=_cfg("bot"),
                               per_key=H["get_setting"]("rr_daily_per_key", "2"), log=log, page="resetrelay")
