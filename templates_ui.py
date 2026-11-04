CSS = """
:root{--bg:#0d1117;--card:#161b22;--bd:#30363d;--tx:#e6edf3;--mu:#8b949e;--ac:#2f81f7;--ok:#238636;--er:#da3633}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px system-ui,Segoe UI,Arial,sans-serif}
a{color:var(--ac);text-decoration:none}h1,h2,h3{margin:.3em 0}
.wrap{max-width:980px;margin:0 auto;padding:14px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px}
.stat b{display:block;font-size:26px;margin-top:4px}.mu{color:var(--mu);font-size:13px}
input,select,button,textarea{font:inherit;padding:9px 11px;border-radius:8px;border:1px solid var(--bd);background:#0d1117;color:var(--tx);max-width:100%}
button,.btn{background:var(--ac);border-color:var(--ac);color:#fff;cursor:pointer;display:inline-block;padding:9px 14px;border-radius:8px}
button.g{background:var(--ok);border-color:var(--ok)}button.r{background:var(--er);border-color:var(--er)}
form.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
table{width:100%;border-collapse:collapse}th,td{padding:8px;border-bottom:1px solid var(--bd);text-align:left;font-size:14px}
.tw{overflow-x:auto}.flash{padding:11px 14px;border-radius:8px;margin:10px 0;word-break:break-all}
.flash.ok{background:#12301c;border:1px solid var(--ok)}.flash.err{background:#3a1416;border:1px solid var(--er)}
.top{display:flex;align-items:center;gap:12px;padding:10px 14px;background:var(--card);border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:20}
.burger{background:none;border:0;padding:4px 8px;font-size:26px;line-height:1;color:var(--tx)}
.side{position:fixed;top:0;left:-270px;width:260px;height:100%;background:var(--card);border-right:1px solid var(--bd);padding:18px;transition:.25s;z-index:30}
.side.open{left:0}.side a{display:block;padding:11px 12px;border-radius:8px;color:var(--tx)}.side a.on,.side a:hover{background:#21262d}
.shade{display:none;position:fixed;inset:0;background:#0008;z-index:25}.shade.open{display:block}
.player{display:flex;align-items:center;gap:8px;background:#0d1117;border:1px solid var(--bd);border-radius:30px;padding:4px 10px;margin-left:auto;max-width:60%}
.player button{background:none;border:0;padding:4px 7px;font-size:18px;color:var(--tx)}.player span{font-size:12px;color:var(--mu);overflow:hidden;white-space:nowrap;text-overflow:ellipsis;max-width:140px}
pre,code{background:#0d1117;border:1px solid var(--bd);border-radius:8px;padding:2px 6px;word-break:break-all}pre{padding:12px;overflow-x:auto;white-space:pre-wrap}
.pill{padding:2px 9px;border-radius:20px;font-size:12px}.pill.a{background:#12301c;color:#56d364}.pill.e{background:#3a1416;color:#ff7b72}
.nav{display:flex;gap:6px;flex-wrap:wrap;padding:10px 14px;background:var(--card);border-bottom:1px solid var(--bd)}.nav a{padding:7px 12px;border-radius:8px;color:var(--tx)}.nav a.on{background:var(--ac)}
.center{max-width:380px;margin:12vh auto;padding:14px}.center input{width:100%;margin:6px 0}
"""

FLASH = """{% with m=get_flashed_messages(with_categories=true) %}{% for c,t in m %}<div class="flash {{c}}">{{t}}</div>{% endfor %}{% endwith %}"""

T = {}
T["login.html"] = """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{{title}}</title><style>""" + CSS + """</style></head><body>
<div class="center"><div class="card"><h2>🔐 {{title}}</h2>""" + FLASH + """
<form method=post action="{{action}}"><input name=username placeholder="Username" required autofocus>
<input name=password type=password placeholder="Password" required><button style="width:100%;margin-top:8px">Login</button></form></div></div></body></html>"""

