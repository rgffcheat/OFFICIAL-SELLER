"""v16 templates (part 1): VIP SELLER HUB API (connect, balance, products + % markup import)."""
from templates_ui6 import TEMPLATES as T, ic  # noqa: F401

# ---- admin menu: new item next to the Tahir API System link
_old = '<a href="/admin/main-api" class="{{\'on\' if page==\'mapi\'}}">Tahir API System</a>'
assert _old in T["abase.html"]
T["abase.html"] = T["abase.html"].replace(
    _old, _old + '<a href="/admin/vsh" class="{{\'on\' if page==\'vsh\'}}">VIP Seller Hub</a>', 1)

VTABS = """<div style="display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 4px">
<a class=btn href="/admin/vsh" style="{{'' if page2=='c' else 'background:transparent;border:1px solid var(--bd);box-shadow:none'}}">{{ic('key',16)}}Connection</a>
<a class=btn href="/admin/vsh/products" style="{{'' if page2=='p' else 'background:transparent;border:1px solid var(--bd);box-shadow:none'}}">{{ic('box',16)}}All Products</a></div>"""

T["admin_vsh.html"] = """{% extends 'abase.html' %}{% block c %}{% set page2='c' %}<h2>{{ic('code',24)}} VIP Seller Hub API</h2>""" + VTABS + """
<div class=card><h3>{{ic('key',20)}} Connect</h3>
<form method=post style="margin-bottom:12px"><input type=hidden name=action value=toggle><button class="{{'g' if enabled else 'r'}}">{{'Turn VIP Seller Hub OFF' if enabled else 'Turn VIP Seller Hub ON'}}</button> <span class="pill {{'a' if enabled else 'e'}}">{{'ON' if enabled else 'OFF'}}</span></form>
<p class=mu>Paste your API token and press <b>Connect</b>. The Base URL is already filled in; change it only if your API link changes.</p>
<form method=post><input type=hidden name=action value=save>
<p class=mu>Base URL</p>
<input name=base value="{{base}}" autocomplete=off autocapitalize=off style="width:100%" required>
<p class=mu style="margin-top:10px">API Token{% if tail %} &mdash; saved (ends with <code>{{tail}}</code>). Leave empty to keep it.{% endif %}</p>
<input name=token type=password autocomplete=off placeholder="Paste your API token" style="width:100%" {{'' if tail else 'required'}}>
<p class=mu style="margin-top:10px">Price multiplier (1 = the prices on that site are already in {{CURRENCY}}; 90 = they are in USD and 1 USD = {{CURRENCY}}90)</p>
<input name=rate type=number step=any min=0.0001 value="{{rate|money}}" style="width:140px">
<br><button class=g style="margin-top:12px">{{ic('check')}} Connect</button></form></div>
<div class=card><h3>{{ic('wallet',20)}} Status &amp; Balance</h3>
{% if st %}{% if st.ok %}<span class="pill a">Connect successful</span>
{% if st.has_bal %}<div style="font-size:30px;font-weight:800;color:#34d399;margin:8px 0 2px">{{st.balance|cur}}</div>{% else %}<div class=mu style="margin:8px 0">Connected, but the balance field was not recognised - see the raw answer below and send it to me.</div>{% endif %}
{% else %}<span class="pill e">Not connected</span><div class=mu style="margin:8px 0">{{st.msg}}</div>{% endif %}
<div class=mu style="margin-top:6px">Last checked: {{st.ts|dt}}</div>
{% if st.raw %}<details style="margin-top:8px"><summary class=mu style="cursor:pointer">Raw answer (for testing)</summary><pre style="white-space:pre-wrap;word-break:break-all;font-size:12px">{{st.raw}}</pre></details>{% endif %}
{% else %}<div class=mu>Not checked yet. Paste your token and press Connect.</div>{% endif %}
<form method=post style="margin-top:12px"><input type=hidden name=action value=check><button>{{ic('wallet')}} Check Balance</button></form></div>
{% if st and st.ok %}<a class=btn href="/admin/vsh/products">{{ic('box',16)}} Open All Products &rarr;</a>{% endif %}
{% endblock %}"""

