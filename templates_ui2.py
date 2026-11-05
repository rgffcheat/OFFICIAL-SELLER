from templates_ui import _P, ic, CSS, HEAD, FLASH, T as _T

_P.update({
 "bolt": '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
 "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
 "palette": '<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.65-.75 1.65-1.69 0-.44-.18-.83-.44-1.12-.29-.29-.44-.65-.44-1.13a1.64 1.64 0 0 1 1.67-1.67h2c3.05 0 5.55-2.5 5.55-5.55C21.97 6.01 17.46 2 12 2z"/>',
 "qr": '<rect width="5" height="5" x="3" y="3" rx="1"/><rect width="5" height="5" x="16" y="3" rx="1"/><rect width="5" height="5" x="3" y="16" rx="1"/><path d="M21 16h-3a2 2 0 0 0-2 2v3"/><path d="M21 21v.01"/><path d="M12 7v3a2 2 0 0 1-2 2H7"/><path d="M3 12h.01"/><path d="M12 3h.01"/><path d="M12 16v.01"/><path d="M16 12h1"/><path d="M21 12v.01"/><path d="M12 21v-1"/>',
 "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
 "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
 "minus": '<path d="M5 12h14"/>',
 "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
 "hourglass": '<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.17a2 2 0 0 0-.59-1.41L12 12l-4.41 4.42A2 2 0 0 0 7 17.83V22"/><path d="M7 2v4.17a2 2 0 0 0 .59 1.41L12 12l4.41-4.42A2 2 0 0 0 17 6.17V2"/>',
 "send": '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
})

# ---- theme: recolour the old violet CSS through variables so ONE colour setting re-skins everything
_end = CSS.index("}") + 1
_body = CSS[_end:]
for a, b in (("139,92,246", "var(--acrgb)"), ("34,211,238", "var(--ac2rgb)"), ("#8b5cf6", "var(--ac)"),
             ("#22d3ee", "var(--ac2)"), ("#6366f1", "var(--ac3)"), ("#c4b5fd", "var(--acl)"), ("#a78bfa", "var(--acl)"),
             ("#a5b4fc", "var(--acl)"), ("#67e8f9", "var(--acl2)"), ("#6d28d9", "var(--ac)"), ("#4c1d95", "var(--acd)"),
             ("#04040a", "var(--bg)"), ("rgba(79,70,229,.35)", "rgba(var(--acrgb),.3)")):
    _body = _body.replace(a, b)
ROOT = (":root{--bg:#050a14;--card:rgba(13,22,40,.74);--bd:rgba(var(--acrgb),.28);--tx:#eef2ff;--mu:#8fa0bf;--ok:#10b981;--er:#f43f5e;"
        "--gl:0 0 22px rgba(var(--acrgb),.45);--acrgb:59,130,246;--ac2rgb:34,211,238;--ac:#3b82f6;--ac2:#22d3ee;--ac3:#4f6ef5;"
        "--acl:#93c5fd;--acl2:#67e8f9;--acd:#1e3a8a}")
