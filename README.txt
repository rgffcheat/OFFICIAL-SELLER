---- v18.7 ----
Admin panel speed: removed the always-moving blurred background blobs, the blur on every card, and off-screen cards are no longer painted. (Phone test: scrolling the Products page 31 -> 60 fps.)

---- v18.6 ----
FIXED the main bug: every admin form has a hidden field named "action", so the background submit (nav.js) posted to a wrong address (Not Found) and nothing was saved - product rename, position, new product, plans, etc. nav.js now reads the form address correctly.

---- v18.5 ----
New admin menu "Manual Keys": pick a product (all your hacks are listed), open it, and paste keys under any of its plans. Normal page submit, separate from the Products page. Option to switch the plan to Manual keys at the same time.

---- v18.4 ----
Add Balance (users + resellers): new "Customize" button - type your own amount (default min 10, max 100000; admin can change the minimum with setting wallet_custom_min) and the UPI / Binance QR is created for that amount.
Keys page: the Add Keys form now sends as a normal page submit (no background send), so keys are always saved.

---- v18.3 ----
Fixed: adding keys on the Keys page could end on a bare "Not Found" screen. Missing admin pages now open Products with a message, and error pages never replace the screen any more.

---- v18.2 ----
TAHIR API > All Products: "Import selected" was broken (it always said nothing selected) - fixed. New button "Import NEW only" adds just the plans that are not on your site yet (it asks the API for its newest list first).
  The product list now refreshes itself when it is older than 5 minutes, so new provider products show up as "New" without pressing Refresh.
A missing admin page (for example the Keys page of a deleted plan) now opens Products with a message instead of a bare "Not Found".

---- v18.1 (bot alerts for resellers are back) ----
Admin > Resellers > Manage > "Telegram alerts": save the reseller's Telegram Chat ID, then press "Turn alerts ON".
  ON  = he gets a bot message for every purchase (panel or API: product, user, validity, price, current balance, key), every balance added, and a LOW BALANCE alert when his balance is under the limit (default 50).
  OFF = nothing is sent to him (the admin copy still arrives). Default for everybody is OFF until you switch it on.

---- v18 (speed + no page refresh) ----
SLOW SITE FIX: the admin background picture (up to 12 MB) was read from the database on EVERY page, and the product / plan lists ran 2-3 database queries per plan.
  Now: settings are cached in memory, lists are built with 4 queries in total, database indexes added, pages are gzip-compressed (about 30x smaller), keys are added in one go.
NO PAGE REFRESH: every Save / Delete / Add / Move / Hide button inside the admin and reseller pages now works in the background (file nav.js).
  Only the page content changes, the scroll position stays, and a small message pops up on top ("Product name saved" ...). Confirm boxes still work.
KEEP-ALIVE (Render): the site pings its own /health every 4 minutes (KEEP_ALIVE_INTERVAL seconds, default 240). It only runs when RENDER_EXTERNAL_URL exists, so on Railway it stays off.
  Extra safety: add https://YOUR-DOMAIN/health to a free uptime monitor (UptimeRobot / cron-job.org) every 4-5 minutes. A site that is already asleep cannot wake itself.
RUN ON ONE PLATFORM AT A TIME: Render uses Procfile / render.yaml.txt, Railway uses railway.json. Never run the same Telegram bot token on both.

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
  1. The bot token is set in Admin > Telegram (never in the code).
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

---- v10.3 (admin alerts) ----
ADMIN LOGIN ALERT: every successful reseller login sends the admin a Telegram "RESELLER LOGIN" (name, device, IP, time, balance).
ADMIN PURCHASE ALERT: every purchase (panel + API) sends the admin the same NEW PURCHASE ALERT, plus at the bottom
  "Bought by: <reseller name>" and "Reseller Current Balance". Admin copy is sent even if the reseller has no Chat ID or alerts OFF.