T["admin_vsh_products.html"] = """{% extends 'abase.html' %}{% block c %}{% set page2='p' %}<h2>{{ic('box',24)}} VIP Seller Hub &mdash; All Products</h2>""" + VTABS + """
{% if not cat %}<div class=card>No products yet. Connect the API first (Connection tab), then press Refresh.<br><br><a class=btn href="/admin/vsh/products?refresh=1">Refresh from API</a></div>
{% else %}
<form method=post>
<div class=card><div class=mu>Tick the products (or single plans) you want to sell, set your percentage, then press <b>Import selected</b>. Cost = the price on VIP Seller Hub.</div>
<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:12px">
<label class=mu>Reseller price = cost + <input name=mk_res id=mkr type=number step=any min=0 value="{{mr|money}}" style="width:80px"> %</label>
<label class=mu>User price = cost + <input name=mk_user id=mku type=number step=any min=0 value="{{mu|money}}" style="width:80px"> %</label></div>
<label class=mu style="display:block;margin-top:10px"><input type=checkbox name=overwrite> Also reset the prices of plans that are already imported</label>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
<button class=g name=scope value=sel>{{ic('plus')}} Import selected</button>
<button name=scope value=all onclick="return confirm('Import ALL products from VIP Seller Hub?')">{{ic('box')}} Import ALL</button>
<button type=submit name=scope value=sync class=o onclick="return confirm('Re-price every imported plan with fresh costs and these percentages?')">Sync prices</button>
<a class=btn href="/admin/vsh/products?refresh=1" style="background:transparent;border:1px solid var(--bd);box-shadow:none">Refresh</a>
<label class=mu style="margin-left:auto;display:flex;align-items:center;gap:6px"><input type=checkbox id=selall style="width:auto"> Select all</label></div>
<div class=mu style="margin-top:8px">Fetched {{cat.product_count or groups|length}} products / {{cat.variant_count or 0}} variants. List fetched: {{cat.ts|dt}} &middot; Edit single prices later in <a href="/admin/products">Products</a>.</div></div>
{% for g in groups %}<div class=card><div style="display:flex;justify-content:space-between;align-items:center"><h3>{{g.name}}</h3><label class=mu style="display:flex;align-items:center;gap:6px"><input type=checkbox class=ga style="width:auto"> all</label></div>
<div class=tw><table><tr><th></th><th>Plan</th><th>ID</th><th>Cost</th><th>Reseller</th><th>User</th><th>Status</th></tr>
{% for p in g.plans %}<tr><td><input type=checkbox name=pid value="{{p.pid}}" class=pc style="width:auto"></td><td>{{p.name}}{% if p.bala %} <span class="pill p">Bala Mod{% if p.mode %} {{p.mode}}{% endif %}</span>{% endif %}</td><td>{{p.pid}}</td>
<td>{{p.cost|cur}}</td><td class=rp data-c="{{p.cost}}">-</td><td class=up data-c="{{p.cost}}">-</td>
<td>{% if p.mine %}<span class="pill a">Imported</span> <span class=mu>R {{p.mine.price|cur}} / U {{p.mine.user_price|cur}}</span>{% else %}<span class="pill p">New</span>{% endif %}{% if not p.avail %} <span class="pill e">Out</span>{% endif %}</td></tr>{% else %}<tr><td colspan=7 class=mu>No plans</td></tr>{% endfor %}</table></div></div>
{% else %}<div class=card>The product list is empty. Press Refresh, or check the raw answer on the Connection tab.
{% if cat.raw_preview %}<details style="margin-top:10px"><summary class=mu style="cursor:pointer">Raw products.php response (diagnostic)</summary><pre style="white-space:pre-wrap;word-break:break-all;font-size:12px">{{cat.raw_preview}}</pre></details>{% endif %}</div>{% endfor %}
</form>
<script>
const f2=v=>{v=Math.round(v*100)/100;return '{{CURRENCY}}'+v},mkr=document.getElementById('mkr'),mku=document.getElementById('mku');
function calc(){const a=parseFloat(mkr.value)||0,b=parseFloat(mku.value)||0;document.querySelectorAll('.rp').forEach(e=>e.textContent=f2(e.dataset.c*(1+a/100)));document.querySelectorAll('.up').forEach(e=>e.textContent=f2(e.dataset.c*(1+b/100)))}
mkr.oninput=mku.oninput=calc;calc();
document.querySelectorAll('.ga').forEach(g=>g.onchange=()=>g.closest('.card').querySelectorAll('.pc').forEach(c=>c.checked=g.checked));
document.getElementById('selall').onchange=function(){document.querySelectorAll('.pc,.ga').forEach(c=>c.checked=this.checked)};
</script>
{% endif %}{% endblock %}"""



# v16 follow-up: visibility controls and provider-aware plan labels.
T["admin_products.html"] = T["admin_products.html"].replace(
    '{{x.p.name}}</h3>',
    '{{x.p.name}} {% if x.p.hidden %}<span class="pill e">Hidden</span>{% endif %}</h3>', 1)