EXTRA = """
.gcard{border-radius:28px;border:1px solid var(--bd);background:var(--card);overflow:hidden;box-shadow:0 0 40px rgba(var(--acrgb),.14);margin-top:14px}
.gh{display:flex;align-items:center;justify-content:center;gap:12px;padding:22px 12px;font-size:23px;font-weight:800;letter-spacing:.2em;text-transform:uppercase}
.gh .ic{color:var(--ac)}
.gs{text-align:center;padding:16px 10px;color:var(--ac2);background:rgba(var(--acrgb),.09);border-top:1px solid var(--bd);border-bottom:1px solid var(--bd)}
.gb{padding:18px}.gb .l{display:flex;align-items:center;gap:10px;margin:16px 0 10px;font-weight:800;letter-spacing:.08em;font-size:16px;text-transform:uppercase}
.gb .l .ic{color:var(--ac)}
.gb select,.gb .qi{width:100%;padding:16px 16px;border-radius:18px;font-size:18px;border:1.5px solid var(--bd);background:rgba(4,8,18,.88)}
.qty{display:flex;gap:10px;align-items:center}.qty .qi{text-align:center;flex:1;min-width:0}
.sq{width:60px;height:58px;flex:none;border-radius:16px;font-size:28px;padding:0;display:inline-flex;align-items:center;justify-content:center}
.genb{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;padding:17px;border-radius:18px;font-size:18px;font-weight:800;letter-spacing:.16em;margin-top:20px}
.genb .ic{margin:0}
.hd{display:flex;align-items:center;justify-content:center;gap:12px;padding:16px;border-radius:20px;border:1px solid var(--bd);background:var(--card);font-size:24px;font-weight:800;margin-top:14px}
.hd .ic{color:var(--ac)}
.tbl{max-height:62vh;overflow:auto;border-radius:16px;border:1px solid var(--bd);margin-top:12px}
.tbl table{min-width:560px}.tbl th{position:sticky;top:0;background:#101a30;z-index:1;text-align:center;padding:14px 8px}
.tbl td{padding:12px 8px;white-space:nowrap}.tbl td code{border:0;background:none;padding:0;color:var(--acl);display:inline-block;max-width:150px;overflow:hidden;text-overflow:ellipsis;vertical-align:middle}
.pn{display:inline-block;max-width:120px;overflow:hidden;text-overflow:ellipsis;vertical-align:middle;font-weight:700}
.src{display:inline-block;padding:5px 14px;border-radius:9px;border:1.5px solid var(--bd);font-weight:800;font-size:13px;color:var(--acl);background:rgba(var(--acrgb),.16)}
.vd{font-weight:800;color:var(--ac);font-size:13px}
.sbox{position:relative;margin-top:12px}.sbox .ic{position:absolute;left:14px;top:50%;margin-top:-10px;color:var(--ac)}.sbox input{width:100%;padding:15px 14px 15px 46px;border-radius:14px}
.plain{border-radius:22px;border:1px solid var(--bd);padding:16px;margin-top:16px;background:rgba(var(--acrgb),.05)}
.plain h3{font-size:18px}.plain select,.plain input.f{width:100%;margin:6px 0;padding:14px;border-radius:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.two button{display:flex;justify-content:center;align-items:center;padding:14px}
.bal{padding:20px;border-radius:22px;background:linear-gradient(135deg,rgba(var(--acrgb),.75),rgba(var(--ac2rgb),.4));border:1px solid var(--bd);margin:14px 0}
.bal small{letter-spacing:.2em;color:rgba(255,255,255,.8);font-weight:700}.bal b{display:block;font-size:34px;margin:4px 0;color:#fff}
.amts{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0}
.amt{padding:16px 4px;border-radius:14px;font-size:18px;font-weight:800;background:rgba(var(--acrgb),.12);border:1.5px solid var(--bd);box-shadow:none;color:var(--tx)}
.amt.on{background:linear-gradient(135deg,var(--ac),var(--ac2));color:#fff;box-shadow:0 0 22px rgba(var(--acrgb),.5)}
.qrbox{background:#fff;border-radius:18px;padding:16px;max-width:300px;margin:14px auto}.qrbox img{width:100%;display:block}
.cd{font-size:30px;font-weight:800;text-align:center;color:var(--ac2);letter-spacing:.06em}
.badge{margin-left:auto;background:var(--er);color:#fff;border-radius:20px;padding:1px 9px;font-size:12px;font-weight:800}
.notice{padding:14px;border-radius:14px;border:1px solid var(--bd);background:rgba(var(--acrgb),.1);margin:10px 0;display:block;color:var(--tx)}
.nt{border-radius:16px;border:1px solid var(--bd);background:var(--card);padding:14px;margin:10px 0}.nt.new{border-color:var(--ac2);box-shadow:0 0 18px rgba(var(--ac2rgb),.3)}
.nt b{font-size:16px}.nt p{margin:8px 0 0;white-space:pre-wrap;word-break:break-word}
.modal{display:none;position:fixed;inset:0;background:#000b;z-index:50;align-items:center;justify-content:center;padding:18px}.modal.open{display:flex}
.modal .bx{width:100%;max-width:360px;border-radius:22px;background:#0b1428;border:1px solid var(--bd);padding:20px}
.sw{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}.sw button{width:42px;height:42px;border-radius:50%;padding:0;border:2px solid rgba(255,255,255,.35);box-shadow:none}
.sw input[type=color]{width:100%;height:46px;padding:2px;border-radius:12px}
"""
CSS2 = ROOT + _body + EXTRA

