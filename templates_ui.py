CSS = """
:root{--bg:#04040a;--card:rgba(17,17,30,.72);--bd:rgba(139,92,246,.25);--tx:#eef0ff;--mu:#8b8fa8;--ac:#8b5cf6;--ac2:#22d3ee;--ok:#10b981;--er:#f43f5e;--gl:0 0 22px rgba(139,92,246,.45)}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;min-height:100vh;color:var(--tx);font:15px/1.5 'Inter',system-ui,Segoe UI,Arial,sans-serif;background:var(--bg);
background-image:radial-gradient(60% 50% at 15% 0%,rgba(139,92,246,.18),transparent 70%),radial-gradient(50% 45% at 100% 20%,rgba(34,211,238,.12),transparent 70%),linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);
background-size:auto,auto,44px 44px,44px 44px;background-attachment:fixed}
body::before,body::after{content:"";position:fixed;width:340px;height:340px;border-radius:50%;filter:blur(110px);opacity:.28;z-index:-1;animation:fl 14s ease-in-out infinite alternate}
body::before{background:#8b5cf6;left:-90px;bottom:-60px}body::after{background:#22d3ee;right:-100px;top:35%;animation-delay:-6s}
@keyframes fl{to{transform:translate(70px,-60px) scale(1.2)}}
a{color:var(--ac2);text-decoration:none}h1,h2,h3{margin:.3em 0;letter-spacing:-.01em}
h2{font-size:24px;background:linear-gradient(90deg,#fff,#c4b5fd 60%,#67e8f9);-webkit-background-clip:text;background-clip:text;color:transparent}
.wrap{max-width:1020px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:18px;margin:14px 0;backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);box-shadow:0 8px 30px rgba(0,0,0,.45);transition:.25s}
.card:hover{border-color:rgba(139,92,246,.5);box-shadow:0 8px 34px rgba(0,0,0,.5),0 0 26px rgba(139,92,246,.18)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:14px}
.stat{position:relative;overflow:hidden;background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:16px;backdrop-filter:blur(14px);transition:.25s}
.stat:hover{transform:translateY(-3px);box-shadow:var(--gl)}
.stat::after{content:"";position:absolute;inset:auto -20% -60% auto;width:90px;height:90px;background:var(--ac);filter:blur(45px);opacity:.35}
.stat b{display:block;font-size:28px;margin-top:4px;background:linear-gradient(90deg,#fff,#a5f3fc);-webkit-background-clip:text;background-clip:text;color:transparent}
.mu{color:var(--mu);font-size:13px}
input,select,button,textarea{font:inherit;padding:10px 13px;border-radius:10px;border:1px solid rgba(139,92,246,.28);background:rgba(6,6,14,.8);color:var(--tx);max-width:100%;outline:0;transition:.2s}
input:focus,select:focus,textarea:focus{border-color:var(--ac);box-shadow:0 0 0 3px rgba(139,92,246,.22),0 0 16px rgba(139,92,246,.3)}
textarea{width:100%;min-height:120px;font-family:ui-monospace,Consolas,monospace;font-size:13px}
button,.btn{background:linear-gradient(135deg,#8b5cf6,#6366f1 55%,#22d3ee);border:0;color:#fff;cursor:pointer;display:inline-block;padding:10px 18px;border-radius:10px;font-weight:600;box-shadow:0 4px 18px rgba(139,92,246,.45);transition:.2s}
button:hover,.btn:hover{transform:translateY(-1px);box-shadow:0 6px 26px rgba(139,92,246,.7);filter:brightness(1.08)}
button:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none}
button.g{background:linear-gradient(135deg,#059669,#10b981);box-shadow:0 4px 16px rgba(16,185,129,.4)}
button.r{background:linear-gradient(135deg,#e11d48,#f43f5e);box-shadow:0 4px 16px rgba(244,63,94,.4)}
button.o{background:transparent;border:1px solid var(--bd);box-shadow:none}
form.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
table{width:100%;border-collapse:collapse}th,td{padding:10px 8px;border-bottom:1px solid rgba(139,92,246,.14);text-align:left;font-size:14px}
th{color:var(--mu);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.06em}tr:hover td{background:rgba(139,92,246,.05)}
.tw{overflow-x:auto}.flash{padding:12px 16px;border-radius:12px;margin:10px 0;word-break:break-all;backdrop-filter:blur(10px)}
.flash.ok{background:rgba(16,185,129,.12);border:1px solid var(--ok);box-shadow:0 0 18px rgba(16,185,129,.25)}
.flash.err{background:rgba(244,63,94,.12);border:1px solid var(--er);box-shadow:0 0 18px rgba(244,63,94,.25)}
.top{display:flex;align-items:center;gap:12px;padding:11px 16px;background:rgba(8,8,18,.75);backdrop-filter:blur(16px);border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:20}
.logo{font-weight:800;letter-spacing:.04em;background:linear-gradient(90deg,#c4b5fd,#22d3ee);-webkit-background-clip:text;background-clip:text;color:transparent;text-shadow:0 0 24px rgba(139,92,246,.6)}
.burger{background:none!important;box-shadow:none!important;border:0;padding:4px 8px;font-size:26px;line-height:1;color:var(--tx)}
.side{position:fixed;top:0;left:-280px;width:270px;height:100%;background:rgba(8,8,18,.96);border-right:1px solid var(--bd);padding:20px;transition:.28s;z-index:30;box-shadow:12px 0 40px rgba(0,0,0,.6)}
.side.open{left:0}.side a{display:block;padding:12px 14px;border-radius:10px;color:var(--tx);margin:3px 0;transition:.2s}
.side a.on,.side a:hover{background:linear-gradient(90deg,rgba(139,92,246,.28),rgba(34,211,238,.1));box-shadow:inset 3px 0 0 var(--ac)}
.shade{display:none;position:fixed;inset:0;background:#000a;z-index:25;backdrop-filter:blur(3px)}.shade.open{display:block}
.player{display:flex;align-items:center;gap:6px;background:rgba(6,6,14,.8);border:1px solid var(--bd);border-radius:30px;padding:3px 10px;margin-left:auto;max-width:60%}
.player button{background:none;border:0;box-shadow:none;padding:4px 7px;font-size:17px;color:var(--tx)}.player span{font-size:12px;color:var(--mu);overflow:hidden;white-space:nowrap;text-overflow:ellipsis;max-width:130px}
pre,code{background:rgba(6,6,14,.85);border:1px solid var(--bd);border-radius:8px;padding:2px 7px;word-break:break-all;color:#c4b5fd}pre{padding:12px;overflow-x:auto;white-space:pre-wrap;margin:6px 0}
.pill{padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600}.pill.a{background:rgba(16,185,129,.15);color:#34d399;box-shadow:0 0 10px rgba(16,185,129,.3)}.pill.e{background:rgba(244,63,94,.15);color:#fb7185}.pill.p{background:rgba(139,92,246,.18);color:#c4b5fd}.pill.c{background:rgba(34,211,238,.14);color:#67e8f9}
.nav{display:flex;gap:6px;flex-wrap:wrap;align-items:center;padding:11px 16px;background:rgba(8,8,18,.75);backdrop-filter:blur(16px);border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:20}
.nav a{padding:8px 14px;border-radius:10px;color:var(--tx);transition:.2s}.nav a:hover{background:rgba(139,92,246,.15)}.nav a.on{background:linear-gradient(135deg,#8b5cf6,#6366f1);box-shadow:var(--gl)}
.center{max-width:400px;margin:13vh auto;padding:14px}.center input{width:100%;margin:7px 0}
.center .card{box-shadow:0 0 60px rgba(139,92,246,.3),0 10px 40px rgba(0,0,0,.6);border-color:rgba(139,92,246,.45)}
.big{font-size:30px;text-align:center;margin-bottom:4px}.hero{background:linear-gradient(135deg,rgba(139,92,246,.22),rgba(34,211,238,.1));text-align:center;padding:26px}
"""