---- v10.5 ----
BOT TOKEN: set in Admin > Telegram (see v10.7).
  (If /start shows another channel's "must join" message, the same token is running somewhere else - revoking the token stops that copy.)
BALANCE ADDED: every top-up (auto UPI or Admin > Reseller > add balance) sends YOU: reseller name, amount added, current balance, method, time.
  The reseller also gets "BALANCE ADDED" (if his alerts are on).
PREMIUM EMOJI: packs RGCHEAT99, botd3, NewsEmoji (change with env EMOJI_PACKS=a,b,c; first pack wins) are loaded from Telegram at start.
  Every normal emoji in bot messages becomes its premium twin automatically; inline buttons get premium icons.
  If Telegram refuses (text emoji need a Fragment username on the bot), the bot falls back to normal emoji by itself - nothing is lost.
  Admin > Telegram > Premium emoji shows status + on/off switch. In the bot (as admin): /emojis = status; send premium emojis or a t.me/addemoji link = get IDs.

---- v10.7 ----
BOT TOKEN IS NO LONGER IN THE CODE: app.py has no token any more, so a GitHub leak cannot expose it.
  Admin > Telegram > paste token > Save. It is checked with Telegram first, then the bot switches to it at once (no redeploy).
  Token leaked? @BotFather /revoke -> paste the new token in Admin > Telegram. Website stays online.
  Priority: token saved in the panel > Render env TG_BOT_TOKEN (optional fallback). The token is part of the normal Backup (settings).
  NOTE: Render free disk is wiped on redeploy -> restore the backup, or set env TG_BOT_TOKEN once as a safety net.
PREMIUM EMOJI: if a pack has no twin for an emoji, the closest one is used (e.g. money bag -> dollar note).
  Admin > Telegram > Premium emoji picker: tap a normal emoji, tap the premium one you like -> used in ALL messages at once.
  "Send sample purchase alert" shows the result in your Telegram. Approve/Reject button text also gets the premium icon.

---- v10.8 (emoji ID manager) ----
Admin > Telegram > "Emoji ID manager": every emoji the bot uses has its own ID box. Paste a premium emoji ID -> Save -> used in ALL messages at once
  (text + button icons). Empty the box + Save = back to automatic. A small preview shows the emoji; Telegram is asked if the ID exists (typo warning).
ADD ANY EMOJI: type any normal emoji + its premium ID -> Add. Works for every emoji that appears in a bot message. Remove button to delete it.
PASTE MANY: one line per emoji ("<emoji> <ID>"), exactly like the bot's /emojis / premium-emoji reply -> Apply all.
GET AN ID: as admin, send any premium emoji (or a t.me/addemoji/... link) to the bot -> it replies with the ID of every emoji.
  IDs from ANY pack work now (they do not have to be in EMOJI_PACKS). Choices are saved in the backup (settings).

---- v10.11 (BOT MAKE) ----
RESELLER: left three-line menu > "Bot Make" (above Security). Fill 3 boxes: Bot name, Bot API token (@BotFather), Admin ID -> the bot is created and started at once.
  The bot name is used everywhere inside the bot, the token is linked, the typed Admin ID becomes the bot's admin. Your own admin ID
  (Admin > Telegram > admin Chat ID) is ALWAYS added too and cannot be removed inside the bot. One bot per reseller.
ADMIN: three-line menu > "Bots": see every reseller bot (name, @username, reseller, admin ID, Running/Stopped), Stop / Start / Restart / Delete,
  Log (last lines of the bot's output), Database download, "Add / restore database" (upload .db or .zip - old DB is kept as safety copy, bot restarts),
  Max bots limit, "Backup all bots (.zip)" + Restore (Render free disk is wiped on redeploy - restore brings every bot and its database back).
FILES: bot_main.py = the bot code (next to app.py - do NOT put it in a folder) (copied into every created bot on each start). To update ALL bots: replace this file and redeploy.
  Each bot lives in data/bot_instances/<id>/ with its OWN shop_data.db. A watchdog restarts crashed bots and starts every bot again after the website restarts.
RENDER: keep  gunicorn app:app --workers 1 --threads 32 ...  (one worker, because it manages the bot processes). Every bot is one extra Python process
  (memory!). On the free 512 MB plan keep "Max bots" small (2-3) or use a paid plan.

---- v11 (users + new main API + logo + light/dark) ----
USERS: login page has "CREATE NEW ACCOUNT" (username + password + confirm). Users log in with username + password only
  (no device approval, no Telegram code). Users see the USER price; resellers see the RESELLER price. Users do not get
  Security / API & Docs / Bot Make. Admin > Resellers / Users (tabs) manages both; Admin > Logo & Theme can close sign-ups.
MAIN API (old adminshops API removed): Admin > Main API > Server URL + API Token -> "Save & Connect" (Connect successful + balance).
  Admin > Main API > All Products: tick products/plans (or Select all / Import ALL). Prices: reseller = cost +50%, user = cost +200%
  (both % can be changed on that page; "Sync prices" re-prices everything imported). Plans are bought live (POST /api/v1/purchase).
  Plans imported from the OLD api are hidden and cannot be bought - delete them in Admin > Products and import again.
LOGO: Admin > Logo & Theme: add / replace / remove the picture shown in the menu, login page and dashboard.
LIGHT / DARK: sun/moon button at the top of every page (saved per browser). Admin sets the default look.

---- v12 (part 1: name + admin security + users section) ----
NAME: OFFICIAL SELLER everywhere (panel, bot messages, bot_main). Admin login: ROHIT / 909090.
ADMIN SECURITY: the admin password alone no longer opens the panel.
  First login (no bot token saved yet): username + password -> "Connect your bot" page -> paste the bot API token (checked with Telegram)
  + admin Chat ID (default is already filled) -> a 6-digit code is sent to that chat -> enter it -> panel.
  EVERY later login: username + password -> NEW 6-digit code in the admin Telegram chat (5 min, one use) -> panel. Cannot be switched off.
  Admin session ends after 8 hours. Wrong codes / too many codes are rate-limited. Admin gets an "ADMIN LOGIN" alert after each login.
  The bot token cannot be removed from the panel (only replaced). The /admin <password> bot command works only until the first verified admin login.
  Session key is no longer derived from the admin password (random key saved in data/.secret_key, or env SECRET_KEY).
ADMIN CHAT ID CHANGE: Admin > Telegram > "Admin Chat ID": type the new ID -> a code goes to the NEW chat -> type it -> saved. Old chat is notified. No code edit needed.
USERS: separate admin menu item "Users" (never mixed into Resellers). Tabs Active / Banned / Deleted + search.
  Ban / Unban, Delete (soft, can be restored), Restore, Delete forever (only from the Deleted tab). Same buttons for resellers.
  Banned / deleted accounts cannot login and their API token stops working.
NEXT (part 2): Paytm gateway + Fampay toggle + simple QR, product logo / premium emoji, "Reseller Update" for users.

---- v12 (part 2: Paytm gateway, QR, product icons, Reseller Update) ----
GATEWAY TOGGLE: Admin > Gateway > "Active gateway": Fampay / Paytm. Paytm ON = Fampay OFF, Paytm OFF = Fampay ON. Only the active one creates new QR codes
  (payments already created on the other one still finish). Paytm = ZYVO PAY API (https://zyvopay.site/api).
PAYTM SETUP: Admin > Gateway > Paytm: paste the API key (public.secret) + webhook secret -> Save -> "Generate Paytm test QR" (Rs.1, never credited) -> switch Paytm ON.
  (or Render env ZYVOPAY_API_KEY / ZYVOPAY_WEBHOOK_SECRET / ZYVOPAY_BASE_URL). The key/secret are never shown again, never put in a page or log.
  Requests are signed on the server: HMAC-SHA256(secret, timestamp + "." + exact JSON body). Paid only when the signed check says "successful"
  and reference, order id, INR and the exact amount match. Credit happens once (safe against duplicates).
  WEBHOOK: set  https://YOUR-SITE/zyvo/webhook  in the Paytm dashboard (signature header X-ZyvoPay-Signature is verified; bad signature = 401; duplicates ignored).
QR: simple black/white QR, same look for both gateways. Paytm QR is made on the server from the exact payment_uri (instant, no outside QR service).
  The payment page opens at once (no gateway call while loading) and checks the payment every 3 seconds. "Open UPI App" shows only if the gateway allows it.
PRODUCT LOGO / EMOJI: Admin > Products > "Logo / premium emoji" on each product: upload a small picture and/or paste a Telegram premium emoji ID.
  Shown next to the product name in Admin > Products and in the Generate Key page.
RESELLER UPDATE: Admin > Gateway > set "Reseller Update price" (0 = closed). Users see "Reseller Update" in the left menu -> pay -> verified -> the account becomes a
  RESELLER at once (reseller prices, API & Docs, Bot Make), balance and history stay, admin gets a "RESELLER UPDATE" alert.
  Admin can also press "Make Reseller" on a user's Manage page.

---- v13 ----
BACKGROUND PICTURE: Admin > Logo & Theme > "Background picture" -> choose image -> Add background. Shows on every page (login, dashboard, admin).
  Darkness (Light / Medium / Strong) keeps the text readable. "Remove background" brings the normal look back.
PAYTM (ZYVO PAY): Admin > Gateway > Paytm: enter UPI ID + API Token -> "Save & connect Paytm". A Rs.1 test QR is made automatically;
  if it works, Paytm turns ON by itself. Webhook secret / API URL are optional (Advanced).
PRODUCT LOGO: Admin > Products > "Logo / premium emoji" under each product (picture upload or Telegram emoji ID). Shown as small chips on the Generate page.
NO BALANCE: Generate Keys with too little balance now opens a popup with an "Add balance" button.

---- v15 (own payment gateway + product names/order) ----
GATEWAY: Admin > Gateway. The old Fampay / Paytm (ZYVO) gateway settings are gone; everything goes through YOUR gateway (payment-gateway-api-docs.txt).
  1. Gateway Base URL box (top): paste the new link whenever your gateway link changes (after restart/redeploy) -> "Save Base URL". Nothing else changes.
     A pasted link with /api/... or a path is cut down to https://host automatically.  Optional env var PG_BASE_URL = first default.
  2. API Token: paste the API key from your gateway, choose Paytm or FamPay -> "Save & connect". A Rs.1 test QR is made; "Connected successfully" = it works.
  3. Active gateway buttons: switch Paytm <-> FamPay any time (same token).
  FamPay adds paise (e.g. 99.37): the payment page shows the EXACT amount to pay; the wallet is credited the amount the reseller chose (e.g. 99).
  Payment is credited only when the gateway says SUCCESS and order id + amount match (checked every few seconds, also by webhook if you set a secret).
  Webhook URL (optional, instant confirmation): https://YOUR-SITE/pgw/webhook  + the signing secret in Advanced.
PRODUCTS: Admin > Products > "Arrange & rename products": edit any product name, type a position number (1 = top) + Go, or use top / up / down.
  The same names and order are used in the reseller panel, the Telegram bot, and /api/v1/products (new field "position") for everyone who uses your API.
  Imported products keep your custom name when you import again from Tahir API System (no duplicates). New products go to the bottom.

---- v16.1 (AUTO PRICE) ----
Admin > Auto Price (menu): when Tahir API or VIP Seller Hub RAISES the price of an imported plan, your Reseller AND User prices
  are raised automatically so they are never below  new provider price + X %  (default 5% for each, changeable on that page).
  - Checks both APIs in the background every 30 min (5 - 1440, changeable) + "Check prices now" button.
  - Only RAISES prices. If the provider gets cheaper, your price stays (only the stored cost is updated).
  - Your current price is kept if it is already higher than new cost + X %.
  - Per-reseller custom prices that fall below the new reseller price are raised to it.
  - Admin gets a Telegram "PRICE AUTO-UPDATED" message; the page shows the last 60 increases.
  - Works only for plans imported from the APIs (mode = provider). Needs the API token saved.

---- v17 (ACCESS & LOGIN) ----
ADMIN > Access & Login (menu):
  BOT MAKE: one ON/OFF switch for everybody + one switch per reseller. OFF = menu item hidden and /bot-make closed. Existing bots keep running.
  TELEGRAM LINK FOR USERS: after sign-up / login a USER must press START in your bot. The site sends him to the bot with a one-time link
    (t.me/<bot>?start=link_<code>), the bot saves his Chat ID automatically and the waiting page opens his account by itself.
    Bot link box is optional (the bot username is detected from the token). Untick the box to stop requiring it.
    One Telegram account can be linked to one account only. Nobody is asked while the bot token is not set.
  GOOGLE SIGN-UP / LOGIN: paste Client ID + Client secret (Google Cloud Console > Credentials > OAuth client ID, Web application).
    Add the "Authorised redirect URI" shown on that page. "Sign up with Google" is on the Create Account page, "Continue with Google" on Login.
    Google users are normal USER accounts (then Telegram link). If a Google user is upgraded to Full Reseller, the normal device approval + Telegram code still apply.
PREMIUM EMOJI + BACKUP: emoji choices are part of the backup (settings). After "Restore" the bot reloads them at once, and every emoji change
  sends a fresh backup file to the admin's Telegram about 1 minute later (needs Auto backup ON).
USERS: the menu item is now "Full Reseller Upgrade" (old: Reseller Update). After paying they become a reseller and see the RESELLER prices.

---- v17.1 ----
MUSIC ORDER: Admin > Music: every song has up / down arrows next to its number. The order is the play order on the site, and it is kept in the Music backup.
BOT MAKE: the ON/OFF switch is also at the top of Admin > Bots (same switch as Access & Login). OFF = hidden for every reseller and user (menu, page, upgrade list).
GOOGLE: Access & Login > Google > "Turn Google OFF" hides the Google button on the Login and Create Account pages and blocks the Google route.
TELEGRAM LINK: users who already have a Chat ID are never asked again; only users without one see the link page.

---- v17.9 (website name from the admin panel) ----
WEBSITE NAME: Admin > Logo & Theme > "Website name": type the new name -> Save. It changes everywhere at once (login page, menu, browser tab,
  footer, API docs examples, Telegram login codes / alerts / welcome message). "Reset to default" brings back OFFICIAL SELLER. No code edit needed.

---- v17.9 RAILWAY ----
RAILWAY DEPLOY: Procfile + railway.json (start command) + main.py (so "gunicorn main:app" also works) are included.
  Start command: gunicorn app:app --workers 1 --threads 32 --timeout 120 --bind 0.0.0.0:$PORT
  Variables: ADMIN_USER, ADMIN_PASS, SECRET_KEY (optional TG_BOT_TOKEN, ADMIN_TG_ID).
  DATA: Railway disk is wiped on every redeploy. Add a Volume (mount path /data) and set variable DATA_DIR=/data
  so panel.db, music, bots and backups survive.

---- v17.10 ----
USERS: no Telegram link any more. A user creates an account (or signs in with Google) and enters the dashboard directly.
  The "Link Telegram" page is gone, /link-telegram goes to the dashboard, the bot ignores /start link_<code>,
  and the "Telegram link for users" box was removed from Admin > Access & Login.
  Only resellers made by the admin (Chat ID added in Admin > Resellers) are linked to the bot - nobody is linked automatically.
RESELLER BOT MESSAGES: the reseller's Telegram now gets ONLY  NEW PURCHASE ALERT  and  LOW BALANCE ALERT.
  Removed for the reseller: NEW LOGIN, BALANCE ADDED, PASSWORD CHANGED. (Admin copies of alerts are unchanged.)
  The 6-digit login code is a security code, not an alert; it is still controlled by the existing switch
  (Admin > Telegram > Login code for resellers / per reseller).

---- v17.10 (part 2: admin login + notifications) ----
ADMIN LOGIN: no 6-digit code any more. Username + password -> (first time: connect bot token + Chat ID) ->
  an "ADMIN LOGIN REQUEST" with Approve / Reject goes to the admin Telegram. Approve = the browser is remembered and enters;
  later logins from that browser go straight in. A different browser/device asks for Approve again. Reject = that browser is blocked.
  No "ADMIN LOGIN" alert when the admin logs in.
RESELLER: no login code. New device still needs admin approval. Reseller bot gets ONLY: NEW PURCHASE, BALANCE ADDED, LOW BALANCE.
ADMIN gets: reseller login, balance added, purchases, AUTO PRICE increases, device requests (+ new user / upgrade info messages).

---- v17.10 (part 3) ----
Resellers and users are NOT linked to Telegram at all any more (no Chat ID field, no link page, no messages to them).
Only the admin is linked to the bot: admin login approval, admin alerts, database backups.
BACKUP RESTORE: restoring a backup keeps this server's bot token / admin chat and clears every reseller/user Telegram link,
so old links never come back. (Old links in the database are also wiped at every start.)

---- v17.10 (part 4: BINANCE PAY, USDT) ----
Admin > Gateway > "Binance Pay (USDT)": paste Merchant API Key + Secret, set the rate (Rs per 1 USDT), tick "Show Pay with Binance", Save, then "Test connection".
Binance Merchant Portal > Developers > Webhooks: set the URL shown there (/bnpay/webhook) for instant confirmation (optional - the site also checks every 5 s).
Customer: Add balance > choose amount > "Pay with Binance (USDT)" > pays the USDT shown > balance is added automatically, any hour.
Safety: balance is added ONLY after a signed Binance "Query Order" says PAID with the right currency and amount; one order can be credited only once.

--- v18.8 GEMINI SUPPORT AI ---
The Support AI feature is added in support_ai.py and is configured from Admin > Support AI.
1. Create a Gemini API key in Google AI Studio.
2. Open Admin > Support AI, paste the key, choose Gemini 2.5 Flash (or Flash-Lite), and press Test Gemini Connection.
3. Save settings and enable Support AI.
4. Add verified website-specific instructions in the Website Knowledge box. Never paste provider tokens, passwords, or private credentials there.
The Support AI launcher appears at the bottom-right of authenticated user/reseller pages when enabled.
Text chat uses Gemini. Voice input/output uses browser speech capabilities and may vary by device/browser. The website's server-side purchase function is reused; a purchase is only started after the user confirms a selected plan. An uncertain external-provider purchase is blocked from immediate retry until the admin reviews it in Admin > Support AI.
Gemini free-tier availability and request limits are controlled by Google and can change. Keep the Gemini API key private and monitor Google AI Studio usage.