THEME_JS = r"""
(function(){function h2r(h){h=h.replace('#','');return[0,2,4].map(function(i){return parseInt(h.substr(i,2),16)})}
function toHsl(r,g,b){r/=255;g/=255;b/=255;var M=Math.max(r,g,b),m=Math.min(r,g,b),l=(M+m)/2,s=0,h=0;if(M!=m){var d=M-m;s=l>.5?d/(2-M-m):d/(M+m);h=M==r?(g-b)/d+(g<b?6:0):M==g?(b-r)/d+2:(r-g)/d+4;h*=60}return[h,s,l]}
function fromHsl(h,s,l){h=((h%360)+360)%360;var a=s*Math.min(l,1-l);function f(n){var k=(n+h/30)%12;return Math.round(255*(l-a*Math.max(-1,Math.min(k-3,9-k,1))))}return[f(0),f(8),f(4)]}
function hex(c){return'#'+c.map(function(x){return('0'+x.toString(16)).slice(-2)}).join('')}
function ck(){var m=document.cookie.match(/(?:^|; )rg_theme=([0-9a-fA-F]{6})/);return m?'#'+m[1]:''}
window.applyTheme=function(c){if(!/^#[0-9a-f]{6}$/i.test(c||''))return false;var r=h2r(c),H=toHsl(r[0],r[1],r[2]),s=document.documentElement.style,S=Math.max(H[1],.55);
var a2=fromHsl(H[0]+40,S,.6),a3=fromHsl(H[0]+15,S,.58);
s.setProperty('--acrgb',r.join(','));s.setProperty('--ac',c);s.setProperty('--ac2',hex(a2));s.setProperty('--ac2rgb',a2.join(','));s.setProperty('--ac3',hex(a3));
s.setProperty('--acl',hex(fromHsl(H[0],S,.8)));s.setProperty('--acl2',hex(fromHsl(H[0]+40,S,.8)));s.setProperty('--acd',hex(fromHsl(H[0],S,.25)));return true};
window.saveTheme=function(c){try{localStorage.rgtheme=c}catch(e){}document.cookie='rg_theme='+c.slice(1)+';path=/;max-age=31536000;SameSite=Lax'};
window.initTheme=function(server){var c=server||ck()||(function(){try{return localStorage.rgtheme}catch(e){return ''}})();if(applyTheme(c))saveTheme(c)};
})();
"""

T = dict(_T)
for k in ("login.html", "rbase.html", "abase.html"):
    T[k] = T[k].replace(CSS, CSS2)
T["login.html"] = T["login.html"].replace("</style></head>", "</style><script>" + THEME_JS + "initTheme('');</script></head>", 1)