FLASH = """{% with m=get_flashed_messages(with_categories=true) %}{% for c,t in m %}<div class="flash {{c}}">{{t}}</div>{% endfor %}{% endwith %}"""
HEAD = """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><meta name=theme-color content="#04040a"><link rel=preconnect href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel=stylesheet><title>"""
T = {}
T["login.html"] = HEAD + """{{title}}</title><style>""" + CSS + """</style></head><body>
<div class="center"><div class="card"><div class="big">🔐</div><h2 style="text-align:center">{{title}}</h2><p class=mu style="text-align:center">Sign in to continue</p>""" + FLASH + """
<form method=post action="{{action}}"><input name=username placeholder="Username" required autofocus autocomplete=username>
<input name=password type=password placeholder="Password" required autocomplete=current-password><button style="width:100%;margin-top:10px">Login →</button></form></div></div></body></html>"""

T["rbase.html"] = HEAD + """Reseller Panel</title><style>""" + CSS + """</style></head><body>
<div class="shade" id=shade></div>
<div class="side" id=side><h3 class=logo>⚡ RESELLER</h3><div class=mu>👤 {{r.username}}</div><div class=mu>Balance: <b style="color:#67e8f9">{{r.balance|money}}</b></div><hr style="border:0;border-top:1px solid rgba(139,92,246,.25);margin:14px 0">
<a href="/dashboard" class="{{'on' if page=='dashboard'}}">📊 Dashboard</a>
<a href="/generate" class="{{'on' if page=='generate'}}">🔑 Generate Key</a>
<a href="/history" class="{{'on' if page=='history'}}">📜 History</a>
<a href="/api-docs" class="{{'on' if page=='api'}}">🔌 API &amp; Docs</a>
<a href="/logout">🚪 Logout</a></div>
<div class="top"><button class="burger" id=bg>☰</button><b class=logo>RESELLER PANEL</b>
<div class="player" id=pl><button id=pv>⏮</button><button id=pp>▶</button><button id=nx>⏭</button><span id=ttl>…</span><audio id=au preload=auto></audio></div></div>
<div class="wrap">""" + FLASH + """{% block c %}{% endblock %}</div>
<script>
const S=document.getElementById('side'),H=document.getElementById('shade');
function tg(){S.classList.toggle('open');H.classList.toggle('open')}bg.onclick=tg;H.onclick=tg;
(async()=>{let L=[];try{L=await(await fetch('/music.json')).json()}catch(e){}
if(!L.length){pl.style.display='none';return}
let i=+localStorage.mi||0;if(i>=L.length)i=0;
function load(n,seek){i=(n+L.length)%L.length;au.src=L[i].url;ttl.textContent=L[i].title;localStorage.mi=i;
 if(seek)au.addEventListener('loadedmetadata',()=>{au.currentTime=seek},{once:true})}
function play(){au.play().then(()=>{pp.textContent='⏸';localStorage.mp=1}).catch(()=>{pp.textContent='▶'})}
function pause(){au.pause();pp.textContent='▶';localStorage.mp=0}
load(i,+localStorage.mt||0);
pp.onclick=()=>au.paused?play():pause();
nx.onclick=()=>{load(i+1);play()};pv.onclick=()=>{load(i-1);play()};
au.onended=()=>{load(i+1);play()};
setInterval(()=>{if(!au.paused)localStorage.mt=au.currentTime},1000);
if(localStorage.mp!=='0'){play();document.addEventListener('click',()=>{if(au.paused&&localStorage.mp!=='0')play()},{once:true})}
})();
</script></body></html>"""

