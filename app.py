import math, io, os, re, json, sqlite3, secrets, time, threading, base64, hmac, hashlib, zipfile, tempfile
import html as _html
import requests
from flask import (Flask, request, session, redirect, render_template, flash,
                   jsonify, send_from_directory, abort, Response, make_response, send_file, after_this_request)
from werkzeug.middleware.proxy_fix import ProxyFix
import tgbot
from jinja2 import DictLoader
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

DATA_DIR = os.environ.get("DATA_DIR", "data")
MUSIC_DIR = os.path.join(DATA_DIR, "music")
os.makedirs(MUSIC_DIR, exist_ok=True)
DB = os.path.join(DATA_DIR, "panel.db")
ADMIN_USER = "ROHIT"  # fixed on purpose (env vars ignored) - change later
ADMIN_PASS = "909090"
TZ_OFFSET = int(os.environ.get("TZ_OFFSET_MIN", "330")) * 60  # default IST
MAX_MUSIC = 20

# Supported music-link metadata. YouTube/Spotify pages are not direct audio files;
# they are played through the providers' official embed players below.
def _music_link_info(raw_url):
    from urllib.parse import urlparse, quote
    raw_url = (raw_url or "").strip()
    try:
        u = urlparse(raw_url)
        host = (u.hostname or "").lower()
        if host in ("youtu.be", "www.youtu.be", "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            if host.endswith("youtu.be"):
                video_id = u.path.strip("/").split("/")[0]
            elif u.path == "/watch":
                from urllib.parse import parse_qs
                video_id = (parse_qs(u.query).get("v") or [""])[0]
            else:
                bits = [x for x in u.path.split("/") if x]
                video_id = bits[1] if len(bits) > 1 and bits[0] in ("embed", "shorts", "live") else ""
            if not re.match(r"^[A-Za-z0-9_-]{6,20}$", video_id or ""):
                return None
            canonical = "https://www.youtube.com/watch?v=" + video_id
            title = ""
            try:
                rr = requests.get("https://www.youtube.com/oembed", params={"url": canonical, "format": "json"}, timeout=8)
                if rr.ok: title = str(rr.json().get("title") or "")[:200]
            except Exception: pass
            return {"kind": "youtube", "title": title, "url": canonical, "embed_url": "https://www.youtube.com/embed/" + video_id}
        if host in ("open.spotify.com", "www.open.spotify.com"):
            if host not in ("open.spotify.com", "www.open.spotify.com"): return None
            parts = [x for x in u.path.split("/") if x and x not in ("intl-en", "intl-de", "intl-es")]
            if len(parts) >= 2 and parts[0] in ("track", "album", "playlist", "episode", "show"):
                kind, item_id = parts[0], parts[1].split("?")[0]
                if not re.match(r"^[A-Za-z0-9]{10,30}$", item_id): return None
                canonical = "https://open.spotify.com/%s/%s" % (kind, item_id)
                title = ""
                try:
                    rr = requests.get("https://open.spotify.com/oembed", params={"url": canonical}, timeout=8)
                    if rr.ok: title = str(rr.json().get("title") or "")[:200]
                except Exception: pass
                return {"kind": "spotify", "title": title, "url": canonical, "embed_url": "https://open.spotify.com/embed/%s/%s" % (kind, item_id)}
    except Exception:
        return None
    return None


def _download_direct_audio(raw_url):
    """Download an administrator-supplied, publicly reachable direct audio URL.

    YouTube/Spotify URLs are intentionally handled by their official embeds and
    never downloaded here. Restrict hosts/IPs and file size to reduce SSRF risk.
    Returns (relative_media_url, suggested_title).
    """
    import ipaddress, socket, mimetypes
    from urllib.parse import urlparse, urljoin, unquote
    from email.message import Message

    allowed_ext = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".oga", ".opus", ".flac", ".webm", ".mp4"}
    mime_ext = {
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mp4": ".m4a",
        "audio/aac": ".aac", "audio/wav": ".wav", "audio/x-wav": ".wav",
        "audio/ogg": ".ogg", "audio/flac": ".flac", "audio/x-flac": ".flac",
        "audio/webm": ".webm", "video/mp4": ".mp4", "application/ogg": ".ogg",
    }
    max_bytes = 50 * 1024 * 1024

    def public_url(value):
        p = urlparse(value)
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
            raise ValueError("Use a public HTTP/HTTPS direct audio URL.")
        if p.port not in (None, 80, 443):
            raise ValueError("Audio URL must use the standard HTTP/HTTPS port.")
        host = p.hostname.lower().rstrip(".")
        if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError("Private/local network URLs are not allowed.")
        try:
            ip = ipaddress.ip_address(host)
            ips = [ip]
        except ValueError:
            try:
                ips = [ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)]
            except Exception:
                raise ValueError("Could not resolve the audio URL host.")
        if not ips or any(not x.is_global for x in ips):
            raise ValueError("Private or non-public network addresses are not allowed.")
        return p

    current = raw_url.strip()
    response = None
    try:
        for hop in range(4):
            p = public_url(current)
            response = requests.get(current, stream=True, timeout=(8, 25), allow_redirects=False,
                                    headers={"User-Agent": "ResellerMusicImporter/1.0", "Accept": "audio/*,application/octet-stream;q=0.8,*/*;q=0.1"}, verify=True)
            if response.status_code in (301, 302, 303, 307, 308):
                loc = response.headers.get("Location")
                response.close(); response = None
                if not loc or hop >= 3:
                    raise ValueError("Audio URL redirected too many times or had no redirect target.")
                current = urljoin(current, loc)
                continue
            if response.status_code < 200 or response.status_code >= 300:
                raise ValueError("Audio host returned HTTP %s." % response.status_code)
            break
        else:
            raise ValueError("Could not follow the audio URL redirect.")

        content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        p = urlparse(current)
        url_name = unquote(os.path.basename(p.path.rstrip("/")))
        ext = os.path.splitext(url_name)[1].lower()
        if ext not in allowed_ext:
            ext = mime_ext.get(content_type, "")
        if content_type.startswith("text/") or content_type in ("text/html", "application/json", "application/xml"):
            raise ValueError("This URL returned a web page, not an audio file. Use a direct audio-file URL.")
        if not content_type.startswith("audio/") and content_type not in ("video/mp4", "application/ogg", "application/octet-stream", "binary/octet-stream"):
            raise ValueError("The URL does not appear to be an audio file.")
        if ext not in allowed_ext:
            raise ValueError("Unsupported audio format. Use MP3, M4A, AAC, WAV, OGG, OPUS or FLAC.")
        size_header = response.headers.get("Content-Length")
        if size_header and size_header.isdigit() and int(size_header) > max_bytes:
            raise ValueError("Audio file is larger than the 50 MB limit.")

        cd_name = ""
        cd = response.headers.get("Content-Disposition", "")
        if cd:
            msg = Message(); msg["content-disposition"] = cd
            cd_name = msg.get_filename() or ""
        suggested = os.path.splitext(os.path.basename(unquote(cd_name or url_name)))[0]
        suggested = re.sub(r"[\x00-\x1f]+", " ", suggested).strip()[:180]
        if not suggested:
            suggested = "Imported Music"

        name = secrets.token_hex(12) + ext
        dest = os.path.join(MUSIC_DIR, name)
        total = 0
        try:
            with open(dest, "wb") as out:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Audio file is larger than the 50 MB limit.")
                    out.write(chunk)
            if total == 0:
                raise ValueError("The audio URL returned an empty file.")
        except Exception:
            try: os.remove(dest)
            except OSError: pass
            raise
        return "/media/" + name, suggested
    except requests.RequestException as e:
        raise ValueError("Could not download the audio file: %s" % str(e)[:140])
    finally:
        if response is not None:
            response.close()

# ---- TELEGRAM BOT (edit here, nothing else to configure) ----------------------------------------
TG_BOT_TOKEN = ""   # NEVER write the bot token here (GitHub leak!). Set it in Admin > Telegram. Optional backup: Render env TG_BOT_TOKEN
TG_ADMIN_ID = "6739795427"      # default admin Chat ID (not secret). Admin > Telegram can change it any time
EMOJI_PACKS = [x for x in (os.environ.get("EMOJI_PACKS") or "RGCHEAT99,botd3,NewsEmoji").replace(" ", "").split(",") if x]   # premium emoji packs (first = highest priority)
BRAND = "OFFICIAL SELLER"      # name shown on login + panel header
CURRENCY = "₹"         # symbol shown before money amounts (all prices are INR)
DEFAULT_API_BASE = "https://adminshops.com/api/v1"   # TAHIR API SYSTEM server (fixed - only the token is entered in Admin)
DEFAULT_VSH_BASE = "https://whitexmodz.store/api/v1"   # VIP SELLER HUB API (base URL can be changed in Admin > VIP Seller Hub)
USD_TO_INR = 30.0                                     # provider price in USD x 30 = our cost in Rs
DEFAULT_MARKUP_RESELLER = 50    # % added on the main-API cost -> RESELLER price
DEFAULT_MARKUP_USER = 200       # % added on the main-API cost -> USER price

app = Flask(__name__)
def _load_secret_key():
    """Never derive the session key from the admin password (anybody knowing it could forge an admin cookie and skip the code).
    Use env SECRET_KEY, else a random key stored once in the data folder."""
    k = os.environ.get("SECRET_KEY", "").strip()
    if k:
        return k
    path = os.path.join(DATA_DIR, ".secret_key")
    try:
        with open(path) as fh:
            k = fh.read().strip()
    except OSError:
        k = ""
    if len(k) < 32:
        k = secrets.token_hex(32)
        try:
            with open(path, "w") as fh:
                fh.write(k)
            os.chmod(path, 0o600)
        except OSError:
            pass
    return k


app.secret_key = _load_secret_key()
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PUBLIC_DOMAIN")),
                  MAX_CONTENT_LENGTH=250 * 1024 * 1024)
ADMIN_TTL = 8 * 3600     # an admin session ends after 8 hours -> new password + new Telegram code
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)   # real client IP / https behind Render


import gzip as _gzip


@app.after_request
def gzip_response(resp):
    """v18: pages are sent compressed (a 100-product admin page shrinks from ~1.3 MB to ~60 KB)."""
    try:
        if (resp.status_code != 200 or resp.direct_passthrough or resp.headers.get("Content-Encoding")
                or "gzip" not in request.headers.get("Accept-Encoding", "")
                or resp.mimetype not in ("text/html", "application/javascript", "application/json", "text/css")):
            return resp
        data = resp.get_data()
        if len(data) < 1024:
            return resp
        resp.set_data(_gzip.compress(data, 5))
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Vary"] = "Accept-Encoding"
        resp.headers["Content-Length"] = str(len(resp.get_data()))
    except Exception as e:
        print("[gzip] %s" % e)
    return resp


_WAL_SET = False