# ---------------------------------------------------------------- reseller base
T["rbase.html"] = HEAD + """Reseller Panel</title><style>""" + CSS2 + """</style><script>""" + THEME_JS + """initTheme({{(r.theme or '')|tojson}});</script></head><body>
<div class="shade" id=shade></div>
<div class="side" id=side><div class=sidehd><span class=tile>{{ic('crown',22)}}</span><div><b class=logo>{{BRAND}}</b><div class=mu>{{r.username}}</div></div></div>
<div class=mu style="margin:8px 0 0">Balance: <b style="color:#34d399" id=sbal>{{r.balance|cur}}</b></div><hr style="border:0;border-top:1px solid var(--bd);margin:14px 0">
<a href="/dashboard" class="{{'on' if page=='dashboard'}}">{{ic('dash')}} Dashboard</a>
<a href="/generate" class="{{'on' if page=='generate'}}">{{ic('bolt')}} Generate Key</a>
<a href="/history" class="{{'on' if page=='history'}}">{{ic('history')}} Key History</a>
<a href="/wallet" class="{{'on' if page=='wallet'}}">{{ic('wallet')}} Add Balance</a>
<a href="/broadcast" class="{{'on' if page=='broadcast'}}">{{ic('bell')}} Broadcast{% if unread and page!='broadcast' %}<span class=badge>{{unread}}</span>{% endif %}</a>
<a href="/api-docs" class="{{'on' if page=='api'}}">{{ic('code')}} API &amp; Docs</a>
<a href="/logout">{{ic('logout')}} Logout</a></div>
<div class="top"><button class="iconbtn" id=bg aria-label="Menu">{{ic('menu',22)}}</button>
<div class="player" id=pl><button id=pv aria-label="Previous">{{ic('prev',16)}}</button><button id=pp aria-label="Play">{{ic('play',16)}}</button><button id=nx aria-label="Next">{{ic('next',16)}}</button><span id=ttl>…</span><audio id=au preload=auto></audio></div>
<button class="iconbtn" id=pal aria-label="Colour" style="margin-left:auto">{{ic('palette',22)}}</button></div>
<div class="modal" id=mod><div class=bx><h3>{{ic('palette',20)}} Portal colour</h3><div class=mu>Your colour is saved and used on the login page too.</div>
<div class="sw" id=sw></div><input type=color id=cc value="#3b82f6" style="width:100%;height:46px;padding:2px;border-radius:12px"><button class="o" id=mx style="margin-top:14px;width:100%">Close</button></div></div>
<div class="wrap">""" + FLASH + """{% if unread and page!='broadcast' %}<a class=notice href="/broadcast">{{ic('bell',18)}} You have {{unread}} new notice{{'s' if unread>1}} from admin &rarr;</a>{% endif %}{% block c %}{% endblock %}</div>
<script>
const PLAY='{{ic('play',16)|e}}',PAUSE='{{ic('pause',16)|e}}';
const S=document.getElementById('side'),H=document.getElementById('shade');
function tg(){S.classList.toggle('open');H.classList.toggle('open')}bg.onclick=tg;H.onclick=tg;
document.addEventListener('click',e=>{const b=e.target.closest('[data-copy]');if(!b)return;navigator.clipboard&&navigator.clipboard.writeText(b.dataset.copy);b.style.color='#34d399';setTimeout(()=>b.style.color='',900)});
const COLS=['#3b82f6','#06b6d4','#10b981','#8b5cf6','#ec4899','#f43f5e','#f97316','#eab308'];
COLS.forEach(c=>{const b=document.createElement('button');b.style.background=c;b.onclick=()=>pick(c);sw.appendChild(b)});
function pick(c){applyTheme(c);saveTheme(c);cc.value=c;const f=new FormData();f.append('color',c);fetch('/theme',{method:'POST',body:f})}
cc.onchange=()=>pick(cc.value);pal.onclick=()=>mod.classList.add('open');mx.onclick=()=>mod.classList.remove('open');mod.onclick=e=>{if(e.target===mod)mod.classList.remove('open')};
(async()=>{let L=[];try{L=await(await fetch('/music.json')).json()}catch(e){}
if(!L.length){pl.style.display='none';return}
const ss=sessionStorage;let i=+localStorage.mi||0;if(i>=L.length)i=0;
function load(n){i=(n+L.length)%L.length;au.src=L[i].url;ttl.textContent=L[i].title;localStorage.mi=i}
function play(){au.play().then(()=>{pp.innerHTML=PAUSE;ss.mp=1}).catch(()=>{pp.innerHTML=PLAY})}
function pause(){au.pause();pp.innerHTML=PLAY;ss.mp=0}
load(i);if(ss.mt)au.addEventListener('loadedmetadata',()=>{au.currentTime=+ss.mt},{once:true});
pp.onclick=()=>au.paused?play():pause();
nx.onclick=()=>{ss.mt=0;load(i+1);play()};pv.onclick=()=>{ss.mt=0;load(i-1);play()};au.onended=()=>{ss.mt=0;load(i+1);play()};
setInterval(()=>{if(!au.paused)ss.mt=au.currentTime},1000);
if(ss.mp!=='0'){play();document.addEventListener('click',()=>{if(au.paused&&ss.mp!=='0')play()},{once:true})}
})();
</script></body></html>"""