T["rbase.html"] = """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Reseller Panel</title><style>""" + CSS + """</style></head><body>
<div class="shade" id=shade></div>
<div class="side" id=side><h3>👤 {{r.username}}</h3><div class=mu>Balance: <b>{{r.balance|money}}</b></div><hr style="border-color:#30363d">
<a href="/dashboard" class="{{'on' if page=='dashboard'}}">📊 Dashboard</a>
<a href="/generate" class="{{'on' if page=='generate'}}">🔑 Generate Key</a>
<a href="/history" class="{{'on' if page=='history'}}">📜 History</a>
<a href="/api-docs" class="{{'on' if page=='api'}}">🔌 API &amp; Docs</a>
<a href="/logout">🚪 Logout</a></div>
<div class="top"><button class="burger" id=bg>☰</button><b>Reseller Panel</b>
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

T["dashboard.html"] = """{% extends 'rbase.html' %}{% block c %}<h2>📊 Dashboard</h2>
<div class=grid>
<div class=stat><span class=mu>💰 Balance</span><b>{{r.balance|money}}</b></div>
<div class=stat><span class=mu>🔑 Total Generated</span><b>{{st.total}}</b></div>
<div class=stat><span class=mu>📅 Today</span><b>{{st.today}}</b></div>
<div class=stat><span class=mu>✅ Active</span><b>{{st.active}}</b></div>
<div class=stat><span class=mu>⌛ Expired</span><b>{{st.expired}}</b></div>
<div class=stat><span class=mu>💸 Total Spent</span><b>{{st.spent|money}}</b></div></div>
<div class=card><a class=btn href="/generate">🔑 Generate New Key</a></div>{% endblock %}"""

T["generate.html"] = """{% extends 'rbase.html' %}{% block c %}<h2>🔑 Generate Key</h2><div class=mu>Balance: <b>{{r.balance|money}}</b></div>
{% for p in cat %}<div class=card><h3>{{p.name}}</h3>{% if not p.plans %}<div class=mu>No plans yet</div>{% endif %}
<div class=tw><table>{% for pl in p.plans %}<tr><td>{{pl.name}}<div class=mu>{{pl.days}} day(s)</div></td>
<td><b>{{pl.price|money}}</b>{% if pl.custom %} <span class="pill a">special</span>{% endif %}</td>
<td style="text-align:right"><form method=post onsubmit="return confirm('Purchase {{pl.name}} for {{pl.price|money}}?')">
<input type=hidden name=plan_id value="{{pl.id}}"><button class=g>Purchase Now</button></form></td></tr>{% endfor %}</table></div></div>
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
<div class=card><h3>Authentication</h3><p>Send your key in every request header:</p><pre>X-API-Key: YOUR_API_KEY</pre>
<p class=mu>(or as query param <code>?api_key=YOUR_API_KEY</code>)</p></div>
<div class=card><h3>1. Check Balance</h3><pre>GET {{base}}/api/v1/balance</pre>
<pre>curl -H "X-API-Key: {{r.api_key}}" {{base}}/api/v1/balance</pre>
<pre>{"success": true, "username": "{{r.username}}", "balance": 150.0}</pre></div>
<div class=card><h3>2. Products &amp; Plan IDs</h3><p>Prices shown are <b>your</b> prices.</p><pre>GET {{base}}/api/v1/products</pre>
<pre>{"success": true, "products": [
  {"product_id": 1, "name": "PUBG Cheat",
   "plans": [{"plan_id": 3, "name": "1 Day", "days": 1, "price": 90.0}]}]}</pre></div>
<div class=card><h3>3. Purchase (Generate Key)</h3><pre>POST {{base}}/api/v1/purchase
Content-Type: application/json

{"plan_id": 3}</pre>
<pre>curl -X POST -H "X-API-Key: {{r.api_key}}" -H "Content-Type: application/json" \\
 -d '{"plan_id":3}' {{base}}/api/v1/purchase</pre>
<pre>{"success": true, "key": "PUBGCH-A1B2-C3D4-E5F6-7890", "product": "PUBG Cheat",
 "plan": "1 Day", "price": 90.0, "expires_at": 1767225600, "balance": 60.0}</pre></div>
