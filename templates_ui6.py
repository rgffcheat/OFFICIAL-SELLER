"""v15 templates: own payment gateway (Base URL + API token, Paytm / FamPay), product rename + own order."""
from templates_ui5 import TEMPLATES as T, ic  # noqa: F401


def sub(name, old, new):
    assert old in T[name], (name, old[:70])
    T[name] = T[name].replace(old, new, 1)


# ---- payment page: show the exact amount the gateway returned (FamPay may add paise)
sub("wallet_pay.html", "<div style=\"font-size:38px;font-weight:800;text-align:left\">{{CURRENCY}}{{t.amount|money}}</div>",
    "<div style=\"font-size:38px;font-weight:800;text-align:left\">{{CURRENCY}}{{(t.pay_amount or t.amount)|money}}</div>")
sub("wallet_pay.html", "<div>Scan and pay <b>{{CURRENCY}}{{t.amount|money}}</b>",
    "<div>Scan and pay exactly <b>{{CURRENCY}}{{(t.pay_amount or t.amount)|money}}</b>")

# ---- Admin > Gateway: ONE gateway (mine), Base URL always editable
T["admin_gateway.html"] = r"""{% extends 'abase.html' %}{% block c %}<h2>{{ic('qr',24)}} Payment Gateway</h2>
<div class=card><h3>Gateway Base URL</h3>
<p class=mu>The web address of your own gateway. When you restart / redeploy the gateway and the link changes, paste the new link here and press Save &mdash; nothing else has to change.</p>
<form method=post><input type=hidden name=action value=save_base>
<input name=pg_base value="{{base}}" placeholder="https://your-gateway.onrender.com" autocomplete=off autocapitalize=off style="width:100%" required>
<button class=g style="margin-top:12px">{{ic('save')}} Save Base URL</button></form>
<form method=post style="margin-top:10px"><input type=hidden name=action value=test_pg><button {{'disabled' if not pg_ok}}>{{ic('qr')}} Test connection ({{CURRENCY}}1 QR)</button></form></div>
<div class=card><h3>Active gateway</h3>
<p class=mu>Resellers and users pay with the gateway that is ON. Both work through your own gateway site.</p>
<form method=post style="display:flex;gap:10px;flex-wrap:wrap;align-items:center"><input type=hidden name=action value=set_gw>
<button name=gw value=paytm class="{{'g' if pg_gw=='paytm' else 'o'}}">Paytm {{'● ON' if pg_gw=='paytm' else 'OFF'}}</button>
<button name=gw value=fampay class="{{'g' if pg_gw=='fampay' else 'o'}}">FamPay {{'● ON' if pg_gw=='fampay' else 'OFF'}}</button></form></div>
<div class=card><h3>API Token</h3>
<form method=post><input type=hidden name=action value=save_pg><input type=hidden name=pg_base value="{{base}}">
<p class=mu>Paste the API key made in your gateway (API Keys page){% if pg_tail %} &mdash; saved (ends with <code>{{pg_tail}}</code>). Leave empty to keep it.{% endif %}</p>
<input name=pg_key type=password autocomplete=off placeholder="paste the API key" style="width:100%">
<p class=mu style="margin-top:10px">Use for payments</p>
<select name=gw style="width:100%"><option value=paytm {{'selected' if pg_gw=='paytm'}}>Paytm</option><option value=fampay {{'selected' if pg_gw=='fampay'}}>FamPay</option></select>
<button class=g style="margin-top:12px">{{ic('save')}} Save &amp; connect</button>
<p class=hint>Only the token is needed. When you press the button a Rs.1 test QR is made automatically; if it works you will see <b>Connected successfully</b>.</p>
<details style="margin-top:10px"><summary class=mu style="cursor:pointer">Advanced (optional)</summary>
<p class=mu>Webhook secret{% if pg_sec %} &mdash; saved. Leave empty to keep it.{% endif %} (not needed: payments are checked automatically every few seconds)</p><input name=pg_secret type=password autocomplete=off style="width:100%">
<p class=hint>Webhook URL (only if you want instant confirmation): <code>{{hook}}</code></p></details></form></div>
<div class=card><h3>Amounts &amp; Full Reseller Upgrade price</h3><form method=post><input type=hidden name=action value=save_common>
<p class=mu>Add-balance amounts shown to resellers/users (comma separated, e.g. <code>100, 200, 500, 1000</code>)</p><input name=amounts value="{{amounts}}" style="width:100%" inputmode=numeric>
<p class=mu>Full Reseller Upgrade price (a user who pays this amount becomes a reseller). <b>0</b> = Full Reseller Upgrade closed.</p><input name=upgrade_price value="{{upgrade_price}}" inputmode=numeric style="width:100%">
<button class=g style="margin-top:12px">{{ic('save')}} Save</button></form></div>
{% if test %}<div class=card><h3>{{test.who}} test</h3>{% if test.ok %}<div class="flash ok">{{test.note or 'QR created successfully.'}} Order {{test.order}}</div>
<div style="background:#fff;padding:12px;border-radius:12px;max-width:260px">{% if test.svg %}{{test.svg}}{% elif test.img %}<img src="{{test.img}}" style="width:100%">{% endif %}</div>
{% else %}<div class="flash err">Failed: {{test.msg}}</div>{% endif %}</div>{% endif %}
<div class="card tw"><h3>Recent payments</h3><table><tr><th>User</th><th>Amount</th><th>For</th><th>Gateway</th><th>Status</th><th>Ref</th><th>Time</th></tr>
{% for t in tops %}<tr><td>{{t.username}}</td><td>{{t.amount|cur}}</td><td>{{'Full Reseller Upgrade' if t.purpose=='upgrade' else 'Balance'}}</td><td>{{'My gateway' if t.provider=='pgw' else ('Paytm (old)' if t.provider=='zyvo' else 'Fampay (old)')}}</td><td>{{t.status}}</td><td>{{t.utr or ''}}</td><td>{{t.created|dt}}</td></tr>{% else %}<tr><td colspan=7>None yet</td></tr>{% endfor %}</table></div>{% endblock %}"""