T["admin_products.html"] = T["admin_products.html"].replace(
    '<form method=post onsubmit=',
    '<form method=post style="display:inline"><input type=hidden name=action value=toggle_hidden><input type=hidden name=product_id value="{{x.p.id}}"><button class=o>{{\'Unhide\' if x.p.hidden else \'Hide\'}}</button></form><form method=post onsubmit=', 1)
T["admin_products.html"] = T["admin_products.html"].replace(
    '<span class="pill c">Main API #{{pl.prov_pid}}</span>',
    '<span class="pill c">{{\'VIP Seller Hub\' if pl.prov_src==\'vsh\' else \'Tahir API\'}} #{{pl.prov_pid}}</span>', 1)

T["admin_products.html"] = T["admin_products.html"].replace(
    """{% if pl.prov_src=='v2' %}<span class="pill c">Tahir API System #{{pl.prov_pid}}</span>{% else %}<span class="pill e">Old API - delete</span>{% endif %}""",
    """<span class="pill c">{{'VIP Seller Hub' if pl.prov_src=='vsh' else 'Tahir API'}} #{{pl.prov_pid}}</span>""", 1)

T["generate.html"] = T["generate.html"].replace(
    "x.name.toUpperCase()+' - '+CU+x.price",
    "x.name.toUpperCase()+' - '+CU+x.price", 1)

# ---- v16.1: AUTO PRICE (admin menu link + page)
_old2 = '<a href="/admin/vsh" class="{{\'on\' if page==\'vsh\'}}">VIP Seller Hub</a>'
assert _old2 in T["abase.html"]
T["abase.html"] = T["abase.html"].replace(
    _old2, _old2 + '<a href="/admin/auto-price" class="{{\'on\' if page==\'autoprice\'}}">Auto Price</a>', 1)

T["admin_auto_price.html"] = """{% extends 'abase.html' %}{% block c %}<h2>{{ic('wallet',24)}} Auto Price</h2>
<div class=card><h3>Provider price goes UP &rarr; your price goes up automatically</h3>
<p class=mu>Every <b>{{cf.mins}}</b> minutes the panel checks Tahir API and VIP Seller Hub. If a provider raises the price of a plan you imported,
your selling price is raised so it is never below <b>new provider price + the % below</b>. Prices are only raised, never lowered. Reseller and User prices both update.</p>
<form method=post><input type=hidden name=action value=save>
<label style="display:flex;gap:8px;align-items:center;margin:10px 0"><input type=checkbox name=on value=1 {{'checked' if cf.on}}> Auto price is ON</label>
<p class=mu>Extra % for RESELLER price</p><input name=pr type=number step=any min=0 value="{{cf.pr|money}}" style="width:120px">
<p class=mu style="margin-top:10px">Extra % for USER price</p><input name=pu type=number step=any min=0 value="{{cf.pu|money}}" style="width:120px">
<p class=mu style="margin-top:10px">Check every (minutes, 5 - 1440)</p><input name=mins type=number min=5 max=1440 value="{{cf.mins}}" style="width:120px">
<br><button class=g style="margin-top:12px">{{ic('check')}} Save</button></form></div>
<div class=card><h3>Check now</h3>
{% if st %}<div class=mu>Last check: {{st.ts|dt}} &mdash; {{st.checked}} plan(s) checked, {{st.changed}} raised.</div>
{% for e in st.errors %}<div class=mu style="color:#f87171">{{e}}</div>{% endfor %}{% else %}<div class=mu>No check yet.</div>{% endif %}
<form method=post style="margin-top:10px"><input type=hidden name=action value=run><button>{{ic('bolt')}} Check prices now</button></form></div>
<div class=card><h3>Recent automatic increases</h3>
{% if not log %}<div class=mu>Nothing yet.</div>{% endif %}
{% for c in log %}<div style="padding:8px 0;border-top:1px solid var(--bd)"><b>{{c.product}}</b> &mdash; {{c.plan}} <span class="pill c">{{c.src}}</span>
<div class=mu>{{c.ts|dt}}</div>
<div class=mu>Provider {{c.old_cost|cur}} &rarr; {{c.new_cost|cur}} &nbsp;|&nbsp; Reseller {{c.old_rp|cur}} &rarr; {{c.new_rp|cur}} &nbsp;|&nbsp; User {{c.old_up|cur}} &rarr; {{c.new_up|cur}}</div></div>{% endfor %}</div>
{% endblock %}"""