<div class=card><h3>4. History</h3><pre>GET {{base}}/api/v1/history</pre><p class=mu>Returns your last 100 keys.</p></div>
<div class=card><h3>Errors</h3><table><tr><th>HTTP</th><th>error</th></tr>
<tr><td>401</td><td>INVALID_API_KEY</td></tr><tr><td>402</td><td>Insufficient balance</td></tr>
<tr><td>400</td><td>plan_id required / Plan not found / Account disabled</td></tr></table></div>
<div class=card><h3>Python Example</h3><pre>import requests
BASE="{{base}}"; H={"X-API-Key":"{{r.api_key}}"}
print(requests.get(BASE+"/api/v1/balance",headers=H).json())
r=requests.post(BASE+"/api/v1/purchase",headers=H,json={"plan_id":3}).json()
print(r.get("key"))</pre></div>{% endblock %}"""

T["abase.html"] = """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Admin</title><style>""" + CSS + """</style></head><body>
<div class=nav><b style="padding:7px">🛠 Admin</b><a href="/admin" class="{{'on' if page=='home'}}">Home</a><a href="/admin/products" class="{{'on' if page=='products'}}">Products</a>
<a href="/admin/resellers" class="{{'on' if page=='resellers'}}">Resellers</a><a href="/admin/music" class="{{'on' if page=='music'}}">Music</a><a href="/admin/logout" style="margin-left:auto">Logout</a></div>
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
<input name=price type=number step=any min=0 placeholder="Base price" required style="width:120px"><button>Add Plan</button></form></div>{% endif %}
{% for x in prods %}<div class=card><div class=row style="display:flex;justify-content:space-between"><h3>{{x.p.name}}</h3>
<form method=post onsubmit="return confirm('Delete product and all plans?')"><input type=hidden name=action value=del_product><input type=hidden name=product_id value="{{x.p.id}}"><button class=r>Delete</button></form></div>
<div class=tw><table><tr><th>ID</th><th>Plan</th><th>Days</th><th>Base Price</th><th></th></tr>
{% for pl in x.plans %}<tr><form method=post><input type=hidden name=action value=edit_plan><input type=hidden name=plan_id value="{{pl.id}}">
<td>{{pl.id}}</td><td><input name=name value="{{pl.name}}" style="width:130px"></td><td><input name=days type=number value="{{pl.days}}" style="width:70px"></td>
<td><input name=price type=number step=any value="{{pl.price}}" style="width:100px"></td><td style="white-space:nowrap"><button class=g>Save</button></form>
<form method=post style="display:inline" onsubmit="return confirm('Delete plan?')"><input type=hidden name=action value=del_plan><input type=hidden name=plan_id value="{{pl.id}}"><button class=r>✕</button></form></td></tr>
{% else %}<tr><td colspan=5>No plans</td></tr>{% endfor %}</table></div></div>{% endfor %}{% endblock %}"""

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
<tr><th>Product</th><th>Plan</th><th>Base</th><th>Custom Price</th></tr>
{% for p in cat %}{% for pl in p.plans %}<tr><td>{{p.name}}</td><td>{{pl.name}}</td><td>-</td><td><input name="p_{{pl.id}}" type=number step=any value="{{pl.price if pl.custom}}" style="width:120px"></td></tr>{% endfor %}{% endfor %}</table></div>
<button class=g style="margin-top:10px">Save Prices</button></form></div>
<div class=card><form method=post style="display:inline"><input type=hidden name=action value=toggle><button>{{'Disable' if r.active else 'Enable'}} Account</button></form>
<form method=post style="display:inline" onsubmit="return confirm('Delete reseller and history?')"><input type=hidden name=action value=delete><button class=r>Delete Reseller</button></form></div>{% endblock %}"""

T["admin_music.html"] = """{% extends 'abase.html' %}{% block c %}<h2>🎵 Music ({{rows|length}}/{{mx}})</h2>
<div class=card><form method=post enctype=multipart/form-data class=row><input name=title placeholder="Title (optional)"><input type=file name=file accept="audio/*">
<span class=mu>or</span><input name=url placeholder="Direct audio URL (.mp3)"><button>Add Song</button></form>
<p class=mu>Songs play in this order, one after another, at the top of the reseller panel. Free Render disk resets on redeploy, so direct URLs are safer than uploads.</p></div>
<div class="card tw"><table>{% for m in rows %}<tr><td>{{loop.index}}</td><td>{{m.title}}</td><td><audio controls preload=none src="{{m.url}}" style="height:32px"></audio></td>
<td><form method=post><input type=hidden name=action value=delete><input type=hidden name=id value="{{m.id}}"><button class=r>Delete</button></form></td></tr>
{% else %}<tr><td>No songs</td></tr>{% endfor %}</table></div>{% endblock %}"""

TEMPLATES = T