# ---------------------------------------------------------------- key generator
T["generate.html"] = r"""{% extends 'rbase.html' %}{% block c %}
<div class=gcard><div class=gh>{{ic('bolt',28)}} Key Generator</div><div class=gs>Generate licence keys for your customers</div>
<div class=gb>
<div class=l>{{ic('box',22)}} Product type</div><select id=sp></select>
<div class=l>{{ic('hourglass',22)}} Validity</div><select id=sl></select>
<div class=l>{{ic('user',22)}} Quantity</div>
<div class=qty><button type=button class=sq id=qm>{{ic('minus',20)}}</button><input class=qi id=qn type=number inputmode=numeric min=1 max=500 value=1><button type=button class=sq id=qp>{{ic('plus',20)}}</button></div>
<div class=mu style="margin-top:12px;text-align:center">Total <b id=tot></b> &middot; Balance <b id=bl style="color:#34d399">{{r.balance|cur}}</b> &middot; <a href="/wallet">Add balance</a></div>
<button class="genb" id=go>{{ic('bolt',22)}} GENERATE KEYS</button></div></div>
<div class="plain" id=res hidden><h3>{{ic('key',20)}} Generated keys</h3><div class=mu id=st></div>
<textarea id=out readonly style="min-height:130px;margin-top:8px"></textarea>
<div class=two><button id=cpall>{{ic('copy',18)}} Copy all</button><a class="btn o" href="/history" style="text-align:center;border:1px solid var(--bd);background:none;box-shadow:none">{{ic('history',18)}} History</a></div></div>
<script>
const C={{cat|tojson}},CU='{{CURRENCY}}',$=i=>document.getElementById(i);let bal={{r.balance}};
const sp=$('sp'),sl=$('sl'),qn=$('qn');
C.forEach((p,i)=>sp.add(new Option(p.name,i)));
function plan(){const p=C[sp.value];return p&&p.plans.find(x=>x.id==sl.value)}
function qty(){return Math.max(1,Math.min(500,parseInt(qn.value)||1))}
function upd(){const x=plan();$('tot').textContent=x?CU+(Math.round(x.price*qty()*100)/100):'-'}
function fill(){sl.innerHTML='';const p=C[sp.value];if(!p)return;let first=-1;p.plans.forEach((x,i)=>{const out=x.mode==='stock'&&x.stock==0;const o=new Option(x.name.toUpperCase()+' - '+CU+x.price+(out?' (out of stock)':''),x.id);o.disabled=out;sl.add(o);if(!out&&first<0)first=i});if(first>=0)sl.selectedIndex=first;upd()}
sp.onchange=fill;sl.onchange=upd;qn.oninput=upd;
$('qm').onclick=()=>{qn.value=Math.max(1,qty()-1);upd()};$('qp').onclick=()=>{qn.value=Math.min(500,qty()+1);upd()};
function setBal(b){bal=b;$('bl').textContent=CU+(Math.round(b*100)/100);const s=$('sbal');if(s)s.textContent=CU+(Math.round(b*100)/100)}
$('cpall').onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText($('out').value)};
$('go').onclick=async()=>{const x=plan(),n=qty();if(!x)return;
 if(n>=10&&!confirm('Generate '+n+' keys for '+CU+(Math.round(x.price*n*100)/100)+'?'))return;
 const go=$('go');go.disabled=true;$('res').hidden=false;$('out').value='';let ok=0,err='';
 for(let k=0;k<n;k++){$('st').textContent='Generating '+(k+1)+' / '+n+' …';
  try{const f=new FormData();f.append('plan_id',x.id);const j=await(await fetch('/generate/one',{method:'POST',body:f})).json();
   if(!j.ok){err=j.error;break}$('out').value+=($('out').value?'\n':'')+j.key;ok++;setBal(j.balance)}catch(e){err='Network error';break}}
 $('st').textContent=ok+' key'+(ok==1?'':'s')+' generated'+(err?' — stopped: '+err:'')+' · '+x.name;go.disabled=false};
fill();
</script>{% endblock %}"""