# ---- v17: Bot Make switch, Telegram link page, Google button, Admin > Access, Full Reseller Upgrade wording
from templates_ui2 import LGHEAD as _LGH, LGFOOT as _LGF, FLASH as _FL  # noqa: E402

_gsvg = ('<svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z"/>'
         '<path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 8 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>'
         '<path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/>'
         '<path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z"/></svg>')

# Bot Make link only when the admin allows it
_o = '<a href="/bot-make" class="{{\'on\' if page==\'botmake\'}}">{{ic(\'bot\')}} Bot Make</a>'
assert _o in T["rbase.html"]
T["rbase.html"] = T["rbase.html"].replace(_o, "{% if bm_allowed(r) %}" + _o + "{% endif %}", 1)

# admin menu
_o = '<a href="/admin/auto-price" class="{{\'on\' if page==\'autoprice\'}}">Auto Price</a>'
assert _o in T["abase.html"]
T["abase.html"] = T["abase.html"].replace(_o, _o + '<a href="/admin/access" class="{{\'on\' if page==\'access\'}}">Access &amp; Login</a>', 1)

# Google button on login + sign-up
_o = "CREATE NEW ACCOUNT</a>{% endif %}"
assert _o in T["login.html"]
T["login.html"] = T["login.html"].replace(
    _o, _o + "{% if google_on() %}<div class=\"or\"><i></i>OR<i></i></div><a class=\"mk\" href=\"/auth/google\">" + _gsvg + " CONTINUE WITH GOOGLE</a>{% endif %}", 1)
_o = '<a class="back" href="/login">Already have an account?'
assert _o in T["signup.html"]
T["signup.html"] = T["signup.html"].replace(
    _o, "{% if google_on() %}<div class=\"or\"><i></i>OR<i></i></div><a class=\"mk\" href=\"/auth/google\">" + _gsvg + " SIGN UP WITH GOOGLE</a>{% endif %}" + _o, 1)

# Full Reseller Upgrade page text
T["upgrade.html"] = T["upgrade.html"].replace(
    "Upgrade your account to a RESELLER account.",
    "Unlock FULL RESELLER: you get the cheaper RESELLER prices on every product, plus all reseller tools.", 1)
T["upgrade.html"] = T["upgrade.html"].replace("Pay {{CURRENCY}}{{price}} &amp; become Reseller", "Pay {{CURRENCY}}{{price}} &amp; unlock Full Reseller", 1)

# "Link Telegram" page shown to users right after sign-up / login
T["link_tg.html"] = _LGH + """<div class="logo-t">{{ic('bot',30)}}</div><h1>Link Telegram</h1><div class="dv"><i></i><u></u><i></i></div>""" + _FL + """
<p class=mu style="text-align:center;margin:0 0 14px">One last step, <b>{{who}}</b>.<br>Press the button, then press <b>START</b> in the bot.<br>Your account is linked automatically and this page opens by itself.</p>
{% if url %}<a class="btn" href="{{url}}" target="_blank" rel="noopener" style="display:block;text-align:center;font-size:16px">{{ic('send',20)}} Open Telegram bot</a>
<div class="cd" id=st style="font-size:16px;margin-top:14px">Waiting for START&hellip;</div>
{% else %}<div class="flash err">The bot link is not ready yet. Please tell the admin (Admin &gt; Access &amp; Login).</div>{% endif %}
<a class="btn" href="/logout" style="display:block;text-align:center;margin-top:16px;background:none;border:1px solid var(--bd);box-shadow:none">Logout</a>
<script>
async function p(){try{const j=await(await fetch('/link-telegram/status',{cache:'no-store'})).json();
 if(j.linked){document.getElementById('st').textContent='Linked! Opening your account...';location.href='/dashboard';return}}catch(e){}
 setTimeout(p,2500)}
if(document.getElementById('st'))p();
</script>""" + _LGF + "</body></html>"

