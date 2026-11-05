"""
RG CHEAT - Telegram bot (runs INSIDE the website, no separate hosting needed).

What it does
  * Sends login codes (6 digit) to resellers
  * Sends "NEW PURCHASE ALERT", "LOW BALANCE ALERT", "BALANCE ADDED" to resellers
  * Sends "NEW DEVICE LOGIN REQUEST" to the admin with [Accept] / [Reject] buttons
  * /start  -> shows the user's own Chat ID (reseller gives this ID to the admin)

It only needs the 'requests' package. Messages go through one queue, so a burst of
purchases never hits Telegram's rate limit (429 is retried automatically).
"""
import html
import json
import queue
import threading
import time

import requests

API = "https://api.telegram.org/bot%s/%s"


class Bot:
    def __init__(self, get_token, get_admin, on_device, brand="RG CHEAT", on_claim=None):
        self.get_token = get_token          # () -> bot token (str)
        self.get_admin = get_admin          # () -> admin chat id (str)
        self.on_device = on_device          # (device_row_id:int, approve:bool) -> text
        self.brand = brand
        self.on_claim = on_claim            # (chat_id, secret) -> bool  ("/admin <password>")
        self.q = queue.Queue(maxsize=2000)
        self._hook_cleared = None
        self._started = False

    # ------------------------------------------------------------ low level
    def api(self, method, _timeout=20, **params):
        tok = self.get_token()
        if not tok:
            raise RuntimeError("bot token not set")
        r = requests.post(API % (tok, method), json=params, timeout=_timeout)
        try:
            j = r.json()
        except ValueError:
            raise RuntimeError("Telegram HTTP %s" % r.status_code)
        if not j.get("ok"):
            e = RuntimeError(str(j.get("description") or "Telegram error")[:150])
            e.retry_after = (j.get("parameters") or {}).get("retry_after")
            raise e
        return j.get("result")

    def me(self):
        try:
            return self.api("getMe", _timeout=10)
        except Exception:
            return None

    # ------------------------------------------------------------ sending
    def send(self, chat_id, text, buttons=None):
        """Queue a message (HTML). buttons = [[(label, callback_data), ...], ...]. Never blocks, never raises."""
        chat_id = str(chat_id or "").strip()
        if not chat_id or not self.get_token():
            return False
        try:
            self.q.put_nowait((chat_id, text, buttons, 0))
            return True
        except queue.Full:
            return False

    def send_now(self, chat_id, text, buttons=None):
        """Send immediately and return (ok, error_text) - used by the 'test' buttons."""
        try:
            self._send(chat_id, text, buttons)
            return True, ""
        except Exception as e:
            return False, str(e)

    def _send(self, chat_id, text, buttons):
        p = dict(chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=True)
        if buttons:
            p["reply_markup"] = {"inline_keyboard": [[{"text": a, "callback_data": b} for a, b in row] for row in buttons]}
        return self.api("sendMessage", **p)

    def _sender(self):
        while True:
            chat_id, text, buttons, tries = self.q.get()
            try:
                self._send(chat_id, text, buttons)
            except Exception as e:
                wait = getattr(e, "retry_after", None)
                if wait and tries < 5:                    # flood control: wait and retry
                    time.sleep(min(int(wait) + 1, 60))
                    self.q.put((chat_id, text, buttons, tries + 1))
                elif tries < 2 and "HTTP" in str(e):      # temporary network problem
                    time.sleep(3)
                    self.q.put((chat_id, text, buttons, tries + 1))
            time.sleep(0.05)

    # ------------------------------------------------------------ receiving
    def _poller(self):
        offset = 0
        while True:
            tok = self.get_token()
            if not tok:
                time.sleep(5)
                continue
            try:
                if self._hook_cleared != tok:          # polling needs the webhook to be off
                    self.api("deleteWebhook", _timeout=10)
                    self._hook_cleared = tok
                ups = self.api("getUpdates", _timeout=40, offset=offset, timeout=25,
                               allowed_updates=["message", "callback_query"]) or []
                for u in ups:
                    offset = u["update_id"] + 1
                    try:
                        self._handle(u)
                    except Exception:
                        pass
            except Exception:
                time.sleep(5)

    def _handle(self, u):
        m = u.get("message")
        if m and m.get("chat", {}).get("type") == "private":
            cid = m["chat"]["id"]
            text = (m.get("text") or "").strip().lower()
            if text.startswith("/admin") and self.on_claim:
                ok = self.on_claim(cid, (m.get("text") or "")[6:])
                try:                                    # remove the message that contains the password
                    self.api("deleteMessage", chat_id=cid, message_id=m["message_id"])
                except Exception:
                    pass
                self.send(cid, "✅ <b>You are the admin now.</b>\nNew-device requests will come to this chat." if ok
                          else "❌ Wrong password (or too many tries).")
                return
            if text.startswith("/start") or text.startswith("/id") or text.startswith("/myid"):
                self.send(cid, "👋 <b>Welcome to %s</b>\n\nYour Telegram Chat ID:\n<code>%s</code>\n\n"
                               "Send this ID to the admin. After he links it you will get login codes "
                               "and purchase alerts here." % (html.escape(self.brand), cid))
            else:
                self.send(cid, "Send /start to see your Chat ID.")
            return
        cb = u.get("callback_query")
        if cb:
            data = cb.get("data") or ""
            who = str((cb.get("from") or {}).get("id"))
            admin = str(self.get_admin() or "")
            if not data.startswith("dv:"):
                self.api("answerCallbackQuery", callback_query_id=cb["id"])
                return
            if not admin or who != admin:              # only the admin may decide
                self.api("answerCallbackQuery", callback_query_id=cb["id"], text="Not allowed", show_alert=True)
                return
            try:
                _, act, did = data.split(":")
                res = self.on_device(int(did), act == "a")
            except Exception:
                res = "Error"
            self.api("answerCallbackQuery", callback_query_id=cb["id"], text=res)
            msg = cb.get("message") or {}
            try:
                self.api("editMessageReplyMarkup", chat_id=msg["chat"]["id"], message_id=msg["message_id"],
                         reply_markup={"inline_keyboard": [[{"text": ("✅ " if act == "a" else "❌ ") + res,
                                                             "callback_data": "noop"}]]})
            except Exception:
                pass

    # ------------------------------------------------------------ start
    def start(self):
        if self._started:
            return
        self._started = True
        threading.Thread(target=self._sender, daemon=True, name="tg-send").start()
        threading.Thread(target=self._poller, daemon=True, name="tg-poll").start()