T["dashboard.html"] = """{% extends 'rbase.html' %}{% block c %}<div class="card hero"><h2 style="font-size:28px">Welcome back, {{r.username}} 👋</h2><div class=mu>Your balance</div><div style="font-size:40px;font-weight:800;color:#67e8f9;text-shadow:0 0 28px rgba(34,211,238,.6)">{{r.balance|money}}</div><a class=btn href="/generate" style="margin-top:10px">🔑 Generate New Key</a></div>
<div class=grid>
<div class=stat><span class=mu>🔑 Total Generated</span><b>{{st.total}}</b></div>
<div class=stat><span class=mu>📅 Today</span><b>{{st.today}}</b></div>
<div class=stat><span class=mu>✅ Active</span><b>{{st.active}}</b></div>
<div class=stat><span class=mu>⌛ Expired</span><b>{{st.expired}}</b></div>
<div class=stat><span class=mu>💸 Total Spent</span><b>{{st.spent|money}}</b></div></div>{% endblock %}"""

T["generate.html"] = """{% extends 'rbase.html' %}{% block c %}<h2>🔑 Generate Key</h2><div class=mu>Balance: <b style="color:#67e8f9">{{r.balance|money}}</b></div>
{% for p in cat %}<div class=card><h3>{{p.name}}</h3>{% if not p.plans %}<div class=mu>No plans yet</div>{% endif %}
<div class=tw><table>{% for pl in p.plans %}{% set out = pl.mode=='stock' and pl.stock==0 %}<tr><td>{{pl.name}}<div class=mu>{{pl.days}} day(s){% if pl.mode=='stock' %} · {{pl.stock}} in stock{% endif %}</div></td>
<td><b style="color:#67e8f9">{{pl.price|money}}</b>{% if pl.custom %} <span class="pill p">special</span>{% endif %}</td>
<td style="text-align:right"><form method=post onsubmit="return confirm('Purchase {{pl.name}} for {{pl.price|money}}?')">
<input type=hidden name=plan_id value="{{pl.id}}"><button class=g {{'disabled' if out}}>{{'Out of stock' if out else 'Purchase Now'}}</button></form></td></tr>{% endfor %}</table></div></div>
{% else %}<div class=card>No products available.</div>{% endfor %}{% endblock %}"""