# Admin > Access & Login
T["admin_access.html"] = """{% extends 'abase.html' %}{% block c %}<h2>{{ic('shield2',24)}} Access &amp; Login</h2>
<div class=card><h3>{{ic('bot',20)}} Bot Make</h3>
<form method=post style="margin-bottom:12px"><input type=hidden name=action value=bm_global><input type=hidden name=on value="{{'0' if bm_on else '1'}}">
<button class="{{'g' if bm_on else 'r'}}">{{'Turn Bot Make OFF for everybody' if bm_on else 'Turn Bot Make ON'}}</button> <span class="pill {{'a' if bm_on else 'e'}}">{{'ON' if bm_on else 'OFF'}}</span></form>
<p class=mu>Per reseller (only works while the switch above is ON). OFF = he does not see Bot Make and cannot open it. Bots he already made keep running.</p>
{% for x in rs %}<form method=post style="display:flex;gap:10px;align-items:center;padding:6px 0;border-top:1px solid var(--bd)"><input type=hidden name=action value=bm_one><input type=hidden name=rid value="{{x.id}}">
<b style="flex:1">{{x.username}}</b><span class="pill {{'e' if x.off else 'a'}}">{{'OFF' if x.off else 'ON'}}</span><button class=o>{{'Turn ON' if x.off else 'Turn OFF'}}</button></form>{% else %}<div class=mu>No resellers yet.</div>{% endfor %}</div>
<div class=card><h3>Create New Account</h3>
<form method=post style="margin-bottom:4px"><input type=hidden name=action value=signup_toggle><input type=hidden name=on value="{{'0' if su_on else '1'}}">
<button class="{{'g' if su_on else 'r'}}">{{'Turn Create Account OFF (hide it everywhere)' if su_on else 'Turn Create Account ON'}}</button> <span class="pill {{'a' if su_on else 'e'}}">{{'ON' if su_on else 'OFF'}}</span></form>
<p class=mu>Login page order: Login, then Create New Account, then Continue with Google. Each switch works on its own: ON = shown, OFF = hidden.</p></div>
<div class=card><h3>Google sign-up / login</h3>
<form method=post style="margin-bottom:12px"><input type=hidden name=action value=google_toggle><input type=hidden name=on value="{{'0' if g_on else '1'}}">
<button class="{{'g' if g_on else 'r'}}">{{'Turn Google OFF (hide it everywhere)' if g_on else 'Turn Google ON'}}</button> <span class="pill {{'a' if g_on else 'e'}}">{{'ON' if g_on else 'OFF'}}</span></form>
<p class=mu>1) Google Cloud Console &rarr; APIs &amp; Services &rarr; Credentials &rarr; Create OAuth client ID (Web application).<br>2) Put this in <b>Authorised redirect URIs</b>:</p>
<input readonly value="{{redirect_uri}}" onclick="this.select()" style="width:100%"><p class=mu style="margin-top:10px">3) Paste the Client ID and Client secret here.</p>
<form method=post><input type=hidden name=action value=google>
<p class=mu>Client ID</p><input name=cid value="{{g_cid}}" autocomplete=off style="width:100%">
<p class=mu style="margin-top:10px">Client secret{% if g_tail %} &mdash; saved (ends with <code>{{g_tail}}</code>). Leave empty to keep it.{% endif %}</p><input name=secret type=password autocomplete=off style="width:100%">
<p class=mu style="margin-top:10px">Site address (optional - only if the redirect link above shows the wrong address)</p><input name=public_url value="{{public_url}}" placeholder="https://your-site.onrender.com" style="width:100%">
<button class=g style="margin-top:12px">{{ic('check')}} Save</button></form></div>{% endblock %}"""

# ---- v17.1: Bot Make switch on the Bots page, upgrade page hides Bot Make when OFF, music up / down
_o = "{% block c %}"
T["admin_bots.html"] = T["admin_bots.html"].replace(_o, _o + """<div class=card><h3>{{ic('bot',20)}} Bot Make switch</h3>
<form method=post action="/admin/access"><input type=hidden name=action value=bm_global><input type=hidden name=next value="/admin/bots"><input type=hidden name=on value="{{'0' if bm_global_on() else '1'}}">
<button class="{{'g' if bm_global_on() else 'r'}}">{{'Turn Bot Make OFF for everybody' if bm_global_on() else 'Turn Bot Make ON'}}</button> <span class="pill {{'a' if bm_global_on() else 'e'}}">{{'ON' if bm_global_on() else 'OFF'}}</span>
<span class=mu> One switch per reseller: Access &amp; Login.</span></form></div>""", 1)
_o = "<div>&#10003; Bot Make (your own bot)</div>"
assert _o in T["upgrade.html"]
T["upgrade.html"] = T["upgrade.html"].replace(_o, "{% if bm_global_on() %}" + _o + "{% endif %}", 1)