# ---- Admin > Products: rename + own order
sub("admin_products.html", "<div class=card><h3>Add Product</h3>",
    """{% if prods %}<div class=card><h3>{{ic('box',20)}} Arrange &amp; rename products</h3>
<p class=mu>Type a new name or a position number (1 = top) and press Save, or use the arrows. Resellers, users, the bot and your API (for people who use your API) all show this exact name and order.</p>
{% for x in prods %}<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0;padding-top:8px;border-top:1px solid var(--bd)">
<form method=post style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;flex:1;min-width:230px"><input type=hidden name=action value=rename_product><input type=hidden name=product_id value="{{x.p.id}}">
<input name=name value="{{x.p.name}}" maxlength=80 style="flex:1;min-width:130px"><button class=g>Save name</button></form>
<form method=post style="display:flex;gap:6px;align-items:center"><input type=hidden name=action value=set_pos><input type=hidden name=product_id value="{{x.p.id}}">
<input name=pos type=number min=1 max="{{prods|length}}" value="{{loop.index}}" style="width:64px"><button class=o>Go</button></form>
<form method=post style="display:flex;gap:4px"><input type=hidden name=action value=move_product><input type=hidden name=product_id value="{{x.p.id}}">
<button class=o name=dir value=top title="Top">&#8648;</button><button class=o name=dir value=up title="Up">&#9650;</button><button class=o name=dir value=down title="Down">&#9660;</button></form></div>{% endfor %}</div>{% endif %}
<div class=card><h3>Add Product</h3>""")

# ---- site name OFFICIAL SELLER in every browser tab title
for _k in ("rbase.html", "abase.html"):
    T[_k] = T[_k].replace("Reseller Panel</title>", "{{BRAND}}</title>", 1).replace("<title>Admin</title>", "<title>{{BRAND}} - Admin</title>", 1)
if "<title>Access blocked</title>" in T["blocked.html"]:
    T["blocked.html"] = T["blocked.html"].replace("<title>Access blocked</title>", "<title>{{BRAND}} - Access blocked</title>", 1)

TEMPLATES = T