T["history.html"] = """{% extends 'rbase.html' %}{% block c %}<h2>📜 History</h2><div class="card tw"><table>
<tr><th>Key</th><th>Product / Plan</th><th>Price</th><th>Created</th><th>Expires</th><th>Status</th></tr>
{% for x in rows %}<tr><td><code>{{x.key}}</code></td><td>{{x.product_name}}<br><span class=mu>{{x.plan_name}}</span></td><td>{{x.price|money}}</td>
<td>{{x.created|dt}}</td><td>{{x.expires|dt}}</td><td>{% if x.expires>now %}<span class="pill a">Active</span>{% else %}<span class="pill e">Expired</span>{% endif %}</td></tr>
{% else %}<tr><td colspan=6>No keys generated yet.</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["api.html"] = """{% extends 'rbase.html' %}{% block c %}<h2>🔌 API &amp; Docs</h2>
<div class=card><h3>Your Credentials</h3>
<p class=mu>Server URL</p><pre>{{base}}</pre><p class=mu>API Key</p><pre>{{r.api_key}}</pre>
<form method=post onsubmit="return confirm('Old key will stop working. Continue?')"><button class=r>Regenerate API Key</button></form></div>
<div class=card><h3>Authentication</h3><p>Send your key in every request header:</p><pre>X-API-Key: YOUR_API_KEY</pre></div>
<div class=card><h3>1. Check Balance</h3><pre>GET {{base}}/api/v1/balance</pre>
<pre>curl -H "X-API-Key: {{r.api_key}}" {{base}}/api/v1/balance</pre></div>
<div class=card><h3>2. Products &amp; Plan IDs</h3><p>Prices shown are <b>your</b> prices.</p><pre>GET {{base}}/api/v1/products</pre></div>
<div class=card><h3>3. Purchase (Generate Key)</h3><pre>POST {{base}}/api/v1/purchase
Content-Type: application/json

{"plan_id": 3}</pre>
<pre>{"success": true, "key": "PUBGCH-A1B2-C3D4-E5F6-7890", "product": "PUBG Cheat",
 "plan": "1 Day", "price": 90.0, "expires_at": 1767225600, "balance": 60.0}</pre></div>