_o = "<tr><td>{{loop.index}}</td><td>{{m.title}}</td>"
assert _o in T["admin_music.html"]
T["admin_music.html"] = T["admin_music.html"].replace(_o, """<tr><td style="white-space:nowrap"><b>{{loop.index}}</b>
<form method=post style="display:inline"><input type=hidden name=action value=move><input type=hidden name=id value="{{m.id}}"><input type=hidden name=dir value=up><button class=o {{'disabled' if loop.first}} aria-label="Move up">&#9650;</button></form>
<form method=post style="display:inline"><input type=hidden name=action value=move><input type=hidden name=id value="{{m.id}}"><input type=hidden name=dir value=down><button class=o {{'disabled' if loop.last}} aria-label="Move down">&#9660;</button></form></td><td>{{m.title}}</td>""", 1)

# ---- v17.2: Music upload fix. The progress-bar markup was missing, so the upload script crashed and the form never sent.
_o = "<button>Add Song</button></form>"
assert _o in T["admin_music.html"]
T["admin_music.html"] = T["admin_music.html"].replace(_o, _o + """<div id=mp style="display:none;margin-top:10px"><div style="height:10px;border-radius:8px;background:rgba(255,255,255,.1);overflow:hidden"><div id=mb style="height:100%;width:0;background:linear-gradient(90deg,var(--ac),var(--ac2))"></div></div><div class=mu id=mt style="margin-top:6px">Uploading 0%</div></div>""", 1)
_o = "x.onload=function(){location.href='/admin/music'};"
assert _o in T["admin_music.html"]
T["admin_music.html"] = T["admin_music.html"].replace(_o,
    "x.onload=function(){if(x.status>=200&&x.status<400){location.href='/admin/music'}else{tx.textContent='Upload failed (error '+x.status+'). The file may be too big for the server - try a smaller file or a direct URL.';mf.querySelectorAll('button').forEach(function(b){b.disabled=false})}};", 1)

# ---- v17.4: BULK PRICE (all reseller / user prices by %)
_o = '<a href="/admin/auto-price" class="{{\'on\' if page==\'autoprice\'}}">Auto Price</a>'
assert _o in T["abase.html"]
T["abase.html"] = T["abase.html"].replace(_o, _o + '<a href="/admin/bulk-price" class="{{\'on\' if page==\'bulkprice\'}}">Bulk Price %</a>', 1)
T["admin_bulk_price.html"] = """{% extends 'abase.html' %}{% block c %}<h2>{{ic('wallet',24)}} Bulk Price %</h2>
<div class=card><h3>Change ALL prices at once</h3>
<p class=mu>Applies to all <b>{{cnt}}</b> plans of every product. Use a minus sign (for example -10) to lower prices.</p>
<form method=post onsubmit="return confirm('Change prices of ALL plans now?')">
<p class=mu>What to change</p>
<select name=target style="width:100%"><option value=both>Reseller price + User price</option><option value=reseller>Only Reseller price</option><option value=user>Only User price</option></select>
<p class=mu style="margin-top:10px">Percentage (%)</p><input name=pct type=number step=any min=-90 max=1000 placeholder="e.g. 10" required style="width:160px">
<label class=mu style="display:flex;gap:8px;align-items:center;margin-top:10px"><input type=checkbox name=custom value=1 style="width:auto"> Also change resellers' custom prices (only when Reseller price is selected)</label>
<br><button class=g style="margin-top:12px">{{ic('check')}} Apply to all</button></form></div>{% endblock %}"""

# ---- Admin > Logo & Theme: change the website name from the panel (used everywhere)
_a = T["admin_branding.html"]
_m = "{% extends 'abase.html' %}{% block c %}"
assert _m in _a
T["admin_branding.html"] = _a.replace(_m, _m + """<div class=card><h3>{{ic('crown',20)}} Website name</h3>
<p class=mu>This name is shown everywhere: login page, menu, browser tab, Telegram messages and login codes. Type the new name and press Save - no code change needed.</p>
<form method=post><input type=hidden name=action value=site_name>
<input name=site_name value="{{site_name}}" maxlength=40 required style="width:100%" placeholder="{{default_name}}">
<button class=g style="margin-top:12px">{{ic('save')}} Save name</button>
<button class=r name=reset value=1 formnovalidate style="margin-top:12px" onclick="return confirm('Go back to the default name?')">Reset to default</button></form></div>
""", 1)


# ---- v17.10: resellers / users are NOT linked to Telegram any more (only the admin)
import re as _re


def _cut(name, start, end, new=""):
    a = T[name]
    i = a.index(start)
    j = a.index(end, i)
    T[name] = a[:i] + new + a[j:]


def _del(name, text, new=""):
    assert text in T[name], (name, text[:60])
    T[name] = T[name].replace(text, new, 1)


