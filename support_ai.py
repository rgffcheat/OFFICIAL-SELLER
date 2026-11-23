"""Gemini-powered Support AI for the existing reseller website."""
import json, re, time, threading, sqlite3
import requests
from flask import request, jsonify, render_template, redirect, flash


def setup(app, templates, admin_required, reseller_required, q, db, get_setting, set_setting, role_of, user_price_of, buy):
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS support_ai_purchases(
      request_id TEXT PRIMARY KEY, reseller_id INTEGER NOT NULL, plan_id INTEGER, status TEXT NOT NULL,
      result_json TEXT DEFAULT '', created INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS support_ai_failures(
      id INTEGER PRIMARY KEY, reseller_id INTEGER NOT NULL, plan_id INTEGER,
      product_name TEXT DEFAULT '', plan_name TEXT DEFAULT '', error_code TEXT DEFAULT '',
      public_message TEXT DEFAULT '', created INTEGER NOT NULL);
    """)
    c.commit(); c.close()

    hits, lock = {}, threading.Lock()

    def conf():
        return {"on": get_setting("support_ai_on", "0") == "1",
                "key": get_setting("gemini_api_key", "").strip(),
                "model": get_setting("gemini_model", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
                "instructions": get_setting("support_ai_instructions", "").strip(),
                "welcome": get_setting("support_ai_welcome", "Hello! I am Support AI. How can I help you?")}

    def gemini(system_prompt, history=None, user_message=None, timeout=35):
        cfg = conf()
        if not cfg["key"]: raise RuntimeError("Gemini API key is not configured.")
        model = cfg["model"]
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,80}", model): raise RuntimeError("Invalid Gemini model name.")
        contents = []
        for item in (history or [])[-8:]:
            role = "user" if item.get("role") == "user" else "model"
            text = str(item.get("text") or "")[:1200]
            if text: contents.append({"role": role, "parts": [{"text": text}]})
        contents.append({"role": "user", "parts": [{"text": str(user_message or "")[:1200]}]})
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
        r = requests.post(url, headers={"x-goog-api-key": cfg["key"], "Content-Type": "application/json"},
                          json={"systemInstruction": {"parts": [{"text": system_prompt}]}, "contents": contents,
                                "generationConfig": {"temperature": .35, "maxOutputTokens": 700}}, timeout=timeout)
        if r.status_code >= 400:
            try: detail = str(r.json().get("error", {}).get("message", ""))[:160]
            except Exception: detail = ""
            raise RuntimeError("Gemini API HTTP %s %s" % (r.status_code, detail))
        data = r.json()
        try: return "".join(x.get("text", "") for x in data["candidates"][0]["content"]["parts"]).strip()
        except Exception: raise RuntimeError("Gemini returned an empty response.")

    def catalog_for(rid):
        rows = q("""SELECT pr.id pid,pr.name pname,pl.id plan_id,pl.name plan_name,pl.days,pl.hours,pl.mode,
                   pl.price,pl.user_price,COALESCE((SELECT COUNT(*) FROM stock st WHERE st.plan_id=pl.id AND st.used=0),0) stock
                   FROM products pr JOIN plans pl ON pl.product_id=pr.id WHERE COALESCE(pr.hidden,0)=0
                   ORDER BY pr.pos,pr.id,pl.id""")
        out=[]
        for row in rows:
            d=dict(row)
            if role_of(rid)=="user":
                d["selling_price"]=float(user_price_of(row))
            else:
                cp=q("SELECT price FROM custom_prices WHERE reseller_id=? AND plan_id=?",(rid,d["plan_id"]),one=True)
                d["selling_price"]=float(cp["price"] if cp else d["price"] or 0)
            if d["mode"] == "stock":
                d["available"] = int(d["stock"] or 0) > 0
            elif d["mode"] in ("provider", "api"):
                d["available"] = None  # provider stock cannot be verified until the actual purchase call
            else:
                d["available"] = True
            out.append(d)
        return out

    def rate_ok(rid):
        now=time.time()
        with lock:
            arr=[t for t in hits.get(rid,[]) if now-t<60]
            if len(arr)>=18: hits[rid]=arr; return False
            arr.append(now); hits[rid]=arr
        return True

    @app.route("/admin/support-ai", methods=["GET", "POST"])
    @admin_required
    def admin_support_ai():
        if request.method == "POST":
            action=request.form.get("action","save")
            if action == "review":
                reqid=request.form.get("request_id","")
                q("UPDATE support_ai_purchases SET status='reviewed' WHERE request_id=? AND status IN ('unknown','processing')",(reqid,),commit=True)
                flash("Uncertain purchase marked as reviewed. The user can now retry if needed.","ok")
                return redirect("/admin/support-ai")
            key=request.form.get("api_key","").strip()
            if key: set_setting("gemini_api_key",key[:300])
            if action=="save":
                model=request.form.get("model","gemini-2.5-flash").strip()
                if model not in ("gemini-2.5-flash","gemini-2.5-flash-lite"): model="gemini-2.5-flash"
                set_setting("gemini_model",model)
                set_setting("support_ai_on","1" if request.form.get("enabled") else "0")
                set_setting("support_ai_welcome",request.form.get("welcome","").strip()[:300] or "Hello! I am Support AI. How can I help you?")
                set_setting("support_ai_instructions",request.form.get("instructions","").strip()[:5000])
                flash("Support AI settings saved.","ok")
            elif action=="test":
                try: flash("Gemini connection successful: "+gemini("Reply with exactly: Gemini connection successful.", [], "Connection test")[:100],"ok")
                except Exception as e: flash("Gemini connection failed: "+str(e)[:200],"err")
            return redirect("/admin/support-ai")
        cfg=conf()
        pending=q("SELECT p.*,r.username FROM support_ai_purchases p LEFT JOIN resellers r ON r.id=p.reseller_id WHERE p.status IN ('unknown','processing') AND p.created<? ORDER BY p.created DESC LIMIT 30",(int(time.time())-60,))
        return render_template("admin_support_ai.html",cfg=cfg,key_tail=cfg["key"][-4:] if cfg["key"] else "",pending=pending,page="supportai")

    @app.route("/support-ai/chat", methods=["POST"])
    @reseller_required
    def support_ai_chat():
        cfg=conf(); rid=request.r["id"]
        if not cfg["on"] or not cfg["key"]: return jsonify(ok=False,error="Support AI is currently unavailable. Please contact the administrator."),503
        if not rate_ok(rid): return jsonify(ok=False,error="Please wait a moment before sending another message."),429
        body=request.get_json(silent=True) or {}; message=str(body.get("message") or "").strip()[:1200]
        if not message: return jsonify(ok=False,error="Please type or speak a message."),400
        products=catalog_for(rid)
        prior=body.get("history") if isinstance(body.get("history"),list) else []
        search_text=message+" "+" ".join(str(x.get("text") or "")[:300] for x in prior[-6:] if isinstance(x,dict))
        low=search_text.casefold(); matched=[]
        for p in products:
            if p["pname"].casefold() in low and p["pid"] not in [x["pid"] for x in matched]: matched.append(p)
        if not matched:
            words=re.findall(r"[a-zA-Z0-9_-]{3,}",low)
            for p in products:
                if any(w in p["pname"].casefold() for w in words) and p["pid"] not in [x["pid"] for x in matched]: matched.append(p)
        cards=[]
        for p in matched[:4]:
            plans=[x for x in products if x["pid"]==p["pid"]]
            cards.append({"id":p["pid"],"name":p["pname"],"plans":[{"id":x["plan_id"],"name":x["plan_name"],"price":round(x["selling_price"],2),"available":x["available"],"selectable":x["available"] is not False} for x in plans]})
        fails=q("SELECT product_name,plan_name,error_code,created FROM support_ai_failures WHERE reseller_id=? ORDER BY id DESC LIMIT 3",(rid,))
        # Do not send balances, keys, usernames, or raw provider diagnostics to the AI vendor.
        safe_events=[]
        for f in fails:
            raw=str(f["error_code"] or "").lower()
            if any(w in raw for w in ("provider","tahir","vip seller","api","timeout","http")):
                reason="external provider temporary issue"
            elif "insufficient balance" in raw:
                reason="user wallet balance insufficient"
            elif "out of stock" in raw:
                reason="product out of stock"
            else:
                reason="purchase could not be completed; needs support review"
            safe_events.append({"product":f["product_name"],"plan":f["plan_name"],"reason":reason})
        catalog_text="\n".join("%s | %s | %.2f | %s"%(p["pname"],p["plan_name"],p["selling_price"],("available" if p["available"] is True else "out of stock" if p["available"] is False else "availability checked at purchase")) for p in products[:100])
        system=("You are this website's official Support AI. Answer in the user's language: Bengali, English, or Hindi. Be helpful and step-by-step. Use only the live facts below; never invent products, prices, plans, stock, API results, or purchase outcomes. Never reveal provider-side balance, API keys, tokens, private URLs, raw errors, stack traces, or admin secrets. If an external provider fails or its balance is insufficient, tell the user only: 'Temporary API server issue. Please wait for a short time and try again.' If the user's own wallet is insufficient, explain that clearly. Purchases can only be completed through the website's Confirm Purchase button; never claim success without server confirmation. Known reseller navigation: Dashboard, Generate Key, Key History, Add Balance, Security, Broadcast, API & Docs. Guide users to these sections by their exact names. The website API documentation uses X-API-Key authentication and includes GET /api/v1/health, GET /api/v1/connect, GET /api/v1/balance, GET /api/v1/products, POST /api/v1/purchase (JSON body with plan_id), and GET /api/v1/history. External API stock is unknown until purchase is attempted. Extra website guidance: %s\nLIVE CATALOG:\n%s\nRECENT SUPPORT EVENTS (sanitized): %s" % (cfg["instructions"] or "Use known website navigation and API documentation only.",catalog_text,json.dumps(safe_events,ensure_ascii=False)))
        history=prior; safe=[]
        for h in history[-8:]:
            if isinstance(h,dict) and h.get("role") in ("user","assistant"):
                safe.append({"role":"user" if h["role"]=="user" else "model","text":str(h.get("text") or "")[:1200]})
        try: answer=gemini(system,safe,message)
        except Exception as e:
            print("[support-ai] Gemini error:",str(e)[:200])
            return jsonify(ok=False,error="Support AI is temporarily unavailable. Please try again shortly."),502
        return jsonify(ok=True,reply=answer,products=cards)

    @app.route("/support-ai/purchase", methods=["POST"])
    @reseller_required
    def support_ai_purchase():
        if not conf()["on"]: return jsonify(ok=False,error="Support AI is currently unavailable."),503
        body=request.get_json(silent=True) or {}
        try: plan_id=int(body.get("plan_id") or 0)
        except Exception: plan_id=0
        reqid=str(body.get("request_id") or "")
        if not re.fullmatch(r"[a-f0-9-]{24,40}",reqid): return jsonify(ok=False,error="Invalid confirmation. Please start again."),400
        old=q("SELECT * FROM support_ai_purchases WHERE request_id=?",(reqid,),one=True)
        if old:
            if old["reseller_id"]!=request.r["id"]: return jsonify(ok=False,error="Invalid purchase request."),403
            if old["status"]=="done": return jsonify(ok=True,**json.loads(old["result_json"]))
            if old["status"]=="failed":
                try: return jsonify(ok=False,**json.loads(old["result_json"])),400
                except Exception: return jsonify(ok=False,error="Purchase could not be completed."),400
            return jsonify(ok=False,error="This request may still be processing. Check Key History before retrying."),409
        unresolved=q("SELECT request_id FROM support_ai_purchases WHERE reseller_id=? AND status IN ('unknown','processing') ORDER BY created DESC LIMIT 1",(request.r["id"],),one=True)
        if unresolved:
            return jsonify(ok=False,error="Temporary API server issue. Your earlier request may still be processing. Please check Key History or contact support before trying again."),409
        try: q("INSERT INTO support_ai_purchases(request_id,reseller_id,plan_id,status,created) VALUES(?,?,?,?,?)",(reqid,request.r["id"],plan_id,"processing",int(time.time())),commit=True)
        except sqlite3.IntegrityError: return jsonify(ok=False,error="This request is already processing."),409
        try:
            valid=q("SELECT pl.id FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=? AND COALESCE(pr.hidden,0)=0",(plan_id,),one=True)
            if not valid: raise ValueError("This product or plan is no longer available.")
            result=buy(request.r["id"],plan_id,via="support_ai")
            payload={"key":result["key"],"product":result["product"],"plan":result["plan"],"price":result["price"],"balance":result["balance"]}
            q("UPDATE support_ai_purchases SET status='done',result_json=? WHERE request_id=?",(json.dumps(payload,ensure_ascii=False),reqid),commit=True)
            return jsonify(ok=True,**payload)
        except Exception as e:
            raw=str(e); low=raw.lower(); msg=raw; status="failed"
            if "key may still be created" in low or "not refunded automatically" in low:
                status="unknown"
                msg="Temporary API server issue. Your request may still be processing. Please check Key History before trying again."
            elif any(w in low for w in ("provider","tahir","vip seller","api","timeout","http")):
                msg="Temporary API server issue. Please wait for a short time and try again."
            q("UPDATE support_ai_purchases SET status=?,result_json=? WHERE request_id=?",(status,json.dumps({"error":msg},ensure_ascii=False),reqid),commit=True)
            q("INSERT INTO support_ai_failures(reseller_id,plan_id,error_code,public_message,created) VALUES(?,?,?,?,?)",(request.r["id"],plan_id,raw[:160],msg,int(time.time())),commit=True)
            return jsonify(ok=False,error=msg),400

    @app.context_processor
    def support_ai_context():
        cfg_now=conf()
        return {"ai_welcome": cfg_now["welcome"], "ai_enabled": bool(cfg_now["on"] and cfg_now["key"])}

    # Admin page
    templates["admin_support_ai.html"] = """{% extends 'abase.html' %}{% block c %}
<h2>✦ Gemini Support AI</h2><div class=card><h3>Gemini API Configuration</h3>
<p class=mu>Enter your Google Gemini API key. It is stored server-side and is never exposed to users. Leave blank to keep the saved key.</p>
<form method=post><input type=hidden name=action value=save><label class=mu>Gemini API Key {% if key_tail %}(saved · ends {{key_tail}}){% endif %}</label><input type=password name=api_key autocomplete=off placeholder="Paste Gemini API key" style="width:100%">
<label class=mu style="display:block;margin-top:12px">Model</label><select name=model style="width:100%"><option value=gemini-2.5-flash {{'selected' if cfg.model=='gemini-2.5-flash'}}>Gemini 2.5 Flash</option><option value=gemini-2.5-flash-lite {{'selected' if cfg.model=='gemini-2.5-flash-lite'}}>Gemini 2.5 Flash-Lite</option></select>
<label class=mu style="display:block;margin-top:12px">Welcome message</label><input name=welcome value="{{cfg.welcome}}" maxlength=300 style="width:100%"><label class=mu style="display:block;margin-top:12px">Website knowledge / extra instructions</label><textarea name=instructions rows=7 style="width:100%" placeholder="Add verified website guidance. Do not paste API secrets here.">{{cfg.instructions}}</textarea>
<label style="display:flex;gap:8px;align-items:center;margin:14px 0"><input type=checkbox name=enabled value=1 {{'checked' if cfg.on}}> Enable Support AI for logged-in users</label><button class=g>Save Support AI Settings</button></form>
<form method=post style="margin-top:12px"><input type=hidden name=action value=test><input type=password name=api_key autocomplete=off placeholder="Optional new API key to test" style="width:100%"><button class=o style="margin-top:8px">Test Gemini Connection</button></form></div>
<div class=card><h3>Connected website information</h3><p class=mu>Live product/plan names, user-specific prices, verified manual-stock status, and sanitized support events are supplied to Gemini. Wallet balances, generated keys, and raw provider diagnostics are not sent to Gemini. Purchases use the existing server-side purchase function after user confirmation.</p><p class=mu>Voice input and spoken replies use browser speech features where supported.</p></div>{% endblock %}"""

    # Admin navigation
    base=templates.get("abase.html","")
    if "/admin/support-ai" not in base:
        base=base.replace('<a href="/admin/logout"','<a href="/admin/support-ai" class="{{\'on\' if page==\'supportai\'}}">Support AI</a><a href="/admin/logout"',1)
        templates["abase.html"]=base

    # Floating support chat in all authenticated reseller pages
    base=templates.get("rbase.html","")
    if "support-ai-launcher" not in base:
        widget=r'''<style>
#support-ai-launcher{position:fixed;right:18px;bottom:18px;z-index:9998;border:0;border-radius:50%;width:64px;height:64px;background:var(--ac,#2563eb);color:#fff;padding:5px;box-shadow:0 8px 28px #0005;font-weight:800;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;font-size:11px}#support-ai-launcher span{font-size:10px}
#support-ai-box{position:fixed;right:16px;bottom:78px;width:min(390px,calc(100vw - 24px));height:min(590px,calc(100vh - 110px));z-index:9999;background:var(--card,#101827);color:var(--tx,#fff);border:1px solid var(--bd,#334155);border-radius:18px;box-shadow:0 18px 55px #0008;display:none;overflow:hidden;flex-direction:column}#support-ai-box.open{display:flex}
#support-ai-head{padding:13px 15px;background:var(--ac,#2563eb);color:#fff;display:flex;align-items:center;justify-content:space-between}#support-ai-msgs{padding:12px;overflow:auto;flex:1;display:flex;flex-direction:column;gap:9px}.sai-msg{max-width:90%;padding:10px 12px;border-radius:14px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.45}.sai-user{align-self:flex-end;background:var(--ac,#2563eb);color:#fff}.sai-bot{align-self:flex-start;background:var(--bg2,#263244);color:var(--tx,#fff)}
#support-ai-controls{border-top:1px solid var(--bd,#334155);padding:9px;display:flex;gap:6px;align-items:center}#support-ai-input{min-width:0;flex:1;border:1px solid var(--bd,#475569);border-radius:12px;padding:10px;background:var(--bg,#0f172a);color:var(--tx,#fff)}.sai-small{border:1px solid var(--bd,#475569);border-radius:10px;padding:9px;background:transparent;color:inherit}.sai-plan{display:flex;justify-content:space-between;align-items:center;gap:8px;border:1px solid var(--bd,#475569);border-radius:10px;padding:9px;margin-top:7px;font-size:13px}.sai-plan button{background:var(--ac,#2563eb);color:white;border:0;border-radius:8px;padding:7px 9px}
</style><button id="support-ai-launcher" type="button" style="display:{{ 'flex' if ai_enabled else 'none' }}">✦ <span>Support AI</span></button><div id="support-ai-box" role="dialog" aria-label="Support AI"><div id="support-ai-head"><div><b>✦ Support AI</b><div style="font-size:11px;opacity:.85">Website Assistant</div></div><button class="sai-small" id="sai-close" type="button" style="color:white">✕</button></div><div id="support-ai-msgs" aria-live="polite"></div><div id="support-ai-controls"><select id="sai-lang" class="sai-small" aria-label="Voice language"><option value="bn-IN">বাংলা</option><option value="en-IN">English</option><option value="hi-IN">हिन्दी</option></select><button class="sai-small" id="sai-mic" type="button">🎙</button><input id="support-ai-input" placeholder="Type your message…" maxlength="1200"><button class="sai-small" id="sai-send" type="button">➤</button></div></div>
<script>(function(){const box=document.getElementById('support-ai-box'),launch=document.getElementById('support-ai-launcher'),msgs=document.getElementById('support-ai-msgs'),input=document.getElementById('support-ai-input');if(!box||!launch)return;let history=[],busy=false;const welcome={{ ai_welcome|tojson }};
function add(text,who){const d=document.createElement('div');d.className='sai-msg '+(who==='user'?'sai-user':'sai-bot');d.textContent=text;msgs.appendChild(d);if(who!=='user'&&window.speechSynthesis){const b=document.createElement('button');b.className='sai-small';b.type='button';b.textContent='🔊';b.style.marginTop='6px';b.onclick=()=>{speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang=/[\u0980-\u09FF]/.test(text)?'bn-IN':(/[\u0900-\u097F]/.test(text)?'hi-IN':'en-IN');speechSynthesis.speak(u)};d.appendChild(document.createElement('br'));d.appendChild(b)}msgs.scrollTop=msgs.scrollHeight;return d}
function open(){box.classList.add('open');launch.style.display='none';if(!msgs.childNodes.length)add(welcome,'bot');input.focus()}function close(){box.classList.remove('open');launch.style.display='flex'}launch.onclick=open;document.getElementById('sai-close').onclick=close;
async function send(){const text=input.value.trim();if(!text||busy)return;input.value='';add(text,'user');history.push({role:'user',text});busy=true;const wait=add('Thinking…','bot');try{const r=await fetch('/support-ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,history:history.slice(-8)})});const j=await r.json();wait.remove();if(!r.ok||!j.ok){add(j.error||'Support AI is temporarily unavailable.','bot');return}add(j.reply||'I could not prepare a response.','bot');history.push({role:'assistant',text:j.reply||''});(j.products||[]).forEach(p=>{const card=document.createElement('div');card.className='sai-msg sai-bot';const title=document.createElement('b');title.textContent=p.name;card.appendChild(title);(p.plans||[]).forEach(pl=>{const row=document.createElement('div');row.className='sai-plan';const label=document.createElement('span');label.textContent=pl.name+' · ₹'+pl.price+(pl.available===false?' · Out of stock':(pl.available===null?' · Stock checked at purchase':''));row.appendChild(label);if(pl.selectable){const b=document.createElement('button');b.textContent='Select';b.onclick=()=>purchase(pl.id,p.name,pl.name,pl.price);row.appendChild(b)}card.appendChild(row)});msgs.appendChild(card)});msgs.scrollTop=msgs.scrollHeight}catch(e){wait.remove();add('Connection problem. Please try again shortly.','bot')}finally{busy=false}}
async function purchase(planId,product,plan,price){if(busy)return;if(!confirm('Confirm purchase?\n'+product+' · '+plan+' · ₹'+price))return;busy=true;const wait=add('Processing your confirmed purchase…','bot');const reqid=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{const r=Math.random()*16|0;return(c==='x'?r:(r&3|8)).toString(16)});try{const r=await fetch('/support-ai/purchase',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan_id:planId,request_id:reqid})});const j=await r.json();wait.remove();if(j.ok)add('Purchase successful!\nProduct: '+j.product+'\nPlan: '+j.plan+'\nPrice: ₹'+j.price+'\nKey: '+j.key+'\nRemaining balance: ₹'+j.balance,'bot');else add(j.error||'Purchase could not be completed.','bot')}catch(e){wait.remove();add('We could not confirm the result. Please check Key History before trying again.','bot')}finally{busy=false}}
document.getElementById('sai-send').onclick=send;input.addEventListener('keydown',e=>{if(e.key==='Enter')send()});const mic=document.getElementById('sai-mic'),SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){mic.disabled=true;mic.title='Voice recognition is not supported in this browser'}else{mic.onclick=()=>{const rec=new SR();rec.lang=document.getElementById('sai-lang').value;rec.interimResults=false;rec.maxAlternatives=1;rec.onresult=e=>{input.value=e.results[0][0].transcript;send()};rec.onerror=()=>add('Voice input is unavailable. You can type your message instead.','bot');rec.start()}}})();</script>'''
        base=base.replace('</body></html>',widget+'</body></html>')
        templates['rbase.html']=base
