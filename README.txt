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

---- v10 ----
SOLD KEYS (admin): each sale is a card - reseller, product / plan, the KEY in a big copyable box with a Copy button,
  price, source, time, Active/Expired. Search box + "Copy all shown keys". Shows the newest 1000.
CREDIT: Admin > Resellers > Manage > Add / Deduct Credit has separate Add and Deduct buttons
  (deduct cannot take more than the balance).
SETTINGS (reseller): sidebar > Settings (above Logout) > Change password (needs the current password).
  Changing it logs out every OTHER device, sends a "PASSWORD CHANGED" alert to the reseller's Telegram.
  A password set by the admin also ends the reseller's old sessions.