_del("admin_accounts.html", '<input name=tg_chat placeholder="Telegram Chat ID (optional)" inputmode=numeric style="width:230px">')
_del("admin_accounts.html", "{% if kind!='user' %}<th>Telegram</th>{% endif %}")
_cut("admin_accounts.html", "{% if kind!='user' %}<td>{% if x.tg_chat %}", "<td>{% if x.deleted %}<span")
_cut("admin_accounts.html", "{% if kind!='user' %}<datalist id=seenids>", "{% endblock %}")
_a = T["admin_resellers.html"]
_a = _re.sub(r'<input name=tg_chat[^>]*>', '', _a)
_a = _a.replace("{% if show!='user' %}<th>Telegram</th>{% endif %}", "")
_i = _a.find("{% if show!='user' %}<td>{% if x.tg_chat %}")
if _i >= 0:
    _k = _a.index("{% endif %}</td>{% endif %}", _i) + len("{% endif %}</td>{% endif %}")
    _a = _a[:_i] + _a[_k:]
_i = _a.find("{% if show!='user' %}<datalist id=seenids>")
if _i >= 0:
    _a = _a[:_i] + "{% endblock %}"
T["admin_resellers.html"] = _a
_cut("admin_reseller.html", "{% if r.role!='user' %}<div class=card><h3>{{ic('send',20)}} Telegram &amp; Security</h3>", "{% if devs %}",
     "{% if r.role!='user' %}<div class=card><h3>{{ic('shield2',20)}} Devices</h3>\n")
_cut("security.html", "<div class=card><h3>{{ic('send',20)}} Telegram</h3>", "<div class=card><h3>{{ic('phone',20)}} My devices</h3>")
_cut("admin_telegram.html", "<div class=card><h3>Resellers &amp; Telegram</h3>", "<div class=card><h3>Delivery log</h3>")
_cut("admin_telegram.html", '<label class=mu style="display:flex;gap:8px;align-items:center;margin-top:12px"><input type=checkbox name=otp_global', '<label class=mu style="display:flex;gap:8px;align-items:center;margin-top:12px"><input type=checkbox name=prem_on')
_del("admin_telegram.html", "Every admin login sends a 6-digit code to this chat (cannot be switched off).", "Only the admin is linked to the bot: new-device login approvals, alerts and database backups come to this chat.")

# ---- v17.10: Binance (USDT) in wallet + admin gateway
_del("wallet.html", "{{ic('qr',20)}} Continue with UPI</button></form>",
     "{{ic('qr',20)}} Continue with UPI</button>"
     "{% if bn_ok %}<button class=genb name=method value=binance style=\"font-size:16px;letter-spacing:.06em;margin-top:10px;background:linear-gradient(135deg,#f0b90b,#c99700);color:#1a1300\">Pay with Binance (USDT)</button>"
     "<div class=mu style=\"margin-top:8px;text-align:center\">For Bangladesh, Pakistan &amp; other countries &middot; 1 USDT = {{CURRENCY}}{{bn_rate|money}} &middot; credited automatically, 24/7</div>{% endif %}</form>")
_del("wallet_pay.html", "<div style=\"font-size:38px;font-weight:800;text-align:left\">{{CURRENCY}}{{(t.pay_amount or t.amount)|money}}</div>",
     "<div style=\"font-size:38px;font-weight:800;text-align:left\">{% if t.provider=='binance' %}{{'%.2f'|format(t.pay_amount)}} USDT <span class=mu style=\"font-size:15px\">= {{CURRENCY}}{{t.amount|money}}</span>{% else %}{{CURRENCY}}{{(t.pay_amount or t.amount)|money}}{% endif %}</div>")
_del("wallet_pay.html", "<div>Scan and pay exactly <b>{{CURRENCY}}{{(t.pay_amount or t.amount)|money}}</b>",
     "<div>{% if t.provider=='binance' %}Open <b>Binance</b> app &rarr; Scan, and pay exactly <b>{{'%.2f'|format(t.pay_amount)}} USDT</b>{% else %}Scan and pay exactly <b>{{CURRENCY}}{{(t.pay_amount or t.amount)|money}}</b>{% endif %}")
_del("wallet_pay.html", "{% if checkout and not qr_svg and not t.qr_url %}", "{% if checkout and (t.provider=='binance' or (not qr_svg and not t.qr_url)) %}")
_del("wallet_pay.html", "<p class=mu>Download the QR to pay from another device. Verification runs automatically for 5 minutes, even after you leave this page.</p>",
     "<p class=mu>{% if t.provider=='binance' %}You can also tap <b>Open payment page</b> to pay in a browser. Verification runs automatically for 1 hour, any time of the day, even after you leave this page.{% else %}Download the QR to pay from another device. Verification runs automatically for 5 minutes, even after you leave this page.{% endif %}</p>")