<div class=card><h3>4. History</h3><pre>GET {{base}}/api/v1/history</pre><p class=mu>Returns your last 100 keys.</p></div>
<div class=card><h3>Errors</h3><table><tr><th>HTTP</th><th>error</th></tr>
<tr><td>401</td><td>INVALID_API_KEY</td></tr><tr><td>402</td><td>Insufficient balance</td></tr>
<tr><td>400</td><td>plan_id required / Plan not found / Out of stock / Account disabled</td></tr></table></div>
<div class=card><h3>Python Example</h3><pre>import requests
BASE="{{base}}"; H={"X-API-Key":"{{r.api_key}}"}
print(requests.get(BASE+"/api/v1/balance",headers=H).json())
r=requests.post(BASE+"/api/v1/purchase",headers=H,json={"plan_id":3}).json()
print(r.get("key"))</pre></div>{% endblock %}"""

T["abase.html"] = HEAD + """Admin</title><style>""" + CSS + """</style></head><body>
<div class=nav><b class=logo style="padding:7px 10px">🛠 ADMIN</b><a href="/admin" class="{{'on' if page=='home'}}">Home</a><a href="/admin/products" class="{{'on' if page=='products'}}">Products</a>
<a href="/admin/keys" class="{{'on' if page=='keys'}}">Sold Keys</a><a href="/admin/resellers" class="{{'on' if page=='resellers'}}">Resellers</a><a href="/admin/music" class="{{'on' if page=='music'}}">Music</a><a href="/admin/logout" style="margin-left:auto">Logout</a></div>
<div class=wrap>""" + FLASH + """{% block c %}{% endblock %}</div></body></html>"""

T["admin_home.html"] = """{% extends 'abase.html' %}{% block c %}<h2>Overview</h2><div class=grid>
<div class=stat><span class=mu>Resellers</span><b>{{st.resellers}}</b></div><div class=stat><span class=mu>Products</span><b>{{st.products}}</b></div>
<div class=stat><span class=mu>Keys Sold</span><b>{{st.keys}}</b></div><div class=stat><span class=mu>Revenue</span><b>{{st.revenue|money}}</b></div>
<div class=stat><span class=mu>Credit Outstanding</span><b>{{st.credit|money}}</b></div></div>
<div class="card tw"><h3>Recent Sales</h3><table><tr><th>Reseller</th><th>Product</th><th>Plan</th><th>Price</th><th>Time</th></tr>
{% for x in recent %}<tr><td>{{x.username}}</td><td>{{x.product_name}}</td><td>{{x.plan_name}}</td><td>{{x.price|money}}</td><td>{{x.created|dt}}</td></tr>
{% else %}<tr><td colspan=5>No sales yet</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["admin_products.html"] = """{% extends 'abase.html' %}{% block c %}<h2>Products &amp; Plans</h2>
<div class=card><h3>Add Product</h3><form class=row method=post><input type=hidden name=action value=product><input name=name placeholder="Product name" required><button>Add</button></form></div>
{% if prods %}<div class=card><h3>Add Plan</h3><form class=row method=post><input type=hidden name=action value=plan>
<select name=product_id>{% for x in prods %}<option value="{{x.p.id}}">{{x.p.name}}</option>{% endfor %}</select>
<input name=name placeholder="Plan name (e.g. 1 Day)" required><input name=days type=number min=1 placeholder="Days" required style="width:90px">
<input name=price type=number step=any min=0 placeholder="Base price" required style="width:120px">
<select name=mode><option value=stock>Manual keys</option><option value=api>External API</option><option value=random>Auto-generate</option></select><button>Add Plan</button></form></div>{% endif %}
{% for x in prods %}<div class=card><div style="display:flex;justify-content:space-between;align-items:center"><h3>{{x.p.name}}</h3>
<form method=post onsubmit="return confirm('Delete product and all plans?')"><input type=hidden name=action value=del_product><input type=hidden name=product_id value="{{x.p.id}}"><button class=r>Delete</button></form></div>
<div class=tw><table><tr><th>ID</th><th>Plan</th><th>Days</th><th>Price</th><th>Key source</th><th></th></tr>
{% for e in x.plans %}{% set pl=e.pl %}<tr><form method=post><input type=hidden name=action value=edit_plan><input type=hidden name=plan_id value="{{pl.id}}">
<td>{{pl.id}}</td><td><input name=name value="{{pl.name}}" style="width:120px"></td><td><input name=days type=number value="{{pl.days}}" style="width:65px"></td>
<td><input name=price type=number step=any value="{{pl.price}}" style="width:90px"></td>
<td><select name=mode>{% for v,l in [('stock','Manual keys'),('api','External API'),('random','Auto-generate')] %}<option value="{{v}}" {{'selected' if (pl.mode or 'random')==v}}>{{l}}</option>{% endfor %}</select></td>
<td style="white-space:nowrap"><button class=g>Save</button></form>
<a class=btn href="/admin/stock/{{pl.id}}" style="padding:8px 12px">🔑 Keys <span class="pill c">{{e.stock}}</span></a>
<a class=btn href="/admin/plan-api/{{pl.id}}" style="padding:8px 12px">🔌 API</a>
<form method=post style="display:inline" onsubmit="return confirm('Delete plan?')"><input type=hidden name=action value=del_plan><input type=hidden name=plan_id value="{{pl.id}}"><button class=r>✕</button></form></td></tr>
{% else %}<tr><td colspan=6>No plans</td></tr>{% endfor %}</table></div></div>{% endfor %}{% endblock %}"""