# ---------------------------------------------------------------- key history
T["history.html"] = r"""{% extends 'rbase.html' %}{% block c %}
<div class=hd>{{ic('history',26)}} KEY HISTORY</div>
<div class=sbox>{{ic('search',20)}}<input id=sq placeholder="Search keys, products, dates..." autocomplete=off></div>
<div class=tbl><table><tr><th>KEY</th><th>PRODUCT</th><th>SRC</th><th>VALID</th><th>TIME</th></tr><tbody id=tb>
{% for x in rows %}<tr data-s="{{(x.key~' '~x.product_name~' '~x.plan_name~' '~(x.via or 'panel')~' '~(x.created|dt2))|lower}}">
<td><code>{{x.key}}</code></td><td><span class=pn>{{x.product_name}}</span></td><td><span class=src>{{(x.via or 'panel')|upper}}</span></td>
<td><span class=vd>{{x.plan_name|upper}}</span></td><td>{{x.created|dt2}} <button class=cp data-copy="{{x.key}}" aria-label="Copy key">{{ic('copy',15)}}</button></td></tr>
{% else %}<tr><td colspan=5 class=mu style="text-align:center">No keys generated yet.</td></tr>{% endfor %}</tbody></table></div>
<div class=mu style="text-align:center;margin:12px 0;font-weight:700"><span id=shown>{{rows|length}}</span> of {{total}} keys shown<br><span style="font-weight:400">Search covers your newest {{rows|length}} keys.</span></div>
<div class=plain><h3>{{ic('key',20)}} Plaintext keys</h3>
<input class=f id=pf placeholder="Filter keys (key or product)..." autocomplete=off>
<select id=pn>{% for n in opts %}<option value="{{n}}">Last {{n}}</option>{% endfor %}<option value="0" {{'selected' if not opts}}>All keys ({{total}})</option></select>
<button id=get style="margin-top:8px">{{ic('bolt',18)}} Get</button>
<textarea id=pt readonly placeholder="Your keys appear here — one per line, ready to copy or send." style="min-height:180px;margin-top:10px"></textarea>
<div class=two><button id=ca>{{ic('copy',18)}} Copy all</button><button id=dl>{{ic('download',18)}} Download .txt</button></div></div>
<script>
const sq=document.getElementById('sq');sq.oninput=()=>{const v=sq.value.trim().toLowerCase();let n=0;document.querySelectorAll('#tb tr[data-s]').forEach(r=>{const m=!v||r.dataset.s.includes(v);r.style.display=m?'':'none';if(m)n++});document.getElementById('shown').textContent=n};
const pt=document.getElementById('pt');
document.getElementById('get').onclick=async()=>{const j=await(await fetch('/history/plain?n='+pn.value+'&q='+encodeURIComponent(pf.value))).json();pt.value=j.text;pt.placeholder=j.count?'':'No keys found.'};
document.getElementById('ca').onclick=()=>{if(pt.value)navigator.clipboard&&navigator.clipboard.writeText(pt.value)};
document.getElementById('dl').onclick=async()=>{if(!pt.value)document.getElementById('get').click(),await new Promise(r=>setTimeout(r,700));if(!pt.value)return;
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([pt.value],{type:'text/plain'}));a.download='keys_'+pt.value.split('\n').length+'.txt';a.click()};
</script>{% endblock %}"""

# ---------------------------------------------------------------- wallet
T["wallet.html"] = r"""{% extends 'rbase.html' %}{% block c %}
<h2 style="margin-top:14px">Add balance</h2><div class=mu>Choose an amount, then pay securely by UPI.</div>
<div class=bal><small>AVAILABLE BALANCE</small><b>{{r.balance|cur}}</b><span style="color:rgba(255,255,255,.85)">Successful payments credit automatically after verification.</span></div>
{% if not ready %}<div class="flash err">Payments are not set up yet. Please contact admin.</div>{% endif %}
<form class=card method=post action="/wallet/create"><h3>{{ic('qr',22)}} Select amount</h3>
<div class=amts>{% for a in amts %}<button type=button class="amt {{'on' if a==500}}" data-a="{{a}}">{{CURRENCY}}{{a}}</button>{% endfor %}</div>
<input type=hidden name=amount id=am value=500>
<button class=genb style="font-size:16px;letter-spacing:.06em" {{'disabled' if not ready}}>{{ic('qr',20)}} Continue with UPI</button></form>
<script>document.querySelectorAll('.amt').forEach(b=>b.onclick=()=>{document.querySelectorAll('.amt').forEach(x=>x.classList.remove('on'));b.classList.add('on');document.getElementById('am').value=b.dataset.a})</script>
{% if tops %}<div class=card><h3>{{ic('history',20)}} Recent top-ups</h3><div class=tw><table>
{% for t in tops %}<tr><td>{{t.created|dt}}</td><td><b>{{t.amount|cur}}</b></td><td>{% if t.status=='paid' %}<span class="pill a">Paid</span>{% elif t.status=='pending' %}<a class="pill c" href="/wallet/pay/{{t.id}}">Pending</a>{% else %}<span class="pill e">Expired</span>{% endif %}</td></tr>{% endfor %}</table></div></div>{% endif %}{% endblock %}"""

