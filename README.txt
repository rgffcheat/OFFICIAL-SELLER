RENDER DEPLOY
1. Upload all these files to a GitHub repo.
2. Render > New > Web Service > connect repo (runtime Python).
   Build: pip install -r requirements.txt
   Start: gunicorn app:app --workers 1 --threads 8 --timeout 60 --bind 0.0.0.0:$PORT
3. Environment variables: ADMIN_USER, ADMIN_PASS, SECRET_KEY
4. Admin: https://YOUR-APP.onrender.com/admin   Reseller: /login
Keep-alive: automatic (uses RENDER_EXTERNAL_URL, pings /health every 10 min).

ADMIN LOGIN
Admin login is fixed in app.py (ADMIN_USER / ADMIN_PASS at the top). Change it there when ready.

KEYS PER PLAN (Admin > Products)
- Manual keys : add keys (one per line) with the "Keys" button; view / edit / delete them there.
- External API: "API" button -> URL, method, headers, body, key location in response.
- Auto-generate: random key (old behaviour).

---- v4 ----
LOGIN: one login page (/login, /admin/login both work). Admin credentials -> Admin panel. Reseller credentials -> Reseller panel.
MAIN API: Admin > Main API  -> paste Base URL + API Token -> "Save & Connect" (shows Connected + balance). "Check Balance" refreshes it.
ALL PRODUCTS: Admin > Main API > All Products -> select (or Import ALL). Plans + INR prices are created automatically.
  Optional markup %. Edit selling prices any time in Admin > Products. Purchases are bought live from the main API.
BACKUP: Admin > Backup -> Download Backup (json, goes to Downloads). Upload it again to restore everything.
  IMPORTANT: Render free disk is wiped on every redeploy/restart -> download a backup after changes, restore after redeploy.