def db():
    global _WAL_SET
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    if not _WAL_SET:                         # v18: WAL is stored in the file, set it only once
        try:
            c.execute("PRAGMA journal_mode=WAL")
            _WAL_SET = True
        except sqlite3.Error:
            pass
    c.execute("PRAGMA synchronous=NORMAL")   # v18: much faster saves, still safe with WAL
    c.execute("PRAGMA busy_timeout=20000")
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
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS topups(id INTEGER PRIMARY KEY,
      reseller_id INTEGER NOT NULL REFERENCES resellers(id) ON DELETE CASCADE,
      amount REAL NOT NULL, order_id TEXT, qr_url TEXT, upi_id TEXT, status TEXT NOT NULL DEFAULT 'pending',
      utr TEXT, created INTEGER NOT NULL, expires INTEGER, deadline INTEGER NOT NULL, paid_at INTEGER,
      last_check INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS broadcasts(id INTEGER PRIMARY KEY, reseller_id INTEGER,
      title TEXT, body TEXT NOT NULL, created INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS broadcast_reads(broadcast_id INTEGER NOT NULL, reseller_id INTEGER NOT NULL,
      PRIMARY KEY(broadcast_id, reseller_id));
    CREATE TABLE IF NOT EXISTS devices(id INTEGER PRIMARY KEY,
      reseller_id INTEGER NOT NULL REFERENCES resellers(id) ON DELETE CASCADE,
      dev_id TEXT NOT NULL, label TEXT, ip TEXT, status TEXT NOT NULL DEFAULT 'pending',
      created INTEGER NOT NULL, decided INTEGER, last_seen INTEGER);
    CREATE TABLE IF NOT EXISTS otps(reseller_id INTEGER PRIMARY KEY, h TEXT NOT NULL, exp INTEGER NOT NULL,
      tries INTEGER NOT NULL DEFAULT 0, sent INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS tg_seen(chat_id TEXT PRIMARY KEY, name TEXT, username TEXT, ts INTEGER NOT NULL);
    """)
    cols = [r[1] for r in c.execute("PRAGMA table_info(plans)")]
    for col, ddl in (("mode", "TEXT DEFAULT 'random'"), ("ext_url", "TEXT DEFAULT ''"),
                     ("ext_method", "TEXT DEFAULT 'POST'"), ("ext_headers", "TEXT DEFAULT ''"),
                     ("ext_body", "TEXT DEFAULT ''"), ("ext_path", "TEXT DEFAULT ''"),
                     ("prov_pid", "INTEGER"), ("hours", "INTEGER NOT NULL DEFAULT 0"),
                     ("user_price", "REAL DEFAULT 0"), ("cost", "REAL DEFAULT 0"), ("prov_src", "TEXT DEFAULT ''"), ("prov_meta", "TEXT DEFAULT ''")):
        if col not in cols:
            c.execute("ALTER TABLE plans ADD COLUMN %s %s" % (col, ddl))
    for r_ in c.execute("SELECT id,name FROM plans WHERE hours=0").fetchall():
        m_ = re.search(r"(\d+)\s*(hours?|hrs?|h)\b", (r_[1] or "").lower())
        if m_:
            c.execute("UPDATE plans SET hours=? WHERE id=?", (int(m_.group(1)), r_[0]))
    for tbl, cols_ in (("topups", (("provider", "TEXT NOT NULL DEFAULT 'fam'"), ("ref", "TEXT DEFAULT ''"), ("pay_uri", "TEXT DEFAULT ''"),
                                   ("checkout_url", "TEXT DEFAULT ''"), ("app_pay", "INTEGER NOT NULL DEFAULT 0"),
                                   ("purpose", "TEXT NOT NULL DEFAULT 'wallet'"), ("pay_amount", "REAL NOT NULL DEFAULT 0"))),
                       ("products", (("icon", "TEXT DEFAULT ''"), ("emoji_id", "TEXT DEFAULT ''"), ("icon_ver", "INTEGER NOT NULL DEFAULT 0"),
                                    ("pos", "INTEGER NOT NULL DEFAULT 0"), ("src_name", "TEXT DEFAULT ''"), ("hidden", "INTEGER NOT NULL DEFAULT 0")))):
        have = [r[1] for r in c.execute("PRAGMA table_info(%s)" % tbl)]
        for col, ddl in cols_:
            if col not in have:
                c.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tbl, col, ddl))
    c.execute("CREATE TABLE IF NOT EXISTS zy_events(id TEXT PRIMARY KEY, ts INTEGER NOT NULL)")
    for _ix in ("CREATE INDEX IF NOT EXISTS ix_stock_plan ON stock(plan_id, used)",
                "CREATE INDEX IF NOT EXISTS ix_plans_prod ON plans(product_id)",
                "CREATE INDEX IF NOT EXISTS ix_plans_prov ON plans(prov_src, prov_pid)",
                "CREATE INDEX IF NOT EXISTS ix_keys_res ON license_keys(reseller_id, id)",
                "CREATE INDEX IF NOT EXISTS ix_topups_status ON topups(status)",
                "CREATE INDEX IF NOT EXISTS ix_topups_res ON topups(reseller_id)",
                "CREATE INDEX IF NOT EXISTS ix_devices_res ON devices(reseller_id, dev_id)",
                "CREATE INDEX IF NOT EXISTS ix_custom_res ON custom_prices(reseller_id)"):
        try:
            c.execute(_ix)
        except sqlite3.Error:
            pass
    c.execute("UPDATE products SET src_name=name WHERE src_name='' OR src_name IS NULL")   # remembers the ORIGINAL (provider) name
    rcols = [r[1] for r in c.execute("PRAGMA table_info(resellers)")]
    for col, ddl in (("theme", "TEXT DEFAULT ''"), ("tg_chat", "TEXT DEFAULT ''"),
                     ("otp_on", "INTEGER NOT NULL DEFAULT 1"), ("notify", "INTEGER NOT NULL DEFAULT 1"),
                     ("low_bal", "REAL NOT NULL DEFAULT 50"), ("tg_alert", "INTEGER NOT NULL DEFAULT 0"), ("role", "TEXT NOT NULL DEFAULT 'reseller'"),
                     ("deleted", "INTEGER NOT NULL DEFAULT 0"), ("deleted_at", "INTEGER NOT NULL DEFAULT 0")):
        if col not in rcols:
            c.execute("ALTER TABLE resellers ADD COLUMN %s %s" % (col, ddl))
    c.commit()
    c.close()


init_db()


# ---------------------------------------------------------------- helpers
def new_api_key():
    return "rk_" + secrets.token_hex(20)


def fmt(ts):
    if not ts:
        return "-"
    return time.strftime("%d %b %Y %H:%M", time.gmtime(ts + TZ_OFFSET))


app.jinja_env.filters["dt"] = fmt
app.jinja_env.filters["dt2"] = lambda ts: time.strftime("%d/%m/%y %I:%M %p", time.gmtime(ts + TZ_OFFSET))
app.jinja_env.filters["money"] = lambda v: ("%.2f" % float(v)).rstrip("0").rstrip(".") if v is not None else "0"


def _cur(v):
    return CURRENCY + app.jinja_env.filters["money"](v)


app.jinja_env.filters["cur"] = _cur
app.jinja_env.globals.update(BRAND=BRAND, year=time.gmtime().tm_year, CURRENCY=CURRENCY)


def plan_label(days, hours=0):
    """'1 Hour' / '3 Hours' when hours>0, else '1 Day' / '7 Days'."""
    hours = int(hours or 0)
    if hours > 0:
        return "%d Hour%s" % (hours, "" if hours == 1 else "s")
    days = max(int(days), 1)
    return "%d Day%s" % (days, "" if days == 1 else "s")


def plan_secs(pl):
    """Real validity of a plan in seconds (hour plans use hours, others use days)."""
    try:
        h = int(pl["hours"] or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        h = 0
    return h * 3600 if h > 0 else max(int(pl["days"]), 1) * 86400


def validity_text(pl):
    """Text for bot alerts: '1 hours (1 HOURS)' or '1 days (1 DAYS)' - matches the real purchase."""
    try:
        h = int(pl["hours"] or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        h = 0
    if h > 0:
        return "%d hours (%d HOURS)" % (h, h)
    d = max(int(pl["days"]), 1)
    return "%d days (%d DAYS)" % (d, d)


def markups():
    return (max(num(get_setting("markup_reseller", str(DEFAULT_MARKUP_RESELLER)), DEFAULT_MARKUP_RESELLER), 0.0),
            max(num(get_setting("markup_user", str(DEFAULT_MARKUP_USER)), DEFAULT_MARKUP_USER), 0.0))


def auto_user_price(reseller_price):
    """User price for a plan that has no own user price: reseller price scaled by the markup difference."""
    mr, mu = markups()
    return round(float(reseller_price or 0) * (1 + mu / 100.0) / (1 + mr / 100.0), 2)


def user_price_of(pl):
    try:
        up = float(pl["user_price"] or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        up = 0
    return up if up > 0 else auto_user_price(pl["price"])


def role_of(rid):
    r = q("SELECT role FROM resellers WHERE id=?", (rid,), one=True)
    return (r["role"] if r else "reseller") or "reseller"


def price_for(rid, plan):
    """(price, custom?)  USER accounts always pay the user price; resellers pay custom price or reseller price."""
    if role_of(rid) == "user":
        return (user_price_of(plan), False)
    cp = q("SELECT price FROM custom_prices WHERE reseller_id=? AND plan_id=?", (rid, plan["id"]), one=True)
    return (cp["price"], True) if cp else (plan["price"], False)


_SET_CACHE = {}          # v18: settings are cached in memory (the big background picture was re-read from disk on EVERY page)
_SET_TTL = 5.0


def get_setting(k, default=""):
    hit = _SET_CACHE.get(k)
    now = time.time()
    if hit is not None and now - hit[1] < _SET_TTL:
        v = hit[0]
    else:
        r = q("SELECT v FROM settings WHERE k=?", (k,), one=True)
        v = r["v"] if r else None
        _SET_CACHE[k] = (v, now)
    return v if v is not None else default


def set_setting(k, v):
    q("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (k, v), commit=True)
    _SET_CACHE[k] = (v, time.time())


def clean_site_name(v):
    """Site name typed in Admin > Logo & Theme: 1-40 characters, no < > or control characters."""
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    if not (1 <= len(v) <= 40) or re.search(r"[<>\x00-\x1f]", v):
        return ""
    return v


def brand_name():
    """The website name. Saved from the admin panel (settings key 'site_name'); falls back to the default BRAND."""
    try:
        return clean_site_name(get_setting("site_name", "")) or BRAND
    except Exception:
        return BRAND


def same(a, b):
    """constant-time compare that never crashes on non-ASCII text"""
    return secrets.compare_digest(str(a).encode("utf-8"), str(b).encode("utf-8"))


# ---- TAHIR API SYSTEM (adminshops.com: Authorization Bearer, GET /balance | /catalog, POST /generate)
class ProvUnknown(Exception):
    """purchase request was sent but the answer never came back -> outcome unknown, never refund blindly"""


def prov_base():
    return DEFAULT_API_BASE.rstrip("/")


def prov_token():
    return (get_setting("tahir_token") or "").strip()


def prov_headers():
    tok = prov_token()
    if not tok:
        raise ValueError("API token not set (Admin > Tahir API System)")
    return {"Authorization": "Bearer " + tok}


def prov_json(r):
    try:
        j = r.json()
    except ValueError:
        raise ValueError("Tahir API HTTP %s (not JSON)" % r.status_code)
    if not isinstance(j, dict):
        raise ValueError("Tahir API HTTP %s (unexpected answer)" % r.status_code)
    return j


def prov_err(j, r):
    e = j.get("error")
    if isinstance(e, dict):
        e = e.get("message")
    return str(e or j.get("message") or "Tahir API HTTP %s" % r.status_code)[:150]


def prov_get(path, **params):
    r = requests.get(prov_base() + path, headers=prov_headers(), params=params, timeout=30)
    j = prov_json(r)
    if not j.get("ok"):
        raise ValueError(prov_err(j, r))
    return j.get("data") or {}


def prov_generate(plan_id, idem):
    """Buy ONE key (POST /generate). The same idempotency_key is sent on a retry, so it can never charge twice."""
    last = None
    for attempt in range(2):
        try:
            r = requests.post(prov_base() + "/generate", headers=prov_headers(),
                              json={"product_id": int(plan_id), "quantity": 1, "idempotency_key": idem}, timeout=60)
        except requests.ConnectTimeout:
            raise ValueError("Tahir API not reachable")
        except requests.ConnectionError:
            raise ValueError("Tahir API not reachable")
        except requests.Timeout:
            last = ProvUnknown("The Tahir API took too long to answer")
            continue
        j = prov_json(r)
        keys = (j.get("data") or {}).get("keys") if j.get("ok") else None
        if not keys:
            raise ValueError(prov_err(j, r))
        return str(keys[0])
    raise last


def prov_status():
    """Connect test = GET /balance -> remembered in settings."""
    try:
        d = prov_get("/balance")
        st = dict(ok=True, balance=float(d.get("balance") or 0), balance_usd=float(d.get("balance_usd") or 0),
                  currency=str(d.get("currency") or "INR"), msg="Connect successful")
    except Exception as e:
        st = dict(ok=False, msg=str(e)[:150])
    st["ts"] = int(time.time())
    set_setting("tahir_status", json.dumps(st))
    return st


def load_catalog(refresh=False):
    """All products of the Tahir API (GET /catalog), grouped by product name. Cost = USD price x 30. Cached in settings."""
    if not refresh:
        try:
            return json.loads(get_setting("tahir_catalog"))
        except ValueError:
            pass
    d = prov_get("/catalog")
    rate = float(d.get("usd_rate") or 0)
    groups, order = {}, []
    for it in d.get("products") or []:
        try:
            pid = int(it["product_id"])
        except (KeyError, TypeError, ValueError):
            continue
        usd = it.get("price_usd")
        if usd is None and rate:
            usd = float(it.get("price") or 0) / rate
        cost = round(float(usd or 0) * USD_TO_INR, 2)
        gname = str(it.get("product_name") or "Product %s" % pid).strip()
        if gname not in groups:
            groups[gname] = dict(product_id=len(order) + 1, name=gname, plans=[])
            order.append(gname)
        raw_duration = str(it.get("duration") or it.get("validity") or it.get("name") or "").strip()
        days, hours, display_name = duration_parts(raw_duration, it)
        groups[gname]["plans"].append(dict(plan_id=pid, name=display_name, days=days, hours=hours, price=cost, available=True))
    obj = dict(ts=int(time.time()), products=[groups[n] for n in order])
    set_setting("tahir_catalog", json.dumps(obj))
    return obj


def catalog_plans(cat):
    """{plan_id: (product_dict, plan_dict)} from a cached catalog."""
    out = {}
    for p in (cat or {}).get("products", []):
        for pl in p.get("plans") or []:
            try:
                out[int(pl["plan_id"])] = (p, pl)
            except (KeyError, TypeError, ValueError):
                pass
    return out


# ---- VIP SELLER HUB API (header X-API-Token, GET balance.php | products.php, POST generate_key.php)
def vsh_base():
    return (get_setting("vsh_base") or DEFAULT_VSH_BASE).strip().rstrip("/")


def vsh_token():
    return (get_setting("vsh_token") or "").strip()


def vsh_rate():
    """Multiplier applied to the prices of this API (1 = prices are already in INR)."""
    r = num(get_setting("vsh_rate", "1"), 1.0)
    return r if r > 0 else 1.0


def vsh_markups():
    mr, mu = markups()
    return (max(num(get_setting("vsh_markup_reseller", "%g" % mr), mr), 0.0),
            max(num(get_setting("vsh_markup_user", "%g" % mu), mu), 0.0))


def api_enabled(source):
    key = "api_%s_enabled" % ("vsh" if source == "vsh" else "tahir")
    return get_setting(key, "1") != "0"


def vsh_call(endpoint, params=None, method="GET", _retried=False):
    """Call the VIP SELLER HUB API. The JSON field 'success' is always checked (Cloudflare wraps origin errors as HTTP 200)."""
    tok = vsh_token()
    if not tok:
        raise ValueError("API token not set (Admin > VIP Seller Hub)")
    url = vsh_base() + "/" + endpoint
    headers = {"X-API-Token": tok, "Accept": "application/json"}
    try:
        if method.upper() == "GET":
            r = requests.get(url, params=params or {}, headers=headers, timeout=30)
        else:
            r = requests.post(url, data=params or {}, headers=headers, timeout=60)
    except requests.ConnectTimeout:
        raise ValueError("VIP Seller Hub API not reachable (timeout)")
    except requests.ConnectionError:
        raise ValueError("VIP Seller Hub API not reachable - check the Base URL")
    except requests.Timeout:
        raise ProvUnknown("The VIP Seller Hub API took too long to answer")
    try:
        j = r.json()
    except ValueError:
        raise ValueError("VIP Seller Hub API HTTP %s (not JSON) - check the Base URL" % r.status_code)
    if not isinstance(j, dict):
        raise ValueError("VIP Seller Hub API HTTP %s (unexpected answer)" % r.status_code)
    err = str(j.get("error") or j.get("message") or "")[:150]
    if r.status_code == 401:
        raise ValueError(err or "Token invalid or revoked")
    if r.status_code == 403:
        raise ValueError(err or "Forbidden (IP not allowed?)")
    if r.status_code == 423:
        raise ValueError(err or "Key cap reached")
    if r.status_code == 429:
        if not _retried:
            ra = r.headers.get("Retry-After")
            time.sleep(min(20, max(1, int(ra))) if ra and ra.isdigit() else 5)
            return vsh_call(endpoint, params, method, _retried=True)
        raise ValueError(err or "Rate limit reached - try again in a minute")
    if r.status_code >= 500:
        raise ValueError("Server error %s: %s" % (r.status_code, err or "try again"))
    if j.get("success") is False or j.get("ok") is False:
        raise ValueError(err or "Request failed")
    return j


def _first_num(d, keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            try:
                return float(str(d[k]).replace(",", "").strip())
            except ValueError:
                pass
    return None


def vsh_status():
    """Connect test = balance.php -> remembered in settings."""
    raw = None
    try:
        raw = vsh_call("balance.php")
        d = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        bal = _first_num(d, ("balance", "wallet", "credits", "credit", "amount"))
        if bal is None:
            bal = _first_num(raw, ("balance", "wallet", "credits", "credit", "amount"))
        st = dict(ok=True, balance=bal if bal is not None else 0.0, has_bal=bal is not None, msg="Connect successful",
                  cur=str((d.get("currency") if isinstance(d, dict) else "") or ""))
    except Exception as e:
        st = dict(ok=False, msg=str(e)[:150])
    st["ts"] = int(time.time())
    st["raw"] = json.dumps(raw, ensure_ascii=False)[:1500] if raw is not None else ""
    set_setting("vsh_status", json.dumps(st))
    return st


def _vsh_product_list(raw):
    """Accept data.products/products and common API response wrappers."""
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict):
        return []
    for node in (raw.get("data"), raw.get("result"), raw.get("response"), raw):
        if isinstance(node, list):
            return node
        if isinstance(node, dict):
            for key in ("products", "items", "list", "catalog"):
                value = node.get(key)
                if isinstance(value, list):
                    return value
            for key in ("data", "result", "response"):
                nested = node.get(key)
                if isinstance(nested, dict):
                    for list_key in ("products", "items", "list", "catalog"):
                        value = nested.get(list_key)
                        if isinstance(value, list):
                            return value
    return []


def _vsh_variants(product):
    for key in ("variants", "plans", "options", "durations", "items"):
        value = product.get(key)
        if isinstance(value, list) and value:
            return value
    if any(product.get(k) not in (None, "") for k in ("id", "variant_id", "plan_id")):
        return [product]
    return []


def vsh_load_catalog(refresh=False):
    """Load every VIP Seller Hub product/variant; retain provider IDs verbatim."""
    if not refresh:
        try:
            cached = json.loads(get_setting("vsh_catalog"))
            if isinstance(cached, dict) and isinstance(cached.get("products"), list) and cached.get("products"):
                return cached
        except (ValueError, TypeError):
            pass
    raw = vsh_call("products.php")
    rate = vsh_rate()
    groups = []
    for n, p in enumerate(_vsh_product_list(raw), 1):
        if not isinstance(p, dict):
            continue
        gname = str(p.get("name") or p.get("title") or p.get("product_name") or
                    p.get("product") or "Product %s" % (p.get("id") or n)).strip()
        plans = []
        for v in _vsh_variants(p):
            if not isinstance(v, dict):
                continue
            raw_id = v.get("variant_id", v.get("plan_id", v.get("id")))
            if raw_id in (None, ""):
                continue
            vid = str(raw_id).strip()
            if not vid:
                continue
            price = _first_num(v, ("price", "cost", "rate", "amount", "price_inr",
                                    "reseller_price", "selling_price", "base_price", "price_usd", "usd_price", "cost_usd"))
            if price is None:
                price = _first_num(p, ("price", "cost", "rate", "amount")) or 0.0
            raw_duration = (v.get("name") or v.get("title") or v.get("duration") or
                            v.get("label") or v.get("validity") or ("Variant %s" % vid))
            vdays, vhours, vname = duration_parts(raw_duration, v)
            bala = bool(v.get("is_balamod", v.get("balamod", False)))
            mode = str(v.get("api_version_mode") or v.get("mode") or "") if bala else ""
            stock = v.get("stock", v.get("available", v.get("in_stock")))
            avail = True if stock in (None, "") else (str(stock).lower() not in ("0", "false", "no", "out", "unavailable"))
            plans.append(dict(plan_id=vid, name=vname, days=vdays, hours=vhours, price=round(price * rate, 2),
                              api_price=price, available=avail, balamod=bala, mode=mode))
        if plans:
            groups.append(dict(product_id=str(p.get("product_id") or p.get("id") or n),
                               name=gname, plans=plans))
    obj = dict(ts=int(time.time()), products=groups, product_count=len(groups),
               variant_count=sum(len(x["plans"]) for x in groups),
               raw_preview=(json.dumps(raw, ensure_ascii=False)[:3500] if not groups else ""))
    set_setting("vsh_catalog", json.dumps(obj))
    return obj


def is_hour_plan(dur):
    """True for durations like '1 Hour', '2 Hours', '3hr', '6 h'."""
    return bool(re.search(r"\d\s*(hours?|hrs?|h)\b", (dur or "").lower()))


def parse_hours(text):
    """Number of hours if the duration is an hour plan ('1 Hour', '3hr', '6 h'), else 0."""
    m = re.search(r"(\d+)\s*(hours?|hrs?|h)\b", (text or "").lower())
    return int(m.group(1)) if m else 0


def parse_days(text):
    s = (text or "").lower()
    if "life" in s:
        return 3650
    m = re.search(r"(\d+)\s*(hour|hr|h\b|day|d\b|week|w\b|month|mo|year|yr|y\b)?", s)
    if not m:
        return 1
    n, u = int(m.group(1)), (m.group(2) or "day")
    if u.startswith("h"):
        return max(1, -(-n // 24))
    if u.startswith("w"):
        return max(1, n * 7)
    if u.startswith("mo"):
        return max(1, n * 30)
    if u.startswith("y"):
        return max(1, n * 365)
    return max(1, n)


def duration_parts(label, raw=None):
    """Return (days, hours, display_name), preserving hour-based provider plans."""
    raw = raw if isinstance(raw, dict) else {}
    text = str(label or "").strip()
    unit = str(raw.get("duration_unit") or raw.get("validity_unit") or raw.get("unit") or raw.get("period_unit") or "").lower()
    explicit_hours = raw.get("duration_hours", raw.get("validity_hours", raw.get("hours")))
    explicit_days = raw.get("duration_days", raw.get("validity_days", raw.get("days")))
    hours = parse_hours(text)
    if not hours and explicit_hours not in (None, ""):
        try: hours = max(0, int(float(explicit_hours)))
        except (TypeError, ValueError): pass
    if not hours and unit in ("hour", "hours", "hr", "hrs", "h"):
        value = raw.get("duration", raw.get("validity", raw.get("duration_value", raw.get("period", ""))))
        try: hours = max(0, int(float(value)))
        except (TypeError, ValueError): hours = parse_days(str(value))
    if hours > 0:
        return max(1, -(-hours // 24)), hours, (text if is_hour_plan(text) else plan_label(1, hours))
    days = 0
    if explicit_days not in (None, ""):
        try: days = max(1, int(float(explicit_days)))
        except (TypeError, ValueError): pass
    if not days: days = parse_days(text)
    if not text or text.isdigit():
        text = plan_label(days, 0)
    return days, 0, text


def _extract_vsh_key(payload):
    """Extract a generated key from common VIP Seller Hub response envelopes."""
    key_names = ("key", "license_key", "license", "generated_key", "access_key", "code")
    def walk(node, depth=0):
        if depth > 6:
            return None
        if isinstance(node, dict):
            for k in key_names:
                value = node.get(k)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for k in ("keys", "data", "result", "order", "response", "items"):
                if k in node:
                    found = walk(node[k], depth + 1)
                    if found:
                        return found
        elif isinstance(node, list):
            for item in node:
                found = walk(item, depth + 1)
                if found:
                    return found
        elif isinstance(node, str) and node.strip():
            return node.strip()
        return None
    return walk(payload)


def vsh_generate_key(variant_id, idem, meta=""):
    """Purchase exactly one VIP Seller Hub variant; never retry an ambiguous POST."""
    try:
        details = json.loads(meta) if meta else {}
    except (ValueError, TypeError):
        details = {}
    mode = str(details.get("mode") or "").lower()
    if mode == "v1":
        raise ValueError("This VIP Seller Hub variant requires the buyer's Android ID; this checkout does not collect it yet.")
    body = {"variant_id": str(variant_id), "quantity": 1}
    if mode == "both":
        body["api_version"] = "v2"
    try:
        raw = vsh_call("generate_key.php", body, "POST")
    except ProvUnknown:
        raise
    except requests.Timeout:
        raise ProvUnknown("VIP Seller Hub timed out after the purchase request; contact admin before retrying.")
    key = _extract_vsh_key(raw)
    if not key:
        raise ValueError("VIP Seller Hub did not return a key. Raw response: %s" %
                         json.dumps(raw, ensure_ascii=False)[:180])
    return key


def next_prod_pos():
    r = q("SELECT MAX(MAX(pos), MAX(id)) FROM products", one=True)
    return int(r[0] or 0) + 1


def renumber_products(ids):
    c = db()
    try:
        c.executemany("UPDATE products SET pos=? WHERE id=?", [(n, pid) for n, pid in enumerate(ids, 1)])
        c.commit()
    finally:
        c.close()


def catalog(rid):
    """v18: built with 4 queries in total (was 2-3 queries PER PLAN -> very slow with 100 products)."""
    out = []
    user = role_of(rid) == "user"
    en = {"tahir": api_enabled("tahir"), "vsh": api_enabled("vsh")}
    stock = {r[0]: r[1] for r in q("SELECT plan_id, COUNT(*) FROM stock WHERE used=0 GROUP BY plan_id")}
    custom = {} if user else {r[0]: r[1] for r in q("SELECT plan_id, price FROM custom_prices WHERE reseller_id=?", (rid,))}
    by_prod = {}
    for pl in q("SELECT * FROM plans ORDER BY (CASE WHEN hours>0 THEN hours*3600 ELSE days*86400 END), id"):
        by_prod.setdefault(pl["product_id"], []).append(pl)
    for p in q("SELECT * FROM products WHERE COALESCE(hidden,0)=0 ORDER BY (CASE WHEN pos>0 THEN pos ELSE id END), id"):
        plans = []
        for pl in by_prod.get(p["id"], []):
            src = (pl["prov_src"] or "").lower()
            if pl["mode"] == "provider" and (src not in ("tahir", "vsh") or not en.get(src, True)):
                continue
            if user:
                price, cst = user_price_of(pl), False
            elif pl["id"] in custom:
                price, cst = custom[pl["id"]], True
            else:
                price, cst = pl["price"], False
            plans.append(dict(id=pl["id"], name=pl["name"], days=pl["days"], hours=pl["hours"] or 0, price=price, custom=cst,
                              mode=pl["mode"] or "random", stock=stock.get(pl["id"], 0),
                              provider=""))  # provider name is hidden from customers
        icon = ("/picon/%d?v=%d" % (p["id"], p["icon_ver"] or 0)) if p["icon"] else ("/emoji/" + p["emoji_id"] if p["emoji_id"] else "")
        out.append(dict(id=p["id"], name=p["name"], plans=plans, icon=icon))
    return out


def _dig(obj, path):
    for part in [p for p in path.split(".") if p]:
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def fetch_external(pl):
    """Call the provider API configured on the plan and return the key text."""
    import requests
    rep = {"{days}": str(pl["days"]), "{hours}": str(pl["hours"] or 0), "{plan}": pl["name"], "{product}": pl["pname"]}

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
        pl = c.execute("SELECT pl.*, pr.name pname, COALESCE(pr.hidden,0) product_hidden "
                       "FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=?",
                       (plan_id,)).fetchone()
        if not r or not r["active"]:
            raise ValueError("Account disabled")
        if not pl:
            raise ValueError("Plan not found")
        # Enforce visibility at purchase time too: a reseller bot may still
        # hold an old/cached plan_id after the product has been hidden.
        if int(pl["product_hidden"] or 0):
            raise ValueError("This product is hidden by the administrator and cannot be purchased.")
        if (r["role"] or "reseller") == "user":
            price = user_price_of(pl)
        else:
            cp = c.execute("SELECT price FROM custom_prices WHERE reseller_id=? AND plan_id=?", (rid, plan_id)).fetchone()
            price = cp["price"] if cp else pl["price"]
        if r["balance"] < price:
            raise ValueError("Insufficient balance")
        now = int(time.time())
        mode, key = (pl["mode"] or "random"), None
        provider_src = (pl["prov_src"] or "").lower()
        if mode == "provider":
            if not pl["prov_pid"] or provider_src not in ("tahir", "vsh"):
                raise ValueError("This plan is not linked to a supported API. Re-import it from the provider.")
            if not api_enabled(provider_src):
                raise ValueError("%s API is currently OFF. Please choose another provider plan." %
                                 ("VIP Seller Hub" if provider_src == "vsh" else "Tahir"))
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
        exp = now + plan_secs(pl)
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
    if mode in ("api", "provider"):  # balance already reserved; refund if the provider fails
        try:
            if mode == "provider":
                idem = "rs-%s-%s-%s-%s" % (rid, plan_id, now, secrets.token_hex(4))
                if provider_src == "vsh":
                    key = vsh_generate_key(pl["prov_pid"], idem, pl["prov_meta"] or "")
                else:
                    key = prov_generate(pl["prov_pid"], idem)
            else:
                key = fetch_external(pl)
        except ProvUnknown as e:      # request may have gone through -> do NOT refund automatically
            c.close()
            raise ValueError("%s. Your balance was NOT refunded automatically because the key may still be created - please contact admin." % e)
        except Exception as e:
            c.execute("UPDATE resellers SET balance=balance+? WHERE id=?", (price, rid))
            c.close()
            raise ValueError("Provider error, balance refunded: %s" % str(e)[:120])
        c.execute("INSERT INTO license_keys(reseller_id,product_name,plan_name,key,price,created,expires,via) "
                  "VALUES(?,?,?,?,?,?,?,?)", (rid, pl["pname"], pl["name"], key, price, now, exp, via))
    c.close()
    bal = q("SELECT balance FROM resellers WHERE id=?", (rid,), one=True)["balance"]
    try:
        notify_purchase(r, pl, price, bal, key, via)
    except Exception:
        pass
    return dict(key=key, price=price, expires=exp, balance=bal, product=pl["pname"], plan=pl["name"])


# ---- payment gateway (FamPay style: /api/create_order.php + /api/verify.php)
DEFAULT_AMOUNTS = [200, 500, 1000, 1500, 2000, 2500]   # used until the admin sets his own list (Admin > Gateway)


def wallet_amounts():
    out = []
    for x in re.split(r"[,\s]+", get_setting("wallet_amounts", "")):
        if x.isdigit() and 1 <= int(x) <= 100000 and int(x) not in out:
            out.append(int(x))
    return out[:12] or list(DEFAULT_AMOUNTS)
DEFAULT_GW_BASE = "https://fampaygateway.site"


def gw_base():
    return (get_setting("gw_base") or DEFAULT_GW_BASE).rstrip("/")


def gw_abs(u):
    u = str(u or "")
    return gw_base() + u if u.startswith("/") else u


def gw_get(path, **params):
    key = get_setting("gw_key")
    if not key:
        raise ValueError("Payment gateway is not set up (Admin > Gateway)")
    params["api_key"] = key
    r = requests.get(gw_base() + path, params=params, timeout=20)
    try:
        return r.json()
    except ValueError:
        raise ValueError("Gateway HTTP %s (not JSON)" % r.status_code)


def gw_create(amount):
    j = gw_get("/api/create_order.php", amount=int(amount))
    d = j.get("data") if isinstance(j, dict) else None
    if not isinstance(j, dict) or j.get("status") != "success" or not isinstance(d, dict) \
            or not d.get("order_id") or not d.get("qr_url"):
        msg = (j.get("message") or j.get("error") or "Gateway error") if isinstance(j, dict) else "Gateway error"
        raise ValueError(str(msg)[:120])
    return d


def gw_verify(order_id):
    """Returns the payment data dict only when the gateway confirms a paid order (has a UTR)."""
    try:
        j = gw_get("/api/verify.php", order_id=order_id)
    except Exception:
        return None
    d = j.get("data") if isinstance(j, dict) else None
    if isinstance(j, dict) and j.get("status") == "success" and isinstance(d, dict) and d.get("utr"):
        return d
    return None


# ---- PAYTM gateway = ZYVO PAY API (signed JSON requests, https://zyvopay.site/api)
ZY_DEFAULT_BASE = "https://zyvopay.site/api"
_HTTP = requests.Session()


def zy_conf():
    key = (get_setting("zy_key") or os.environ.get("ZYVOPAY_API_KEY") or "").strip()
    wh = (get_setting("zy_whsec") or os.environ.get("ZYVOPAY_WEBHOOK_SECRET") or "").strip()
    base = (get_setting("zy_base") or os.environ.get("ZYVOPAY_BASE_URL") or ZY_DEFAULT_BASE).strip().rstrip("/")
    return key, wh, base


def zy_ready():
    key = zy_conf()[0]
    return "." in key and len(key.split(".", 1)[1]) > 0


def gw_active():
    return "pgw"                                        # the old Fampay / Paytm gateways are replaced by MY payment gateway


def gw_is_ready():
    return pg_ready()


class ZyError(Exception):
    pass


ZY_MSG = {400: "Payment request was rejected (bad data).", 401: "Paytm gateway key is wrong (Admin > Gateway).",
          402: "Paytm gateway account has no balance/plan.", 404: "Payment not found.", 405: "Gateway method not allowed.",
          409: "This payment already exists.", 422: "Payment data is not valid.", 429: "Too many requests. Try again in a minute."}


def zy_call(path, body=None, method="POST"):
    """Signed call. The JSON is serialized ONCE and exactly those bytes are signed: HMAC-SHA256(secret, timestamp + '.' + body)."""
    key, _, base = zy_conf()
    if "." not in key:
        raise ZyError("Paytm gateway is not set up (Admin > Gateway)")
    secret = key.split(".", 1)[1]                      # only the secret part signs; the full key goes in X-API-Key
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8") if method == "POST" else b""
    last = None
    for attempt in range(3):                            # retries ONLY for network errors / 5xx
        ts = str(int(time.time()))
        sig = hmac.new(secret.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
        hdr = {"Content-Type": "application/json", "X-API-Key": key, "X-Timestamp": ts, "X-Signature": sig}
        try:
            r = _HTTP.request(method, base + path, data=raw if method == "POST" else None, headers=hdr, timeout=(4, 10))
        except requests.RequestException as e:
            last = ZyError("Paytm gateway is not reachable. Please try again.")
            print("[zyvo] network error %s %s" % (path, type(e).__name__))
            time.sleep(0.6 * (attempt + 1))
            continue
        if r.status_code >= 500:
            last = ZyError("Paytm gateway is busy. Please try again.")
            print("[zyvo] %s %s -> %s req-id=%s" % (method, path, r.status_code, r.headers.get("X-Request-Id", "-")))
            time.sleep(0.6 * (attempt + 1))
            continue
        try:
            j = r.json()
        except ValueError:
            raise ZyError("Paytm gateway sent an unreadable answer (HTTP %s)" % r.status_code)
        if r.status_code >= 400:
            detail = ""
            if isinstance(j, dict):
                detail = str(j.get("message") or j.get("error") or "")[:120]
            print("[zyvo] %s %s -> %s req-id=%s %s" % (method, path, r.status_code, r.headers.get("X-Request-Id", "-"), detail))
            raise ZyError((ZY_MSG.get(r.status_code) or "Paytm gateway error %s." % r.status_code) + ((" (%s)" % detail) if detail else ""))
        d = j.get("data") if isinstance(j, dict) and isinstance(j.get("data"), dict) else j
        if not isinstance(d, dict):
            raise ZyError("Paytm gateway answer has no data")
        return d
    raise last or ZyError("Paytm gateway error")


def parse_exp(v):
    if isinstance(v, (int, float)) and v > 0:
        return int(v / 1000) if v > 1e11 else int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return parse_exp(int(v.strip()))
    return parse_iso(v)


def zy_create(order_id, amount):
    amt = int(amount) if float(amount) == int(amount) else round(float(amount), 2)
    d = zy_call("/create-payment.php", {"order_id": order_id, "amount": amt, "currency": "INR"})
    ref = str(d.get("reference") or "")
    if not ref:
        raise ZyError("Paytm gateway did not return a payment reference")
    return dict(ref=ref, pay_uri=str(d.get("payment_uri") or ""), qr_url=str(d.get("qr_image_url") or ""),
                app_pay=1 if d.get("app_payment_available") else 0, checkout=str(d.get("checkout_url") or ""),
                exp=parse_exp(d.get("expires_at") or d.get("expiry") or d.get("expires")), status=str(d.get("status") or "pending"))


def zy_check(t):
    """Signed status check. Returns {'utr','amount'} ONLY if status is 'successful' and reference / order / currency / amount all match."""
    try:
        d = zy_call("/check-payment.php", {"reference": t["ref"], "order_id": t["order_id"]})
    except ZyError:
        return None
    st = str(d.get("status") or "").lower()
    if st in ("failed", "expired") and t["status"] == "pending":
        q("UPDATE topups SET status='expired' WHERE id=? AND status='pending'", (t["id"],), commit=True)
    if st != "successful":
        return None
    if str(d.get("reference") or t["ref"]) != t["ref"] or str(d.get("order_id") or t["order_id"]) != t["order_id"]:
        return None
    if str(d.get("currency") or "INR").upper() != "INR":
        return None
    try:
        if abs(float(d.get("amount")) - float(t["amount"])) > 0.001:
            return None
    except (TypeError, ValueError):
        return None
    return {"utr": "ZY:" + t["ref"], "amount": t["amount"]}


def qr_matrix(data):
    import qrcode
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()


def qr_svg(data):
    """Simple black-on-white QR (same look for both gateways), made locally from the exact payment_uri: instant, nothing is sent anywhere."""
    m = qr_matrix(data)
    n = len(m)
    path = []
    for y, row in enumerate(m):
        x = 0
        while x < n:
            if row[x]:
                x0 = x
                while x < n and row[x]:
                    x += 1
                path.append("M%d %dh%dv1h-%dz" % (x0, y, x - x0, x - x0))
            else:
                x += 1
    return Markup('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" shape-rendering="crispEdges" role="img" aria-label="UPI QR">'
                  '<rect width="%d" height="%d" fill="#fff"/><path d="%s" fill="#000"/></svg>' % (n, n, n, n, "".join(path)))


def qr_png(data):
    from PIL import Image
    import io
    m = qr_matrix(data)
    n, k = len(m), 12
    im = Image.new("L", (n * k, n * k), 255)
    px = im.load()
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                for dy in range(k):
                    for dx in range(k):
                        px[x * k + dx, y * k + dy] = 0
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def safe_svg(uri):
    try:
        return qr_svg(uri) if uri else None
    except Exception as e:
        print("[qr] %s" % e)
        return None


def parse_iso(v):
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(str(v)).timestamp())
    except Exception:
        return 0


# ---- MY PAYMENT GATEWAY  (POST /api/v1/payment/create, POST /api/v1/payment/verify, X-API-Key)
PG_DEFAULT_BASE = "https://paymentgateway-0km8.onrender.com"


class PgError(Exception):
    pass


def pg_norm_base(u):
    """Keeps only scheme + host of a pasted link (https://xxxx.onrender.com). Returns '' if it is not a web address."""
    from urllib.parse import urlsplit
    u = (u or "").strip()
    if u and "://" not in u:
        u = "https://" + u
    sp = urlsplit(u)
    if sp.scheme not in ("http", "https") or not sp.netloc or " " in sp.netloc:
        return ""
    return "%s://%s" % (sp.scheme, sp.netloc)


def pg_conf():
    base = pg_norm_base(get_setting("pg_base") or os.environ.get("PG_BASE_URL") or "") or PG_DEFAULT_BASE
    key = (get_setting("pg_key") or os.environ.get("PG_API_KEY") or "").strip()
    gw = get_setting("pg_gw", "paytm")
    return base, key, (gw if gw in ("paytm", "fampay") else "paytm"), (get_setting("pg_secret") or "").strip()


def pg_ready():
    return bool(pg_conf()[1])


PG_MSG = {400: "Gateway is not set up on your gateway site (or bad data).", 401: "API key is wrong.",
          403: "Your gateway plan does not include this gateway / limit reached / account suspended.",
          404: "Payment not found.", 429: "Too many requests. Try again in a minute.", 502: "Gateway could not reach the provider. Try again."}


def pg_call(method, path, body=None):
    base, key, _, _ = pg_conf()
    if not key:
        raise PgError("Payment gateway is not set up (Admin > Gateway)")
    hdr = {"X-API-Key": key, "Content-Type": "application/json", "Accept": "application/json"}
    last = None
    for attempt in range(3):                             # retries ONLY for network errors / 5xx (a sleeping Render site needs time)
        try:
            r = _HTTP.request(method, base + path, json=body if method == "POST" else None, headers=hdr, timeout=(6, 40))
        except requests.RequestException as e:
            last = PgError("Gateway is not reachable. Check the Base URL in Admin > Gateway (it changes when you redeploy the gateway).")
            print("[pg] network error %s %s" % (path, type(e).__name__))
            time.sleep(1.0 * (attempt + 1))
            continue
        if r.status_code >= 500 and r.status_code != 502:
            last = PgError("Gateway is busy. Please try again.")
            time.sleep(1.0 * (attempt + 1))
            continue
        try:
            j = r.json()
        except ValueError:
            raise PgError("Gateway sent an unreadable answer (HTTP %s). Is the Base URL correct?" % r.status_code)
        if r.status_code >= 400 or (isinstance(j, dict) and j.get("success") is False):
            detail = str(j.get("error") or j.get("message") or "")[:140] if isinstance(j, dict) else ""
            raise PgError(detail or PG_MSG.get(r.status_code) or "Gateway error %s." % r.status_code)
        if not isinstance(j, dict):
            raise PgError("Gateway answer has no data")
        return j
    raise last or PgError("Gateway error")


def pg_exp(v):
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def pg_create(order_id, amount):
    gw = pg_conf()[2]
    amt = int(amount) if float(amount) == int(amount) else round(float(amount), 2)
    j = pg_call("POST", "/api/v1/payment/create", {"amount": amt, "order_id": order_id, "gateway": gw})
    d = j.get("data") if isinstance(j.get("data"), dict) else j
    ref = str(d.get("pay_id") or "")
    if not ref:
        raise PgError("Gateway did not return a payment id")
    uri = str(d.get("upi_uri") or "")
    try:
        pay_amt = float(d.get("amount") or amt)               # FamPay may add paise: the customer MUST pay this exact amount
    except (TypeError, ValueError):
        pay_amt = float(amt)
    return dict(ref=ref, pay_uri=uri, qr_url=str(d.get("qr_png_url") or d.get("qr_url") or ""), app_pay=1 if uri.lower().startswith("upi:") else 0,
                checkout=str(d.get("payment_url") or ""), exp=pg_exp(d.get("expires_at")), pay_amount=pay_amt)


def pg_check(t):
    """Returns {'utr','amount'} ONLY when the gateway says SUCCESS and order id + amount match."""
    try:
        j = pg_call("POST", "/api/v1/payment/verify", {"order_id": t["order_id"]})
    except PgError:
        return None
    d = j.get("data") if isinstance(j.get("data"), dict) else j
    st = str(d.get("status") or j.get("status") or "").upper()
    if st in ("FAILED", "EXPIRED") and t["status"] == "pending":
        q("UPDATE topups SET status='expired' WHERE id=? AND status='pending'", (t["id"],), commit=True)
    if st != "SUCCESS":
        return None
    got = str(d.get("order_id") or t["order_id"])
    if got not in (t["order_id"], t["ref"]) or str(d.get("pay_id") or t["ref"]) != t["ref"]:
        return None
    want = float(t["pay_amount"] or t["amount"])
    try:
        if d.get("amount") is not None and abs(float(d.get("amount")) - want) > 0.001:
            return None
    except (TypeError, ValueError):
        return None
    tx = str(d.get("transaction_id") or d.get("utr") or "").strip()
    return {"utr": tx or ("PG:" + t["ref"]), "amount": t["amount"]}


def credit_topup(tid, d):
    """Add the money exactly once (safe even if several workers verify the same order)."""
    c = sqlite3.connect(DB, timeout=20, isolation_level=None)
    c.row_factory = sqlite3.Row
    try:
        c.execute("BEGIN IMMEDIATE")
        t = c.execute("SELECT * FROM topups WHERE id=?", (tid,)).fetchone()
        utr = str(d.get("utr"))
        done = (not t or t["status"] == "paid"
                or c.execute("SELECT 1 FROM topups WHERE utr=? AND id!=?", (utr, tid)).fetchone())
        try:
            paid_amt = float(d.get("amount") or t["amount"])
        except Exception:
            paid_amt = t["amount"] if t else 0
        if done or paid_amt + 0.001 < t["amount"]:
            c.execute("COMMIT")
            return False
        c.execute("UPDATE topups SET status='paid', utr=?, paid_at=? WHERE id=?", (utr, int(time.time()), tid))
        upgrade = t["purpose"] == "upgrade"
        if upgrade:                                         # paid "Full Reseller Upgrade": the account becomes a reseller, no balance is added
            c.execute("UPDATE resellers SET role='reseller', otp_on=1 WHERE id=? AND role='user'", (t["reseller_id"],))
            c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", ("upg_%d" % t["reseller_id"], "1"))
            _SET_CACHE.clear()
        else:
            c.execute("UPDATE resellers SET balance=balance+? WHERE id=?", (t["amount"], t["reseller_id"]))
        c.execute("COMMIT")
        try:
            rr = c.execute("SELECT * FROM resellers WHERE id=?", (t["reseller_id"],)).fetchone()
            if upgrade:
                notify_upgrade(rr, t["amount"])
            else:
                notify_topup(rr, t["amount"])
        except Exception:
            pass
        return True
    except Exception:
        try:
            c.execute("ROLLBACK")
        except Exception:
            pass
        return False
    finally:
        c.close()


# ---- v17.10: BINANCE PAY (USDT) - automatic 24/7 verification. Money is credited ONLY after a signed "Query Order" says PAID.
BN_BASE = "https://bpay.binanceapi.com"


def bn_conf():
    key = (get_setting("bn_key") or os.environ.get("BINANCE_PAY_KEY") or "").strip()
    sec = (get_setting("bn_secret") or os.environ.get("BINANCE_PAY_SECRET") or "").strip()
    try:
        rate = float(get_setting("bn_rate", "0") or 0)
    except ValueError:
        rate = 0.0
    return key, sec, rate


def bn_ready():
    key, sec, rate = bn_conf()
    return get_setting("bn_on", "0") == "1" and bool(key and sec) and rate > 0


class BnError(Exception):
    pass


def bn_call(path, body):
    key, sec, _ = bn_conf()
    if not key or not sec:
        raise BnError("Binance Pay is not set up (Admin > Gateway)")
    ts = str(int(time.time() * 1000))
    nonce = "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789") for _ in range(32))
    raw = json.dumps(body, separators=(",", ":"))
    sig = hmac.new(sec.encode(), (ts + "\n" + nonce + "\n" + raw + "\n").encode(), hashlib.sha512).hexdigest().upper()
    try:
        r = _HTTP.post(BN_BASE + path, data=raw.encode(), timeout=20, headers={
            "Content-Type": "application/json", "BinancePay-Timestamp": ts, "BinancePay-Nonce": nonce,
            "BinancePay-Certificate-SN": key, "BinancePay-Signature": sig})
        j = r.json()
    except ValueError:
        raise BnError("Binance HTTP %s (not JSON)" % r.status_code)
    except requests.RequestException as e:
        raise BnError("Could not reach Binance: %s" % str(e)[:80])
    if not isinstance(j, dict) or j.get("status") != "SUCCESS":
        msg = (j.get("errorMessage") or j.get("code") or "error") if isinstance(j, dict) else "error"
        raise BnError("Binance: %s (code %s)" % (str(msg)[:100], j.get("code") if isinstance(j, dict) else "?"))
    return j.get("data") or {}


def bn_usdt(inr):
    """Rupee amount -> USDT to pay (rounded UP to cents). Rate = Rs per 1 USDT, set by the admin."""
    rate = bn_conf()[2]
    return max(math.ceil(float(inr) / rate * 100 - 1e-9) / 100.0, 0.01)


def bn_create(order_id, usdt):
    body = {"env": {"terminalType": "WEB"}, "merchantTradeNo": order_id, "orderAmount": round(float(usdt), 2), "currency": "USDT",
            "goods": {"goodsType": "02", "goodsCategory": "6000", "referenceGoodsId": "wallet", "goodsName": "Wallet balance"},
            "webhookUrl": request.host_url.rstrip("/").replace("http://", "https://", 1) + "/bnpay/webhook"}
    d = bn_call("/binancepay/openapi/v2/order", body)
    if not d.get("prepayId"):
        raise BnError("Binance did not return an order id")
    return dict(ref=str(d["prepayId"]), pay_uri=str(d.get("qrContent") or ""), qr_url=str(d.get("qrcodeLink") or ""),
                checkout=str(d.get("checkoutUrl") or d.get("universalUrl") or ""), pay_amount=float(usdt))


def bn_check(t):
    """{'utr','amount'} ONLY when Binance says PAID, currency is USDT and the paid amount covers the order."""
    try:
        d = bn_call("/binancepay/openapi/v2/order/query", {"merchantTradeNo": t["order_id"]})
    except BnError:
        return None
    st = str(d.get("status") or "").upper()
    if st in ("EXPIRED", "CANCELED", "ERROR") and t["status"] == "pending":
        q("UPDATE topups SET status='expired' WHERE id=? AND status='pending'", (t["id"],), commit=True)
    if st != "PAID" or str(d.get("merchantTradeNo") or t["order_id"]) != t["order_id"]:
        return None
    try:
        if str(d.get("currency") or "USDT").upper() != "USDT" or float(d.get("orderAmount")) + 0.0001 < float(t["pay_amount"]):
            return None
    except (TypeError, ValueError):
        return None
    tx = str(d.get("transactionId") or d.get("prepayId") or t["ref"]).strip()
    return {"utr": "BN:" + tx, "amount": t["amount"]}


@app.route("/bnpay/webhook", methods=["POST"])
def bn_webhook():
    """Binance calls this the moment a customer pays. Nothing in the body is trusted: the order is re-checked with a SIGNED query."""
    ip = request.remote_addr or "?"
    if rl_blocked("bnwh:" + ip, 120, 600):
        return jsonify(returnCode="FAIL", returnMessage="rate limit"), 429
    rl_hit("bnwh:" + ip)
    try:
        j = json.loads(request.get_data().decode("utf-8"))
        data = j.get("data")
        data = json.loads(data) if isinstance(data, str) else (data or {})
        oid = re.sub(r"[^A-Za-z0-9]", "", str(data.get("merchantTradeNo") or ""))[:40]
    except Exception:
        return jsonify(returnCode="SUCCESS", returnMessage=None)
    if oid:
        t = q("SELECT * FROM topups WHERE provider='binance' AND order_id=?", (oid,), one=True)
        if t:
            threading.Thread(target=check_topup, args=(t,), daemon=True, name="bn-webhook").start()
    return jsonify(returnCode="SUCCESS", returnMessage=None)


def check_topup(t):
    """Verify one top-up with the gateway; returns its status (pending / paid / expired)."""
    if t["status"] == "paid":
        return "paid"
    now = int(time.time())
    if t["status"] == "pending" and now > t["deadline"]:
        q("UPDATE topups SET status='expired' WHERE id=? AND status='pending'", (t["id"],), commit=True)
    elif t["status"] == "expired" and now - t["created"] > 3600:
        return "expired"
    if t["provider"] in ("zyvo", "pgw", "binance") and not t["ref"]:
        return t["status"]
    q("UPDATE topups SET last_check=? WHERE id=?", (now, t["id"]), commit=True)
    d = bn_check(t) if t["provider"] == "binance" else pg_check(t) if t["provider"] == "pgw" else (zy_check(t) if t["provider"] == "zyvo" else gw_verify(t["order_id"]))
    if d and credit_topup(t["id"], d):
        return "paid"
    return q("SELECT status FROM topups WHERE id=?", (t["id"],), one=True)["status"]


def topup_worker():
    """Keeps verifying pending payments for 5 minutes even if the customer left the page."""
    while True:
        try:
            now = int(time.time())
            for t in q("SELECT * FROM topups WHERE status='pending'"):
                if now > t["deadline"]:
                    q("UPDATE topups SET status='expired' WHERE id=? AND status='pending'", (t["id"],), commit=True)
                elif now - (t["last_check"] or 0) >= 5:
                    check_topup(t)
        except Exception:
            pass
        time.sleep(4)


@app.context_processor
def inject_unread():
    rid = session.get("rid")
    if not rid:
        return {}
    n = q("SELECT COUNT(*) FROM broadcasts b WHERE (b.reseller_id IS NULL OR b.reseller_id=?) "
          "AND b.created>=(SELECT created FROM resellers WHERE id=?) "
          "AND NOT EXISTS(SELECT 1 FROM broadcast_reads x WHERE x.broadcast_id=b.id AND x.reseller_id=?)",
          (rid, rid, rid), one=True)[0]
    return dict(unread=n)


def reseller_required(f):
    from functools import wraps

    @wraps(f)
    def w(*a, **k):
        if not session.get("rid"):
            return redirect("/login")
        r = q("SELECT * FROM resellers WHERE id=?", (session["rid"],), one=True)
        if not r or not r["active"] or r["deleted"]:
            session.clear()
            return redirect("/login")
        if session.get("pwh") and session["pwh"] != pw_fp(r):     # password was changed elsewhere
            session.clear()
            return redirect("/login")
        if r["role"] != "user" and dev_check_on() and not device_ok(r["id"]):      # devices are for resellers only
            if get_setting("upg_%d" % r["id"]) == "1" and re.fullmatch(r"[0-9a-f]{32}", request.cookies.get("rgd", "")):
                set_setting("upg_%d" % r["id"], "0")          # just upgraded: this logged-in browser becomes his first approved device
                q("INSERT INTO devices(reseller_id,dev_id,label,ip,status,created,decided,last_seen) VALUES(?,?,?,?,?,?,?,?)",
                  (r["id"], request.cookies["rgd"], ua_label(request.headers.get("User-Agent", "")), request.remote_addr,
                   "approved", int(time.time()), int(time.time()), int(time.time())), commit=True)
            else:
                session.clear()
                return blocked_page()
        if (r["role"] == "user" and not (r["tg_chat"] or "").strip() and link_required()
                and not request.path.startswith(LINK_OK)):          # users must link Telegram first (website -> bot)
            return redirect("/link-telegram")
        request.r = r
        return f(*a, **k)
    return w


def reseller_only(f):
    """Same as reseller_required, but normal USER accounts are sent back to their dashboard."""
    from functools import wraps

    @wraps(f)
    @reseller_required
    def w(*a, **k):
        if request.r["role"] == "user":
            return redirect("/dashboard")
        return f(*a, **k)
    return w


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def w(*a, **k):
        if not session.get("admin") or time.time() - session.get("admin_ts", 0) > ADMIN_TTL:
            session.pop("admin", None)                    # keep a half-finished login (adm_pre) alive
            session.pop("admin_ts", None)
            return redirect("/admin/wait" if admin_pre() else "/admin/login")
        return f(*a, **k)
    return w


def num(v, default=0.0):
    try:
        return float(str(v).strip())
    except Exception:
        return default


# ---------------------------------------------------------------- telegram + security helpers
def tg_token():
    """Panel (Admin > Telegram) wins. Render env var TG_BOT_TOKEN is only the fallback (e.g. after a free-disk wipe)."""
    return (get_setting("tg_token") or os.environ.get("TG_BOT_TOKEN") or TG_BOT_TOKEN or "").strip()


def tg_token_source():
    if get_setting("tg_token"):
        return "panel"
    return "env" if (os.environ.get("TG_BOT_TOKEN") or TG_BOT_TOKEN) else ""


def tg_admin():
    return str(get_setting("tg_admin") or os.environ.get("ADMIN_TG_ID") or TG_ADMIN_ID or "").strip()


def emoji_overrides():
    """{plain emoji: custom_emoji_id} picked in Admin > Telegram > Premium emoji picker."""
    try:
        d = json.loads(get_setting("emoji_map", "{}") or "{}")
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


# every emoji the bot uses in its messages (the picker lets you choose a premium emoji for each one)
EMOJI_ROLES = [("\u2705", "Done / Product"), ("\u274C", "Reject / Error"), ("\U0001F6D2", "Quantity"),
               ("\U0001F4B0", "Balance"), ("\U0001F4B8", "Paid / Amount"),
               ("\u23F1", "Validity"), ("\U0001F552", "Time"), ("\U0001F6AB", "Paid by / Warning"),
               ("\U0001F511", "Key"), ("\U0001F464", "Reseller"), ("\U0001F4F1", "Device"),
               ("\U0001F310", "IP"), ("\U0001F514", "Notification"), ("\U0001F513", "Login"),
               ("\U0001F510", "Login code"), ("\U0001F6A8", "Low balance"), ("\U0001F4B3", "Method"),
               ("\U0001F44B", "Welcome")]


_CLAIMS = []


def claim_admin(chat_id, secret):
    """Bot command '/admin <admin password>' makes that Telegram chat the admin (device requests go there)."""
    now = time.time()
    _CLAIMS[:] = [t for t in _CLAIMS if now - t < 600]
    if len(_CLAIMS) >= 5 or get_setting("adm_linked") == "1":      # after the first verified login the chat ID can only be changed inside the panel (with a code)
        return False
    if same(secret.strip(), ADMIN_PASS):
        set_setting("tg_admin", str(chat_id))
        return True
    _CLAIMS.append(now)
    return False


def dev_check_on():
    """Device approval is active only when the admin has set his Telegram ID (so nobody can get locked out)."""
    return get_setting("dev_check", "1") == "1" and bool(tg_admin()) and bool(tg_token())


def esc(v):
    return _html.escape(str(v if v is not None else ""))


def money_txt(v):
    return CURRENCY + app.jinja_env.filters["money"](v)


def device_decision(did, approve):
    if did < 0:                                           # ADMIN device (callback id is -row id)
        row = q("SELECT * FROM adm_devices WHERE id=?", (-did,), one=True)
        if not row:
            return "Request not found"
        q("UPDATE adm_devices SET status=?, decided=? WHERE id=?", ("approved" if approve else "denied", int(time.time()), -did), commit=True)
        return "Approved: admin device" if approve else "Rejected: admin device"
    d = q("SELECT d.*, r.username FROM devices d JOIN resellers r ON r.id=d.reseller_id WHERE d.id=?", (did,), one=True)
    if not d:
        return "Request not found"
    q("UPDATE devices SET status=?, decided=? WHERE id=?", ("approved" if approve else "denied", int(time.time()), did),
      commit=True)
    return ("Approved: " if approve else "Rejected: ") + d["username"]


def tg_seen(chat_id, name, username):
    """Remember everybody who pressed /start in the bot, so the admin can link them with one click."""
    q("INSERT OR REPLACE INTO tg_seen(chat_id,name,username,ts) VALUES(?,?,?,?)",
      (str(chat_id), (name or "")[:60], (username or "")[:40], int(time.time())), commit=True)


def otp_global_on():
    """Master switch (Admin > Telegram). OFF = nobody needs a code (use it if the bot is not delivering yet)."""
    return get_setting("otp_global", "1") == "1"


def mask_id(tc):
    tc = str(tc or "")
    return ("•" * max(len(tc) - 4, 0) + tc[-4:]) if tc else ""


bot = tgbot.Bot(tg_token, tg_admin, device_decision, brand_name, claim_admin, tg_seen,
                packs=EMOJI_PACKS, prem_on=lambda: get_setting("prem_on", "1") == "1", get_overrides=emoji_overrides, on_link=None)


def ua_label(ua):
    ua = ua or ""
    os_ = next((n for k, n in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"),
                               ("Mac OS", "macOS"), ("Linux", "Linux")) if k in ua), "Unknown OS")
    br = next((n for k, n in (("Edg/", "Edge"), ("OPR/", "Opera"), ("SamsungBrowser", "Samsung Browser"),
                              ("Firefox", "Firefox"), ("Chrome", "Chrome"), ("Safari", "Safari")) if k in ua), "Browser")
    return "%s on %s" % (br, os_)


def inr(v):
    return "%s INR" % money_txt(v)


def purchase_text(pname, validity, price, bal, key, via, buyer=None):
    line = "\u2500" * 16
    extra = ("\n\U0001F464 Bought by: <b>%s</b>\n\U0001F4B0 Reseller Current Balance: <b>%s</b>\n"
             % (esc(buyer), inr(bal))) if buyer else "\n"
    return ("<blockquote>\u2705 <b>NEW PURCHASE ALERT</b></blockquote>\n%s\n"
            "\u2705 Product: <b>%s</b>\n\U0001F6D2 Quantity: 1\n\U0001F4B0 Wallet Balance: <b>%s</b>\n"
            "\u23F1 Validity: %s\n\U0001F4B8 Paid: <b>%s</b>\n\U0001F6AB Paid by: Wallet (%s)\n"
            "\U0001F552 Time: %s\n"
            "\U0001F511 Key Issued: <code>%s</code>%s%s"
            % (line, esc(pname), inr(bal), esc(validity), inr(price),
               "API" if via == "api" else "Panel", fmt(time.time()), esc(key), extra, line))


def low_text(bal, lim):
    line = "\u2500" * 16
    return ("<blockquote>\U0001F6A8 <b>LOW BALANCE ALERT</b></blockquote>\n%s\n"
            "\U0001F4B0 Wallet Balance: <b>%s</b>\n\U0001F6A8 Low balance limit: <b>%s</b>\n"
            "\U0001F4B0 Please add funds to your wallet to continue purchasing keys.\n%s"
            % (line, inr(bal), inr(lim), line))


def alerts_on(r):
    """True only when the admin turned alerts ON for this account AND a Telegram Chat ID is saved."""
    try:
        return bool(r["tg_alert"]) and bool((r["tg_chat"] or "").strip()) and r["notify"] != 0
    except (KeyError, IndexError, TypeError):
        return False


def low_limit(r):
    try:
        return 50 if r["low_bal"] is None else float(r["low_bal"])
    except (KeyError, IndexError, TypeError, ValueError):
        return 50


def notify_purchase(r, pl, price, bal, key, via):
    """Telegram 'NEW PURCHASE ALERT' (+ low balance alert) to the reseller. Never raises, never blocks.
    Every outcome (sent / skipped / error) is written to the delivery log (Admin > Telegram)."""
    who = r["username"]
    try:                                                # admin always gets a copy (+ who bought, current balance)
        adm = tg_admin()
        if adm:
            bot.send(adm, purchase_text(pl["pname"], validity_text(pl), price, bal, key, via, buyer=who),
                     what="admin purchase alert (%s)" % who)
    except Exception as e:
        bot._note(False, "-", "admin purchase alert (%s)" % who, "error: %s" % str(e)[:150])
    # v18: the reseller gets his own alert ONLY if the admin switched "Telegram alerts" ON for him (Admin > Resellers > Manage)
    try:
        if not alerts_on(r):
            return
        items = [(purchase_text(pl["pname"], validity_text(pl), price, bal, key, via, buyer=who), None)]
        lim = low_limit(r)
        if lim > 0 and bal < lim:                       # wallet is under the limit -> warn after every purchase
            items.append((low_text(bal, lim), None))
        bot.send_many(r["tg_chat"], items, what="purchase alert (%s)" % who)
    except Exception as e:
        import traceback
        traceback.print_exc()
        bot._note(False, "-", "purchase alert (%s)" % who, "error: %s" % str(e)[:150])


def notify_upgrade(r, amount):
    if not r:
        return
    try:
        if tg_admin():
            bot.send(tg_admin(), "<blockquote>\U0001F195 <b>FULL RESELLER UPGRADE</b></blockquote>\n\U0001F464 User: <b>%s</b> is now a RESELLER\n"
                                 "\U0001F4B8 Paid: <b>%s</b>\n\U0001F552 %s" % (esc(r["username"]), inr(amount), fmt(time.time())),
                     what="reseller upgrade (%s)" % r["username"])
    except Exception:
        pass


def notify_topup(r, amount, how="UPI (auto)"):
    """BALANCE ADDED: admin always gets a copy (who, how much, current balance); the reseller gets one too."""
    if not r:
        return
    who = r["username"]
    line = "\u2500" * 16
    adm = tg_admin()
    try:
        if adm:
            bot.send(adm, "<blockquote>\U0001F4B0 <b>BALANCE ADDED</b></blockquote>\n%s\n"
                          "\U0001F464 Reseller: <b>%s</b>\n\u2705 Added: <b>%s</b>\n"
                          "\U0001F4B0 Current Balance: <b>%s</b>\n\U0001F4B3 Method: %s\n\U0001F552 Time: %s\n%s"
                     % (line, esc(who), inr(amount), inr(r["balance"]), esc(how), fmt(time.time()), line),
                     what="admin balance alert (%s)" % who)
    except Exception as e:
        bot._note(False, "-", "admin balance alert (%s)" % who, "error: %s" % str(e)[:150])
    try:
        if not alerts_on(r):                     # v18: only for accounts the admin switched ON
            return
        bot.send(r["tg_chat"], "<blockquote>\U0001F4B0 <b>BALANCE ADDED</b></blockquote>\n%s\n"
                               "\U0001F464 User: <b>%s</b>\n\u2705 Added: <b>%s</b>\n\U0001F4B0 Current Balance: <b>%s</b>\n"
                               "\U0001F4B3 Method: %s\n\U0001F552 Time: %s\n%s"
                 % (line, esc(who), inr(amount), inr(r["balance"]), esc(how), fmt(time.time()), line),
                 what="balance added (%s)" % who)
    except Exception as e:
        bot._note(False, "-", "balance alert (%s)" % who, "error: %s" % str(e)[:150])


# ---- login protection
_FAILS = {}


def rl_blocked(key, limit=8, window=600):
    now = time.time()
    _FAILS[key] = [t for t in _FAILS.get(key, []) if now - t < window]
    return len(_FAILS[key]) >= limit


def rl_hit(key):
    _FAILS.setdefault(key, []).append(time.time())


def otp_hash(rid, code):
    return hmac.new(app.secret_key.encode(), ("%d:%s" % (rid, code)).encode(), hashlib.sha256).hexdigest()


_OTP_STATE = {}          # reseller id -> {"state": "sending"|"ok"|"fail", "err": str}


def send_otp(r, force=False):
    """Make a NEW random 6-digit code and send it to the reseller's Telegram IN THE BACKGROUND.
    The login page never waits for Telegram (so it can never freeze); the verification page shows the result."""
    now = int(time.time())
    o = q("SELECT * FROM otps WHERE reseller_id=?", (r["id"],), one=True)
    if o and not force and now - o["sent"] < 30 and o["exp"] > now:
        return                                           # a fresh code was just sent
    code = "%06d" % secrets.randbelow(1000000)
    q("INSERT OR REPLACE INTO otps(reseller_id,h,exp,tries,sent) VALUES(?,?,?,?,?)",
      (r["id"], otp_hash(r["id"], code), now + 300, 0, now), commit=True)
    st = {"state": "sending", "err": "", "ts": now}
    _OTP_STATE[r["id"]] = st
    if r["id"] == 0:                                     # ADMIN login code
        text = ("<blockquote>\U0001F510 <b>ADMIN LOGIN CODE</b></blockquote>\n\n"
                "Someone entered the correct admin password for <b>%s</b>.\n"
                "\U0001F4F1 %s\n\U0001F310 IP: <code>%s</code>\n\U0001F552 %s\n\n"
                "<blockquote><code>%s</code></blockquote>\n\n\u23F1 Expires in <b>5 minutes</b>.\n"
                "\U0001F6AB If this was NOT you, do not share the code - change the admin password."
                % (esc(brand_name()), esc(ua_label(request.headers.get("User-Agent", ""))), esc(request.remote_addr),
                   fmt(now), code))
    elif r["id"] == -1:                                  # confirm a NEW admin chat id
        text = ("<blockquote>\U0001F510 <b>CONFIRM ADMIN CHAT</b></blockquote>\n\n"
                "This chat will become the <b>admin chat</b> of <b>%s</b> (login codes + alerts come here).\n\n"
                "<blockquote><code>%s</code></blockquote>\n\n\u23F1 Expires in <b>5 minutes</b>." % (esc(brand_name()), code))
    else:
        text = ("<blockquote>\U0001F510 <b>Login verification</b></blockquote>\n\n"
                "Use this one-time code to sign in to <b>%s</b>.\n\n<blockquote><code>%s</code></blockquote>\n\n"
                "\u23F1 Expires in <b>5 minutes</b>.\n\U0001F6AB Keep this code private. Our team will never ask for it."
                % (esc(brand_name()), code))
    chat, uname, rid = r["tg_chat"], r["username"], r["id"]

    def work():
        try:
            ok, err = bot.send_now(chat, text, what="login code (%s)" % uname)
        except Exception as e:
            ok, err = False, str(e)[:150]
        st["state"], st["err"] = ("ok", "") if ok else ("fail", err)
        if not ok:
            try:
                q("DELETE FROM otps WHERE reseller_id=? AND sent=?", (rid, now), commit=True)   # nothing delivered = no valid code
            except Exception:
                pass
    threading.Thread(target=work, daemon=True, name="otp-send").start()


def check_otp(rid, code):
    o = q("SELECT * FROM otps WHERE reseller_id=?", (rid,), one=True)
    now = int(time.time())
    if not o or o["exp"] < now:
        return False, "Code expired. Press Resend to get a new one."
    if o["tries"] >= 5:
        q("DELETE FROM otps WHERE reseller_id=?", (rid,), commit=True)
        return False, "Too many wrong attempts. Please login again."
    if same(o["h"], otp_hash(rid, code.strip())):
        q("DELETE FROM otps WHERE reseller_id=?", (rid,), commit=True)
        return True, ""
    q("UPDATE otps SET tries=tries+1 WHERE reseller_id=?", (rid,), commit=True)
    return False, "Wrong code. %d attempt(s) left." % max(4 - o["tries"], 0)


# ---- device id (cookie issued by the server, bound to the reseller by the admin's approval)
def get_dev():
    d = request.cookies.get("rgd", "")
    return (d, False) if re.fullmatch(r"[0-9a-f]{32}", d) else (secrets.token_hex(16), True)


def set_dev_cookie(resp, dev, is_new):
    if is_new:
        resp.set_cookie("rgd", dev, max_age=63072000, httponly=True, samesite="Lax",
                        secure=request.is_secure)
    return resp


def device_blocked_any(dev):
    return bool(q("SELECT 1 FROM devices WHERE dev_id=? AND status='denied'", (dev,), one=True)
                or q("SELECT 1 FROM adm_devices WHERE dev_id=? AND status='denied'", (dev,), one=True))


def device_ok(rid):
    d = request.cookies.get("rgd", "")
    if not re.fullmatch(r"[0-9a-f]{32}", d):
        return False
    row = q("SELECT id FROM devices WHERE reseller_id=? AND dev_id=? AND status='approved'", (rid, d), one=True)
    if row:
        q("UPDATE devices SET last_seen=? WHERE id=?", (int(time.time()), row["id"]), commit=True)
    return bool(row)


def blocked_page(msg=None):
    resp = make_response(render_template("blocked.html", msg=msg), 403)
    resp.headers["Cache-Control"] = "no-store"
    return resp


def ask_admin_approval(r, dev):
    """Create / refresh a pending device row and send the Accept / Reject message to the admin."""
    now = int(time.time())
    d = q("SELECT * FROM devices WHERE reseller_id=? AND dev_id=?", (r["id"], dev), one=True)
    label = ua_label(request.headers.get("User-Agent", ""))
    if d and d["status"] == "pending" and now - d["created"] < 120:
        return d["id"]                                   # request already sent a moment ago
    if d:
        did = d["id"]
        q("UPDATE devices SET status='pending', created=?, label=?, ip=? WHERE id=?",
          (now, label, request.remote_addr, did), commit=True)
    else:
        did = q("INSERT INTO devices(reseller_id,dev_id,label,ip,status,created) VALUES(?,?,?,?,?,?)",
                (r["id"], dev, label, request.remote_addr, "pending", now), commit=True)
    bot.send(tg_admin(),
             "<blockquote>\U0001F514 <b>NEW DEVICE LOGIN REQUEST</b></blockquote>\n\n"
             "\U0001F464 Reseller: <b>%s</b>\n\U0001F4F1 Device: %s\n\U0001F310 IP: <code>%s</code>\n"
             "\U0001F552 Time: %s\n\nAllow this device to open the panel?"
             % (esc(r["username"]), esc(label), esc(request.remote_addr), fmt(now)),
             [[("\u2705 Accept", "dv:a:%d" % did), ("\u274C Reject", "dv:d:%d" % did)]])
    return did


def pw_fp(r):
    return hashlib.sha256((r["pw"] + app.secret_key).encode()).hexdigest()[:16]


def finish_login(r, dev, alert=False):
    """Final step: the browser becomes logged in. Returns the URL to go to."""
    session.clear()
    session["rid"] = r["id"]
    session["pwh"] = pw_fp(r)
    q("UPDATE devices SET last_seen=? WHERE reseller_id=? AND dev_id=?", (int(time.time()), r["id"], dev), commit=True)
    try:                                                # admin is told about EVERY successful reseller login
        adm = tg_admin()
        if adm:
            bot.send(adm, "<blockquote>\U0001F513 <b>RESELLER LOGIN</b></blockquote>\n\U0001F464 Reseller: <b>%s</b>\n"
                          "\U0001F4F1 %s\n\U0001F310 IP: <code>%s</code>\n\U0001F552 Time: %s\n"
                          "\U0001F4B0 Balance: <b>%s</b>"
                     % (esc(r["username"]), esc(ua_label(request.headers.get("User-Agent", ""))),
                        esc(request.remote_addr), fmt(time.time()), inr(r["balance"])),
                     what="admin login alert (%s)" % r["username"])
    except Exception:
        pass
    if False:       # v17.10: reseller gets NO message on login (only purchase + low balance)
        bot.send(r["tg_chat"], "<blockquote>\U0001F513 <b>NEW LOGIN</b></blockquote>\n\U0001F4F1 %s\n"
                               "\U0001F310 IP: <code>%s</code>\n\U0001F552 %s"
                 % (esc(ua_label(request.headers.get("User-Agent", ""))), esc(request.remote_addr), fmt(time.time())))
    return "/dashboard"


def next_step(r, dev, fresh=False):
    """After password (+ device approval): code check if enabled, otherwise straight in. Returns a URL."""
    if False and otp_global_on() and r["otp_on"] and r["tg_chat"] and tg_token():      # v17.10: no login code for resellers
        session.clear()
        session["pre"] = dict(rid=r["id"], dev=dev, ts=int(time.time()))
        send_otp(r, force=fresh)                 # fresh=True: every new login gets its own brand-new code
        return "/login/verify"
    return finish_login(r, dev, alert=True)


def with_theme(resp, r):
    if r["theme"]:
        resp.set_cookie("rg_theme", r["theme"][1:], max_age=31536000, samesite="Lax")
    return resp


PRE_TTL = 900


def pre_reseller():
    p = session.get("pre")
    if not p or time.time() - p.get("ts", 0) > PRE_TTL:
        return None, None
    r = q("SELECT * FROM resellers WHERE id=? AND active=1 AND deleted=0", (p["rid"],), one=True)
    return (r, p) if r else (None, None)



# ---------------------------------------------------------------- admin security (password + Telegram code, every login)
def admin_pre():
    p = session.get("adm_pre")
    return p if p and time.time() - p.get("ts", 0) <= PRE_TTL else None


def admin_pseudo(kind=0, chat=None):
    """send_otp()/check_otp() work with a dict: id 0 = admin login code, id -1 = 'confirm new admin chat' code."""
    return {"id": kind, "tg_chat": chat or tg_admin(), "username": ADMIN_USER}


def admin_enter():
    session.clear()
    session["admin"] = True
    session["admin_ts"] = int(time.time())
    set_setting("adm_linked", "1")


def admin_next_step(fresh=False, dev=None):
    """v17.10: NO login code. Known (approved) browser -> straight in. New browser -> Accept / Reject in the admin's Telegram."""
    if not tg_token() or not tg_admin():
        return "/admin/setup"                                    # first time: bot token has to be connected
    dev = dev or request.cookies.get("rgd", "")
    if not re.fullmatch(r"[0-9a-f]{32}", dev or ""):
        dev = get_dev()[0]
    d = q("SELECT * FROM adm_devices WHERE dev_id=?", (dev,), one=True)
    now = int(time.time())
    if d and d["status"] == "approved":
        q("UPDATE adm_devices SET last_seen=? WHERE id=?", (now, d["id"]), commit=True)
        admin_enter()
        return "/admin"
    label = ua_label(request.headers.get("User-Agent", ""))
    if d and d["status"] == "pending" and now - d["created"] < 120:
        did = d["id"]                                            # request was sent a moment ago
    else:
        if d:
            did = d["id"]
            q("UPDATE adm_devices SET status='pending', created=?, label=?, ip=? WHERE id=?",
              (now, label, request.remote_addr, did), commit=True)
        else:
            did = q("INSERT INTO adm_devices(dev_id,label,ip,status,created) VALUES(?,?,?,?,?)",
                    (dev, label, request.remote_addr, "pending", now), commit=True)
        bot.send(tg_admin(),
                 "<blockquote>\U0001F514 <b>ADMIN LOGIN REQUEST</b></blockquote>\n\n"
                 "Someone entered the correct admin username + password.\n\U0001F4F1 Device: %s\n"
                 "\U0001F310 IP: <code>%s</code>\n\U0001F552 Time: %s\n\nIs this YOU (the admin)?"
                 % (esc(label), esc(request.remote_addr), fmt(now)),
                 [[("\u2705 Approve", "dv:a:%d" % -did), ("\u274C Reject", "dv:d:%d" % -did)]], what="admin device request")
    session["adm_pre"] = dict(ts=now, dev=dev)
    return "/admin/wait"


@app.route("/admin/wait")
def admin_wait():
    if not admin_pre():
        return redirect("/login")
    return render_template("admin_wait.html", title="Approval needed")


@app.route("/admin/wait/status")
def admin_wait_status():
    p = admin_pre()
    if not p:
        return jsonify(status="gone", next="/login")
    d = q("SELECT * FROM adm_devices WHERE dev_id=?", (p.get("dev", ""),), one=True)
    if not d or request.cookies.get("rgd") != p.get("dev"):
        return jsonify(status="gone", next="/login")
    if d["status"] == "approved":
        admin_enter()
        return jsonify(status="approved", next="/admin")
    if d["status"] == "denied":
        session.clear()
        return jsonify(status="denied", next="/login")
    if int(time.time()) - d["created"] > 600:
        return jsonify(status="expired", next="/login")
    return jsonify(status="pending")


@app.route("/admin/setup", methods=["GET", "POST"])
def admin_setup():
    """FIRST TIME only (no bot token saved yet): paste the bot API token -> it is linked -> a code is sent."""
    if not admin_pre():
        return redirect("/login")
    need_token = not tg_token()
    if not need_token and tg_admin():
        return redirect(admin_next_step())
    chat = request.form.get("chat_id", tg_admin() or TG_ADMIN_ID).strip() if request.method == "POST" else (tg_admin() or TG_ADMIN_ID)
    if request.method == "POST":
        tok = request.form.get("token", "").strip()
        err = None
        if rl_blocked("setup:" + (request.remote_addr or "?"), 8, 600):
            err = "Too many attempts. Please wait 10 minutes."
        elif not re.fullmatch(r"-?\d{5,15}", chat):
            err = "Chat ID must be numbers only"
        elif need_token and not re.fullmatch(r"\d{6,12}:[\w-]{30,60}", tok):
            err = "That does not look like a bot token (get it from @BotFather)"
        if not err and need_token:
            ok, info = bot.check_token(tok)
            if not ok and ("unauthorized" in info.lower() or "not found" in info.lower()):
                err = "Telegram rejected this token (%s)" % info
            else:
                set_setting("tg_token", tok)
                bot.token_changed()                              # bot is linked and running right now
        if err:
            rl_hit("setup:" + (request.remote_addr or "?"))
            flash(err, "err")
        else:
            set_setting("tg_admin", chat)
            session["adm_pre"] = dict(ts=int(time.time()))
            return redirect(admin_next_step(fresh=True))
    return render_template("admin_setup.html", title="Connect bot", need_token=need_token, chat_id=chat)


@app.route("/admin/verify", methods=["GET", "POST"])
def admin_verify():
    return redirect("/admin/wait" if admin_pre() else "/login")      # v17.10: no admin login code any more


def _old_admin_verify():
    if not admin_pre():
        return redirect("/login")
    if not tg_token() or not tg_admin():
        return redirect("/admin/setup")
    mk, ip = mask_id(tg_admin()), request.remote_addr or "?"
    page = lambda: render_template("admin_verify.html", title="Admin verification", tg_mask=mk)
    if request.method == "POST":
        if request.form.get("action") == "resend":
            if rl_blocked("otp-send:0", 6, 600):
                flash("Too many codes requested. Wait a few minutes.", "err")
            else:
                rl_hit("otp-send:0")
                send_otp(admin_pseudo(), force=True)
                flash("A new code is being sent to the admin Telegram.", "ok")
            return page()
        if rl_blocked("otp:0", 6, 600) or rl_blocked("otpip:" + ip, 8, 600):
            flash("Too many wrong codes. Please wait 10 minutes.", "err")
            return page()
        ok, msg = check_otp(0, request.form.get("code", ""))
        if ok:
            set_setting("adm_linked", "1")
            session.clear()
            session["admin"] = True
            session["admin_ts"] = int(time.time())
            try:
                bot.send(tg_admin(), "<blockquote>\U0001F513 <b>ADMIN LOGIN</b></blockquote>\n\U0001F4F1 %s\n\U0001F310 IP: <code>%s</code>\n\U0001F552 %s"
                         % (esc(ua_label(request.headers.get("User-Agent", ""))), esc(ip), fmt(time.time())), what="admin login alert")
            except Exception:
                pass
            return redirect("/admin")
        rl_hit("otp:0")
        rl_hit("otpip:" + ip)
        flash(msg, "err")
    return page()


@app.route("/admin/otp_status")
def admin_otp_status():
    if not admin_pre() and not session.get("admin"):
        return jsonify(state="gone")
    st = _OTP_STATE.get(-1 if request.args.get("k") == "-1" else 0) or {"state": "ok", "err": ""}
    return jsonify(state=st["state"], err=st["err"][:200])


# ---------------------------------------------------------------- public
@app.route("/health")
def health():
    return "ok"


@app.route("/")
def index():
    return redirect("/admin" if session.get("admin") else "/dashboard" if session.get("rid") else "/login")


def do_login():
    """ONE login for everybody: admin credentials -> admin panel, reseller credentials -> reseller panel
    (reseller: password -> device approval by admin -> 6 digit Telegram code -> dashboard)."""
    dev, is_new = get_dev()
    ip = request.remote_addr or "?"

    def out(resp):
        return set_dev_cookie(resp, dev, is_new)
    if dev_check_on() and device_blocked_any(dev):          # rejected device: the login page is never shown
        return out(blocked_page())
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        raw = request.form.get("password", "")
        pw = raw.strip()
        if rl_blocked("ip:" + ip):
            flash("Too many attempts. Please wait 10 minutes.", "err")
            return out(make_response(render_template("login.html", title="Login", action=request.path, signup=(request.path == "/login" and signup_on()), u=request.args.get("u", ""))))
        if same(u.upper(), ADMIN_USER.upper()) and same(pw, ADMIN_PASS):
            session.clear()                               # password alone NEVER opens the admin panel (code from Telegram needed)
            session["adm_pre"] = dict(ts=int(time.time()))
            return out(redirect(admin_next_step(fresh=True, dev=dev)))
        for r in q("SELECT * FROM resellers WHERE lower(username)=lower(?) AND deleted=0", (u,)):
            if check_password_hash(r["pw"], raw) or (pw != raw and check_password_hash(r["pw"], pw)):
                if not r["active"]:
                    flash("Your account is disabled. Please contact admin.", "err")
                    break
                if r["role"] == "user":                    # USER: username + password only (no device check, no code)
                    session.clear()
                    session["rid"] = r["id"]
                    session["pwh"] = pw_fp(r)
                    return out(with_theme(redirect("/dashboard"), r))
                if dev_check_on():
                    d = q("SELECT * FROM devices WHERE reseller_id=? AND dev_id=?", (r["id"], dev), one=True)
                    if d and d["status"] == "denied":
                        return out(blocked_page())
                    if not d or d["status"] != "approved":
                        ask_admin_approval(r, dev)
                        session.clear()
                        session["pre"] = dict(rid=r["id"], dev=dev, ts=int(time.time()))
                        return out(redirect("/login/wait"))
                return out(with_theme(redirect(next_step(r, dev, fresh=True)), r))
        else:
            rl_hit("ip:" + ip)
            flash("Invalid username or password", "err")
    return out(make_response(render_template("login.html", title="Login", action=request.path, signup=(request.path == "/login" and signup_on()), u=request.args.get("u", ""))))


@app.route("/login/wait")
def login_wait():
    r, p = pre_reseller()
    if not r:
        return redirect("/login")
    return render_template("login_wait.html", title="Approval needed")


@app.route("/login/status")
def login_status():
    r, p = pre_reseller()
    if not r:
        return jsonify(status="gone", next="/login")
    d = q("SELECT * FROM devices WHERE reseller_id=? AND dev_id=?", (r["id"], p["dev"]), one=True)
    if not d:
        return jsonify(status="gone", next="/login")
    if d["status"] == "approved" and request.cookies.get("rgd") == p["dev"]:
        return with_theme(jsonify(status="approved", next=next_step(r, p["dev"])), r)
    if d["status"] == "denied":
        return jsonify(status="denied", next="/login")
    if int(time.time()) - d["created"] > 600:
        return jsonify(status="expired", next="/login")
    return jsonify(status="pending")


@app.route("/login/otp_status")
def login_otp_status():
    r, p = pre_reseller()
    if not r:
        return jsonify(state="gone")
    st = _OTP_STATE.get(r["id"]) or {"state": "ok", "err": ""}
    return jsonify(state=st["state"], err=st["err"][:200])


@app.route("/login/cancel")
def login_cancel():
    session.clear()
    return redirect("/login")


@app.route("/login/verify", methods=["GET", "POST"])
def login_verify():
    r, p = pre_reseller()
    if not r or request.cookies.get("rgd") != p["dev"]:
        return redirect("/login")
    if not (otp_global_on() and r["otp_on"] and r["tg_chat"]):
        return redirect("/login")                        # code was switched OFF meanwhile -> log in again, no code needed
    mk = mask_id(r["tg_chat"])
    if request.method == "POST":
        if request.form.get("action") == "resend":
            if rl_blocked("otp-send:%d" % r["id"], 5, 600):
                flash("Too many codes requested. Wait a few minutes.", "err")
            else:
                rl_hit("otp-send:%d" % r["id"])
                send_otp(r, force=True)
                flash("A new code is being sent to your Telegram.", "ok")
            return render_template("login_verify.html", title="Verification", tg_mask=mk)
        if rl_blocked("otp:%d" % r["id"], 10, 600):
            flash("Too many wrong codes. Please wait 10 minutes.", "err")
            return render_template("login_verify.html", title="Verification", tg_mask=mk)
        ok, msg = check_otp(r["id"], request.form.get("code", ""))
        if ok:
            return with_theme(redirect(finish_login(r, p["dev"])), r)
        rl_hit("otp:%d" % r["id"])
        flash(msg, "err")
    return render_template("login_verify.html", title="Verification", tg_mask=mk)


@app.route("/login", methods=["GET", "POST"])
def login():
    return do_login()


def signup_on():
    return get_setting("signup_on", "1") != "0"


@app.route("/signup", methods=["GET", "POST"])
def signup():
    dev, is_new = get_dev()
    ip = request.remote_addr or "?"

    def out(resp):
        return set_dev_cookie(resp, dev, is_new)
    if session.get("rid"):
        return redirect("/dashboard")
    if not signup_on():
        flash("New accounts are closed right now. Please contact admin.", "err")
        return out(redirect("/login"))
    u = request.form.get("username", "").strip()
    if request.method == "POST":
        p, cf = request.form.get("password", ""), request.form.get("confirm", "")
        err = None
        if rl_blocked("signup:" + ip, 6, 3600):
            err = "Too many accounts created from this network. Try again later."
        elif not re.fullmatch(r"[A-Za-z0-9_.\-]{3,24}", u):
            err = "Username: 3-24 characters, only letters, numbers, _ . -"
        elif same(u.upper(), ADMIN_USER.upper()):
            err = "This username is not available"
        elif len(p) < 6:
            err = "Password must be at least 6 characters"
        elif p != cf:
            err = "Password and confirm password do not match"
        elif q("SELECT 1 FROM resellers WHERE lower(username)=lower(?)", (u,), one=True):
            err = "This username is already taken"
        if not err:
            try:
                q("INSERT INTO resellers(username,pw,balance,api_key,created,role,otp_on) VALUES(?,?,?,?,?,?,?)",
                  (u, generate_password_hash(p), 0, new_api_key(), int(time.time()), "user", 0), commit=True)
            except sqlite3.IntegrityError:
                err = "This username is already taken"
        if not err:
            rl_hit("signup:" + ip)
            try:
                if tg_admin():
                    bot.send(tg_admin(), "<blockquote>\U0001F195 <b>NEW USER ACCOUNT</b></blockquote>\n\U0001F464 User: <b>%s</b>\n"
                                         "\U0001F310 IP: <code>%s</code>\n\U0001F552 %s" % (esc(u), esc(ip), fmt(time.time())),
                             what="new user alert (%s)" % u)
            except Exception:
                pass
            flash("Account created successfully. Now login with your username and password.", "ok")
            return out(redirect("/login?u=" + u))
        flash(err, "err")
    return out(make_response(render_template("signup.html", title="Create Account", u=u)))


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------------------------------------------------------- reseller panel
@app.route("/dashboard")
@reseller_required
def dashboard():
    import calendar
    rid, now = request.r["id"], int(time.time())
    lt = time.gmtime(now + TZ_OFFSET)
    midnight = now - ((now + TZ_OFFSET) % 86400)
    week_start = midnight - lt.tm_wday * 86400          # Monday 00:00 (local)
    month_start = calendar.timegm((lt.tm_year, lt.tm_mon, 1, 0, 0, 0)) - TZ_OFFSET
    cnt = lambda since: q("SELECT COUNT(*) FROM license_keys WHERE reseller_id=? AND created>=?", (rid, since), one=True)[0]
    stats = dict(
        today=cnt(midnight), week=cnt(week_start), month=cnt(month_start), total=cnt(0),
        month_spent=q("SELECT COALESCE(SUM(price),0) FROM license_keys WHERE reseller_id=? AND created>=?",
                      (rid, month_start), one=True)[0],
        products=q("SELECT COUNT(*) FROM products", one=True)[0],
        month_name=time.strftime("%B %Y", lt))
    recent = q("SELECT * FROM license_keys WHERE reseller_id=? ORDER BY id DESC LIMIT 5", (rid,))
    return render_template("dashboard.html", r=request.r, st=stats, recent=recent, page="dashboard")


@app.route("/generate")
@reseller_required
def generate():
    cat = [p for p in catalog(request.r["id"]) if p["plans"]]
    return render_template("generate.html", r=request.r, cat=cat, page="generate")


@app.route("/generate/one", methods=["POST"])
@reseller_required
def generate_one():
    try:
        res = buy(request.r["id"], int(request.form.get("plan_id", 0)))
        return jsonify(ok=True, key=res["key"], balance=res["balance"])
    except Exception as e:
        try:
            pid = int(request.form.get("plan_id", 0) or 0)
            pl = q("SELECT pr.name pname, pl.name plan_name FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=?", (pid,), one=True)
            q("INSERT INTO support_ai_failures(reseller_id,plan_id,product_name,plan_name,error_code,public_message,created) VALUES(?,?,?,?,?,?,?)",
              (request.r["id"], pid, (pl["pname"] if pl else ""), (pl["plan_name"] if pl else ""), str(e)[:160], "Purchase could not be completed. Please contact support.", int(time.time())), commit=True)
        except Exception:
            pass
        raw_error = str(e)
        low_error = raw_error.lower()
        if "key may still be created" in low_error or "not refunded automatically" in low_error:
            public_error = "Temporary API server issue. Your request may still be processing. Please check Key History before trying again."
        elif any(word in low_error for word in ("provider", "tahir", "vip seller", "api", "timeout", "http")):
            public_error = "Temporary API server issue. Please wait for a short time and try again."
        else:
            public_error = raw_error
        return jsonify(ok=False, error=public_error)


PRESETS = [10, 20, 30, 50, 70, 100, 200, 300, 500, 1000, 2000, 5000, 10000]


@app.route("/history")
@reseller_required
def history():
    rid = request.r["id"]
    rows = q("SELECT * FROM license_keys WHERE reseller_id=? ORDER BY id DESC LIMIT 5000", (rid,))
    total = q("SELECT COUNT(*) FROM license_keys WHERE reseller_id=?", (rid,), one=True)[0]
    return render_template("history.html", r=request.r, rows=rows, total=total,
                           opts=[n for n in PRESETS if n < total], page="history")


@app.route("/history/plain")
@reseller_required
def history_plain():
    n, s_ = int(num(request.args.get("n"), 0)), request.args.get("q", "").strip().lower()
    rows = q("SELECT key, product_name FROM license_keys WHERE reseller_id=? ORDER BY id DESC", (request.r["id"],))
    keys = [x["key"] for x in rows if not s_ or s_ in (x["key"] + " " + (x["product_name"] or "")).lower()]
    if n > 0:
        keys = keys[:n]
    return jsonify(count=len(keys), text="\n".join(keys))


@app.route("/theme", methods=["POST"])
@reseller_required
def set_theme():
    c = request.form.get("color", "").strip().lower()
    if not re.match(r"^#[0-9a-f]{6}$", c):
        return jsonify(ok=False), 400
    q("UPDATE resellers SET theme=? WHERE id=?", (c, request.r["id"]), commit=True)
    resp = jsonify(ok=True)
    resp.set_cookie("rg_theme", c[1:], max_age=31536000, samesite="Lax")
    return resp


# ---- security (reseller)
@app.route("/settings", methods=["GET", "POST"])
@reseller_required
def settings():
    r = request.r
    if request.method == "POST":
        key = "pw:%d" % r["id"]
        cur = request.form.get("current", "")
        new = request.form.get("new", "").strip()
        con = request.form.get("confirm", "").strip()
        if rl_blocked(key, 5, 600):
            flash("Too many wrong attempts. Try again in 10 minutes.", "err")
        elif not (check_password_hash(r["pw"], cur) or check_password_hash(r["pw"], cur.strip())):
            rl_hit(key)
            flash("Current password is wrong", "err")
        elif len(new) < 6:
            flash("New password must be at least 6 characters", "err")
        elif new != con:
            flash("New password and confirm password do not match", "err")
        elif check_password_hash(r["pw"], new):
            flash("New password must be different from the current one", "err")
        else:
            q("UPDATE resellers SET pw=? WHERE id=?", (generate_password_hash(new), r["id"]), commit=True)
            extra = ""
            if request.form.get("newkey"):
                q("UPDATE resellers SET api_key=? WHERE id=?", (new_api_key(), r["id"]), commit=True)
                extra = " A new API key was generated too (old key stopped working)."
            r2 = q("SELECT * FROM resellers WHERE id=?", (r["id"],), one=True)
            session["pwh"] = pw_fp(r2)            # this browser stays logged in, all other browsers are logged out
            try:
                if False:      # v17.10: reseller bot gets only purchase + low balance messages
                    bot.send(r2["tg_chat"], "<blockquote>\U0001F511 <b>PASSWORD CHANGED</b></blockquote>\n"
                             "\U0001F310 IP: <code>%s</code>\n\U0001F552 %s\n\nIf this was not you, contact admin at once."
                             % (esc(request.remote_addr), fmt(time.time())))
            except Exception:
                pass
            flash("Password changed. Other logged-in browsers were logged out." + extra, "ok")
        return redirect("/settings")
    return render_template("settings.html", r=r, page="settings")


@app.route("/security", methods=["GET", "POST"])
@reseller_only
def security():
    r = request.r
    if request.method == "POST":
        a = request.form.get("action")
        if a == "otp_on":
            if not r["tg_chat"]:
                flash("Your Telegram is not linked yet. Ask admin to add your Chat ID.", "err")
            else:
                q("UPDATE resellers SET otp_on=1 WHERE id=?", (r["id"],), commit=True)
                flash("Login verification is ON", "ok")
        elif a == "otp_off":
            pw = request.form.get("password", "")
            if check_password_hash(r["pw"], pw) or check_password_hash(r["pw"], pw.strip()):
                q("UPDATE resellers SET otp_on=0 WHERE id=?", (r["id"],), commit=True)
                flash("Login verification is OFF. Username + password is enough to log in.", "ok")
            else:
                flash("Wrong password", "err")
        elif a == "alerts":
            q("UPDATE resellers SET notify=?, low_bal=? WHERE id=?",
              (1 if request.form.get("notify") else 0, max(num(request.form.get("low_bal")), 0), r["id"]), commit=True)
            flash("Alert settings saved", "ok")
        elif a == "test_alert":
            if not r["tg_chat"]:
                flash("Your Telegram is not linked yet. Ask admin to add your Chat ID.", "err")
            else:
                ok, err = send_bounded(r["tg_chat"], purchase_text("TEST PRODUCT", 1, 18, r["balance"], "TEST-KEY-0000", "panel")
                                       + "\n\n<i>(this is only a test)</i>", what="test alert (%s)" % r["username"])
                flash("Test alert sent to your Telegram" if ok else "Could not send: %s" % err, "ok" if ok else "err")
        elif a == "rm_device":
            q("DELETE FROM devices WHERE id=? AND reseller_id=?", (int(num(request.form.get("id"))), r["id"]), commit=True)
            flash("Device removed", "ok")
        return redirect("/security")
    devs = q("SELECT * FROM devices WHERE reseller_id=? ORDER BY id DESC", (r["id"],))
    tc = r["tg_chat"] or ""
    return render_template("security.html", r=r, devs=devs, cur_dev=request.cookies.get("rgd", ""),
                           tg_mask=("\u2022" * max(len(tc) - 3, 0) + tc[-3:]) if tc else "",
                           bot_ready=bool(tg_token()), dev_on=dev_check_on(), page="security")


# ---- wallet (UPI top-up)
def my_topup(tid):
    return q("SELECT * FROM topups WHERE id=? AND reseller_id=?", (tid, request.r["id"]), one=True) or abort(404)


@app.route("/wallet")
@reseller_required
def wallet():
    tops = q("SELECT * FROM topups WHERE reseller_id=? AND purpose='wallet' ORDER BY id DESC LIMIT 8", (request.r["id"],))
    return render_template("wallet.html", r=request.r, amts=wallet_amounts(), tops=tops,
                           cmin=custom_min(), cmax=CUSTOM_MAX, ready=gw_is_ready(), bn_ok=bn_ready(), bn_rate=bn_conf()[2], page="wallet")


def start_payment(rid, amt, purpose, method=""):
    """Create a payment on the ACTIVE gateway (Fampay or Paytm) and save it. Returns topup id. Raises on error."""
    now, prov = int(time.time()), ("binance" if method == "binance" else gw_active())
    ex = q("SELECT id FROM topups WHERE reseller_id=? AND amount=? AND purpose=? AND provider=? AND status='pending' AND deadline>? "
           "ORDER BY id DESC", (rid, amt, purpose, prov, now), one=True)
    if ex:
        return ex["id"]
    if q("SELECT COUNT(*) FROM topups WHERE reseller_id=? AND status='pending' AND deadline>?", (rid, now), one=True)[0] >= 5:
        raise ValueError("Too many pending payments. Please wait a few minutes.")
    if prov == "binance":
        if not bn_ready():
            raise ValueError("Binance payment is not available right now")
        usdt = bn_usdt(amt)
        oid = "NP%d%s" % (rid, secrets.token_hex(6))
        tid = q("INSERT INTO topups(reseller_id,amount,order_id,qr_url,upi_id,status,created,expires,deadline,provider,purpose,pay_amount) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (rid, amt, oid, "", "", "pending", now, now + 3600, now + 3600, "binance", purpose, usdt), commit=True)
        try:
            d = bn_create(oid, usdt)
        except Exception:
            q("DELETE FROM topups WHERE id=?", (tid,), commit=True)
            raise
        q("UPDATE topups SET ref=?, pay_uri=?, qr_url=?, checkout_url=?, pay_amount=? WHERE id=?",
          (d["ref"], d["pay_uri"], d["qr_url"], d["checkout"], d["pay_amount"], tid), commit=True)
        return tid
    if prov == "pgw":
        oid = "NP%d%s" % (rid, secrets.token_hex(6))          # unique order id (saved BEFORE the gateway is called)
        tid = q("INSERT INTO topups(reseller_id,amount,order_id,qr_url,upi_id,status,created,expires,deadline,provider,purpose) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)", (rid, amt, oid, "", "", "pending", now, now + 600, now + 600, "pgw", purpose), commit=True)
        try:
            d = pg_create(oid, amt)
        except Exception:
            q("DELETE FROM topups WHERE id=?", (tid,), commit=True)
            raise
        exp = d["exp"] or now + 600
        q("UPDATE topups SET ref=?, pay_uri=?, qr_url=?, app_pay=?, checkout_url=?, pay_amount=?, expires=?, deadline=? WHERE id=?",
          (d["ref"], d["pay_uri"], d["qr_url"], d["app_pay"], d["checkout"], d["pay_amount"], exp, min(max(now + 600, exp + 60), now + 1800), tid), commit=True)
        return tid
    if prov == "paytm":
        oid = "NP%d%s" % (rid, secrets.token_hex(6))          # unique, stable order id (saved BEFORE the gateway is called)
        tid = q("INSERT INTO topups(reseller_id,amount,order_id,qr_url,upi_id,status,created,expires,deadline,provider,purpose) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)", (rid, amt, oid, "", "", "pending", now, now + 300, now + 300, "zyvo", purpose), commit=True)
        try:
            d = zy_create(oid, amt)
        except Exception:
            q("DELETE FROM topups WHERE id=?", (tid,), commit=True)
            raise
        exp = d["exp"] or now + 300
        q("UPDATE topups SET ref=?, pay_uri=?, qr_url=?, app_pay=?, checkout_url=?, expires=?, deadline=? WHERE id=?",
          (d["ref"], d["pay_uri"], d["qr_url"], d["app_pay"], d["checkout"], exp, min(max(now + 300, exp), now + 1800), tid), commit=True)
        return tid
    d = gw_create(amt)
    exp = parse_iso(d.get("expires_at"))
    return q("INSERT INTO topups(reseller_id,amount,order_id,qr_url,upi_id,status,created,expires,deadline,provider,purpose) "
             "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
             (rid, amt, str(d["order_id"]), gw_abs(d["qr_url"]), str(d.get("upi_id") or ""), "pending", now,
              exp or now + 300, min(max(now + 300, exp), now + 1800), "fam", purpose), commit=True)


CUSTOM_MAX = 100000


def custom_min():
    return max(int(num(get_setting("wallet_custom_min", "10"), 10)), 1)


@app.route("/wallet/create", methods=["POST"])
@reseller_required
def wallet_create():
    amt = int(num(request.form.get("amount")))
    if request.form.get("custom") == "1":
        if not (custom_min() <= amt <= CUSTOM_MAX):
            flash("Enter an amount from %d to %d" % (custom_min(), CUSTOM_MAX), "err")
            return redirect("/wallet")
    elif amt not in wallet_amounts():
        flash("Please choose one of the listed amounts", "err")
        return redirect("/wallet")
    try:
        tid = start_payment(request.r["id"], amt, "wallet", "binance" if request.form.get("method") == "binance" else "")
    except Exception as e:
        flash("Could not create the QR: %s" % e, "err")
        return redirect("/wallet")
    return redirect("/wallet/pay/%d" % tid)


def upgrade_price():
    return int(num(get_setting("upgrade_price", "0")))


@app.route("/upgrade", methods=["GET", "POST"])
@reseller_required
def upgrade():
    r = request.r
    if r["role"] != "user":
        return redirect("/dashboard")
    price = upgrade_price()
    if request.method == "POST":
        if price <= 0 or not gw_is_ready():
            flash("Full Reseller Upgrade is not available right now.", "err")
            return redirect("/upgrade")
        try:
            tid = start_payment(r["id"], price, "upgrade")
        except Exception as e:
            flash("Could not create the QR: %s" % e, "err")
            return redirect("/upgrade")
        return redirect("/wallet/pay/%d" % tid)
    return render_template("upgrade.html", r=r, price=price, ready=gw_is_ready(), page="upgrade")


@app.route("/wallet/pay/<int:tid>")
@reseller_required
def wallet_pay(tid):
    t = my_topup(tid)                                   # no gateway call here: the page opens instantly, polling does the checking
    r = q("SELECT * FROM resellers WHERE id=?", (request.r["id"],), one=True)
    svg = None
    if t["provider"] in ("zyvo", "pgw", "binance") and (t["pay_uri"] or "").strip():
        try:
            svg = qr_svg(t["pay_uri"])
        except Exception as e:
            print("[qr] %s" % e)
    pay_uri = t["pay_uri"] if (t["pay_uri"] or "").lower().startswith("upi:") and t["app_pay"] else ""
    chk = t["checkout_url"] if (t["checkout_url"] or "").startswith("https://") else ""
    return render_template("wallet_pay.html", r=r, t=t, left=max(int(t["deadline"] - time.time()), 0), qr_svg=svg,
                           pay_uri=pay_uri, checkout=chk, page="upgrade" if t["purpose"] == "upgrade" else "wallet")


@app.route("/wallet/status/<int:tid>")
@reseller_required
def wallet_status(tid):
    st = check_topup(my_topup(tid))
    me = q("SELECT balance, role FROM resellers WHERE id=?", (request.r["id"],), one=True)
    return jsonify(status=st, balance=me["balance"], role=me["role"])


@app.route("/wallet/qr/<int:tid>")
@reseller_required
def wallet_qr(tid):
    t = my_topup(tid)
    name = re.sub(r"\W", "", t["order_id"] or "qr")
    if t["provider"] in ("zyvo", "pgw", "binance") and (t["pay_uri"] or "").strip():
        try:
            return Response(qr_png(t["pay_uri"]), mimetype="image/png",
                            headers={"Content-Disposition": 'attachment; filename="%s.png"' % name})
        except Exception:
            abort(502)
    base = pg_conf()[0] if t["provider"] == "pgw" else (zy_conf()[2].rsplit("/api", 1)[0] if t["provider"] == "zyvo" else gw_base())
    if not (t["qr_url"] or "").startswith(base):
        abort(404)
    try:
        r = _HTTP.get(t["qr_url"], timeout=10)
        r.raise_for_status()
    except Exception:
        abort(502)
    return Response(r.content, mimetype=r.headers.get("Content-Type", "image/png"),
                    headers={"Content-Disposition": 'attachment; filename="%s.png"' % name})


def _zy_webhook_work(ref, order_id, event):
    t = q("SELECT * FROM topups WHERE provider='zyvo' AND (ref=? OR order_id=?)", (ref, order_id), one=True)
    if not t:
        return
    if event == "payment.successful":
        check_topup(t)                                  # trusted path: re-verified with a signed status call before crediting
    elif t["status"] == "pending":
        q("UPDATE topups SET status='expired' WHERE id=? AND status='pending'", (t["id"],), commit=True)


@app.route("/zyvo/webhook", methods=["POST"])
def zyvo_webhook():
    raw = request.get_data()                            # untouched raw body, read BEFORE any JSON parsing
    ip = request.remote_addr or "?"
    sec = zy_conf()[1]
    got = request.headers.get("X-ZyvoPay-Signature", "")
    if rl_blocked("zywh:" + ip, 30, 600):
        return jsonify(ok=False), 429
    if not sec or not got or not same(hmac.new(sec.encode(), raw, hashlib.sha256).hexdigest(), got.strip().lower()):
        rl_hit("zywh:" + ip)
        return jsonify(ok=False, error="invalid signature"), 401
    try:
        j = json.loads(raw.decode("utf-8"))
        ev = str(j.get("event") or "")
        d = j.get("data") if isinstance(j.get("data"), dict) else {}
        ref, oid = str(d.get("reference") or ""), str(d.get("order_id") or "")
    except Exception:
        return jsonify(ok=False, error="bad payload"), 400
    if ev not in ("payment.successful", "payment.failed", "payment.expired") or not (ref or oid):
        return jsonify(ok=True, ignored=True)
    eid = hashlib.sha256(("%s|%s|%s" % (ev, ref or oid, ev)).encode()).hexdigest()
    try:
        q("INSERT INTO zy_events(id,ts) VALUES(?,?)", (eid, int(time.time())), commit=True)
    except sqlite3.IntegrityError:
        return jsonify(ok=True, duplicate=True)         # same event again: already handled
    threading.Thread(target=_zy_webhook_work, args=(ref, oid, ev), daemon=True, name="zy-webhook").start()
    return jsonify(ok=True)


def _pg_webhook_work(order_id):
    t = q("SELECT * FROM topups WHERE provider='pgw' AND (order_id=? OR ref=?)", (order_id, order_id), one=True)
    if t:
        check_topup(t)                                  # trusted path: re-verified with the gateway before crediting


@app.route("/pgw/webhook", methods=["POST"])
def pg_webhook():
    raw = request.get_data()
    ip = request.remote_addr or "?"
    sec = pg_conf()[3]
    ts = request.headers.get("X-Payment-Gateway-Timestamp", "0")
    got = request.headers.get("X-Payment-Gateway-Signature", "").strip().lower()
    if rl_blocked("pgwh:" + ip, 30, 600):
        return jsonify(ok=False), 429
    exp = "sha256=" + hmac.new(sec.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest() if sec else ""
    try:
        fresh = abs(time.time() - int(ts)) <= 300
    except ValueError:
        fresh = False
    if not sec or not fresh or not same(exp, got):
        rl_hit("pgwh:" + ip)
        return jsonify(ok=False, error="invalid signature"), 401
    try:
        j = json.loads(raw.decode("utf-8"))
        ev, eid, oid = str(j.get("event") or ""), str(j.get("event_id") or ""), str(j.get("order_id") or j.get("pay_id") or "")
    except Exception:
        return jsonify(ok=False, error="bad payload"), 400
    if ev not in ("payment.success", "payment.failed", "payment.expired") or not oid:
        return jsonify(ok=True, ignored=True)
    try:
        q("INSERT INTO zy_events(id,ts) VALUES(?,?)", ("pg:" + (eid or oid + ev), int(time.time())), commit=True)
    except sqlite3.IntegrityError:
        return jsonify(ok=True, duplicate=True)
    threading.Thread(target=_pg_webhook_work, args=(oid,), daemon=True, name="pg-webhook").start()
    return jsonify(ok=True)


@app.route("/broadcast")
@reseller_required
def broadcast():
    rid = request.r["id"]
    rows = q("SELECT b.*, EXISTS(SELECT 1 FROM broadcast_reads x WHERE x.broadcast_id=b.id AND x.reseller_id=?) rd "
             "FROM broadcasts b WHERE (b.reseller_id IS NULL OR b.reseller_id=?) AND b.created>=? "
             "ORDER BY b.id DESC LIMIT 100", (rid, rid, request.r["created"]))
    html = render_template("broadcast.html", r=request.r, rows=rows, page="broadcast")
    for x in rows:
        if not x["rd"]:
            q("INSERT OR IGNORE INTO broadcast_reads(broadcast_id,reseller_id) VALUES(?,?)", (x["id"], rid), commit=True)
    return html


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
    items = []
    for m in q("SELECT * FROM music ORDER BY pos, id"):
        info = _music_link_info(m["url"])
        saved_title = str(m["title"] or "").strip()
        detected_title = str((info or {}).get("title") or "").strip()
        if detected_title and (not saved_title or saved_title.lower() in ("youtube song", "spotify song", "music")):
            saved_title = detected_title
        items.append(dict(title=saved_title or m["url"], url=m["url"], kind=(info or {}).get("kind", "audio"),
                          embed_url=(info or {}).get("embed_url", "")))
    return jsonify(items)


@app.route("/media/<path:name>")
def media(name):
    return send_from_directory(MUSIC_DIR, name)


# ---------------------------------------------------------------- reseller API
def api_token():
    """Token can come as X-API-Key header, Authorization: Bearer, ?api_key= / ?token= or in the body."""
    k = request.headers.get("X-API-Key") or ""
    if not k:
        a = request.headers.get("Authorization", "")
        if a.lower().startswith("bearer "):
            k = a[7:]
    if not k:
        k = request.args.get("api_key") or request.args.get("token") or ""
    if not k:
        d = request.get_json(silent=True)
        if isinstance(d, dict):
            k = str(d.get("api_key") or d.get("token") or "")
        elif request.form:
            k = request.form.get("api_key") or request.form.get("token") or ""
    return k.strip()


def api_auth():
    k = api_token()
    r = q("SELECT * FROM resellers WHERE api_key=?", (k,), one=True) if k else None
    if not r or not r["active"] or r["deleted"]:          # API works for resellers and users
        return None
    return r


def api_guard(f):
    from functools import wraps

    @wraps(f)
    def w(*a, **k):
        r = api_auth()
        if not r:
            return jsonify(success=False, connected=False, error="INVALID_API_KEY",
                           message="Not connected: API token is wrong, missing or the account is disabled."), 401
        request.r = r
        return f(*a, **k)
    return w


@app.after_request
def api_cors(resp):
    if request.path.startswith("/api/v1/"):
        resp.headers["Access-Control-Allow-Origin"] = "*"      # token based (no cookies) so this is safe
        resp.headers["Access-Control-Allow-Headers"] = "X-API-Key, Authorization, Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/v1/health")
def api_health():
    return jsonify(success=True, status="online")


@app.route("/api/v1/connect", methods=["GET", "POST"])
@api_guard
def api_connect():
    """Used by a bot when the reseller enters Server URL + API token: 'Connect successful' / 'Not connected'."""
    r = request.r
    return jsonify(success=True, connected=True, message="Connect successful",
                   username=r["username"], balance=r["balance"], currency="INR",
                   server=request.host_url.rstrip("/"))


@app.route("/api/v1/balance")
@api_guard
def api_balance():
    return jsonify(success=True, username=request.r["username"], balance=request.r["balance"], currency="INR")


def _id_list(raw):
    out = []
    if isinstance(raw, (list, tuple)):
        parts = raw
    else:
        parts = re.split(r"[,\s]+", str(raw or ""))
    for x in parts:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            pass
    return out


@app.route("/api/v1/products", methods=["GET", "POST"])
@api_guard
def api_products():
    """All products (default) or only the selected ones: ?ids=1,2,3  (or POST {"product_ids":[1,2,3]})."""
    raw = request.args.get("ids") or request.args.get("product_ids")
    body = request.get_json(silent=True) if request.method == "POST" else None
    if raw is None and isinstance(body, dict):
        raw = body.get("product_ids") or body.get("ids")
    want = _id_list(raw)
    cat = catalog(request.r["id"])
    missing = []
    if want and not str(request.args.get("all", "")).lower() in ("1", "true", "yes"):
        have = {p["id"] for p in cat}
        missing = [i for i in want if i not in have]
        cat = [p for p in cat if p["id"] in want]
    return jsonify(success=True, currency="INR", count=len(cat), missing_ids=missing, products=[
        dict(product_id=p["id"], name=p["name"], position=n,
             plans=[dict(plan_id=x["id"], name=x["name"], days=x["days"], hours=x["hours"], price=x["price"],
                         currency="INR", available=(x["stock"] > 0 if x["mode"] == "stock" else True))
                    for x in p["plans"]])
        for n, p in enumerate(cat, 1)])


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
    return do_login()


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin/login")


@app.route("/admin")
@admin_required
def admin_home():
    now = int(time.time())
    st = dict(resellers=q("SELECT COUNT(*) FROM resellers WHERE role!='user' AND deleted=0", one=True)[0],
              users=q("SELECT COUNT(*) FROM resellers WHERE role='user' AND deleted=0", one=True)[0],
              products=q("SELECT COUNT(*) FROM products", one=True)[0],
              keys=q("SELECT COUNT(*) FROM license_keys", one=True)[0],
              revenue=q("SELECT COALESCE(SUM(price),0) FROM license_keys", one=True)[0],
              credit=q("SELECT COALESCE(SUM(balance),0) FROM resellers WHERE deleted=0", one=True)[0])
    recent = q("SELECT k.*, r.username FROM license_keys k JOIN resellers r ON r.id=k.reseller_id ORDER BY k.id DESC LIMIT 15")
    return render_template("admin_home.html", st=st, recent=recent, now=now, page="home")


@app.route("/admin/products", methods=["GET", "POST"])
@admin_required
def admin_products():
    if request.method == "POST":
        a = request.form.get("action")
        if a == "product" and request.form.get("name", "").strip():
            nm = request.form["name"].strip()
            q("INSERT INTO products(name,src_name,pos) VALUES(?,?,?)", (nm, nm, next_prod_pos()), commit=True)
        elif a == "rename_product":
            nm = request.form.get("name", "").strip()[:80]
            if nm and q("SELECT 1 FROM products WHERE id=?", (int(num(request.form.get("product_id"))),), one=True):
                q("UPDATE products SET name=? WHERE id=?", (nm, int(num(request.form.get("product_id")))), commit=True)
                flash("Product name saved", "ok")
            else:
                flash("Enter a name", "err")
        elif a in ("move_product", "set_pos"):
            pid = int(num(request.form.get("product_id")))
            ids = [r["id"] for r in q("SELECT id FROM products ORDER BY (CASE WHEN pos>0 THEN pos ELSE id END), id")]
            if pid in ids:
                ids.remove(pid)
                if a == "set_pos":
                    at = min(max(int(num(request.form.get("pos"), 1)), 1), len(ids) + 1) - 1
                else:
                    cur = [r["id"] for r in q("SELECT id FROM products ORDER BY (CASE WHEN pos>0 THEN pos ELSE id END), id")].index(pid)
                    d = request.form.get("dir")
                    at = 0 if d == "top" else len(ids) if d == "bottom" else max(cur - 1, 0) if d == "up" else min(cur + 1, len(ids))
                ids.insert(at, pid)
                renumber_products(ids)
                flash("Order saved", "ok")
        elif a == "plan":
            try:
                n = max(int(num(request.form.get("days"), 1)), 1)
                hours = n if request.form.get("unit") == "hours" else 0
                days = max(-(-n // 24), 1) if hours else n
                price = num(request.form.get("price"))
                uprice = num(request.form.get("user_price")) or auto_user_price(price)
                q("INSERT INTO plans(product_id,name,days,hours,price,user_price,mode) VALUES(?,?,?,?,?,?,?)",
                  (int(request.form["product_id"]), plan_label(days, hours), days, hours,
                   price, uprice, request.form.get("mode", "stock")), commit=True)
            except Exception as e:
                flash("Error: %s" % e, "err")
        elif a == "edit_plan":
            n = max(int(num(request.form.get("days"), 1)), 1)
            hours = n if request.form.get("unit") == "hours" else 0
            days = max(-(-n // 24), 1) if hours else n
            plid = int(request.form["plan_id"])
            old = q("SELECT days,hours,name,prov_pid,prov_src FROM plans WHERE id=?", (plid,), one=True)
            mode = request.form.get("mode", "stock")
            if old and mode == "provider" and (not old["prov_pid"] or old["prov_src"] not in ("tahir", "vsh")):
                flash("This plan is not linked to Tahir or VIP Seller Hub. Import it from the correct API first.", "err")
            elif old:
                same = old["days"] == days and (old["hours"] or 0) == hours
                name = old["name"] if same else plan_label(days, hours)
                price = num(request.form.get("price"))
                uprice = num(request.form.get("user_price")) or auto_user_price(price)
                q("UPDATE plans SET name=?, days=?, hours=?, price=?, user_price=?, mode=? WHERE id=?",
                  (name, days, hours, price, uprice, mode, plid), commit=True)
        elif a == "del_plan":
            q("DELETE FROM plans WHERE id=?", (int(request.form["plan_id"]),), commit=True)
        elif a == "product_icon":
            pid = int(num(request.form.get("product_id")))
            cid = request.form.get("emoji_id", "").strip()
            if cid and not re.fullmatch(r"\d{5,25}", cid):
                flash("Premium emoji ID must be numbers only (5-25 digits)", "err")
            elif q("SELECT 1 FROM products WHERE id=?", (pid,), one=True):
                q("UPDATE products SET emoji_id=?, icon_ver=icon_ver+1 WHERE id=?", (cid, pid), commit=True)
                fl = request.files.get("icon")
                if request.form.get("remove_icon"):
                    q("UPDATE products SET icon='' WHERE id=?", (pid,), commit=True)
                elif fl and fl.filename:
                    try:
                        from PIL import Image
                        import io
                        im = Image.open(fl.stream)
                        im.load()
                        im = im.convert("RGBA")
                        im.thumbnail((128, 128))
                        buf = io.BytesIO()
                        im.save(buf, "PNG")
                        q("UPDATE products SET icon=? WHERE id=?", (base64.b64encode(buf.getvalue()).decode(), pid), commit=True)
                    except Exception:
                        flash("That file is not a picture", "err")
                flash("Product icon saved", "ok")
        elif a == "toggle_hidden":
            pid = int(num(request.form.get("product_id")))
            q("UPDATE products SET hidden=CASE WHEN COALESCE(hidden,0)=0 THEN 1 ELSE 0 END WHERE id=?", (pid,), commit=True)
            flash("Product visibility updated", "ok")
        elif a == "del_product":
            q("DELETE FROM products WHERE id=?", (int(request.form["product_id"]),), commit=True)
        return redirect("/admin/products")
    stock_n = {r[0]: r[1] for r in q("SELECT plan_id, COUNT(*) FROM stock WHERE used=0 GROUP BY plan_id")}
    by_prod = {}
    for pl in q("SELECT * FROM plans ORDER BY (CASE WHEN hours>0 THEN hours*3600 ELSE days*86400 END), id"):
        by_prod.setdefault(pl["product_id"], []).append(dict(pl=pl, stock=stock_n.get(pl["id"], 0)))
    prods = [dict(p=p, plans=by_prod.get(p["id"], []))
             for p in q("SELECT * FROM products ORDER BY (CASE WHEN pos>0 THEN pos ELSE id END), id")]
    return render_template("admin_products.html", prods=prods, page="products")



@app.errorhandler(404)
def admin_404(e):
    """v18.3: a missing admin page (deleted plan, stale link after a restart) never shows a bare 'Not Found'."""
    if request.path.startswith("/admin/") and request.method in ("GET", "POST"):
        if session.get("admin"):
            flash("That page / plan no longer exists - opened Products instead.", "err")
            return redirect("/admin/products")
        return redirect("/admin/login")
    return e


@app.route("/admin/stock/<int:pid>", methods=["GET", "POST"])
@admin_required
def admin_stock(pid):
    pl = q("SELECT pl.*, pr.name pname FROM plans pl JOIN products pr ON pr.id=pl.product_id WHERE pl.id=?",
           (pid,), one=True)
    if not pl:
        flash("This plan no longer exists - opened Products instead.", "err")
        return redirect("/admin/products")
    if request.method == "POST":
        a = request.form.get("action")
        try:
            if a == "add":
                keys = [k.strip() for k in (request.form.get("keys", "") or "").replace("\r", "\n").split("\n") if k.strip()]
                if not keys:
                    flash("Paste at least one key", "err")
                else:
                    now = int(time.time())
                    c_ = db()
                    try:
                        c_.executemany("INSERT INTO stock(plan_id,key,created) VALUES(?,?,?)", [(pid, k, now) for k in keys])
                        c_.commit()
                    finally:
                        c_.close()
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
        except Exception as e:
            flash("Could not save: %s" % e, "err")
        return redirect("/admin/stock/%d" % pid)
    rows = q("SELECT * FROM stock WHERE plan_id=? ORDER BY used, id DESC", (pid,))
    return render_template("admin_stock.html", pl=pl, rows=rows, page="products")


# ---- v18.5: separate "Manual Keys" section: pick a product -> its plans -> paste keys (plain page, no background submit)
@app.route("/admin/manual-keys")
@admin_required
def admin_manual_keys():
    stock_n = {r[0]: r[1] for r in q("SELECT plan_id, COUNT(*) FROM stock WHERE used=0 GROUP BY plan_id")}
    prods = q("SELECT * FROM products ORDER BY (CASE WHEN pos>0 THEN pos ELSE id END), id")
    plans_by = {}
    for pl in q("SELECT * FROM plans ORDER BY (CASE WHEN hours>0 THEN hours*3600 ELSE days*86400 END), id"):
        plans_by.setdefault(pl["product_id"], []).append(dict(pl=pl, stock=stock_n.get(pl["id"], 0)))
    sel = int(num(request.args.get("p"), 0))
    cur = next((p for p in prods if p["id"] == sel), None)
    rows = [dict(p=p, n=len(plans_by.get(p["id"], [])), stock=sum(x["stock"] for x in plans_by.get(p["id"], [])))
            for p in prods]
    return render_template("admin_manual_keys.html", rows=rows, cur=cur, plans=plans_by.get(sel, []) if cur else [],
                           page="mkeys")


@app.route("/admin/manual-keys/add", methods=["POST"])
@admin_required
def admin_manual_keys_add():
    try:
        plid = int(request.form.get("plan_id", "0"))
    except ValueError:
        plid = 0
    pl = q("SELECT * FROM plans WHERE id=?", (plid,), one=True)
    if not pl:
        flash("Plan not found", "err")
        return redirect("/admin/manual-keys")
    back = "/admin/manual-keys?p=%d" % pl["product_id"]
    keys = [k.strip() for k in (request.form.get("keys", "") or "").replace("\r", "\n").split("\n") if k.strip()]
    if not keys:
        flash("Paste at least one key", "err")
        return redirect(back)
    try:
        now = int(time.time())
        c_ = db()
        try:
            c_.executemany("INSERT INTO stock(plan_id,key,created) VALUES(?,?,?)", [(plid, k, now) for k in keys])
            c_.commit()
        finally:
            c_.close()
        msg = "%d key(s) added to %s" % (len(keys), pl["name"])
        if request.form.get("make_manual") and (pl["mode"] or "random") in ("random", "api"):
            q("UPDATE plans SET mode='stock' WHERE id=?", (plid,), commit=True)
            msg += " - plan switched to Manual keys"
        flash(msg, "ok")
    except Exception as e:
        flash("Could not save keys: %s" % e, "err")
    return redirect(back)


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


def send_bounded(chat_id, text, what, wait=7):
    """Send now but NEVER make the page wait longer than `wait` seconds (the send goes on in the background)."""
    box = {}

    def work():
        box["r"] = bot.send_now(chat_id, text, what=what)
    t = threading.Thread(target=work, daemon=True, name="tg-bounded")
    t.start()
    t.join(wait)
    if "r" in box:
        return box["r"]
    return False, ("Telegram did not answer within %d seconds - this server cannot reach Telegram right now "
                   "(see Admin > Telegram > Delivery log)" % wait)


def link_notice(chat_id, username):
    """Tell a freshly linked chat that it is linked; returns (delivered, error) - this IS the delivery test."""
    return send_bounded(chat_id, "✅ <b>%s</b>\n\nYour account <b>%s</b> is now linked. Login codes and purchase "
                                 "alerts will arrive here." % (esc(brand_name()), esc(username)), what="link test (%s)" % username)


def seen_unlinked():
    """People who pressed /start in the bot and are not linked to any reseller yet (newest first)."""
    return q("SELECT * FROM tg_seen WHERE chat_id NOT IN (SELECT tg_chat FROM resellers WHERE tg_chat<>'') "
             "ORDER BY ts DESC LIMIT 12")


@app.route("/admin/resellers", methods=["GET", "POST"])
@admin_required
def admin_resellers():
    if request.method == "POST":
        u, p = request.form.get("username", "").strip(), request.form.get("password", "").strip()
        if not u or not p:
            flash("Username and password required", "err")
        elif same(u.upper(), ADMIN_USER.upper()):
            flash("This username is reserved for the admin", "err")
        elif q("SELECT 1 FROM resellers WHERE lower(username)=lower(?)", (u,), one=True):
            flash("Username already exists", "err")
        else:
            tg = ""                                     # v17.10: resellers are never linked to the bot
            role = "user" if request.form.get("role") == "user" else "reseller"
            if tg and not re.fullmatch(r"-?\d{5,15}", tg):
                flash("Telegram Chat ID must be numbers only", "err")
                return redirect("/admin/resellers")
            try:
                q("INSERT INTO resellers(username,pw,balance,api_key,created,tg_chat,role,otp_on) VALUES(?,?,?,?,?,?,?,?)",
                  (u, generate_password_hash(p), num(request.form.get("credit")), new_api_key(), int(time.time()), tg, role,
                   0 if role == "user" else 1), commit=True)
                if tg:
                    ok, err = link_notice(tg, u)
                    flash("Reseller created. " + ("Telegram linked - test message delivered." if ok
                                                  else "Telegram saved BUT delivery failed: %s" % err), "ok" if ok else "err")
                else:
                    flash("Reseller created", "ok")
            except sqlite3.IntegrityError:
                flash("Username already exists", "err")
        return redirect("/admin/resellers")
    if request.args.get("role") == "user":
        return redirect("/admin/users")
    return render_accounts("reseller")


def render_accounts(kind):
    """ONE list for resellers and ONE for users (never mixed): tabs Active / Banned / Deleted + search."""
    st = request.args.get("st", "active")
    st = st if st in ("active", "banned", "deleted") else "active"
    sq = request.args.get("q", "").strip()
    roles = "r.role='user'" if kind == "user" else "r.role!='user'"
    cond = {"active": "r.deleted=0 AND r.active=1", "banned": "r.deleted=0 AND r.active=0", "deleted": "r.deleted=1"}[st]
    args = []
    if sq:
        cond += " AND lower(r.username) LIKE ?"
        args.append("%" + sq.lower() + "%")
    rows = q("SELECT r.*, (SELECT COUNT(*) FROM license_keys k WHERE k.reseller_id=r.id) kc FROM resellers r "
             "WHERE %s AND %s ORDER BY r.id DESC LIMIT 500" % (roles, cond), args)
    c = q("SELECT SUM(deleted=0 AND active=1) a, SUM(deleted=0 AND active=0) b, SUM(deleted=1) d FROM resellers r WHERE %s" % roles, one=True)
    cnt = dict(active=c["a"] or 0, banned=c["b"] or 0, deleted=c["d"] or 0)
    return render_template("admin_accounts.html", kind=kind, rows=rows, st=st, sq=sq, cnt=cnt, seen=seen_unlinked(),
                           base="/admin/users" if kind == "user" else "/admin/resellers",
                           page="users" if kind == "user" else "resellers")


@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    if request.method == "POST":
        u, p = request.form.get("username", "").strip(), request.form.get("password", "").strip()
        if not u or not p:
            flash("Username and password required", "err")
        elif same(u.upper(), ADMIN_USER.upper()):
            flash("This username is reserved for the admin", "err")
        elif q("SELECT 1 FROM resellers WHERE lower(username)=lower(?)", (u,), one=True):
            flash("Username already exists", "err")
        else:
            try:
                q("INSERT INTO resellers(username,pw,balance,api_key,created,role,otp_on) VALUES(?,?,?,?,?,?,?)",
                  (u, generate_password_hash(p), num(request.form.get("credit")), new_api_key(), int(time.time()), "user", 0), commit=True)
                flash("User created", "ok")
            except sqlite3.IntegrityError:
                flash("Username already exists", "err")
        return redirect("/admin/users")
    return render_accounts("user")


@app.route("/admin/account/<int:rid>/<act>", methods=["POST"])
@admin_required
def admin_account_action(rid, act):
    """Ban / Unban / Delete (soft, can be undone) / Restore / Delete forever (only from the Deleted tab)."""
    r = q("SELECT * FROM resellers WHERE id=?", (rid,), one=True) or abort(404)
    if act == "ban":
        q("UPDATE resellers SET active=0 WHERE id=?", (rid,), commit=True)
        flash("%s is BANNED (cannot login, API stops)" % r["username"], "ok")
    elif act == "unban":
        q("UPDATE resellers SET active=1 WHERE id=?", (rid,), commit=True)
        flash("%s is unbanned" % r["username"], "ok")
    elif act == "delete":
        q("UPDATE resellers SET deleted=1, deleted_at=? WHERE id=?", (int(time.time()), rid), commit=True)
        flash("%s moved to Deleted. You can restore it any time." % r["username"], "ok")
    elif act == "restore":
        q("UPDATE resellers SET deleted=0, deleted_at=0 WHERE id=?", (rid,), commit=True)
        flash("%s restored" % r["username"], "ok")
    elif act == "purge":
        if not r["deleted"]:
            flash("Delete the account first, then you can delete it forever", "err")
        else:
            q("DELETE FROM resellers WHERE id=?", (rid,), commit=True)
            flash("%s deleted forever" % r["username"], "ok")
    nxt = request.form.get("next", "")
    return redirect(nxt if nxt.startswith("/admin/") and "//" not in nxt else ("/admin/users" if r["role"] == "user" else "/admin/resellers"))


@app.route("/admin/reseller/<int:rid>", methods=["GET", "POST"])
@admin_required
def admin_reseller(rid):
    r = q("SELECT * FROM resellers WHERE id=?", (rid,), one=True) or abort(404)
    if request.method == "POST":
        a = request.form.get("action")
        if a == "credit":
            amt = abs(num(request.form.get("amount")))
            op = request.form.get("op", "add")
            if op == "sub":
                amt = -amt
            elif num(request.form.get("amount")) < 0:          # old behaviour: a negative number also deducts
                amt = num(request.form.get("amount"))
            if amt == 0:
                flash("Enter an amount", "err")
            else:
                before = r["balance"]
                q("UPDATE resellers SET balance=MAX(balance+?,0) WHERE id=?", (amt, rid), commit=True)
                after = q("SELECT balance FROM resellers WHERE id=?", (rid,), one=True)["balance"]
                if amt > 0:
                    try:
                        notify_topup(q("SELECT * FROM resellers WHERE id=?", (rid,), one=True), amt, "Admin panel")
                    except Exception:
                        pass
                    flash("Added %s. New balance %s" % (money_txt(amt), money_txt(after)), "ok")
                elif before + amt < 0:
                    flash("Balance cannot go below 0 - deducted only %s. New balance %s" % (money_txt(before - after), money_txt(after)), "ok")
                else:
                    flash("Deducted %s. New balance %s" % (money_txt(-amt), money_txt(after)), "ok")
        elif a == "password" and request.form.get("password", "").strip():
            q("UPDATE resellers SET pw=? WHERE id=?", (generate_password_hash(request.form["password"].strip()), rid), commit=True)
            flash("Password changed", "ok")
        elif a == "toggle":
            q("UPDATE resellers SET active=1-active WHERE id=?", (rid,), commit=True)
        elif a == "make_reseller" and r["role"] == "user":
            q("UPDATE resellers SET role='reseller', otp_on=1 WHERE id=?", (rid,), commit=True)
            set_setting("upg_%d" % rid, "1")
            flash("%s is a RESELLER now" % r["username"], "ok")
        elif a in ("tg", "tg_test"):
            flash("Telegram linking of resellers / users is removed. Only the admin is linked to the bot.", "err")
        elif a == "tg_old":
            tg = request.form.get("tg_chat", "").strip()
            if tg and not re.fullmatch(r"-?\d{5,15}", tg):
                flash("Telegram Chat ID must be numbers only", "err")
            else:
                q("UPDATE resellers SET tg_chat=? WHERE id=?", (tg, rid), commit=True)
                if tg:
                    ok, err = link_notice(tg, r["username"])
                    flash("Telegram linked - test message delivered to that chat." if ok else
                          "Chat ID saved BUT the test message failed: %s" % err, "ok" if ok else "err")
                else:
                    flash("Telegram unlinked", "ok")
        elif a == "tg_alert_toggle":
            if not (r["tg_chat"] or "").strip() and not r["tg_alert"]:
                flash("Save the Telegram Chat ID first, then switch alerts ON", "err")
            else:
                q("UPDATE resellers SET tg_alert=1-COALESCE(tg_alert,0) WHERE id=?", (rid,), commit=True)
                flash("Telegram alerts are now %s for %s" % ("OFF" if r["tg_alert"] else "ON", r["username"]), "ok")
        elif a == "tg_low":
            q("UPDATE resellers SET low_bal=? WHERE id=?", (max(num(request.form.get("low_bal"), 50), 0), rid), commit=True)
            flash("Low balance limit saved", "ok")
        elif a == "tg_test_old":
            if not r["tg_chat"]:
                flash("No Chat ID saved for this reseller yet", "err")
            else:
                ok, err = link_notice(r["tg_chat"], r["username"])
                flash("Test message delivered" if ok else "Delivery failed: %s" % err, "ok" if ok else "err")
        elif a == "otp_toggle":
            q("UPDATE resellers SET otp_on=1-otp_on WHERE id=?", (rid,), commit=True)
            flash("Login verification changed", "ok")
        elif a == "prices":
            for pl in q("SELECT id FROM plans"):
                v = request.form.get("p_%d" % pl["id"], "").strip()
                if v == "":
                    q("DELETE FROM custom_prices WHERE reseller_id=? AND plan_id=?", (rid, pl["id"]), commit=True)
                else:
                    q("INSERT OR REPLACE INTO custom_prices(reseller_id,plan_id,price) VALUES(?,?,?)",
                      (rid, pl["id"], num(v)), commit=True)
            flash("Custom prices saved", "ok")
        elif a in ("delete", "restore", "purge"):
            return admin_account_action(rid, a)
        return redirect("/admin/reseller/%d" % rid)
    cat = catalog(rid)
    devs = q("SELECT * FROM devices WHERE reseller_id=? ORDER BY id DESC", (rid,))
    return render_template("admin_reseller.html", r=r, cat=cat, devs=devs, seen=seen_unlinked(), page="resellers")


@app.route("/admin/gateway", methods=["GET", "POST"])
@admin_required
def admin_gateway():
    test = None
    if request.method == "POST":
        f = request.form
        a = f.get("action")
        if a == "set_gw":                               # Paytm or FamPay (both go through MY gateway)
            want = "fampay" if f.get("gw") == "fampay" else "paytm"
            set_setting("pg_gw", want)
            flash("%s is ON" % ("FamPay" if want == "fampay" else "Paytm"), "ok")
            return redirect("/admin/gateway")
        if a == "save_bn":
            if f.get("bn_key", "").strip():
                set_setting("bn_key", f["bn_key"].strip())
            if f.get("bn_secret", "").strip():
                set_setting("bn_secret", f["bn_secret"].strip())
            try:
                rate = float(f.get("bn_rate", "0") or 0)
            except ValueError:
                rate = 0
            if rate <= 0:
                flash("Enter the rate: how many Rs = 1 USDT (for example 92)", "err")
            else:
                set_setting("bn_rate", str(rate))
                set_setting("bn_on", "1" if f.get("bn_on") else "0")
                flash("Binance settings saved", "ok")
            return redirect("/admin/gateway")
        if a == "test_bn":
            try:
                d = bn_create("TEST%s" % secrets.token_hex(6), 1)
                test = dict(ok=True, svg=safe_svg(d["pay_uri"]) if d["pay_uri"] else "", img=d["qr_url"], order="Binance test (1 USDT, never credited)",
                            who="Binance", note="Connected successfully. Binance Pay API accepted the signed request.")
            except Exception as e:
                test = dict(ok=False, msg=str(e), who="Binance")
        if a == "save_common":
            amts = sorted({int(x) for x in re.split(r"[,\s]+", f.get("amounts", "")) if x.isdigit() and 1 <= int(x) <= 100000})
            if amts:
                set_setting("wallet_amounts", ",".join(str(x) for x in amts[:12]))
            up = f.get("upgrade_price", "").strip()
            if up == "" or up.isdigit():
                set_setting("upgrade_price", up or "0")
            flash("Saved", "ok")
            return redirect("/admin/gateway")
        if a == "save_base":                            # only the Base URL (the quick change after every gateway redeploy)
            base = pg_norm_base(f.get("pg_base", ""))
            if not base:
                flash("Base URL must look like https://your-gateway.onrender.com", "err")
            else:
                set_setting("pg_base", base)
                flash("Base URL saved: %s" % base, "ok")
            return redirect("/admin/gateway")
        if a == "save_pg":
            base = pg_norm_base(f.get("pg_base", "")) if f.get("pg_base", "").strip() else pg_conf()[0]
            if not base:
                flash("Base URL must look like https://your-gateway.onrender.com", "err")
                return redirect("/admin/gateway")
            set_setting("pg_base", base)
            set_setting("pg_gw", "fampay" if f.get("gw") == "fampay" else "paytm")
            if f.get("pg_key", "").strip():
                set_setting("pg_key", f["pg_key"].strip())
            if f.get("pg_secret", "").strip():
                set_setting("pg_secret", f["pg_secret"].strip())
            if not pg_ready():
                flash("Enter your API token to finish the setup", "err")
                return redirect("/admin/gateway")
            a = "test_pg"                               # automatic check: a Rs.1 QR (never credited to anybody)
        if a == "test_pg":
            who = "FamPay" if pg_conf()[2] == "fampay" else "Paytm"
            try:
                oid = "TEST%s" % secrets.token_hex(6)
                d = pg_create(oid, 1)
                test = dict(ok=True, svg=safe_svg(d["pay_uri"]), img=d["qr_url"], order=oid, who=who,
                            note="Connected successfully. %s is ON." % who, pay=d["pay_amount"])
            except Exception as e:
                test = dict(ok=False, msg=str(e), who=who)
    base, key, gw, sec = pg_conf()
    tops = q("SELECT t.*, r.username FROM topups t JOIN resellers r ON r.id=t.reseller_id ORDER BY t.id DESC LIMIT 20")
    return render_template("admin_gateway.html", base=base, pg_gw=gw, pg_tail=key[-4:] if key else "", pg_sec=bool(sec), pg_ok=pg_ready(),
                           test=test, tops=tops, amounts=", ".join(str(x) for x in wallet_amounts()), active=gw_active(),
                           upgrade_price=upgrade_price(), hook=request.host_url.rstrip("/") + "/pgw/webhook",
                           bn_hook=request.host_url.rstrip("/").replace("http://", "https://", 1) + "/bnpay/webhook",
                           bn_tail=bn_conf()[0][-4:], bn_sec=bool(bn_conf()[1]), bn_rate=bn_conf()[2], bn_on=get_setting("bn_on", "0") == "1", page="gateway")


@app.route("/admin/telegram", methods=["GET", "POST"])
@admin_required
def admin_telegram():
    if request.method == "POST":
        f = request.form
        a = f.get("action")
        if a == "save":
            tok = f.get("token", "").strip()
            adm_id = f.get("admin_id", "").strip()
            if adm_id and not re.fullmatch(r"-?\d{5,15}", adm_id):
                flash("Admin Chat ID must be numbers only", "err")
                return redirect("/admin/telegram")
            if tok:
                if not re.fullmatch(r"\d{6,12}:[\w-]{30,60}", tok):
                    flash("That does not look like a bot token (from @BotFather)", "err")
                    return redirect("/admin/telegram")
                ok, info = bot.check_token(tok)            # ask Telegram BEFORE saving
                if not ok and ("unauthorized" in info.lower() or "not found" in info.lower()):
                    flash("Telegram rejected this token - not saved. (%s)" % info, "err")
                    return redirect("/admin/telegram")
                if tok != tg_token():
                    set_setting("tg_token", tok)
                    bot.token_changed()                    # the bot switches to the new token right now
                if ok:
                    flash("New token saved - @%s is running now. No redeploy needed." % info.get("username", "bot"), "ok")
                else:
                    flash("Token saved, but Telegram could not be reached to check it (%s)." % info, "err")
            set_setting("dev_check", "1" if f.get("dev_check") else "0")
            set_setting("otp_global", "1" if f.get("otp_global") else "0")
            set_setting("prem_on", "1" if f.get("prem_on") else "0")
            if not tok:
                flash("Telegram settings saved", "ok")
        elif a == "clear_token":
            flash("For security the bot token cannot be removed - paste a NEW token and press Save to replace it.", "err")
        elif a == "chatid_start":
            new = f.get("new_chat", "").strip()
            if not re.fullmatch(r"-?\d{5,15}", new):
                flash("Chat ID must be numbers only", "err")
            elif rl_blocked("otp-send:-1", 5, 600):
                flash("Too many codes requested. Wait a few minutes.", "err")
            else:
                rl_hit("otp-send:-1")
                session["adm_newchat"] = dict(id=new, ts=int(time.time()))
                send_otp(admin_pseudo(-1, new), force=True)
                flash("A confirm code is being sent to the NEW chat. That chat must have pressed START in the bot.", "ok")
        elif a == "chatid_confirm":
            pend = session.get("adm_newchat")
            if not pend or time.time() - pend["ts"] > 600:
                session.pop("adm_newchat", None)
                flash("Request expired. Start again.", "err")
            elif rl_blocked("otp:-1", 6, 600):
                flash("Too many wrong codes. Wait 10 minutes.", "err")
            else:
                ok, msg = check_otp(-1, f.get("code", ""))
                if ok:
                    old = tg_admin()
                    set_setting("tg_admin", pend["id"])
                    session.pop("adm_newchat", None)
                    note = "<blockquote>\U0001F510 <b>ADMIN CHAT CHANGED</b></blockquote>\nAdmin login codes and alerts now go to the chat ending <code>%s</code>." % esc(pend["id"][-4:])
                    if old and old != pend["id"]:
                        bot.send(old, note, what="admin chat changed (old)")
                    bot.send(pend["id"], note, what="admin chat changed (new)")
                    flash("Admin Chat ID changed. Login codes now go to the new chat.", "ok")
                else:
                    rl_hit("otp:-1")
                    flash(msg, "err")
        elif a == "chatid_cancel":
            session.pop("adm_newchat", None)
        elif a == "reset_emoji":
            set_setting("emoji_map", "{}")
            bot.refresh_map()
            schedule_emoji_backup()
            flash("Emoji choices reset to automatic", "ok")
        elif a == "test_alert":
            ok, err = send_bounded(tg_admin(), purchase_text("SAMPLE PRODUCT", 1, 20, 824.44, "5456242 : 49892697",
                                                             "panel", buyer=brand_name()), what="sample alert")
            flash("Sample alert sent to your Telegram" if ok else "Could not send: %s" % err, "ok" if ok else "err")
        elif a == "test":
            ok, err = send_bounded(tg_admin(), "\u2705 <b>%s</b>\nTest message - the bot is connected." % esc(brand_name()),
                                   what="admin test")
            flash("Test message sent to your Telegram" if ok else "Could not send: %s" % err, "ok" if ok else "err")
        elif a == "test_reseller" and False:
            r = q("SELECT * FROM resellers WHERE id=?", (int(num(f.get("id"))),), one=True)
            if r and r["tg_chat"]:
                ok, err = link_notice(r["tg_chat"], r["username"])
                flash(("Delivered to %s" % r["username"]) if ok else "%s: delivery FAILED - %s" % (r["username"], err),
                      "ok" if ok else "err")
            else:
                flash("That reseller has no Chat ID", "err")
        return redirect("/admin/telegram")
    me = bot.me_cached() if tg_token() else None
    rs = q("SELECT id, username, tg_chat, otp_on, notify, active FROM resellers ORDER BY (tg_chat='' OR tg_chat IS NULL), username")
    return render_template("admin_telegram.html", me=me, has_token=bool(tg_token()), tail=tg_token()[-4:],
                           admin_id=tg_admin(), dev_check=get_setting("dev_check", "1") == "1",
                           otp_global=otp_global_on(), rs=rs, log=list(bot.log), poll_err=bot.poll_err, me_err=bot.me_err,
                           sent_ok=bot.sent_ok, sent_fail=bot.sent_fail, seen=seen_unlinked(),
                           tok_src=tg_token_source(), roles=emoji_roles(), extras=emoji_extras(),
                           cat=bot.catalog(), n_over=len(emoji_overrides()),
                           active=dev_check_on(), prem_on=get_setting("prem_on", "1") == "1", prem=bot.status(), page="telegram",
                           chat_pending=mask_id((session.get("adm_newchat") or {}).get("id", "")), admin_mask=mask_id(tg_admin()))


def emoji_roles():
    ov, out = emoji_overrides(), []
    for em, label in EMOJI_ROLES:
        cid = ov.get(em) or bot.emap.get(em.replace("\ufe0f", "")) or ""
        out.append(dict(em=em, label=label, cid=cid, manual=bool(ov.get(em)), mine=ov.get(em) or ""))
    return out


def emoji_extras():
    """Emoji added by the admin that are not in the fixed list (Admin > Telegram > Emoji ID manager > Add any emoji)."""
    known = {e for e, _ in EMOJI_ROLES}
    return [dict(em=k, cid=v) for k, v in emoji_overrides().items() if k not in known]


def valid_emoji_key(k):
    """A plain emoji (1-12 characters, no letters/digits/spaces) that can be replaced by a premium emoji."""
    k = (k or "").strip()
    return 0 < len(k) <= 12 and not re.search(r"[A-Za-z0-9\s<>&]", k) and any(ord(c) > 0x2000 for c in k)


@app.route("/picon/<int:pid>")
def product_icon(pid):
    r = q("SELECT icon FROM products WHERE id=?", (pid,), one=True)
    if not r or not r["icon"]:
        abort(404)
    resp = make_response(base64.b64decode(r["icon"]))
    resp.headers["Content-Type"] = "image/png"
    resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp


@app.route("/emoji/<cid>")
def public_emoji(cid):
    """Picture of a Telegram premium emoji (product icon). Only for logged-in people."""
    if not (session.get("rid") or session.get("admin")) or not re.fullmatch(r"\d{5,25}", cid):
        abort(404)
    return admin_emoji_thumb.__wrapped__(cid)


@app.route("/admin/emoji/thumb/<cid>")
@admin_required
def admin_emoji_thumb(cid):
    if not re.fullmatch(r"\d{5,25}", cid):
        abort(404)
    try:
        t = bot.thumb(cid)
    except Exception:
        t = None
    if not t:
        abort(404)
    resp = make_response(t[0])
    resp.headers["Content-Type"] = t[1]
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@app.route("/admin/emoji/set", methods=["POST"])
@admin_required
def admin_emoji_set():
    """Set / clear the premium emoji ID of ONE plain emoji (any emoji, not only the fixed list)."""
    d = request.get_json(silent=True) or {}
    role, cid = str(d.get("role") or "").strip(), re.sub(r"\D", "", str(d.get("cid") or ""))
    if not valid_emoji_key(role) or (cid and not re.fullmatch(r"\d{5,25}", cid)):
        return jsonify(ok=False, msg="Wrong emoji or ID (the ID is only digits, e.g. 5368324170671202286)"), 400
    found = None
    if cid:
        try:                                    # ask Telegram if this ID really exists (so a typo is caught at once)
            found = bool(bot.lookup(cid))
        except Exception:
            found = None                        # Telegram not reachable now: still save it
    m = emoji_overrides()
    if cid:
        m[role] = cid
    else:
        m.pop(role, None)
    set_setting("emoji_map", json.dumps(m))
    bot.refresh_map()
    schedule_emoji_backup()
    return jsonify(ok=True, cid=cid or bot.emap.get(role.replace("\ufe0f", ""), ""), found=found)


@app.route("/admin/emoji/bulk", methods=["POST"])
@admin_required
def admin_emoji_bulk():
    """Paste many lines like  '✅ 5368324170671202286'  (exactly what the bot's /emojis reply gives)."""
    txt = str((request.get_json(silent=True) or {}).get("text") or "")
    m, n = emoji_overrides(), 0
    for line in txt.splitlines():
        mm = re.match(r"^\s*(\S{1,12}?)\s*[:=>\-\u2192]*\s*(\d{5,25})\s*$", line)
        if mm and valid_emoji_key(mm.group(1)):
            m[mm.group(1)] = mm.group(2)
            n += 1
    if n:
        set_setting("emoji_map", json.dumps(m))
        bot.refresh_map()
        schedule_emoji_backup()
    return jsonify(ok=bool(n), n=n)


@app.route("/admin/devices", methods=["GET", "POST"])
@admin_required
def admin_devices():
    if request.method == "POST":
        a, did = request.form.get("action"), int(num(request.form.get("id")))
        if a in ("approve", "deny"):
            device_decision(did, a == "approve")
        elif a == "delete":
            q("DELETE FROM devices WHERE id=?", (did,), commit=True)
        flash("Done", "ok")
        return redirect("/admin/devices")
    rows = q("SELECT d.*, r.username FROM devices d JOIN resellers r ON r.id=d.reseller_id "
             "ORDER BY (d.status='pending') DESC, d.id DESC LIMIT 300")
    return render_template("admin_devices.html", rows=rows, page="devices")


@app.route("/admin/broadcast", methods=["GET", "POST"])
@admin_required
def admin_broadcast():
    if request.method == "POST":
        f = request.form
        if f.get("action") == "delete":
            bid = int(num(f.get("id")))
            q("DELETE FROM broadcasts WHERE id=?", (bid,), commit=True)
            q("DELETE FROM broadcast_reads WHERE broadcast_id=?", (bid,), commit=True)
        elif not f.get("body", "").strip():
            flash("Write a message first", "err")
        else:
            tgt = f.get("target", "all")
            rid = None if tgt == "all" else int(num(tgt))
            q("INSERT INTO broadcasts(reseller_id,title,body,created) VALUES(?,?,?,?)",
              (rid, f.get("title", "").strip(), f["body"].strip(), int(time.time())), commit=True)
            flash("Broadcast sent to %s" % ("all resellers" if rid is None else "1 reseller"), "ok")
        return redirect("/admin/broadcast")
    rows = q("SELECT b.*, r.username FROM broadcasts b LEFT JOIN resellers r ON r.id=b.reseller_id ORDER BY b.id DESC LIMIT 50")
    return render_template("admin_broadcast.html", rows=rows, rs=q("SELECT id, username FROM resellers ORDER BY username"),
                           page="broadcast")


@app.route("/admin/music/metadata", methods=["POST"])
@admin_required
def admin_music_metadata():
    info = _music_link_info(request.form.get("url", ""))
    if not info:
        return jsonify({"ok": False, "error": "Paste a valid YouTube or Spotify link."}), 400
    return jsonify({"ok": True, "title": info.get("title") or "", "kind": info["kind"], "url": info["url"], "embed_url": info.get("embed_url", "")})


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
        elif request.form.get("action") == "move":
            rows_ = [x["id"] for x in q("SELECT id FROM music ORDER BY pos, id")]
            try:
                i = rows_.index(int(request.form.get("id", "0")))
            except ValueError:
                i = -1
            j = i - 1 if request.form.get("dir") == "up" else i + 1
            if i >= 0 and 0 <= j < len(rows_):
                rows_[i], rows_[j] = rows_[j], rows_[i]
                for n_, mid_ in enumerate(rows_, 1):
                    q("UPDATE music SET pos=? WHERE id=?", (n_, mid_), commit=True)
        elif q("SELECT COUNT(*) FROM music", one=True)[0] >= MAX_MUSIC:
            flash("Maximum %d songs allowed" % MAX_MUSIC, "err")
        else:
            title = request.form.get("title", "").strip()
            f = request.files.get("file")
            url = request.form.get("url", "").strip()
            if f and f.filename:
                ext = os.path.splitext(f.filename)[1].lower()
                if ext not in (".mp3", ".m4a", ".aac", ".wav", ".ogg", ".oga", ".opus", ".flac", ".webm", ".mp4"):
                    flash("Audio files only (mp3, m4a, wav, ogg, flac ...)", "err")
                    return redirect("/admin/music")
                name = "%s_%s%s" % (secrets.token_hex(4), secure_filename(os.path.splitext(f.filename)[0])[:60], ext)
                try:
                    f.save(os.path.join(MUSIC_DIR, name))
                except OSError as e:
                    flash("Could not save the file: %s" % str(e)[:100], "err")
                    return redirect("/admin/music")
                # an uploaded file is added straight away (it must NOT go through the "download from URL" step below)
                q("INSERT INTO music(title,url,pos) VALUES(?,?,(SELECT COALESCE(MAX(pos),0)+1 FROM music))",
                  (title or os.path.splitext(f.filename)[0][:200], "/media/" + name), commit=True)
                flash("Song uploaded and added to Music.", "ok")
                return redirect("/admin/music")
            if url:
                link_info = _music_link_info(url)
                if link_info:
                    # YouTube and Spotify remain on their official embed players.
                    url = link_info["url"]
                    title = title or link_info.get("title") or ("YouTube song" if link_info["kind"] == "youtube" else "Spotify song")
                    q("INSERT INTO music(title,url,pos) VALUES(?,?,(SELECT COALESCE(MAX(pos),0)+1 FROM music))", (title, url), commit=True)
                    flash("Song link added. It will play using the official provider player.", "ok")
                else:
                    # A direct audio file URL is downloaded into this website's server storage.
                    try:
                        local_url, detected_title = _download_direct_audio(url)
                        q("INSERT INTO music(title,url,pos) VALUES(?,?,(SELECT COALESCE(MAX(pos),0)+1 FROM music))", (title or detected_title, local_url), commit=True)
                        flash("Audio downloaded to website storage and added to Music.", "ok")
                    except ValueError as e:
                        flash(str(e), "err")
            else:
                flash("Upload a file or paste a direct audio URL", "err")
        return redirect("/admin/music")
    return render_template("admin_music.html", rows=q("SELECT * FROM music ORDER BY pos, id"), mx=MAX_MUSIC, page="music")


# ---------------------------------------------------------------- admin: main API
@app.route("/admin/main-api", methods=["GET", "POST"])
@admin_required
def admin_main_api():
    if request.method == "POST":
        if request.form.get("action") == "toggle":
            set_setting("api_tahir_enabled", "0" if api_enabled("tahir") else "1")
            flash("Tahir API is now %s." % ("ON" if api_enabled("tahir") else "OFF"), "ok")
            return redirect("/admin/main-api")
        if request.form.get("action") == "save":
            tok = request.form.get("token", "").strip()
            if tok and tok != prov_token():
                set_setting("tahir_token", tok)
                set_setting("tahir_catalog", "")          # other account -> old product list is useless
        st = prov_status()
        if st["ok"]:
            flash("Connect successful - balance %s (USD %s)" % (_cur(st["balance"]), "%g" % st.get("balance_usd", 0)), "ok")
        else:
            flash("Not connected: %s" % st["msg"], "err")
        return redirect("/admin/main-api")
    try:
        st = json.loads(get_setting("tahir_status"))
    except ValueError:
        st = None
    tok = prov_token()
    return render_template("admin_mapi.html", tail=tok[-4:] if tok else "", st=st, enabled=api_enabled("tahir"), page="mapi")


@app.route("/admin/main-api/products", methods=["GET", "POST"])
@admin_required
def admin_main_api_products():
    mr0, mu0 = markups()
    if request.method == "POST":
        mr = max(num(request.form.get("mk_res"), mr0), 0.0)
        mu = max(num(request.form.get("mk_user"), mu0), 0.0)
        set_setting("markup_reseller", ("%g" % mr))
        set_setting("markup_user", ("%g" % mu))
        scope = request.form.get("scope")
        try:
            cat = load_catalog(refresh=(scope in ("sync", "new")))      # "new" always asks the API for its newest list
        except Exception as e:
            flash("Could not load products: %s" % e, "err")
            return redirect("/admin/main-api/products")
        rows = catalog_plans(cat)

        def prices(cost):
            return round(cost * (1 + mr / 100.0), 2), round(cost * (1 + mu / 100.0), 2)
        if scope == "sync":                      # re-price every plan already imported, using fresh costs
            n = 0
            for pl in q("SELECT id, prov_pid FROM plans WHERE prov_src='tahir'"):
                hit = rows.get(pl["prov_pid"])
                if hit:
                    cost = float(hit[1].get("price") or 0)
                    rp, up = prices(cost)
                    d_days, d_hours, d_name = duration_parts(hit[1].get("name"), hit[1])
                    q("UPDATE plans SET name=?, days=?, hours=?, cost=?, price=?, user_price=? WHERE id=?",
                      (d_name, d_days, d_hours, cost, rp, up, pl["id"]), commit=True)
                    n += 1
            flash("Prices updated for %d imported plan(s): reseller +%g%%, user +%g%%." % (n, mr, mu), "ok")
            return redirect("/admin/main-api/products")
        have = set()
        for r_ in q("SELECT prov_pid FROM plans WHERE prov_src='tahir'"):
            try:
                have.add(int(r_[0]))
            except (TypeError, ValueError):
                pass
        if scope == "all":
            ids = list(rows)
        elif scope == "new":                     # v18.2: only plans that are not on the site yet
            ids = [pid_ for pid_ in rows if pid_ not in have]
            if not ids:
                flash("No new products - everything from the Tahir API is already on your site.", "ok")
                return redirect("/admin/main-api/products")
        else:                                    # selected (plan ids are numbers, the form sends text)
            ids = []
            for x in request.form.getlist("pid"):
                try:
                    if int(x) in rows and int(x) not in ids:
                        ids.append(int(x))
                except (TypeError, ValueError):
                    pass
        if not ids:
            flash("Nothing selected. Tick the products / plans you want to add.", "err")
            return redirect("/admin/main-api/products")
        overwrite = bool(request.form.get("overwrite"))
        new_pl = upd = skip = new_pr = 0
        for pid in ids:
            p, pl = rows[pid]
            cost = float(pl.get("price") or 0)
            rp, up = prices(cost)
            ex = q("SELECT id FROM plans WHERE prov_pid=? AND prov_src='tahir'", (pid,), one=True)
            if ex:
                d_days, d_hours, d_name = duration_parts(pl.get("name"), pl)
                if overwrite:
                    q("UPDATE plans SET name=?, days=?, hours=?, cost=?, price=?, user_price=? WHERE id=?",
                      (d_name, d_days, d_hours, cost, rp, up, ex["id"]), commit=True)
                    upd += 1
                else:
                    q("UPDATE plans SET name=?, days=?, hours=? WHERE id=?", (d_name, d_days, d_hours, ex["id"]), commit=True)
                    skip += 1
                continue
            pname = (p.get("name") or "Product %s" % p.get("product_id")).strip()
            pr = q("SELECT id FROM products WHERE lower(src_name)=lower(?) OR lower(name)=lower(?) ORDER BY id", (pname, pname), one=True)
            if pr:
                prid = pr["id"]
            else:
                prid = q("INSERT INTO products(name,src_name,pos) VALUES(?,?,?)", (pname, pname, next_prod_pos()), commit=True)
                new_pr += 1
            days, hours, name = duration_parts(pl.get("name"), pl)
            q("INSERT INTO plans(product_id,name,days,hours,price,user_price,cost,mode,prov_pid,prov_src) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (prid, name, max(days, 1), hours, rp, up, cost, "provider", pid, "tahir"), commit=True)
            new_pl += 1
        flash("Added %d plan(s) (%d new product(s)). Prices updated: %d. Already there (skipped): %d."
              % (new_pl, new_pr, upd, skip), "ok")
        return redirect("/admin/main-api/products")
    cat, err = None, None
    try:
        stale = True
        try:
            stale = time.time() - int(json.loads(get_setting("tahir_catalog")).get("ts") or 0) > 300     # v18.2: new products show up by themselves
        except (ValueError, AttributeError, TypeError):
            pass
        cat = load_catalog(refresh=bool(request.args.get("refresh")) or stale)
    except Exception as e:
        err = str(e)
        try:
            cat = json.loads(get_setting("tahir_catalog"))
        except ValueError:
            cat = None
    if err:
        flash("Could not load products: %s" % err, "err")
    mine = {int(r["prov_pid"]): r for r in q("SELECT prov_pid, price, user_price FROM plans WHERE prov_src='tahir' AND prov_pid IS NOT NULL")}
    groups = []
    for p in (cat or {}).get("products", []):
        plans = []
        for pl in p.get("plans") or []:
            try:
                pid = int(pl["plan_id"])
            except (KeyError, TypeError, ValueError):
                continue
            m = mine.get(pid)
            plans.append(dict(pid=pid, name=pl.get("name") or "", cost=float(pl.get("price") or 0),
                              avail=pl.get("available", True), mine=m))
        groups.append(dict(id=p.get("product_id"), name=(p.get("name") or "Product").strip(), plans=plans))
    return render_template("admin_mapi_products.html", groups=groups, cat=cat, mr=mr0, mu=mu0, page="mapi")


# ---------------------------------------------------------------- admin: VIP SELLER HUB API (second main API)
@app.route("/admin/vsh", methods=["GET", "POST"])
@admin_required
def admin_vsh():
    if request.method == "POST":
        act = request.form.get("action")
        if act == "toggle":
            set_setting("api_vsh_enabled", "0" if api_enabled("vsh") else "1")
            flash("VIP Seller Hub API is now %s." % ("ON" if api_enabled("vsh") else "OFF"), "ok")
            return redirect("/admin/vsh")
        if act == "save":
            base = request.form.get("base", "").strip()
            if base:
                base = re.sub(r"/+$", "", base)
                if not re.match(r"^https?://[^\s]+$", base):
                    flash("Base URL must start with https://", "err")
                    return redirect("/admin/vsh")
                if base != vsh_base():
                    set_setting("vsh_base", base)
                    set_setting("vsh_catalog", "")
            tok = request.form.get("token", "").strip()
            if tok and tok != vsh_token():
                set_setting("vsh_token", tok)
                set_setting("vsh_catalog", "")            # other account -> old product list is useless
            rate = num(request.form.get("rate"), vsh_rate())
            if rate > 0 and rate != vsh_rate():
                set_setting("vsh_rate", "%g" % rate)
                set_setting("vsh_catalog", "")
        st = vsh_status()
        if st["ok"]:
            flash("Connect successful - balance %s" % (_cur(st["balance"]) if st.get("has_bal") else "(see raw answer below)"), "ok")
        else:
            flash("Not connected: %s" % st["msg"], "err")
        return redirect("/admin/vsh")
    try:
        st = json.loads(get_setting("vsh_status"))
    except ValueError:
        st = None
    tok = vsh_token()
    return render_template("admin_vsh.html", tail=tok[-4:] if tok else "", st=st, base=vsh_base(), rate=vsh_rate(), enabled=api_enabled("vsh"), page="vsh")


@app.route("/admin/vsh/products", methods=["GET", "POST"])
@admin_required
def admin_vsh_products():
    mr0, mu0 = vsh_markups()
    if request.method == "POST":
        mr = max(num(request.form.get("mk_res"), mr0), 0.0)
        mu = max(num(request.form.get("mk_user"), mu0), 0.0)
        set_setting("vsh_markup_reseller", "%g" % mr)
        set_setting("vsh_markup_user", "%g" % mu)
        scope = request.form.get("scope")
        try:
            cat = vsh_load_catalog(refresh=(scope == "sync"))
        except Exception as e:
            flash("Could not load products: %s" % e, "err")
            return redirect("/admin/vsh/products")
        rows = {}
        for p in cat.get("products", []):
            for pl in p.get("plans") or []:
                rows[str(pl["plan_id"])] = (p, pl)

        def prices(cost):
            return round(cost * (1 + mr / 100.0), 2), round(cost * (1 + mu / 100.0), 2)
        if scope == "sync":                      # re-price every plan already imported, using fresh costs
            n = 0
            for pl in q("SELECT id, prov_pid FROM plans WHERE prov_src='vsh'"):
                hit = rows.get(str(pl["prov_pid"]))
                if hit:
                    cost = float(hit[1].get("price") or 0)
                    rp, up = prices(cost)
                    d_days, d_hours, d_name = duration_parts(hit[1].get("name"), hit[1])
                    q("UPDATE plans SET name=?, days=?, hours=?, cost=?, price=?, user_price=? WHERE id=?",
                      (d_name, d_days, d_hours, cost, rp, up, pl["id"]), commit=True)
                    n += 1
            flash("Prices updated for %d imported plan(s): reseller +%g%%, user +%g%%." % (n, mr, mu), "ok")
            return redirect("/admin/vsh/products")
        if scope == "all":
            ids = list(rows)
        else:
            ids = [str(x) for x in request.form.getlist("pid") if str(x) in rows]
        if not ids:
            flash("Nothing selected. Tick the products / plans you want to add.", "err")
            return redirect("/admin/vsh/products")
        overwrite = bool(request.form.get("overwrite"))
        new_pl = upd = skip = new_pr = 0
        for pid in ids:
            p, pl = rows[pid]
            cost = float(pl.get("price") or 0)
            rp, up = prices(cost)
            meta = json.dumps(dict(balamod=bool(pl.get("balamod")), mode=pl.get("mode") or ""))
            ex = q("SELECT id FROM plans WHERE prov_pid=? AND prov_src='vsh'", (str(pid),), one=True)
            if ex:
                d_days, d_hours, d_name = duration_parts(pl.get("name"), pl)
                if overwrite:
                    q("UPDATE plans SET name=?, days=?, hours=?, cost=?, price=?, user_price=?, prov_meta=? WHERE id=?",
                      (d_name, d_days, d_hours, cost, rp, up, meta, ex["id"]), commit=True)
                    upd += 1
                else:
                    q("UPDATE plans SET name=?, days=?, hours=?, prov_meta=? WHERE id=?",
                      (d_name, d_days, d_hours, meta, ex["id"]), commit=True)
                    skip += 1
                continue
            pname = (p.get("name") or "Product").strip()
            # Merge identical product names from Tahir and VIP Seller Hub into one panel product.
            pr = q("SELECT id FROM products WHERE lower(name)=lower(?) OR lower(src_name)=lower(?) ORDER BY id",
                   (pname, pname), one=True)
            if pr:
                prid = pr["id"]
            else:
                prid = q("INSERT INTO products(name,src_name,pos) VALUES(?,?,?)", (pname, pname, next_prod_pos()), commit=True)
                new_pr += 1
            days, hours, name = duration_parts(pl.get("name"), pl)
            q("INSERT INTO plans(product_id,name,days,hours,price,user_price,cost,mode,prov_pid,prov_src,prov_meta) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
              (prid, name, max(days, 1), hours, rp, up, cost, "provider", pid, "vsh", meta), commit=True)
            new_pl += 1
        flash("Added %d plan(s) (%d new product(s)). Prices updated: %d. Already there (skipped): %d."
              % (new_pl, new_pr, upd, skip), "ok")
        return redirect("/admin/vsh/products")
    cat, err = None, None
    try:
        cat = vsh_load_catalog(refresh=bool(request.args.get("refresh")))
    except Exception as e:
        err = str(e)
        try:
            cat = json.loads(get_setting("vsh_catalog"))
        except ValueError:
            cat = None
    if err:
        flash("Could not load products: %s" % err, "err")
    mine = {str(r["prov_pid"]): r for r in q("SELECT prov_pid, price, user_price FROM plans WHERE prov_src='vsh'")}
    groups = []
    for p in (cat or {}).get("products", []):
        plans = []
        for pl in p.get("plans") or []:
            plans.append(dict(pid=str(pl["plan_id"]), name=pl.get("name") or "", cost=float(pl.get("price") or 0),
                              avail=pl.get("available", True), bala=pl.get("balamod"), mode=pl.get("mode") or "",
                              mine=mine.get(str(pl["plan_id"]))))
        groups.append(dict(id=p.get("product_id"), name=(p.get("name") or "Product").strip(), plans=plans))
    return render_template("admin_vsh_products.html", groups=groups, cat=cat, mr=mr0, mu=mu0, page="vsh")


# ---------------------------------------------------------------- logo + look (admin)
LOGO_MAX_BYTES = 8 * 1024 * 1024


@app.route("/logo")
def logo_image():
    d = get_setting("logo_data")
    if not d:
        abort(404)
    resp = Response(base64.b64decode(d), mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=604800"      # url carries ?v=<version>, so changes show at once
    return resp


BG_MAX_BYTES = 12 * 1024 * 1024
BG_DIM = {"low": 0.25, "mid": 0.45, "high": 0.65}


@app.route("/bg")
def bg_image():
    d = get_setting("bg_data")
    if not d:
        abort(404)
    resp = Response(base64.b64decode(d), mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "public, max-age=604800"      # url carries ?v=<version>, so changes show at once
    return resp


@app.after_request
def inject_background(resp):
    """Shows the admin's background picture on EVERY page (login, dashboard, admin ...)."""
    try:
        if resp.status_code != 200 or resp.mimetype != "text/html" or resp.direct_passthrough:
            return resp
        ver = get_setting("bg_ver")
        if not ver or not get_setting("bg_data"):
            return resp
        html = resp.get_data(as_text=True)
        if "<body" not in html or 'id="sitebg"' in html:
            return resp
        dim = BG_DIM.get(get_setting("bg_dim", "mid"), 0.45)
        css = ("<style id=sitebg-css>html body{background:transparent!important;background-image:none!important}"
               "#sitebg{position:fixed;inset:0;z-index:-3;background:#000 url(/bg?v=%s) center/cover no-repeat;pointer-events:none}"
               "#sitebg::after{content:'';position:absolute;inset:0;background:rgba(4,8,18,%s)}"
               "html[data-mode=light] #sitebg::after{background:rgba(255,255,255,%s)}"
               "</style>" % (_html.escape(ver), dim, round(dim * 0.7, 2)))
        html = html.replace("</head>", css + "</head>", 1)
        html = re.sub(r"(<body[^>]*>)", r'\1<div id="sitebg"></div>', html, count=1)
        resp.set_data(html)
    except Exception as e:
        print("[bg] %s" % e)
    return resp


# ---- v18: forms are sent in the background (no full page refresh) -> nav.js
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nav.js"), encoding="utf-8") as _fh:
        NAV_JS = _fh.read()
except OSError:
    NAV_JS = ""
NAV_VER = str(len(NAV_JS))


@app.route("/_nav.js")
def nav_js():
    resp = Response(NAV_JS, mimetype="application/javascript")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.after_request
def inject_nav(resp):
    try:
        if (NAV_JS and resp.status_code == 200 and resp.mimetype == "text/html" and not resp.direct_passthrough):
            html = resp.get_data(as_text=True)
            if "</body>" in html and "/_nav.js" not in html and 'class="wrap"' in html.replace("class=wrap", 'class="wrap"'):
                resp.set_data(html.replace("</body>", '<script src="/_nav.js?v=%s" defer></script></body>' % NAV_VER, 1))
    except Exception as e:
        print("[nav] %s" % e)
    return resp


@app.route("/admin/branding", methods=["GET", "POST"])
@admin_required
def admin_branding():
    if request.method == "POST":
        a = request.form.get("action")
        if a == "logo":
            f = request.files.get("logo")
            raw = f.read(LOGO_MAX_BYTES + 1) if f and f.filename else b""
            if not raw:
                flash("Choose an image first", "err")
            elif len(raw) > LOGO_MAX_BYTES:
                flash("Image is too big (max 8 MB)", "err")
            else:
                try:
                    import io
                    from PIL import Image
                    im = Image.open(io.BytesIO(raw))
                    im.load()
                    im = im.convert("RGBA")
                    im.thumbnail((256, 256))
                    buf = io.BytesIO()
                    im.save(buf, "PNG", optimize=True)
                    set_setting("logo_data", base64.b64encode(buf.getvalue()).decode())
                    set_setting("logo_ver", str(int(time.time())))
                    flash("Logo saved. It now shows in the menu, on the login page and on the dashboard.", "ok")
                except Exception:
                    flash("This file is not a valid image (use PNG, JPG, WEBP or GIF)", "err")
        elif a == "remove":
            set_setting("logo_data", "")
            set_setting("logo_ver", "")
            flash("Logo removed - the default icon is shown again", "ok")
        elif a == "bg":
            f = request.files.get("bg")
            raw = f.read(BG_MAX_BYTES + 1) if f and f.filename else b""
            if not raw:
                flash("Choose an image first", "err")
            elif len(raw) > BG_MAX_BYTES:
                flash("Image is too big (max 12 MB)", "err")
            else:
                try:
                    import io
                    from PIL import Image, ImageOps
                    im = Image.open(io.BytesIO(raw))
                    im.load()
                    im = ImageOps.exif_transpose(im).convert("RGB")
                    im.thumbnail((1600, 1600))
                    buf = io.BytesIO()
                    im.save(buf, "JPEG", quality=82, optimize=True)
                    set_setting("bg_data", base64.b64encode(buf.getvalue()).decode())
                    set_setting("bg_ver", str(int(time.time())))
                    flash("Background saved. It now shows on every page (login, dashboard, admin).", "ok")
                except Exception:
                    flash("This file is not a valid image (use PNG, JPG, WEBP or GIF)", "err")
        elif a == "bg_dim":
            set_setting("bg_dim", request.form.get("dim") if request.form.get("dim") in BG_DIM else "mid")
            flash("Saved", "ok")
        elif a == "bg_remove":
            set_setting("bg_data", "")
            set_setting("bg_ver", "")
            flash("Background removed", "ok")
        elif a == "site_name":
            nm = clean_site_name(request.form.get("site_name"))
            if request.form.get("reset"):
                set_setting("site_name", "")
                flash("Site name reset to the default: %s" % BRAND, "ok")
            elif not nm:
                flash("Site name must be 1-40 characters (no < > symbols)", "err")
            else:
                set_setting("site_name", nm)
                flash("Site name saved: %s. It is now used everywhere on the website." % nm, "ok")
        elif a == "look":
            set_setting("site_mode", "light" if request.form.get("mode") == "light" else "dark")
            set_setting("signup_on", "1" if request.form.get("signup") else "0")
            flash("Saved", "ok")
        return redirect("/admin/branding")
    return render_template("admin_branding.html", site_name=brand_name(), default_name=BRAND, has_logo=bool(get_setting("logo_data")), has_bg=bool(get_setting("bg_data")), bg_dim=get_setting("bg_dim", "mid"),
                           mode=get_setting("site_mode", "dark"), signup=signup_on(), page="branding")


# ---------------------------------------------------------------- admin: backup / restore
RESTORE_KEEP = ("tg_token", "tg_admin", "adm_linked", "tg_link_required")
BACKUP_TABLES = ["products", "plans", "resellers", "custom_prices", "license_keys", "stock", "settings",
                 "topups", "broadcasts", "broadcast_reads", "devices"]      # music has its OWN backup (below)


@app.route("/admin/backup")
@admin_required
def admin_backup():
    counts = {t: q("SELECT COUNT(*) FROM %s" % t, one=True)[0] for t in BACKUP_TABLES}
    songs = q("SELECT * FROM music ORDER BY pos, id")
    size = 0
    for m in songs:
        try:
            size += os.path.getsize(os.path.join(MUSIC_DIR, os.path.basename(m["url"]))) if m["url"].startswith("/media/") else 0
        except OSError:
            pass
    last = int(get_setting("auto_backup_last", "0") or 0)
    return render_template("admin_backup.html", counts=counts, songs=len(songs), msize=round(size / 1048576, 1), page="backup",
                           ab_on=auto_backup_on(), ab_hours=auto_backup_hours(), ab_status=get_setting("auto_backup_status", ""),
                           ab_last=time.strftime("%d %b %Y, %I:%M %p", time.gmtime(last + TZ_OFFSET)) if last else "",
                           ab_files=sorted(os.listdir(AUTO_BACKUP_DIR))[-AUTO_BACKUP_KEEP:][::-1] if os.path.isdir(AUTO_BACKUP_DIR) else [])


def build_backup():
    """Whole-panel snapshot (same format the Restore button reads). Music is NOT inside."""
    out = dict(app="reseller-panel", version=1, created=int(time.time()), tables={})
    for t in BACKUP_TABLES:
        out["tables"][t] = [dict(r) for r in q("SELECT * FROM %s" % t)]
    name = "backup_%s.json" % time.strftime("%Y%m%d_%H%M", time.gmtime(time.time() + TZ_OFFSET))
    return name, json.dumps(out, ensure_ascii=False).encode("utf-8")


# ---- AUTOMATIC backup every 12 hours: saved on the server + sent to the admin's Telegram chat
AUTO_BACKUP_DIR = os.path.join(DATA_DIR, "auto_backups")
AUTO_BACKUP_KEEP = 10                                                    # newest files kept on the server
AUTO_BACKUP_LOCK = threading.Lock()


def auto_backup_hours():
    try:
        return max(1, min(168, int(get_setting("auto_backup_hours", "12"))))
    except ValueError:
        return 12


def auto_backup_on():
    return get_setting("auto_backup", "1") == "1"


def run_auto_backup():
    """Make one backup now. Returns (ok, message). Never raises."""
    if not AUTO_BACKUP_LOCK.acquire(blocking=False):
        return False, "A backup is already running"
    try:
        name, raw = build_backup()
        os.makedirs(AUTO_BACKUP_DIR, exist_ok=True)
        with open(os.path.join(AUTO_BACKUP_DIR, name), "wb") as f:
            f.write(raw)
        files = sorted(x for x in os.listdir(AUTO_BACKUP_DIR) if x.startswith("backup_") and x.endswith(".json"))
        for old_f in files[:-AUTO_BACKUP_KEEP]:
            try:
                os.remove(os.path.join(AUTO_BACKUP_DIR, old_f))
            except OSError:
                pass
        set_setting("auto_backup_last", str(int(time.time())))
        tok, adm = tg_token(), tg_admin()
        if not tok or not adm:
            set_setting("auto_backup_status", "Saved on server only - connect the Telegram bot + admin chat to receive it")
            return False, "Saved on the server, but Telegram bot / admin chat is not set"
        send_name, send_raw, mime = name, raw, "application/json"
        if len(raw) > 45 * 1024 * 1024:                                   # Telegram bot upload limit is 50 MB
            bio = io.BytesIO()
            with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr(name, raw)
            send_name, send_raw, mime = name[:-5] + ".zip", bio.getvalue(), "application/zip"
        cap = "\U0001F4BE <b>%s</b> - AUTO BACKUP\n\U0001F552 %s\n\U0001F4E6 %s KB" % (
            esc(brand_name()), time.strftime("%d %b %Y, %I:%M %p", time.gmtime(time.time() + TZ_OFFSET)), round(len(send_raw) / 1024, 1))
        import requests
        r = requests.post("https://api.telegram.org/bot%s/sendDocument" % tok,
                          data={"chat_id": adm, "caption": cap, "parse_mode": "HTML"},
                          files={"document": (send_name, send_raw, mime)}, timeout=(10, 90))
        ok = r.status_code == 200 and r.json().get("ok")
        set_setting("auto_backup_status", "Sent to Telegram" if ok else "Telegram refused the file (HTTP %s)" % r.status_code)
        return bool(ok), ("Backup sent to your Telegram" if ok else "Telegram did not accept the file (HTTP %s)" % r.status_code)
    except Exception as e:
        set_setting("auto_backup_status", "Failed: %s" % str(e)[:80])
        return False, "Backup failed: %s" % str(e)[:80]
    finally:
        AUTO_BACKUP_LOCK.release()


def backup_worker():
    time.sleep(120)                                        # let the site finish starting first
    while True:
        try:
            if auto_backup_on():
                last = int(get_setting("auto_backup_last", "0") or 0)
                if time.time() - last >= auto_backup_hours() * 3600:
                    run_auto_backup()
        except Exception:
            pass
        time.sleep(300)                                    # check every 5 minutes (works even after a Render restart)


@app.route("/admin/backup/auto", methods=["POST"])
@admin_required
def admin_backup_auto():
    act = request.form.get("action")
    if act == "now":
        ok, msg = run_auto_backup()
        flash(msg, "ok" if ok else "err")
    else:
        set_setting("auto_backup", "1" if request.form.get("on") == "1" else "0")
        try:
            set_setting("auto_backup_hours", str(max(1, min(168, int(request.form.get("hours", "12"))))))
        except ValueError:
            pass
        flash("Auto backup settings saved", "ok")
    return redirect("/admin/backup")


@app.route("/admin/backup/download")
@admin_required
def admin_backup_download():
    name, raw = build_backup()
    return Response(raw, mimetype="application/json",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % name,
                             "Cache-Control": "no-store"})


@app.route("/admin/backup/file/<name>")
@admin_required
def admin_backup_file(name):
    name = os.path.basename(name)
    p = os.path.join(AUTO_BACKUP_DIR, name)
    if not (name.startswith("backup_") and name.endswith(".json") and os.path.isfile(p)):
        return "Not found", 404
    with open(p, "rb") as f:
        raw = f.read()
    return Response(raw, mimetype="application/json", headers={"Content-Disposition": 'attachment; filename="%s"' % name, "Cache-Control": "no-store"})


@app.route("/admin/backup/restore", methods=["POST"])
@admin_required
def admin_backup_restore():
    f = request.files.get("file")
    try:
        data = json.loads(f.read().decode("utf-8")) if f and f.filename else None
        if not isinstance(data, dict) or data.get("app") != "reseller-panel" or not isinstance(data.get("tables"), dict):
            raise ValueError("This is not a backup file of this panel")
        tables = data["tables"]
    except (ValueError, UnicodeDecodeError) as e:
        flash("Restore failed: %s" % (e if isinstance(e, ValueError) and "backup" in str(e) else "invalid file"), "err")
        return redirect("/admin/backup")
    c = sqlite3.connect(DB, timeout=20, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=OFF")
    try:
        c.execute("BEGIN IMMEDIATE")
        keep = {r_["k"]: r_["v"] for r_ in c.execute("SELECT k,v FROM settings WHERE k IN (%s)" % ",".join("?" * len(RESTORE_KEEP)), RESTORE_KEEP)}
        for t in reversed(BACKUP_TABLES):
            c.execute("DELETE FROM %s" % t)
        total = 0
        for t in BACKUP_TABLES:          # table names come from the fixed list above
            cols = [r[1] for r in c.execute("PRAGMA table_info(%s)" % t)]
            for row in tables.get(t) or []:
                keys = [k for k in row if k in cols]      # only known column names are ever used
                if not keys:
                    continue
                vals = [row[k] for k in keys]
                if any(isinstance(v, (dict, list)) for v in vals):
                    raise ValueError("bad value in table %s" % t)
                c.execute("INSERT INTO %s(%s) VALUES(%s)" % (t, ",".join(keys), ",".join("?" * len(keys))), vals)
                total += 1
        for k_, v_ in keep.items():                  # this server's bot token / admin chat stay as they are
            if v_:
                c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (k_, v_))
        c.execute("UPDATE resellers SET tg_chat=''")  # a backup never brings reseller / user Telegram links back
        c.execute("DELETE FROM tg_link")
        c.execute("COMMIT")
        _SET_CACHE.clear()
        try:
            bot.refresh_map()                                   # premium emoji choices come back to life at once
        except Exception:
            pass
        flash("Backup restored (%d records). Music is not part of this backup - restore it from the Music backup below." % total, "ok")
    except Exception as e:
        try:
            c.execute("ROLLBACK")
        except Exception:
            pass
        flash("Restore failed, nothing was changed: %s" % str(e)[:120], "err")
    finally:
        c.close()
    return redirect("/admin/backup")


# ---- separate MUSIC backup (one .zip: song list + the uploaded audio files)
@app.route("/admin/music/backup")
@admin_required
def admin_music_backup():
    rows = [dict(r) for r in q("SELECT title, url FROM music ORDER BY pos, id")]
    fd, path = tempfile.mkstemp(suffix=".zip", dir=DATA_DIR)
    os.close(fd)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:          # audio is already compressed
        z.writestr("music.json", json.dumps(dict(app="reseller-panel-music", version=1, rows=rows), ensure_ascii=False))
        for m in rows:
            if m["url"].startswith("/media/"):
                fp = os.path.join(MUSIC_DIR, os.path.basename(m["url"]))
                if os.path.isfile(fp):
                    z.write(fp, "files/" + os.path.basename(m["url"]))

    @after_this_request
    def _rm(resp):
        try:
            os.remove(path)
        except OSError:
            pass
        return resp
    name = "music_backup_%s.zip" % time.strftime("%Y%m%d_%H%M", time.gmtime(time.time() + TZ_OFFSET))
    return send_file(path, as_attachment=True, download_name=name, mimetype="application/zip", max_age=0)


@app.route("/admin/music/restore", methods=["POST"])
@admin_required
def admin_music_restore():
    f = request.files.get("file")
    try:
        z = zipfile.ZipFile(f.stream)
        meta = json.loads(z.read("music.json").decode("utf-8"))
        if meta.get("app") != "reseller-panel-music" or not isinstance(meta.get("rows"), list):
            raise ValueError("bad")
    except Exception:
        flash("This is not a music backup file of this panel", "err")
        return redirect("/admin/backup")
    for m in q("SELECT * FROM music"):                                  # replace the current library
        if m["url"].startswith("/media/"):
            try:
                os.remove(os.path.join(MUSIC_DIR, os.path.basename(m["url"])))
            except OSError:
                pass
    q("DELETE FROM music", commit=True)
    names = {n for n in z.namelist() if n.startswith("files/") and not n.endswith("/")}
    n_files = n_rows = 0
    for n in names:
        safe = secure_filename(os.path.basename(n))
        if safe:
            with z.open(n) as src, open(os.path.join(MUSIC_DIR, safe), "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
            n_files += 1
    for m in meta["rows"]:
        url = str(m.get("url") or "")
        if url.startswith("/media/") and not os.path.isfile(os.path.join(MUSIC_DIR, secure_filename(os.path.basename(url)))):
            continue                                                    # file missing inside the zip
        q("INSERT INTO music(title,url,pos) VALUES(?,?,(SELECT COALESCE(MAX(pos),0)+1 FROM music))", (str(m.get("title") or "")[:200], url), commit=True)
        n_rows += 1
    flash("Music restored: %d song(s), %d audio file(s)." % (n_rows, n_files), "ok")
    return redirect("/admin/backup")


# ---------------------------------------------------------------- v17: ACCESS (Bot Make switch, Telegram link for users, Google login)
def _v17_schema():
    c = db()
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(resellers)")]
        for col in ("gid", "email"):
            if col not in cols:
                c.execute("ALTER TABLE resellers ADD COLUMN %s TEXT DEFAULT ''" % col)
        mcols = [r[1] for r in c.execute("PRAGMA table_info(music)")]
        if "pos" not in mcols:
            c.execute("ALTER TABLE music ADD COLUMN pos INTEGER NOT NULL DEFAULT 0")
            for n_, r_ in enumerate(c.execute("SELECT id FROM music ORDER BY id").fetchall(), 1):
                c.execute("UPDATE music SET pos=? WHERE id=?", (n_, r_[0]))
        c.execute("CREATE TABLE IF NOT EXISTS tg_link(token TEXT PRIMARY KEY, rid INTEGER NOT NULL, ts INTEGER NOT NULL)")
        c.execute("UPDATE resellers SET tg_chat='' WHERE tg_chat IS NOT NULL AND tg_chat<>''")     # v17.10: no reseller/user Telegram links
        c.execute("DELETE FROM tg_link")
        c.execute("CREATE TABLE IF NOT EXISTS adm_devices(id INTEGER PRIMARY KEY, dev_id TEXT NOT NULL, label TEXT, ip TEXT, "
                  "status TEXT NOT NULL DEFAULT 'pending', created INTEGER NOT NULL, decided INTEGER, last_seen INTEGER)")
        c.commit()
    finally:
        c.close()


_v17_schema()


# ---- Bot Make ON / OFF (global switch + one switch per reseller)
def bm_allowed(r):
    try:
        if get_setting("botmake_on", "1") == "0":
            return False
        return get_setting("bm_off_%d" % r["id"], "0") != "1"
    except Exception:
        return True


app.jinja_env.globals["bm_allowed"] = bm_allowed
app.jinja_env.globals["bm_global_on"] = lambda: get_setting("botmake_on", "1") != "0"


@app.before_request
def _bm_gate():
    if request.path.startswith("/bot-make") and session.get("rid"):
        r = q("SELECT id FROM resellers WHERE id=?", (session["rid"],), one=True)
        if r and not bm_allowed(r):
            flash("Bot Make is turned off by the admin.", "err")
            return redirect("/dashboard")


# ---- Telegram link for USER accounts: website -> bot (/start link_<token>) -> account linked automatically
LINK_OK = ("/link-telegram", "/logout", "/theme", "/music.json", "/media/")
_BOT_UN = {}


def link_required():
    return False        # v17.10: users create an account directly, no Telegram link needed


def tg_bot_username():
    m = re.search(r"(?:t\.me/|telegram\.me/|^@)([A-Za-z0-9_]{4,32})", (get_setting("tg_bot_link") or "").strip())
    if m:
        return m.group(1)
    tok = tg_token()
    if tok in _BOT_UN:
        return _BOT_UN[tok]
    try:
        me = bot.api("getMe", _timeout=6)
        un = str((me or {}).get("username") or "") if isinstance(me, dict) else ""
    except Exception:
        un = ""
    if un:
        _BOT_UN[tok] = un
    return un


def tg_link_claim(cid, token, frm):
    """Called by the bot when someone sends /start link_<token>. Returns (ok, html text for the chat)."""
    row = q("SELECT * FROM tg_link WHERE token=?", (token,), one=True)
    if not row or time.time() - row["ts"] > 1800:
        return False, "\u274C This link has expired.\nGo back to the website and press the Telegram button again."
    r = q("SELECT * FROM resellers WHERE id=? AND deleted=0", (row["rid"],), one=True)
    if not r:
        return False, "\u274C Account not found."
    other = q("SELECT username FROM resellers WHERE tg_chat=? AND id<>? AND deleted=0", (str(cid), r["id"]), one=True)
    if other:
        return False, "\u274C This Telegram account is already linked to another account."
    q("UPDATE resellers SET tg_chat=? WHERE id=?", (str(cid), r["id"]), commit=True)
    q("DELETE FROM tg_link WHERE rid=?", (r["id"],), commit=True)
    try:
        if tg_admin():
            bot.send(tg_admin(), "<blockquote>\U0001F517 <b>TELEGRAM LINKED</b></blockquote>\n\U0001F464 User: <b>%s</b>\n"
                                 "\U0001F194 Chat ID: <code>%s</code>" % (esc(r["username"]), esc(cid)), what="telegram linked")
    except Exception:
        pass
    return True, ("\u2705 <b>%s</b>\n\nYour account <b>%s</b> is now linked.\nGo back to the website &mdash; it opens by itself. "
                  "Purchase alerts will arrive here." % (esc(brand_name()), esc(r["username"])))


@app.route("/link-telegram")
@reseller_required
def link_telegram():
    return redirect("/dashboard")        # v17.10: Telegram link page removed
    r = request.r
    un = tg_bot_username()
    row = q("SELECT * FROM tg_link WHERE rid=?", (r["id"],), one=True)
    if row and time.time() - row["ts"] < 1500:
        token = row["token"]
    else:
        token = secrets.token_hex(12)
        q("DELETE FROM tg_link WHERE rid=? OR ts<?", (r["id"], int(time.time()) - 3600), commit=True)
        q("INSERT INTO tg_link(token,rid,ts) VALUES(?,?,?)", (token, r["id"], int(time.time())), commit=True)
    url = ("https://t.me/%s?start=link_%s" % (un, token)) if un else ""
    return render_template("link_tg.html", title="Link Telegram", url=url, uname=un, who=r["username"])


@app.route("/link-telegram/status")
@reseller_required
def link_telegram_status():
    return jsonify(linked=bool((request.r["tg_chat"] or "").strip()))


# ---- Google sign-up / login (OAuth 2.0, needs Client ID + Secret from Google Cloud Console)
def google_conf():
    return (get_setting("google_client_id", "").strip(), get_setting("google_client_secret", "").strip())


def google_on():
    cid, sec = google_conf()
    return bool(cid and sec) and get_setting("google_on", "1") != "0"


app.jinja_env.globals["google_on"] = google_on


def google_redirect_uri():
    base = (get_setting("public_url") or "").strip().rstrip("/") or request.host_url.rstrip("/")
    return base + "/auth/google/callback"


@app.route("/auth/google", strict_slashes=False)
def auth_google():
    if request.args.get("code") and request.args.get("state"):       # Google sent the user back to this address
        return auth_google_callback()
    if not google_on():
        flash("Google sign-in is not available right now.", "err")
        return redirect("/login")
    if session.get("rid"):
        return redirect("/dashboard")
    from urllib.parse import urlencode
    state = secrets.token_urlsafe(24)
    session["g_state"] = state
    qs = urlencode(dict(client_id=google_conf()[0], redirect_uri=google_redirect_uri(), response_type="code",
                        scope="openid email profile", state=state, prompt="select_account"))
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + qs)


@app.route("/auth/google/callback", strict_slashes=False)
@app.route("/auth/google/<path:rest>")                               # tolerate a slightly different callback address
def auth_google_callback(rest=None):
    import requests
    dev, is_new = get_dev()
    ip = request.remote_addr or "?"

    def out(resp):
        return set_dev_cookie(resp, dev, is_new)
    st = session.pop("g_state", None)
    if request.args.get("error") or not st or not same(st, request.args.get("state", "")) or not request.args.get("code"):
        flash("Google sign-in was cancelled or expired. Please try again.", "err")
        return out(redirect("/login"))
    if rl_blocked("gauth:" + ip, 20, 600):
        flash("Too many attempts. Please wait 10 minutes.", "err")
        return out(redirect("/login"))
    rl_hit("gauth:" + ip)
    cid, sec = google_conf()
    try:
        tj = requests.post("https://oauth2.googleapis.com/token", timeout=12, data=dict(
            code=request.args["code"], client_id=cid, client_secret=sec,
            redirect_uri=google_redirect_uri(), grant_type="authorization_code")).json()
        at = tj.get("access_token")
        if not at:
            raise ValueError(tj.get("error_description") or tj.get("error") or "no token")
        info = requests.get("https://openidconnect.googleapis.com/v1/userinfo", timeout=12,
                            headers={"Authorization": "Bearer " + at}).json()
    except Exception as e:
        flash("Google sign-in failed: %s" % str(e)[:100], "err")
        return out(redirect("/login"))
    sub, email = str(info.get("sub") or ""), str(info.get("email") or "").strip().lower()
    if not sub or not email or info.get("email_verified") is False:
        flash("Google did not give a verified email. Please try again.", "err")
        return out(redirect("/login"))
    r = q("SELECT * FROM resellers WHERE gid=? AND deleted=0", (sub,), one=True)
    if not r:
        if rl_blocked("signup:" + ip, 6, 3600):
            flash("Too many accounts created from this network. Try again later.", "err")
            return out(redirect("/login"))
        base = re.sub(r"[^A-Za-z0-9_.\-]", "", email.split("@")[0])[:20]
        if len(base) < 3:
            base = (base + "user")[:20]
        name = base
        while same(name.upper(), ADMIN_USER.upper()) or q("SELECT 1 FROM resellers WHERE lower(username)=lower(?)", (name,), one=True):
            name = "%s%d" % (base[:19], secrets.randbelow(9000) + 1000)
        try:
            q("INSERT INTO resellers(username,pw,balance,api_key,created,role,otp_on,gid,email) VALUES(?,?,?,?,?,?,?,?,?)",
              (name, generate_password_hash(secrets.token_urlsafe(24)), 0, new_api_key(), int(time.time()), "user", 0, sub, email), commit=True)
        except sqlite3.IntegrityError:
            flash("Could not create the account. Please try again.", "err")
            return out(redirect("/login"))
        rl_hit("signup:" + ip)
        r = q("SELECT * FROM resellers WHERE username=?", (name,), one=True)
        try:
            if tg_admin():
                bot.send(tg_admin(), "<blockquote>\U0001F195 <b>NEW USER ACCOUNT (Google)</b></blockquote>\n\U0001F464 User: <b>%s</b>\n"
                                     "\U0001F4E7 %s\n\U0001F310 IP: <code>%s</code>\n\U0001F552 %s" % (esc(name), esc(email), esc(ip), fmt(time.time())),
                         what="new google user (%s)" % name)
        except Exception:
            pass
    if not r["active"]:
        flash("Your account is disabled. Please contact admin.", "err")
        return out(redirect("/login"))
    if r["role"] == "user":                                  # USER: Google is the login (no device check, no code)
        session.clear()
        session["rid"] = r["id"]
        session["pwh"] = pw_fp(r)
        return out(with_theme(redirect("/dashboard"), r))
    if dev_check_on():                                        # upgraded to FULL RESELLER: same device + code rules as the password login
        d = q("SELECT * FROM devices WHERE reseller_id=? AND dev_id=?", (r["id"], dev), one=True)
        if d and d["status"] == "denied":
            return out(blocked_page())
        if not d or d["status"] != "approved":
            ask_admin_approval(r, dev)
            session.clear()
            session["pre"] = dict(rid=r["id"], dev=dev, ts=int(time.time()))
            return out(redirect("/login/wait"))
    return out(with_theme(redirect(next_step(r, dev, fresh=True)), r))


# ---- Admin > Access (Bot Make switch, Telegram link, Google)
@app.route("/admin/access", methods=["GET", "POST"])
@admin_required
def admin_access():
    if request.method == "POST":
        a = request.form.get("action")
        if a == "bm_global":
            set_setting("botmake_on", "1" if request.form.get("on") == "1" else "0")
            flash("Bot Make is now %s for everybody." % ("ON" if get_setting("botmake_on", "1") != "0" else "OFF"), "ok")
        elif a == "bm_one":
            rid = int(num(request.form.get("rid")))
            off = get_setting("bm_off_%d" % rid, "0") == "1"
            set_setting("bm_off_%d" % rid, "0" if off else "1")
            flash("Bot Make turned %s for that reseller." % ("ON" if off else "OFF"), "ok")
        elif a == "link":
            set_setting("tg_link_required", "1" if request.form.get("on") else "0")
            set_setting("tg_bot_link", request.form.get("bot_link", "").strip()[:120])
            _BOT_UN.clear()
            flash("Telegram link settings saved.", "ok")
        elif a == "signup_toggle":
            set_setting("signup_on", "1" if request.form.get("on") == "1" else "0")
            flash("Create New Account is now %s." % ("ON" if request.form.get("on") == "1" else "OFF (hidden everywhere)"), "ok")
        elif a == "google_toggle":
            set_setting("google_on", "1" if request.form.get("on") == "1" else "0")
            flash("Google sign-up / login is now %s." % ("ON" if request.form.get("on") == "1" else "OFF (hidden everywhere)"), "ok")
        elif a == "google":
            cid, sec = request.form.get("cid", "").strip(), request.form.get("secret", "").strip()
            if cid:
                set_setting("google_client_id", cid)
            if sec:
                set_setting("google_client_secret", sec)
            set_setting("public_url", request.form.get("public_url", "").strip().rstrip("/")[:120])
            flash("Google settings saved.", "ok")
        nxt = request.form.get("next", "")
        return redirect(nxt if nxt.startswith("/admin/") and not nxt.startswith("//") else "/admin/access")
    sec = google_conf()[1]
    rs = q("SELECT id, username FROM resellers WHERE role<>'user' AND deleted=0 ORDER BY username")
    return render_template("admin_access.html", page="access", bm_on=get_setting("botmake_on", "1") != "0",
                           rs=[dict(id=x["id"], username=x["username"], off=get_setting("bm_off_%d" % x["id"], "0") == "1") for x in rs],
                           link_on=get_setting("tg_link_required", "1") != "0", bot_link=get_setting("tg_bot_link", ""),
                           bot_un=tg_bot_username() if tg_token() else "", has_token=bool(tg_token()),
                           su_on=signup_on(), g_cid=google_conf()[0], g_tail=sec[-4:] if sec else "", g_on=get_setting("google_on", "1") != "0",
                           public_url=get_setting("public_url", ""), redirect_uri=google_redirect_uri())


# ---- premium emoji: a change is sent to the admin's Telegram as a fresh backup a minute later
_emoji_bk = [None]


def schedule_emoji_backup():
    def go():
        _emoji_bk[0] = None
        try:
            if auto_backup_on():
                run_auto_backup()
        except Exception as e:
            print("[emoji-backup]", e)
    t = _emoji_bk[0]
    if t:
        t.cancel()
    t = threading.Timer(60, go)
    t.daemon = True
    _emoji_bk[0] = t
    t.start()


# ---------------------------------------------------------------- AUTO PRICE PROTECTION (v16.1)
# When Tahir API or VIP Seller Hub RAISES the price of a plan that is imported here, the selling prices
# (reseller + user) are raised automatically so they are never below  new provider cost + X %.
# Prices are only ever raised by this feature, never lowered. Runs in the background + "Check now" button.
_ap_lock = threading.Lock()


def ap_conf():
    return dict(on=get_setting("auto_price_on", "1") != "0",
                pr=max(num(get_setting("auto_price_pct_reseller", "5"), 5.0), 0.0),
                pu=max(num(get_setting("auto_price_pct_user", "5"), 5.0), 0.0),
                mins=min(max(int(num(get_setting("auto_price_mins", "30"), 30)), 5), 1440))


def _ap_costs(src):
    """{provider plan id (str): fresh cost in INR} from a FRESH catalog, or None if the API is not set up."""
    if src == "tahir":
        if not (get_setting("tahir_token") or "").strip():
            return None
        cat = load_catalog(refresh=True)
        return {str(pid): float(pl.get("price") or 0) for pid, (_p, pl) in catalog_plans(cat).items()}
    if not vsh_token():
        return None
    cat = vsh_load_catalog(refresh=True)
    out = {}
    for p in cat.get("products", []):
        for pl in p.get("plans") or []:
            out[str(pl["plan_id"])] = float(pl.get("price") or 0)
    return out


def auto_price_run(force=False):
    """One check of both APIs. Returns the status dict (also saved for the admin page)."""
    if not _ap_lock.acquire(blocking=False):
        return None
    try:
        cf = ap_conf()
        if not cf["on"] and not force:
            return None
        changes, errors, checked = [], [], 0
        for src, label in (("tahir", "Tahir API"), ("vsh", "VIP Seller Hub")):
            if not api_enabled(src):
                continue
            try:
                costs = _ap_costs(src)
            except Exception as e:
                errors.append("%s: %s" % (label, str(e)[:120]))
                continue
            if costs is None:
                continue
            for pl in q("SELECT pl.*, p.name AS pname FROM plans pl JOIN products p ON p.id=pl.product_id "
                        "WHERE pl.prov_src=? AND pl.mode='provider'", (src,)):
                new = costs.get(str(pl["prov_pid"]))
                if new is None or new <= 0:
                    continue
                checked += 1
                old = float(pl["cost"] or 0)
                if abs(new - old) < 0.005:
                    continue
                if old <= 0 or new < old:                       # first time seen, or provider got cheaper:
                    q("UPDATE plans SET cost=? WHERE id=?", (new, pl["id"]), commit=True)   # remember cost only
                    continue
                cur_rp = float(pl["price"] or 0)
                cur_up = float(user_price_of(pl))
                new_rp = max(cur_rp, round(new * (1 + cf["pr"] / 100.0), 2))
                new_up = max(cur_up, round(new * (1 + cf["pu"] / 100.0), 2))
                q("UPDATE plans SET cost=?, price=?, user_price=? WHERE id=?", (new, new_rp, new_up, pl["id"]), commit=True)
                q("UPDATE custom_prices SET price=? WHERE plan_id=? AND price<?", (new_rp, pl["id"], new_rp), commit=True)
                changes.append(dict(src=label, product=pl["pname"], plan=pl["name"], old_cost=old, new_cost=new,
                                    old_rp=cur_rp, new_rp=new_rp, old_up=cur_up, new_up=new_up))
        st = dict(ts=int(time.time()), checked=checked, changed=len(changes), errors=errors, forced=bool(force))
        set_setting("auto_price_status", json.dumps(st))
        if changes:
            try:
                old_log = json.loads(get_setting("auto_price_log", "[]") or "[]")
            except ValueError:
                old_log = []
            stamped = [dict(c, ts=st["ts"]) for c in changes]
            set_setting("auto_price_log", json.dumps((stamped + old_log)[:60]))
            if tg_admin():
                lines = ["<blockquote>\U0001F4C8 <b>PRICE AUTO-UPDATED</b></blockquote>",
                         "Provider raised %d plan price(s). Your selling prices were raised automatically:" % len(changes)]
                for c in changes[:12]:
                    lines.append("\n<b>%s</b> - %s (%s)\nProvider: %.2f \u2192 %.2f INR\nReseller: %.2f \u2192 %.2f INR\nUser: %.2f \u2192 %.2f INR"
                                 % (esc(c["product"]), esc(c["plan"]), esc(c["src"]), c["old_cost"], c["new_cost"],
                                    c["old_rp"], c["new_rp"], c["old_up"], c["new_up"]))
                if len(changes) > 12:
                    lines.append("\n...and %d more (see Admin > Auto Price)" % (len(changes) - 12))
                try:
                    bot.send(tg_admin(), "\n".join(lines), what="auto price update")
                except Exception as e:
                    print("[auto-price] telegram failed:", e)
        return st
    finally:
        _ap_lock.release()


def auto_price_worker():
    time.sleep(120)
    while True:
        try:
            auto_price_run()
        except Exception as e:
            print("[auto-price] error:", e)
        time.sleep(ap_conf()["mins"] * 60)


@app.route("/admin/auto-price", methods=["GET", "POST"])
@admin_required
def admin_auto_price():
    if request.method == "POST":
        a = request.form.get("action")
        if a == "save":
            set_setting("auto_price_on", "1" if request.form.get("on") else "0")
            set_setting("auto_price_pct_reseller", "%g" % max(num(request.form.get("pr"), 5.0), 0.0))
            set_setting("auto_price_pct_user", "%g" % max(num(request.form.get("pu"), 5.0), 0.0))
            set_setting("auto_price_mins", str(min(max(int(num(request.form.get("mins"), 30)), 5), 1440)))
            flash("Auto price settings saved.", "ok")
        elif a == "run":
            st = auto_price_run(force=True)
            if st is None:
                flash("A check is already running. Try again in a moment.", "err")
            elif st["errors"]:
                flash("Checked %d plan(s), %d raised. Problem: %s" % (st["checked"], st["changed"], "; ".join(st["errors"])), "err")
            else:
                flash("Checked %d plan(s). Prices raised: %d." % (st["checked"], st["changed"]), "ok")
        return redirect("/admin/auto-price")
    try:
        st = json.loads(get_setting("auto_price_status", "") or "null")
    except ValueError:
        st = None
    try:
        log = json.loads(get_setting("auto_price_log", "[]") or "[]")
    except ValueError:
        log = []
    return render_template("admin_auto_price.html", cf=ap_conf(), st=st, log=log, page="autoprice")


@app.route("/admin/bulk-price", methods=["GET", "POST"])
@admin_required
def admin_bulk_price():
    """Raise (or lower) ALL reseller prices and/or ALL user prices by a percentage, in one click."""
    if request.method == "POST":
        pct = num(request.form.get("pct"), 0.0)
        tgt = request.form.get("target", "")
        if not (-90 <= pct <= 1000) or pct == 0:
            flash("Enter a percentage between -90 and 1000 (not 0).", "err")
            return redirect("/admin/bulk-price")
        if tgt not in ("reseller", "user", "both"):
            flash("Choose what to change.", "err")
            return redirect("/admin/bulk-price")
        f = 1 + pct / 100.0
        n = 0
        c = db()
        try:
            for pl in c.execute("SELECT * FROM plans").fetchall():
                rp = float(pl["price"] or 0)
                up = user_price_of(pl)
                new_rp, new_up = rp, round(up, 2)      # a side that is not selected keeps its current price
                if tgt in ("reseller", "both"):
                    new_rp = round(rp * f, 2)
                if tgt in ("user", "both"):
                    new_up = round(up * f, 2)
                c.execute("UPDATE plans SET price=?, user_price=? WHERE id=?", (new_rp, new_up, pl["id"]))
                n += 1
            if tgt in ("reseller", "both") and request.form.get("custom"):
                for cp in c.execute("SELECT * FROM custom_prices").fetchall():
                    c.execute("UPDATE custom_prices SET price=? WHERE reseller_id=? AND plan_id=?",
                              (round(float(cp["price"] or 0) * f, 2), cp["reseller_id"], cp["plan_id"]))
            c.commit()
        finally:
            c.close()
        flash("Done: %d plan(s) changed by %+g%% (%s)." % (n, pct, {"reseller": "Reseller price", "user": "User price",
                                                                     "both": "Reseller + User price"}[tgt]), "ok")
        return redirect("/admin/bulk-price")
    cnt = q("SELECT COUNT(*) FROM plans", one=True)[0]
    return render_template("admin_bulk_price.html", cnt=cnt, page="bulkprice")


# ---------------------------------------------------------------- keep-alive (Render never sleeps)
def keep_alive():
    url = (os.environ.get("KEEP_ALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if not url:
        return
    import requests
    time.sleep(60)
    while True:
        try:
            requests.get(url + "/health", timeout=20, headers={"User-Agent": "keep-alive"})
        except Exception:
            pass
        time.sleep(max(60, int(os.environ.get("KEEP_ALIVE_INTERVAL", "240"))))     # v18: every 4 minutes


threading.Thread(target=keep_alive, daemon=True, name="keep-alive").start()
threading.Thread(target=topup_worker, daemon=True, name="topup-worker").start()
threading.Thread(target=backup_worker, daemon=True, name="auto-backup").start()
threading.Thread(target=auto_price_worker, daemon=True, name="auto-price").start()
bot.start()                                   # Telegram bot (login codes, alerts, device approval)

from templates_ui7 import TEMPLATES, ic  # noqa: E402
from markupsafe import Markup  # noqa: E402
app.jinja_env.globals["ic"] = ic


def brand_mark(icon="crown", size=22):
    """The uploaded logo (Admin > Logo & Theme) or, if none, the default icon."""
    v = get_setting("logo_ver")
    if v and get_setting("logo_data"):
        return Markup('<img class="brandimg" src="/logo?v=%s" alt="">' % _html.escape(v))
    return ic(icon, size)


app.jinja_env.globals["brand_mark"] = brand_mark
app.jinja_env.globals["user_price_of"] = user_price_of


@app.context_processor
def inject_site():
    return dict(site_mode=get_setting("site_mode", "dark"), BRAND=brand_name())

# ---- v18.4: "Customize" amount button on Add Balance (users + resellers) and plain-POST key form
def _patch_tpl(name, old, new):
    t = TEMPLATES.get(name, "")
    if old in t and new not in t:
        TEMPLATES[name] = t.replace(old, new, 1)


_patch_tpl("wallet.html", "{% endfor %}</div>\n<input type=hidden name=amount id=am",
           "{% endfor %}<button type=button class=\"amt\" id=cbtn data-a=\"\">{{ic('qr',16)}} Customize</button></div>\n"
           "<div id=cbox style=\"display:none;margin:10px 0\"><div class=mu style=\"margin-bottom:6px\">Enter your own amount ({{CURRENCY}}{{cmin}} - {{CURRENCY}}{{cmax}})</div>"
           "<input type=number id=cin inputmode=numeric min=\"{{cmin}}\" max=\"{{cmax}}\" step=1 placeholder=\"Amount\" style=\"width:100%;font-size:18px\"></div>\n"
           "<input type=hidden name=custom id=cflag value=0>\n<input type=hidden name=amount id=am")
_patch_tpl("wallet.html", "</script>\n{% if tops %}",
           "</script>\n<script>(function(){var am=document.getElementById('am'),fl=document.getElementById('cflag'),bx=document.getElementById('cbox'),"
           "bt=document.getElementById('cbtn'),inp=document.getElementById('cin');if(!bt)return;var first=document.querySelector('.amt');"
           "function sync(){am.value=inp.value||'';fl.value='1'}"
           "bt.addEventListener('click',function(){bx.style.display='block';fl.value='1';sync();inp.focus()});"
           "document.querySelectorAll('.amt').forEach(function(b){if(b!==bt)b.addEventListener('click',function(){bx.style.display='none';fl.value='0'})});"
           "inp.addEventListener('input',sync);"
           "var f=am.form;f.addEventListener('submit',function(e){if(fl.value==='1'){var v=parseInt(inp.value,10);"
           "if(!(v>={{cmin}}&&v<={{cmax}})){e.preventDefault();if(window.rgToast)rgToast('Enter an amount from {{cmin}} to {{cmax}}','err');else alert('Enter an amount from {{cmin}} to {{cmax}}')}}})})()</script>\n{% if tops %}")
# key form: normal POST with explicit action (no background submit)
_patch_tpl("admin_stock.html", "<form method=post><input type=hidden name=action value=add>",
           "<form method=post action=\"/admin/stock/{{pl.id}}\" data-noajax><input type=hidden name=action value=add>")

TEMPLATES["admin_manual_keys.html"] = """{% extends 'abase.html' %}{% block c %}
{% if cur %}<a href="/admin/manual-keys">{{ic('back',16)}} All products</a><h2>{{ic('key',24)}} {{cur.name}}</h2>
<div class=mu>Paste keys under the plan you want (one key per line).</div>
{% for e in plans %}{% set pl=e.pl %}<div class=card><div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap"><h3>{{pl.name}}</h3>
<span><span class="pill p">{{ {'stock':'Manual keys','api':'External API','random':'Auto-generate','provider':'Main API'}[pl.mode or 'random'] }}</span> <span class="pill c">{{e.stock}} available</span></span></div>
{% if (pl.mode or 'random')=='provider' %}<div class=mu>This plan gets its keys from a provider API, so manual keys are not used for it.</div>{% endif %}
<form method=post action="/admin/manual-keys/add" data-noajax><input type=hidden name=plan_id value="{{pl.id}}">
<textarea name=keys placeholder="One key per line" required style="width:100%;min-height:90px"></textarea>
{% if (pl.mode or 'random') in ('random','api') %}<label class=mu style="display:flex;gap:8px;align-items:center;margin-top:8px"><input type=checkbox name=make_manual value=1 checked> Also switch this plan to "Manual keys"</label>{% endif %}
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px"><button class=g>{{ic('plus')}} Add Keys</button><a class=btn href="/admin/stock/{{pl.id}}">{{ic('key',16)}} View / edit keys</a></div></form></div>
{% else %}<div class=card>No plans in this product yet. Add a plan on the Products page first.</div>{% endfor %}
{% else %}<h2>{{ic('key',24)}} Manual Keys</h2><div class=mu>Choose a product, then add keys to its plans.</div>
{% for e in rows %}<a class=card href="/admin/manual-keys?p={{e.p.id}}" style="display:flex;justify-content:space-between;align-items:center;gap:8px;text-decoration:none;color:inherit"><b>{{e.p.name}}</b><span><span class="pill p">{{e.n}} plans</span> <span class="pill c">{{e.stock}} keys</span></span></a>
{% else %}<div class=card>No products yet.</div>{% endfor %}{% endif %}{% endblock %}"""
_patch_tpl("abase.html", '<a href="/admin/products" class="{{\'on\' if page==\'products\'}}">Products</a>',
           '<a href="/admin/products" class="{{\'on\' if page==\'products\'}}">Products</a><a href="/admin/manual-keys" class="{{\'on\' if page==\'mkeys\'}}">Manual Keys</a>')

# ---- v18.7: admin panel speed - no always-animated blurred blobs, no blur on every card, skip painting off-screen cards
_ADMIN_FAST_CSS = ("/* v18.7 speed */body::before,body::after{animation:none!important;filter:none!important;will-change:auto}"
                   "body::before{background:radial-gradient(circle,var(--ac) 0%,transparent 70%)!important}"
                   "body::after{background:radial-gradient(circle,var(--ac2) 0%,transparent 70%)!important}"
                   ".card,.stat,.flash{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}"
                   ".card{content-visibility:auto;contain-intrinsic-size:auto 260px}"
                   "button:hover,.btn:hover{filter:none!important}")
_t = TEMPLATES.get("abase.html", "")
if "v18.7 speed" not in _t and "</style>" in _t:
    TEMPLATES["abase.html"] = _t.replace("</style>", _ADMIN_FAST_CSS + "</style>", 1)

app.jinja_env.loader = DictLoader(TEMPLATES)

# v18.8 Gemini Support AI integration (keeps existing purchase/account flows).
import support_ai  # noqa: E402
support_ai.setup(app, TEMPLATES, admin_required, reseller_required, q, db, get_setting, set_setting, role_of, user_price_of, buy)


# ---- v10.11: BOT MAKE (resellers create their own bot from the website) -> botmake.py
import botmake  # noqa: E402


def _bm_notify_admin(text):
    if tg_admin():
        bot.send(tg_admin(), text, what="new reseller bot")


botmake.setup(app, data_dir=DATA_DIR, q=q, get_setting=get_setting, set_setting=set_setting,
              reseller_required=reseller_only, admin_required=admin_required,
              owner_admin=tg_admin, site_token=tg_token, esc=esc, rl_blocked=rl_blocked, rl_hit=rl_hit,
              tz_offset=TZ_OFFSET, notify_admin=_bm_notify_admin,
              tg_post=lambda token, method, payload, read: tgbot._post(tgbot.API % (token, method), payload, 5, read))

# ---- RESET RELAY (auto key reset through a Telegram account) -> resetrelay.py
import resetrelay  # noqa: E402
resetrelay.setup(app, q=q, get_setting=get_setting, set_setting=set_setting,
                 reseller_required=reseller_required, admin_required=admin_required, api_guard=api_guard,
                 notify_admin=_bm_notify_admin, esc=esc, tz_offset=TZ_OFFSET)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