T["wallet_pay.html"] = r"""{% extends 'rbase.html' %}{% block c %}
<h2 style="margin-top:14px">Add wallet balance</h2><div class=mu>Pay by UPI; balance credits only after secure verification.</div>
<a class="btn o" href="/wallet" style="margin:12px 0;background:none;border:1px solid var(--bd);box-shadow:none">Back to wallet</a>
<div class=card style="text-align:center"><div class=mu style="text-align:left">Pending top-up<br>{{t.order_id}}</div><div style="font-size:38px;font-weight:800;text-align:left">{{CURRENCY}}{{t.amount|money}}</div>
<div id=wait {{'hidden' if t.status!='pending'}}>
<div class=qrbox><img src="{{t.qr_url}}" alt="UPI QR"></div>
<div>Scan and pay <b>{{CURRENCY}}{{t.amount|money}}</b> to add it to your wallet.</div>
{% if t.upi_id %}<div class=mu style="margin-top:6px">UPI ID: <code>{{t.upi_id}}</code></div>{% endif %}
<div class=cd id=cd style="margin:10px 0">--:--</div>
<a class=btn href="/wallet/qr/{{t.id}}" style="margin:6px 0">{{ic('download',18)}} Download QR</a>
<p class=mu>Download the QR to pay from another device. Verification runs automatically for 5 minutes, even after you leave this page.</p></div>
<div id=ok {{'hidden' if t.status!='paid'}}><div style="font-size:54px">✅</div><h3 style="justify-content:center">Payment successful</h3><div class=mu>{{CURRENCY}}{{t.amount|money}} added. New balance: <b id=nb style="color:#34d399">{{r.balance|cur}}</b></div>
<a class=btn href="/generate" style="margin-top:12px">{{ic('bolt',18)}} Generate keys</a></div>
<div id=ex {{'hidden' if t.status!='expired'}}><h3 style="justify-content:center">QR expired</h3><div class=mu>If you already paid, it is still checked for a while. Otherwise create a new QR.</div><a class=btn href="/wallet" style="margin-top:12px">New payment</a></div></div>
<script>
let left={{left}};const $=i=>document.getElementById(i),CU='{{CURRENCY}}';
function show(s,b){if(s==='paid'){$('wait').hidden=true;$('ex').hidden=true;$('ok').hidden=false;$('nb').textContent=CU+(Math.round(b*100)/100);const e=$('sbal');if(e)e.textContent=CU+(Math.round(b*100)/100);clearInterval(T1);clearInterval(T2)}else if(s==='expired'){$('wait').hidden=true;$('ex').hidden=false}}
function tick(){if(left>0)left--;const m=Math.floor(left/60),s=left%60;$('cd').textContent=String(m).padStart(2,'0')+':'+String(s).padStart(2,'0')}
async function poll(){try{const j=await(await fetch('/wallet/status/{{t.id}}')).json();show(j.status,j.balance)}catch(e){}}
let T1,T2;if(!$('wait').hidden){tick();T1=setInterval(tick,1000);T2=setInterval(poll,4000)}
</script>{% endblock %}"""

