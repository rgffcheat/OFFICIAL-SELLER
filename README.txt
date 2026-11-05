RENDER DEPLOY
1. Upload all these files to a GitHub repo.
2. Render > New > Web Service > connect repo (runtime Python).
   Build: pip install -r requirements.txt
   Start: gunicorn app:app --workers 1 --threads 32 --timeout 120 --bind 0.0.0.0:$PORT
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

---- v5 ----
KEY GENERATOR: pick product -> validity (plan + price) -> quantity (- / +) -> Generate Keys. Keys are made one by one (no timeout) and shown in a copy box.
KEY HISTORY: search, SRC column (API / PANEL), copy button beside each time, "Plaintext keys" box with Last N (only sizes you really have) / All, Copy all, Download .txt.
ADD BALANCE (UPI): fixed amounts 200/500/1000/1500/2000/2500 -> QR -> auto verification (also 5 min in background) -> balance credited once.
  Admin > Gateway: enter Gateway URL (default https://fampaygateway.site), your UPI ID and API token, then "Generate test QR".
BROADCAST: Admin > Broadcast (one reseller or all). Resellers see it in sidebar > Broadcast (new-notice badge).
COLOUR: palette button (top right) - saved per reseller, also applied on the login page.
MUSIC: after reopening, the same song restarts from its beginning; backup now includes uploaded songs (backup file gets bigger).

---- v6 ----
TELEGRAM BOT (runs inside the website - tgbot.py, no separate hosting)
  1. The bot token is already inside app.py (TG_BOT_TOKEN at the top). Keep the GitHub repo PRIVATE.
  2. Open your bot in Telegram and send:  /admin 909090   (your admin password) -> you become the admin. Nothing else to set.
  3. Reseller opens the bot, presses Start, sends you his Chat ID -> Admin > Resellers (create form or Manage).
LOGIN: username + password -> (new device: admin gets Accept/Reject in Telegram) -> 6-digit code in Telegram -> dashboard.
  Reseller > Security: login code ON/OFF, alerts, low-balance limit, own devices. Rejected device sees only a red ACCESS BLOCKED page.
  Admin > Devices: accept / reject / remove any device.
ALERTS: NEW PURCHASE ALERT (panel + API), LOW BALANCE ALERT, BALANCE ADDED.
ADD BALANCE AMOUNTS: Admin > Gateway > "Add-balance amounts" (e.g. 100, 300, 500).
BACKUP: music now has its OWN backup (Admin > Backup > Music Backup .zip). The normal backup no longer contains music.

---- v7 ----
LOGIN CODE (Telegram): every login makes a NEW random 6-digit code and sends it to the reseller's Telegram.
  Wrong code / too many tries = never reaches the dashboard. Right code = dashboard. A code works only once, for 5 minutes.
  The code is now sent immediately, and if Telegram refuses, the REAL reason is shown on the verification page
  (e.g. "Chat ID is wrong, or that person never pressed START in the bot") instead of failing silently.
  The verification page shows the last 4 digits of the Chat ID the code was sent to.
MASTER SWITCH: Admin > Telegram > "Login code for resellers" (untick = nobody needs a code until the bot works).
  Per reseller: Admin > Resellers > Manage > Login code ON/OFF (or the reseller's own Security page).
LINKING EXISTING RESELLERS: Admin > Resellers: every "Not linked" reseller has a Chat ID box + Link button.
  Everybody who pressed /start in the bot is listed, so you can tap the name (Manage page) or pick the ID.
  Saving a Chat ID sends a test message at once and tells you if it was really delivered.
DELIVERY LOG: Admin > Telegram shows the last sends (Delivered / Failed + exact reason), per-reseller Test buttons,
  and warns if another copy of the bot (same token) is running somewhere else.
PURCHASE ALERT: product, quantity, wallet balance left, validity, amount paid, TIME, key issued.
LOW BALANCE ALERT: sent after every purchase while the balance is under the reseller's limit (default 50).

---- v8 (freeze fix) ----
Login no longer waits for Telegram: the code is sent in the background and the verification page shows
"Sending... / Code delivered / Could not send: <reason>" live. If Telegram is slow the page still opens at once.
Telegram connections are forced to IPv4 (broken IPv6 routes can make requests hang on Render) and have short timeouts.
Failed Telegram sends are also printed to the Render > Logs tab as "[telegram] FAILED ...".

---- v9 (alerts) ----
Every Telegram message is now sent from its own background thread (no shared queue that could stall).
Alerts show money in INR (e.g. "59 INR"). Purchase alert: product, quantity, wallet balance, validity, paid, time, key.
If an alert is NOT sent, the reason is written to Admin > Telegram > Delivery log
(e.g. "skipped: no Telegram Chat ID linked", "skipped: reseller turned alerts OFF", or the Telegram error).
Reseller > Security > "Send me a test alert" sends a sample purchase alert at once.

---- v10.1 ----
ADMIN > SOLD KEYS: new card layout (no broken keys). Key is in its own box, tap the key or press Copy. Search, Active/Expired filter, "Copy shown keys".
BOT / API CONNECT (Reseller > API & Docs): reseller gives his bot the Server URL (your Render link) + API Token.
  GET  /api/v1/connect   -> "Connect successful" (connected:true) or "Not connected" (401, connected:false)
  GET  /api/v1/balance   -> wallet balance
  GET  /api/v1/products  -> ALL products with plans + the reseller's prices;  ?ids=1,4,7 (or POST {"product_ids":[..]}) -> only selected
  POST /api/v1/purchase  -> {"plan_id": N} returns the key
  Token can be sent as X-API-Key, Authorization: Bearer, or ?api_key=. CORS is open for /api/v1 (token based).
  API & Docs page has: 4-step guide, copy buttons, a Connection tester (Connect / Check balance / Select products), Python helper for bots, cURL.
RESELLER > SETTINGS (above Logout): change password with current password (or generate a strong one). All other logged-in browsers are logged out,
  Telegram gets a "PASSWORD CHANGED" alert, optional new API key, 5 wrong tries = 10 min lock. New devices still need admin approval.

---- v10.2 ----
FIXES: Telegram calls can no longer freeze the site (hard 5-16 s deadline on every Telegram request; test buttons wait max 7 s; Admin > Telegram page opens at once).
  Admin > Telegram now says "Cannot reach Telegram: ..." with the real reason if the server cannot reach Telegram.
ADMIN HOME: "Keys Sold" showed <built-in method keys ...> - fixed.
RESELLER BALANCE: Admin > Resellers > Manage > "Add / Deduct Balance" has separate Add and Deduct buttons (balance never goes below 0).
MUSIC: upload shows a progress bar; reseller panel no longer pre-downloads songs on every page.
RENDER: set Start Command to  gunicorn app:app --workers 1 --threads 32 --timeout 120 --bind 0.0.0.0:$PORT

---- v11 (MULTIPLE APIs) ----
ADMIN > APIs (old "Main API"): connect as many provider APIs as you want at the same time.
  1. Choose the API type (AdminShops / LicencePanelHub) -> paste ONLY the API token -> Save & Connect.
     The Base URL is filled automatically (optional "Advanced" box to change it or name the API).
  2. Each API card shows Connected / Not connected + balance. "Check Balance" refreshes it. "Change token" updates the token.
  3. "Products" -> list of ALL products of that API -> tick what you want -> Import selected (or Import ALL). Optional markup %.
     Imported plans are bought live from THAT api when a reseller buys. Same plan from 2 APIs -> second one is named "1 Day (API name)".
  4. Remove API: its imported plans are switched to "Manual keys" (nothing else is deleted).
  Your old single Main API is moved automatically into the list as "Main API" (nothing to redo). Backups include all APIs.
LicencePanelHub notes: uses GET /products and POST /order {variant_id, quantity}. No idempotency key exists there, so a purchase is never auto-retried;
  if it times out the reseller is refunded and Admin should check the provider's order history. Device-bound plans (android_id) are not supported.