T["admin_stock.html"] = """{% extends 'abase.html' %}{% block c %}<a href="/admin/products">← Back</a><h2>🔑 {{pl.pname}} — {{pl.name}}</h2>
<div class=mu>Key source: <span class="pill p">{{ {'stock':'Manual keys','api':'External API','random':'Auto-generate'}[pl.mode or 'random'] }}</span> (change it on the Products page; keys below are used only in "Manual keys" mode)</div>
<div class=card><h3>Add Keys</h3><form method=post><input type=hidden name=action value=add><textarea name=keys placeholder="One key per line" required></textarea><button class=g style="margin-top:8px">➕ Add Keys</button></form></div>
<div class="card tw"><div style="display:flex;justify-content:space-between;align-items:center"><h3>All Keys ({{rows|length}})</h3>
<form method=post onsubmit="return confirm('Remove all used keys?')"><input type=hidden name=action value=clear_used><button class="r">Clear used</button></form></div>
<table><tr><th>#</th><th>Key</th><th>Status</th><th></th></tr>
{% for k in rows %}<tr><td>{{k.id}}</td>
<td>{% if k.used %}<code>{{k.key}}</code>{% else %}<form method=post class=row style="flex-wrap:nowrap"><input type=hidden name=action value=edit><input type=hidden name=id value="{{k.id}}"><input name=key value="{{k.key}}" style="min-width:220px"><button class=g style="padding:8px 12px">Save</button></form>{% endif %}</td>
<td>{% if k.used %}<span class="pill e">Sold</span><div class=mu>{{k.used_by}} · {{k.used_at|dt}}</div>{% else %}<span class="pill a">Available</span>{% endif %}</td>
<td><form method=post onsubmit="return confirm('Delete this key?')"><input type=hidden name=action value=delete><input type=hidden name=id value="{{k.id}}"><button class=r>Delete</button></form></td></tr>
{% else %}<tr><td colspan=4>No keys added yet.</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["admin_plan_api.html"] = """{% extends 'abase.html' %}{% block c %}<a href="/admin/products">← Back</a><h2>🔌 {{pl.pname}} — {{pl.name}} (External API)</h2>
<div class=card><form method=post>
<p class=mu>API URL</p><input name=ext_url value="{{pl.ext_url or ''}}" placeholder="https://provider.com/api/generate" style="width:100%">
<p class=mu>Method</p><select name=ext_method><option {{'selected' if pl.ext_method=='POST'}}>POST</option><option {{'selected' if pl.ext_method=='GET'}}>GET</option></select>
<p class=mu>Headers (JSON)</p><textarea name=ext_headers placeholder='{"X-API-Key": "PROVIDER_KEY"}'>{{pl.ext_headers or ''}}</textarea>
<p class=mu>Body / params (JSON)</p><textarea name=ext_body placeholder='{"duration": "{days}"}'>{{pl.ext_body or ''}}</textarea>
<p class=mu>Key location in the response (e.g. <code>data.key</code>). Empty = whole response text.</p><input name=ext_path value="{{pl.ext_path or ''}}" placeholder="data.key" style="width:100%">
<p class=mu>Placeholders: <code>{days}</code> <code>{plan}</code> <code>{product}</code>. If the provider fails, the reseller's balance is refunded automatically.</p>
<button class=g>💾 Save API Settings</button></form></div>{% endblock %}"""

T["admin_keys.html"] = """{% extends 'abase.html' %}{% block c %}<h2>Sold Keys</h2><div class="card tw"><table>
<tr><th>Reseller</th><th>Key</th><th>Product / Plan</th><th>Price</th><th>Via</th><th>Created</th><th>Status</th></tr>
{% for x in rows %}<tr><td>{{x.username}}</td><td><code>{{x.key}}</code></td><td>{{x.product_name}}<br><span class=mu>{{x.plan_name}}</span></td><td>{{x.price|money}}</td><td>{{x.via}}</td><td>{{x.created|dt}}</td>
<td>{% if x.expires>now %}<span class="pill a">Active</span>{% else %}<span class="pill e">Expired</span>{% endif %}</td></tr>
{% else %}<tr><td colspan=7>No keys sold yet.</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["admin_resellers.html"] = """{% extends 'abase.html' %}{% block c %}<h2>Resellers</h2>
<div class=card><h3>Create Reseller</h3><form class=row method=post><input name=username placeholder="Username" required><input name=password placeholder="Password" required>
<input name=credit type=number step=any value=0 placeholder="Starting credit" style="width:140px"><button>Create</button></form></div>
<div class="card tw"><table><tr><th>User</th><th>Balance</th><th>Keys</th><th>Status</th><th></th></tr>
{% for x in rows %}<tr><td>{{x.username}}</td><td>{{x.balance|money}}</td><td>{{x.kc}}</td><td>{% if x.active %}<span class="pill a">Active</span>{% else %}<span class="pill e">Disabled</span>{% endif %}</td>
<td><a class=btn href="/admin/reseller/{{x.id}}">Manage</a></td></tr>{% else %}<tr><td colspan=5>No resellers</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["admin_reseller.html"] = """{% extends 'abase.html' %}{% block c %}<a href="/admin/resellers">← Back</a><h2>{{r.username}} <span class=mu>Balance: {{r.balance|money}}</span></h2>
<div class=card><h3>Add / Deduct Credit</h3><form class=row method=post><input type=hidden name=action value=credit><input name=amount type=number step=any placeholder="Amount (negative to deduct)" required><button class=g>Update</button></form></div>
<div class=card><h3>Change Password</h3><form class=row method=post><input type=hidden name=action value=password><input name=password placeholder="New password" required><button>Change</button></form></div>
<div class=card><h3>Custom Prices</h3><p class=mu>Leave empty to use the base price.</p><form method=post><input type=hidden name=action value=prices><div class=tw><table>
<tr><th>Product</th><th>Plan</th><th>Custom Price</th></tr>
{% for p in cat %}{% for pl in p.plans %}<tr><td>{{p.name}}</td><td>{{pl.name}}</td><td><input name="p_{{pl.id}}" type=number step=any value="{{pl.price if pl.custom}}" style="width:120px"></td></tr>{% endfor %}{% endfor %}</table></div>
<button class=g style="margin-top:10px">Save Prices</button></form></div>
<div class=card><form method=post style="display:inline"><input type=hidden name=action value=toggle><button>{{'Disable' if r.active else 'Enable'}} Account</button></form>
<form method=post style="display:inline" onsubmit="return confirm('Delete reseller and history?')"><input type=hidden name=action value=delete><button class=r>Delete Reseller</button></form></div>{% endblock %}"""

T["admin_music.html"] = """{% extends 'abase.html' %}{% block c %}<h2>🎵 Music ({{rows|length}}/{{mx}})</h2>
<div class=card><form method=post enctype=multipart/form-data class=row><input name=title placeholder="Title (optional)"><input type=file name=file accept="audio/*">
<span class=mu>or</span><input name=url placeholder="Direct audio URL (.mp3)"><button>Add Song</button></form>
<p class=mu>Songs play in order at the top of the reseller panel. Free Render disk resets on redeploy, so direct URLs are safer than uploads.</p></div>
<div class="card tw"><table>{% for m in rows %}<tr><td>{{loop.index}}</td><td>{{m.title}}</td><td><audio controls preload=none src="{{m.url}}" style="height:32px"></audio></td>
<td><form method=post><input type=hidden name=action value=delete><input type=hidden name=id value="{{m.id}}"><button class=r>Delete</button></form></td></tr>
{% else %}<tr><td>No songs</td></tr>{% endfor %}</table></div>{% endblock %}"""

TEMPLATES = T