# ---------------------------------------------------------------- broadcast (reseller)
T["broadcast.html"] = r"""{% extends 'rbase.html' %}{% block c %}<div class=hd>{{ic('bell',26)}} BROADCAST</div>
{% for x in rows %}<div class="nt {{'new' if not x.rd}}"><div style="display:flex;justify-content:space-between;gap:8px"><b>{{x.title or 'Notice'}}</b>{% if not x.rd %}<span class="pill c">NEW</span>{% endif %}</div>
<div class=mu>{{x.created|dt}}{% if x.reseller_id %} &middot; personal{% endif %}</div><p>{{x.body}}</p></div>
{% else %}<div class=card style="text-align:center" ><span class=mu>No notices yet.</span></div>{% endfor %}{% endblock %}"""

# ---------------------------------------------------------------- admin
T["abase.html"] = T["abase.html"].replace('<a href="/admin/music"',
    '<a href="/admin/gateway" class="{{\'on\' if page==\'gateway\'}}">Gateway</a><a href="/admin/broadcast" class="{{\'on\' if page==\'broadcast\'}}">Broadcast</a><a href="/admin/music"', 1)

T["admin_gateway.html"] = r"""{% extends 'abase.html' %}{% block c %}<h2>{{ic('qr',24)}} Payment Gateway</h2>
<div class=card><form method=post><input type=hidden name=action value=save>
<p class=mu>Gateway URL</p><input name=base value="{{base}}" style="width:100%" required>
<p class=mu>UPI ID (your receiving ID, for your reference)</p><input name=upi value="{{upi}}" placeholder="yourid@fam" style="width:100%">
<p class=mu>API Token{% if tail %} &mdash; saved (ends with <code>{{tail}}</code>). Leave empty to keep it.{% endif %}</p>
<input name=token type=password autocomplete=off placeholder="FAM_xxxxxxxx" style="width:100%" {{'' if tail else 'required'}}>
<button class=g style="margin-top:12px">{{ic('save')}} Save</button></form></div>
<div class=card><h3>Test QR</h3><p class=mu>Creates a {{CURRENCY}}1 test order to check that the UPI ID + token work. Nothing is credited.</p>
<form method=post><input type=hidden name=action value=test><button>{{ic('qr')}} Generate test QR</button></form>
{% if test %}{% if test.ok %}<div class="flash ok">QR created successfully. Order {{test.order}}{% if test.upi %} &middot; UPI {{test.upi}}{% endif %}</div><div style="background:#fff;padding:12px;border-radius:12px;max-width:230px"><img src="{{test.qr}}" style="width:100%"></div>
{% else %}<div class="flash err">Failed: {{test.msg}}</div>{% endif %}{% endif %}</div>
<div class="card tw"><h3>Recent top-ups</h3><table><tr><th>Reseller</th><th>Amount</th><th>Status</th><th>UTR</th><th>Time</th></tr>
{% for t in tops %}<tr><td>{{t.username}}</td><td>{{t.amount|cur}}</td><td>{{t.status}}</td><td>{{t.utr or ''}}</td><td>{{t.created|dt}}</td></tr>{% else %}<tr><td colspan=5>None yet</td></tr>{% endfor %}</table></div>{% endblock %}"""

T["admin_broadcast.html"] = r"""{% extends 'abase.html' %}{% block c %}<h2>{{ic('bell',24)}} Broadcast</h2>
<div class=card><form method=post><input type=hidden name=action value=send>
<p class=mu>Send to</p><select name=target><option value=all>All resellers</option>{% for x in rs %}<option value="{{x.id}}">{{x.username}}</option>{% endfor %}</select>
<p class=mu>Title (optional)</p><input name=title style="width:100%"><p class=mu>Message</p><textarea name=body required></textarea>
<button class=g style="margin-top:10px">{{ic('send')}} Broadcast</button></form></div>
<div class="card tw"><h3>Sent</h3><table><tr><th>To</th><th>Message</th><th>Time</th><th></th></tr>
{% for x in rows %}<tr><td>{{x.username or 'ALL'}}</td><td><b>{{x.title}}</b><div class=mu style="white-space:pre-wrap">{{x.body}}</div></td><td>{{x.created|dt}}</td>
<td><form method=post><input type=hidden name=action value=delete><input type=hidden name=id value="{{x.id}}"><button class=r>{{ic('trash',16)}}</button></form></td></tr>{% else %}<tr><td colspan=4>Nothing sent yet</td></tr>{% endfor %}</table></div>{% endblock %}"""

TEMPLATES = T
