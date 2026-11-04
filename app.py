import os, re, json, sqlite3, secrets, time, threading
from flask import (Flask, request, session, redirect, render_template, flash,
                   jsonify, send_from_directory, abort)
from jinja2 import DictLoader
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

DATA_DIR = os.environ.get("DATA_DIR", "data")
MUSIC_DIR = os.path.join(DATA_DIR, "music")
os.makedirs(MUSIC_DIR, exist_ok=True)
DB = os.path.join(DATA_DIR, "panel.db")
ADMIN_USER = os.environ.get("ADMIN_USER", "RGCHEAT")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "909090")
TZ_OFFSET = int(os.environ.get("TZ_OFFSET_MIN", "330")) * 60  # default IST
MAX_MUSIC = 20

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-" + ADMIN_PASS)
app.config.update(SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=60 * 1024 * 1024)


def db():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def q(sql, args=(), one=False, commit=False):
    c = db()
    try:
        cur = c.execute(sql, args)
        if commit:
            c.commit()
            return cur.lastrowid
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        c.close()


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY,
      product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
      name TEXT NOT NULL, days INTEGER NOT NULL, price REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS resellers(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
      pw TEXT NOT NULL, balance REAL NOT NULL DEFAULT 0, api_key TEXT UNIQUE NOT NULL,
      active INTEGER NOT NULL DEFAULT 1, created INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS custom_prices(
      reseller_id INTEGER REFERENCES resellers(id) ON DELETE CASCADE,
      plan_id INTEGER REFERENCES plans(id) ON DELETE CASCADE,
      price REAL NOT NULL, PRIMARY KEY(reseller_id, plan_id));
    CREATE TABLE IF NOT EXISTS license_keys(id INTEGER PRIMARY KEY,
      reseller_id INTEGER NOT NULL REFERENCES resellers(id) ON DELETE CASCADE,
      product_name TEXT, plan_name TEXT, key TEXT NOT NULL, price REAL NOT NULL,
      created INTEGER NOT NULL, expires INTEGER NOT NULL, via TEXT DEFAULT 'panel');
    CREATE TABLE IF NOT EXISTS music(id INTEGER PRIMARY KEY, title TEXT, url TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS stock(id INTEGER PRIMARY KEY,
      plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
      key TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0, used_by TEXT, used_at INTEGER, created INTEGER NOT NULL);
    """)
    cols = [r[1] for r in c.execute("PRAGMA table_info(plans)")]
    for col, ddl in (("mode", "TEXT DEFAULT 'random'"), ("ext_url", "TEXT DEFAULT ''"),
                     ("ext_method", "TEXT DEFAULT 'POST'"), ("ext_headers", "TEXT DEFAULT ''"),
                     ("ext_body", "TEXT DEFAULT ''"), ("ext_path", "TEXT DEFAULT ''")):
        if col not in cols:
            c.execute("ALTER TABLE plans ADD COLUMN %s %s" % (col, ddl))
    c.commit()
    c.close()


init_db()


# ---------------------------------------------------------------- helpers
def new_api_key():
    return "rk_" + secrets.token_hex(20)


def fmt(ts):
    return time.strftime("%d %b %Y %H:%M", time.gmtime(ts + TZ_OFFSET))


app.jinja_env.filters["dt"] = fmt
app.jinja_env.filters["money"] = lambda v: ("%.2f" % float(v)).rstrip("0").rstrip(".") if v is not None else "0"


def price_for(rid, plan):
    cp = q("SELECT price FROM custom_prices WHERE reseller_id=? AND plan_id=?", (rid, plan["id"]), one=True)
    return (cp["price"], True) if cp else (plan["price"], False)


def catalog(rid):
    out = []
    for p in q("SELECT * FROM products ORDER BY id"):
        plans = []
        for pl in q("SELECT * FROM plans WHERE product_id=? ORDER BY days, id", (p["id"],)):
            price, custom = price_for(rid, pl)
            sc = q("SELECT COUNT(*) FROM stock WHERE plan_id=? AND used=0", (pl["id"],), one=True)[0]
            plans.append(dict(id=pl["id"], name=pl["name"], days=pl["days"], price=price, custom=custom,
                              mode=pl["mode"] or "random", stock=sc))
        out.append(dict(id=p["id"], name=p["name"], plans=plans))
    return out


def _dig(obj, path):
    for part in [p for p in path.split(".") if p]:
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def fetch_external(pl):
    """Call the provider API configured on the plan and return the key text."""
    import requests
    rep = {"{days}": str(pl["days"]), "{plan}": pl["name"], "{product}": pl["pname"]}

    def sub(t):
        for k, v in rep.items():
            t = t.replace(k, v)
        return t
    headers = json.loads(sub(pl["ext_headers"])) if (pl["ext_headers"] or "").strip() else {}
    body = json.loads(sub(pl["ext_body"])) if (pl["ext_body"] or "").strip() else None
    m = (pl["ext_method"] or "POST").upper()
    kw = dict(headers=headers, timeout=25)
    if m == "GET":
        kw["params"] = body
    else:
        kw["json"] = body
    r = requests.request(m, sub(pl["ext_url"]), **kw)
    if r.status_code >= 400:
        raise ValueError("Provider HTTP %s" % r.status_code)
    if (pl["ext_path"] or "").strip():
        val = _dig(r.json(), pl["ext_path"].strip())
    else:
        val = r.text.strip()
    if not val:
        raise ValueError("Provider returned no key")
    return str(val)


def buy(rid, plan_id, via="panel"):
    c = sqlite3.connect(DB, timeout=20, isolation_level=None)
    c.row_factory = sqlite3.Row
    try:
        c.execute("BEGIN IMMEDIATE")
        r = c.execute("SELECT * FROM resellers WHERE id=?", (rid,)).fetchone()
        pl = c.execute("SELECT pl.*, pr.name pname FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=?",
                       (plan_id,)).fetchone()
        if not r or not r["active"]:
            raise ValueError("Account disabled")
        if not pl:
            raise ValueError("Plan not found")
        cp = c.execute("SELECT price FROM custom_prices WHERE reseller_id=? AND plan_id=?", (rid, plan_id)).fetchone()
        price = cp["price"] if cp else pl["price"]
        if r["balance"] < price:
            raise ValueError("Insufficient balance")
        now = int(time.time())
        mode, key = (pl["mode"] or "random"), None
        if mode == "stock":
            row = c.execute("SELECT * FROM stock WHERE plan_id=? AND used=0 ORDER BY id LIMIT 1", (plan_id,)).fetchone()
            if not row:
                raise ValueError("Out of stock")
            key = row["key"]
            c.execute("UPDATE stock SET used=1, used_by=?, used_at=? WHERE id=?", (r["username"], now, row["id"]))
        elif mode == "random":
            pre = re.sub(r"[^A-Z0-9]", "", pl["pname"].upper())[:6] or "KEY"
            raw = secrets.token_hex(8).upper()
            key = pre + "-" + "-".join(raw[i:i + 4] for i in range(0, 16, 4))
        exp = now + int(pl["days"]) * 86400
        c.execute("UPDATE resellers SET balance=balance-? WHERE id=?", (price, rid))
        if key:
            c.execute("INSERT INTO license_keys(reseller_id,product_name,plan_name,key,price,created,expires,via) "
                      "VALUES(?,?,?,?,?,?,?,?)", (rid, pl["pname"], pl["name"], key, price, now, exp, via))
        c.execute("COMMIT")
    except Exception:
        try:
            c.execute("ROLLBACK")
        except Exception:
            pass
        c.close()
        raise
    if mode == "api":  # balance already reserved; refund if the provider fails
        try:
            key = fetch_external(pl)
        except Exception as e:
            c.execute("UPDATE resellers SET balance=balance+? WHERE id=?", (price, rid))
            c.close()
            raise ValueError("Provider error, balance refunded: %s" % str(e)[:120])
        c.execute("INSERT INTO license_keys(reseller_id,product_name,plan_name,key,price,created,expires,via) "
                  "VALUES(?,?,?,?,?,?,?,?)", (rid, pl["pname"], pl["name"], key, price, now, exp, via))
    c.close()
    bal = q("SELECT balance FROM resellers WHERE id=?", (rid,), one=True)["balance"]
    return dict(key=key, price=price, expires=exp, balance=bal, product=pl["pname"], plan=pl["name"])


def reseller_required(f):
    from functools import wraps

    @wraps(f)
    def w(*a, **k):
        if not session.get("rid"):
            return redirect("/login")
        r = q("SELECT * FROM resellers WHERE id=?", (session["rid"],), one=True)
        if not r or not r["active"]:
            session.clear()
            return redirect("/login")
        request.r = r
        return f(*a, **k)
    return w


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"):
            return redirect("/admin/login")
        return f(*a, **k)
    return w


def num(v, default=0.0):
    try:
        return float(str(v).strip())
    except Exception:
        return default


# ---------------------------------------------------------------- public
@app.route("/health")
def health():
    return "ok"


@app.route("/")
def index():
    return redirect("/dashboard" if session.get("rid") else "/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        r = q("SELECT * FROM resellers WHERE username=?", (u,), one=True)
        if r and r["active"] and check_password_hash(r["pw"], request.form.get("password", "")):
            session.clear()
            session["rid"] = r["id"]
            return redirect("/dashboard")
        flash("Invalid username/password or account disabled", "err")
    return render_template("login.html", title="Reseller Login", action="/login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------------------------------------------------------- reseller panel
@app.route("/dashboard")
@reseller_required
def dashboard():
    rid, now = request.r["id"], int(time.time())
    midnight = now - ((now + TZ_OFFSET) % 86400)
    s = lambda sql, *a: q(sql, a, one=True)[0]
    stats = dict(
        total=s("SELECT COUNT(*) FROM license_keys WHERE reseller_id=?", rid),
        today=s("SELECT COUNT(*) FROM license_keys WHERE reseller_id=? AND created>=?", rid, midnight),
        active=s("SELECT COUNT(*) FROM license_keys WHERE reseller_id=? AND expires>?", rid, now),
        expired=s("SELECT COUNT(*) FROM license_keys WHERE reseller_id=? AND expires<=?", rid, now),
        spent=q("SELECT COALESCE(SUM(price),0) FROM license_keys WHERE reseller_id=?", (rid,), one=True)[0])
    return render_template("dashboard.html", r=request.r, st=stats, page="dashboard")


@app.route("/generate", methods=["GET", "POST"])
@reseller_required
def generate():
    if request.method == "POST":
        try:
            res = buy(request.r["id"], int(request.form.get("plan_id", 0)))
            flash("Purchased %s - %s | Key: %s | Expires: %s | Balance: %s" % (
                res["product"], res["plan"], res["key"], fmt(res["expires"]), res["balance"]), "ok")
        except Exception as e:
            flash(str(e), "err")
        return redirect("/generate")
    return render_template("generate.html", r=request.r, cat=catalog(request.r["id"]), page="generate")


@app.route("/history")
@reseller_required
def history():
    rows = q("SELECT * FROM license_keys WHERE reseller_id=? ORDER BY id DESC LIMIT 500", (request.r["id"],))
    return render_template("history.html", r=request.r, rows=rows, now=int(time.time()), page="history")


@app.route("/api-docs", methods=["GET", "POST"])
@reseller_required
def api_docs():
    if request.method == "POST":
        q("UPDATE resellers SET api_key=? WHERE id=?", (new_api_key(), request.r["id"]), commit=True)
        flash("New API key generated. Old key no longer works.", "ok")
        return redirect("/api-docs")
    return render_template("api.html", r=request.r, base=request.host_url.rstrip("/"), page="api")


@app.route("/music.json")
@reseller_required
def music_json():
    return jsonify([dict(title=m["title"], url=m["url"]) for m in q("SELECT * FROM music ORDER BY id")])


@app.route("/media/<path:name>")
def media(name):
    return send_from_directory(MUSIC_DIR, name)


# ---------------------------------------------------------------- reseller API
def api_auth():
    k = request.headers.get("X-API-Key") or request.args.get("api_key") or ""
    r = q("SELECT * FROM resellers WHERE api_key=?", (k,), one=True) if k else None
    if not r or not r["active"]:
        return None
    return r


def api_guard(f):
    from functools import wraps

    @wraps(f)
    def w(*a, **k):
        r = api_auth()
        if not r:
            return jsonify(success=False, error="INVALID_API_KEY"), 401
        request.r = r
        return f(*a, **k)
    return w


@app.route("/api/v1/health")
def api_health():
    return jsonify(success=True, status="online")


@app.route("/api/v1/balance")
@api_guard
def api_balance():
    return jsonify(success=True, username=request.r["username"], balance=request.r["balance"])


@app.route("/api/v1/products")
@api_guard
def api_products():
    return jsonify(success=True, products=[
        dict(product_id=p["id"], name=p["name"],
             plans=[dict(plan_id=x["id"], name=x["name"], days=x["days"], price=x["price"]) for x in p["plans"]])
        for p in catalog(request.r["id"])])


@app.route("/api/v1/purchase", methods=["POST"])
@api_guard
def api_purchase():
    d = request.get_json(silent=True) or request.form
    try:
        pid = int(d.get("plan_id"))
    except Exception:
        return jsonify(success=False, error="plan_id required"), 400
    try:
        res = buy(request.r["id"], pid, via="api")
    except ValueError as e:
        code = 402 if "Insufficient" in str(e) else 400
        return jsonify(success=False, error=str(e)), code
    return jsonify(success=True, key=res["key"], product=res["product"], plan=res["plan"],
                   price=res["price"], expires_at=res["expires"], balance=res["balance"])


@app.route("/api/v1/history")
@api_guard
def api_history():
    rows = q("SELECT * FROM license_keys WHERE reseller_id=? ORDER BY id DESC LIMIT 100", (request.r["id"],))
    return jsonify(success=True, keys=[dict(key=x["key"], product=x["product_name"], plan=x["plan_name"],
                                            price=x["price"], created_at=x["created"], expires_at=x["expires"]) for x in rows])


# ---------------------------------------------------------------- admin
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        ok_u = secrets.compare_digest(request.form.get("username", ""), ADMIN_USER)
        ok_p = secrets.compare_digest(request.form.get("password", ""), ADMIN_PASS)
        if ok_u and ok_p:
            session.clear()
            session["admin"] = True
            return redirect("/admin")
        flash("Wrong admin username/password", "err")
    return render_template("login.html", title="Admin Login", action="/admin/login")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin/login")


@app.route("/admin")
@admin_required
def admin_home():
    now = int(time.time())
    st = dict(resellers=q("SELECT COUNT(*) FROM resellers", one=True)[0],
              products=q("SELECT COUNT(*) FROM products", one=True)[0],
              keys=q("SELECT COUNT(*) FROM license_keys", one=True)[0],
              revenue=q("SELECT COALESCE(SUM(price),0) FROM license_keys", one=True)[0],
              credit=q("SELECT COALESCE(SUM(balance),0) FROM resellers", one=True)[0])
    recent = q("SELECT k.*, r.username FROM license_keys k JOIN resellers r ON r.id=k.reseller_id ORDER BY k.id DESC LIMIT 15")
    return render_template("admin_home.html", st=st, recent=recent, now=now, page="home")


@app.route("/admin/products", methods=["GET", "POST"])
@admin_required
def admin_products():
    if request.method == "POST":
        a = request.form.get("action")
        if a == "product" and request.form.get("name", "").strip():
            q("INSERT INTO products(name) VALUES(?)", (request.form["name"].strip(),), commit=True)
        elif a == "plan":
            try:
                q("INSERT INTO plans(product_id,name,days,price,mode) VALUES(?,?,?,?,?)",
                  (int(request.form["product_id"]), request.form["name"].strip(),
                   int(num(request.form.get("days"), 1)), num(request.form.get("price")),
                   request.form.get("mode", "stock")), commit=True)
            except Exception as e:
                flash("Error: %s" % e, "err")
        elif a == "edit_plan":
            q("UPDATE plans SET name=?, days=?, price=?, mode=? WHERE id=?",
              (request.form["name"].strip(), int(num(request.form.get("days"), 1)),
               num(request.form.get("price")), request.form.get("mode", "stock"),
               int(request.form["plan_id"])), commit=True)
        elif a == "del_plan":
            q("DELETE FROM plans WHERE id=?", (int(request.form["plan_id"]),), commit=True)
        elif a == "del_product":
            q("DELETE FROM products WHERE id=?", (int(request.form["product_id"]),), commit=True)
        return redirect("/admin/products")
    prods = [dict(p=p, plans=[dict(pl=pl, stock=q("SELECT COUNT(*) FROM stock WHERE plan_id=? AND used=0", (pl["id"],), one=True)[0])
                              for pl in q("SELECT * FROM plans WHERE product_id=? ORDER BY days,id", (p["id"],))])
             for p in q("SELECT * FROM products ORDER BY id")]
    return render_template("admin_products.html", prods=prods, page="products")



@app.route("/admin/stock/<int:pid>", methods=["GET", "POST"])
@admin_required
def admin_stock(pid):
    pl = q("SELECT pl.*, pr.name pname FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=?",
           (pid,), one=True) or abort(404)
    if request.method == "POST":
        a = request.form.get("action")
        if a == "add":
            keys = [k.strip() for k in request.form.get("keys", "").splitlines() if k.strip()]
            now = int(time.time())
            for k in keys:
                q("INSERT INTO stock(plan_id,key,created) VALUES(?,?,?)", (pid, k, now), commit=True)
            flash("%d key(s) added" % len(keys), "ok")
        elif a == "edit":
            q("UPDATE stock SET key=? WHERE id=? AND plan_id=? AND used=0",
              (request.form.get("key", "").strip(), int(request.form["id"]), pid), commit=True)
            flash("Key updated", "ok")
        elif a == "delete":
            q("DELETE FROM stock WHERE id=? AND plan_id=?", (int(request.form["id"]), pid), commit=True)
            flash("Key deleted", "ok")
        elif a == "clear_used":
            q("DELETE FROM stock WHERE plan_id=? AND used=1", (pid,), commit=True)
            flash("Used keys cleared", "ok")
        return redirect("/admin/stock/%d" % pid)
    rows = q("SELECT * FROM stock WHERE plan_id=? ORDER BY used, id DESC", (pid,))
    return render_template("admin_stock.html", pl=pl, rows=rows, page="products")


@app.route("/admin/plan-api/<int:pid>", methods=["GET", "POST"])
@admin_required
def admin_plan_api(pid):
    pl = q("SELECT pl.*, pr.name pname FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=?",
           (pid,), one=True) or abort(404)
    if request.method == "POST":
        f = request.form
        try:
            for fld in ("ext_headers", "ext_body"):
                if f.get(fld, "").strip():
                    json.loads(f[fld].replace("{days}", "1").replace("{plan}", "x").replace("{product}", "x"))
        except ValueError:
            flash("Headers/Body must be valid JSON", "err")
            return redirect("/admin/plan-api/%d" % pid)
        q("UPDATE plans SET ext_url=?, ext_method=?, ext_headers=?, ext_body=?, ext_path=? WHERE id=?",
          (f.get("ext_url", "").strip(), f.get("ext_method", "POST"), f.get("ext_headers", "").strip(),
           f.get("ext_body", "").strip(), f.get("ext_path", "").strip(), pid), commit=True)
        flash("API settings saved. Set the plan mode to 'External API' on the Products page to use it.", "ok")
        return redirect("/admin/plan-api/%d" % pid)
    return render_template("admin_plan_api.html", pl=pl, page="products")


@app.route("/admin/keys")
@admin_required
def admin_keys():
    rows = q("SELECT k.*, r.username FROM license_keys k JOIN resellers r ON r.id=k.reseller_id ORDER BY k.id DESC LIMIT 500")
    return render_template("admin_keys.html", rows=rows, now=int(time.time()), page="keys")


@app.route("/admin/resellers", methods=["GET", "POST"])
@admin_required
def admin_resellers():
    if request.method == "POST":
        u, p = request.form.get("username", "").strip(), request.form.get("password", "")
        if not u or not p:
            flash("Username and password required", "err")
        else:
            try:
                q("INSERT INTO resellers(username,pw,balance,api_key,created) VALUES(?,?,?,?,?)",
                  (u, generate_password_hash(p), num(request.form.get("credit")), new_api_key(), int(time.time())),
                  commit=True)
                flash("Reseller created", "ok")
            except sqlite3.IntegrityError:
                flash("Username already exists", "err")
        return redirect("/admin/resellers")
    rows = q("SELECT r.*, (SELECT COUNT(*) FROM license_keys k WHERE k.reseller_id=r.id) kc FROM resellers r ORDER BY r.id DESC")
    return render_template("admin_resellers.html", rows=rows, page="resellers")


@app.route("/admin/reseller/<int:rid>", methods=["GET", "POST"])
@admin_required
def admin_reseller(rid):
    r = q("SELECT * FROM resellers WHERE id=?", (rid,), one=True) or abort(404)
    if request.method == "POST":
        a = request.form.get("action")
        if a == "credit":
            q("UPDATE resellers SET balance=balance+? WHERE id=?", (num(request.form.get("amount")), rid), commit=True)
            flash("Credit updated (use negative number to deduct)", "ok")
        elif a == "password" and request.form.get("password"):
            q("UPDATE resellers SET pw=? WHERE id=?", (generate_password_hash(request.form["password"]), rid), commit=True)
            flash("Password changed", "ok")
        elif a == "toggle":
            q("UPDATE resellers SET active=1-active WHERE id=?", (rid,), commit=True)
        elif a == "prices":
            for pl in q("SELECT id FROM plans"):
                v = request.form.get("p_%d" % pl["id"], "").strip()
                if v == "":
                    q("DELETE FROM custom_prices WHERE reseller_id=? AND plan_id=?", (rid, pl["id"]), commit=True)
                else:
                    q("INSERT OR REPLACE INTO custom_prices(reseller_id,plan_id,price) VALUES(?,?,?)",
                      (rid, pl["id"], num(v)), commit=True)
            flash("Custom prices saved", "ok")
        elif a == "delete":
            q("DELETE FROM resellers WHERE id=?", (rid,), commit=True)
            return redirect("/admin/resellers")
        return redirect("/admin/reseller/%d" % rid)
    cat = catalog(rid)
    return render_template("admin_reseller.html", r=r, cat=cat, page="resellers")


@app.route("/admin/music", methods=["GET", "POST"])
@admin_required
def admin_music():
    if request.method == "POST":
        if request.form.get("action") == "delete":
            m = q("SELECT * FROM music WHERE id=?", (int(request.form["id"]),), one=True)
            if m:
                if m["url"].startswith("/media/"):
                    try:
                        os.remove(os.path.join(MUSIC_DIR, m["url"][7:]))
                    except OSError:
                        pass
                q("DELETE FROM music WHERE id=?", (m["id"],), commit=True)
        elif q("SELECT COUNT(*) FROM music", one=True)[0] >= MAX_MUSIC:
            flash("Maximum %d songs allowed" % MAX_MUSIC, "err")
        else:
            title = request.form.get("title", "").strip()
            f = request.files.get("file")
            url = request.form.get("url", "").strip()
            if f and f.filename:
                name = "%s_%s" % (secrets.token_hex(4), secure_filename(f.filename))
                f.save(os.path.join(MUSIC_DIR, name))
                url = "/media/" + name
                title = title or os.path.splitext(f.filename)[0]
            if url:
                q("INSERT INTO music(title,url) VALUES(?,?)", (title or url.split("/")[-1], url), commit=True)
                flash("Song added", "ok")
            else:
                flash("Upload a file or paste a direct audio URL", "err")
        return redirect("/admin/music")
    return render_template("admin_music.html", rows=q("SELECT * FROM music ORDER BY id"), mx=MAX_MUSIC, page="music")


# ---------------------------------------------------------------- keep-alive (Render never sleeps)
def keep_alive():
    url = (os.environ.get("KEEP_ALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if not url:
        return
    import requests
    time.sleep(60)
    while True:
        try:
            requests.get(url + "/health", timeout=20)
        except Exception:
            pass
        time.sleep(int(os.environ.get("KEEP_ALIVE_INTERVAL", "600")))


threading.Thread(target=keep_alive, daemon=True, name="keep-alive").start()

from templates_ui import TEMPLATES  # noqa: E402
app.jinja_env.loader = DictLoader(TEMPLATES)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