_del("admin_gateway.html", "{% if test %}<div class=card><h3>{{test.who}} test</h3>",
     """<div class=card><h3>Binance Pay (USDT) &mdash; automatic</h3>
<p class=mu>Customers (Bangladesh, Pakistan, other countries) pay in USDT through Binance. The payment is verified automatically with a signed Binance check and the balance is added at once, day or night.</p>
<form method=post><input type=hidden name=action value=save_bn>
<p class=mu>Merchant API Key{% if bn_tail %} &mdash; saved (ends with <code>{{bn_tail}}</code>). Leave empty to keep it.{% endif %}</p><input name=bn_key type=password autocomplete=off placeholder="Binance Pay API Key" style="width:100%">
<p class=mu style="margin-top:10px">Merchant Secret Key{% if bn_sec %} &mdash; saved. Leave empty to keep it.{% endif %}</p><input name=bn_secret type=password autocomplete=off placeholder="Binance Pay Secret Key" style="width:100%">
<p class=mu style="margin-top:10px">Rate: how many {{CURRENCY}} = 1 USDT (add your margin here)</p><input name=bn_rate value="{{bn_rate or ''}}" inputmode=decimal placeholder="e.g. 92" style="width:160px">
<label class=mu style="display:flex;gap:8px;align-items:center;margin-top:12px"><input type=checkbox name=bn_on value=1 {{'checked' if bn_on}} style="width:auto"> Show &ldquo;Pay with Binance&rdquo; to customers</label>
<button class=g style="margin-top:12px">{{ic('save')}} Save Binance</button></form>
<form method=post style="margin-top:10px"><input type=hidden name=action value=test_bn><button>{{ic('qr')}} Test connection (1 USDT order, not credited)</button></form>
<p class=hint>Webhook URL (set it in Binance Merchant Portal &rarr; Developers &rarr; Webhooks for instant confirmation; without it the site still checks every few seconds): <code>{{bn_hook}}</code></p></div>
{% if test %}<div class=card><h3>{{test.who}} test</h3>""")
_del("admin_gateway.html", "{{'My gateway' if t.provider=='pgw' else", "{{'Binance (USDT)' if t.provider=='binance' else 'My gateway' if t.provider=='pgw' else")

_AL = """<div class=card><h3>{{ic('bell',20)}} Telegram alerts <span class="pill {{'g' if r.tg_alert else 'e'}}">{{'ON' if r.tg_alert else 'OFF'}}</span></h3>
<p class=mu>When ON, this account gets a bot message for every purchase (panel or API), balance added and low balance. When OFF, nothing is sent to him.</p>
<form class=row method=post><input type=hidden name=action value=tg_old><input name=tg_chat value="{{r.tg_chat or ''}}" list=seenids placeholder="Telegram Chat ID (numbers)" inputmode=numeric style="flex:1;min-width:170px"><button>Save ID</button>
<datalist id=seenids>{% for s in seen %}<option value="{{s.chat_id}}">{{s.name}}</option>{% endfor %}</datalist></form>
<form class=row method=post style="margin-top:8px"><input type=hidden name=action value=tg_alert_toggle><button class="{{'r' if r.tg_alert else 'g'}}">{{'Turn alerts OFF' if r.tg_alert else 'Turn alerts ON'}}</button></form>
{% if r.tg_chat %}<form class=row method=post style="margin-top:8px"><input type=hidden name=action value=tg_test_old><button class=o>Send test message</button></form>{% endif %}
<form class=row method=post style="margin-top:8px"><input type=hidden name=action value=tg_low><input name=low_bal type=number step=any min=0 value="{{50 if r.low_bal is none else r.low_bal|int}}" style="width:110px"><button class=o>Save low balance limit</button><span class=mu>Low balance alert below this amount (50 = default)</span></form></div>
"""
_k = "<div class=card><h3>Change Password</h3>"
assert _k in T["admin_reseller.html"]
T["admin_reseller.html"] = T["admin_reseller.html"].replace(_k, _AL + _k, 1)

_old = """<button class=g name=scope value=sel>{{ic('plus')}} Import selected</button>"""
assert _old in T["admin_mapi_products.html"]
T["admin_mapi_products.html"] = T["admin_mapi_products.html"].replace(_old, """<button class=g name=scope value=new>{{ic('plus')}} Import NEW only</button>""" + _old, 1)

TEMPLATES = T
