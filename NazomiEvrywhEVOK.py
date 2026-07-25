# meta developer: @Nazomi_Modules
# Адаптация под Kitsune @Mikasu32
__version__ = (3, 5, 0)

import asyncio
import time
from telethon.tl.types import (
    ReplyInlineMarkup,
    ReplyKeyboardForceReply,
    ReplyKeyboardHide,
    ReplyKeyboardMarkup,
)
from telethon.extensions import html as _tl_html
from telethon import functions, events

from ..core.loader import KitsuneModule, command, watcher
from ..core.security import OWNER
from .. import utils


class _EditTarget:
    __slots__ = ("chat_id", "message_id", "inline_message_id")

    def __init__(self, chat_id, message_id, inline_message_id=None):
        self.chat_id = chat_id
        self.message_id = message_id
        self.inline_message_id = inline_message_id


class _Waiter:
    __slots__ = ("module", "future", "tracked", "after_id", "base_sig", "fallback", "deleted")

    def __init__(self, module, tracked=None, after_id=0, base_sig=None):
        self.module = module
        self.future = module.loop.create_future()
        self.tracked = tracked
        self.after_id = after_id or 0
        self.base_sig = base_sig
        self.fallback = None
        self.deleted = False

    def feed(self, msg, sig, msg_id):
        future = self.future
        if future.done():
            return
        if self.tracked is not None and msg_id == self.tracked:
            if self.base_sig is not None and sig == self.base_sig:
                return
        elif msg_id <= self.after_id:
            return
        if self.module._is_placeholder(msg):
            self.fallback = msg
            return
        future.set_result(msg)

    def feed_deleted(self, ids):
        if self.tracked is None or self.tracked not in ids:
            return
        self.deleted = True
        if not self.future.done():
            self.future.set_result(None)


class NazomiEvrywhEVOK(KitsuneModule):
    name        = "NazomiEvrywhEVOK"
    description = "Модуль для использования бота везде"
    author      = "@Nazomi_Modules | Kitsune-адаптация: @Mikasu32"
    version     = "3.5.0"
    icon        = "🌐"
    category    = "evo"

    BOT_ID = 5522271758

    WAIT_WORDS = ("Ожидайте", "ожидайте", "Загрузка", "загрузка", "Подождите", "подождите")
    WAIT_SYMBOLS = ("⏳", "⌛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🔄")
    PLACEHOLDER_MAX_LEN = 60

    FIRST_TIMEOUT = 20.0
    REPLY_TIMEOUT = 15.0
    CALLBACK_TIMEOUT = 10.0
    ANSWER_QUIET = 0.7
    FOLLOWUP_WINDOW = 8.0

    BTN_TEXT_MAX = 48
    ROW_MAX = 5
    KEYBOARD_SCAN_LIMIT = 25
    CACHE_LIMIT = 96

    REFRESH_BTN = "🔄 Обновить"
    INPUT_BTN = "✍️ Написать"
    INPUT_HINT = "✍️ Введи текст для бота"
    CLOSE_BTN = "🔻 Закрыть"

    async def on_load(self) -> None:
        self.loop = asyncio.get_running_loop()

        self.sessions = {}
        self.bot_index = {}
        self.followups = {}
        self.waiters = []

        self.msg_cache = {}
        self.sig_cache = {}
        self.last_bot_id = 0

        self.keyboard_rows = []
        self.keyboard_single_use = False
        self.keyboard_msg_id = 0

        self.peer = self.BOT_ID
        try:
            self.peer = await self.client.get_input_entity(self.BOT_ID)
        except Exception:
            self.peer = self.BOT_ID

        self.handlers = (
            (self._on_new, events.NewMessage(chats=self.BOT_ID, incoming=True, from_users=self.BOT_ID)),
            (self._on_edit, events.MessageEdited(chats=self.BOT_ID, from_users=self.BOT_ID)),
            (self._on_delete, events.MessageDeleted()),
        )
        for func, event in self.handlers:
            self.client.add_event_handler(func, event)

        asyncio.ensure_future(self._restore_keyboard())

    async def on_unload(self) -> None:
        for func, _ in getattr(self, "handlers", ()):
            self.remove(func)
        self.handlers = ()

        for task in list(self.followups.values()):
            try:
                task.cancel()
            except Exception:
                pass
        self.followups.clear()

        for waiter in tuple(self.waiters):
            if not waiter.future.done():
                waiter.future.cancel()
        self.waiters.clear()

    def get_inline(self):
        return getattr(self.client, "_kitsune_inline", None)

    def remove(self, handler):
        try:
            self.client.remove_event_handler(handler)
        except Exception:
            pass

    async def _on_new(self, event) -> None:
        self._feed(event.message)

    async def _on_edit(self, event) -> None:
        self._feed(event.message)

    async def _on_delete(self, event) -> None:
        chat_id = getattr(event, "chat_id", None)
        if chat_id is not None and chat_id != self.BOT_ID:
            return
        ids = {i for i in (getattr(event, "deleted_ids", None) or ()) if i in self.msg_cache}
        if not ids:
            return
        for msg_id in ids:
            self.msg_cache.pop(msg_id, None)
            self.sig_cache.pop(msg_id, None)
        for waiter in tuple(self.waiters):
            waiter.feed_deleted(ids)

    def _feed(self, msg) -> None:
        if msg is None:
            return
        msg_id = getattr(msg, "id", 0) or 0
        self._update_keyboard(msg)
        sig = self._signature(msg)
        if msg_id:
            self._store(msg_id, msg, sig)
            if msg_id > self.last_bot_id:
                self.last_bot_id = msg_id
        if not self.waiters:
            return
        for waiter in tuple(self.waiters):
            waiter.feed(msg, sig, msg_id)

    def _store(self, msg_id, msg, sig) -> None:
        self.msg_cache[msg_id] = msg
        self.sig_cache[msg_id] = sig
        if len(self.msg_cache) > self.CACHE_LIMIT:
            for stale in sorted(self.msg_cache)[: len(self.msg_cache) - self.CACHE_LIMIT]:
                self.msg_cache.pop(stale, None)
                self.sig_cache.pop(stale, None)

    def _cached_sig(self, msg_id):
        if not msg_id:
            return None
        return self.sig_cache.get(msg_id)

    def _new_waiter(self, tracked=None, after_id=0, base_sig=None):
        waiter = _Waiter(self, tracked=tracked, after_id=after_id, base_sig=base_sig)
        self.waiters.append(waiter)
        return waiter

    def _drop_waiter(self, waiter) -> None:
        try:
            self.waiters.remove(waiter)
        except ValueError:
            pass

    async def _await_waiter(self, waiter, timeout):
        try:
            return await asyncio.wait_for(asyncio.shield(waiter.future), timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            return waiter.fallback
        finally:
            self._drop_waiter(waiter)

    def _render_html(self, msg) -> str:
        if msg is None:
            return ""
        raw = getattr(msg, "raw_text", None)
        if raw is None:
            raw = getattr(msg, "message", None)
        if raw is None:
            raw = getattr(msg, "text", "") or ""
        entities = getattr(msg, "entities", None)
        if raw and entities:
            try:
                return _tl_html.unparse(raw, entities)
            except Exception:
                pass
        if raw:
            return raw
        return getattr(msg, "text", "") or ""

    def _is_placeholder(self, msg) -> bool:
        if msg is None:
            return False
        text = getattr(msg, "raw_text", None) or getattr(msg, "text", "") or ""
        if not text:
            return False
        if self._has_markup(msg):
            return False
        stripped = text.strip()
        for word in self.WAIT_WORDS:
            if word in stripped:
                return True
        if len(stripped) > self.PLACEHOLDER_MAX_LEN or "\n" in stripped:
            return False
        return any(symbol in stripped for symbol in self.WAIT_SYMBOLS)

    def _has_markup(self, msg) -> bool:
        markup = getattr(msg, "reply_markup", None)
        return bool(markup and getattr(markup, "rows", None))

    def _better(self, candidate, current) -> bool:
        if current is None:
            return True
        if self._is_placeholder(candidate) and not self._is_placeholder(current):
            return False
        if not self._is_placeholder(candidate) and self._is_placeholder(current):
            return True
        if self._has_markup(candidate) and not self._has_markup(current):
            return True
        if not self._has_markup(candidate) and self._has_markup(current):
            return False
        return candidate.id >= current.id

    def _best_known(self, msg):
        if msg is None:
            return None
        cached = self.msg_cache.get(msg.id)
        if cached is not None and cached is not msg and not self._is_placeholder(cached):
            if self._better(cached, msg):
                return cached
        return msg

    def _update_keyboard(self, msg) -> None:
        if msg is None:
            return
        markup = getattr(msg, "reply_markup", None)
        if markup is None:
            return
        msg_id = getattr(msg, "id", 0) or 0
        if msg_id and msg_id < self.keyboard_msg_id:
            return
        if isinstance(markup, (ReplyKeyboardHide, ReplyKeyboardForceReply)):
            self.keyboard_rows = []
            self.keyboard_single_use = False
            self.keyboard_msg_id = msg_id
            return
        if not isinstance(markup, ReplyKeyboardMarkup):
            return
        rows = []
        for row in getattr(markup, "rows", None) or []:
            line = []
            for btn in getattr(row, "buttons", None) or []:
                text = getattr(btn, "text", None)
                if text:
                    line.append(text)
            if line:
                rows.append(line)
        self.keyboard_rows = rows
        self.keyboard_single_use = bool(getattr(markup, "single_use", False))
        self.keyboard_msg_id = msg_id

    async def _restore_keyboard(self) -> None:
        try:
            async for msg in self.client.iter_messages(self.peer, limit=self.KEYBOARD_SCAN_LIMIT):
                if getattr(msg, "out", False):
                    continue
                markup = getattr(msg, "reply_markup", None)
                if markup is None:
                    continue
                if isinstance(markup, (ReplyKeyboardMarkup, ReplyKeyboardHide, ReplyKeyboardForceReply)):
                    self._update_keyboard(msg)
                    break
        except Exception:
            pass

    def _btn_text(self, text) -> str:
        text = str(text or "")
        if len(text) <= self.BTN_TEXT_MAX:
            return text
        return text[: self.BTN_TEXT_MAX - 1] + "…"

    def _split_row(self, row):
        if len(row) <= self.ROW_MAX:
            return [row]
        return [row[i : i + self.ROW_MAX] for i in range(0, len(row), self.ROW_MAX)]

    def _inline_rows(self, reply_markup, msg_id):
        if not isinstance(reply_markup, ReplyInlineMarkup):
            return []
        rows = []
        for row in getattr(reply_markup, "rows", None) or []:
            line = []
            for btn in getattr(row, "buttons", None) or []:
                text = getattr(btn, "text", None)
                if getattr(btn, "data", None) is not None:
                    line.append({
                        "text": self._btn_text(text),
                        "callback": self.proxy_callback,
                        "args": (btn.data, msg_id),
                    })
                elif getattr(btn, "url", None) is not None:
                    line.append({"text": self._btn_text(text), "url": btn.url})
                elif text:
                    line.append({
                        "text": self._btn_text(text),
                        "callback": self.proxy_text_button,
                        "args": (text, msg_id),
                    })
            if line:
                rows.extend(self._split_row(line))
        return rows

    def _reply_keyboard_rows(self, msg_id):
        rows = []
        for row in self.keyboard_rows:
            line = [
                {
                    "text": self._btn_text(text),
                    "callback": self.proxy_text_button,
                    "args": (text, msg_id),
                }
                for text in row
                if text
            ]
            if line:
                rows.extend(self._split_row(line))
        return rows

    def _control_row(self, msg_id):
        return [
            {"text": self.REFRESH_BTN, "callback": self.proxy_refresh, "args": (msg_id,)},
            {
                "text": self.INPUT_BTN,
                "input": self.INPUT_HINT,
                "handler": self.proxy_input,
                "args": (msg_id,),
            },
            {"text": self.CLOSE_BTN, "callback": self.proxy_close, "args": (msg_id,)},
        ]

    def build_markup(self, reply_markup, msg_id):
        rows = self._inline_rows(reply_markup, msg_id)
        rows.extend(self._reply_keyboard_rows(msg_id))
        if not rows:
            return []
        rows.append(self._control_row(msg_id))
        return rows

    def _signature(self, msg):
        if msg is None:
            return None
        text = getattr(msg, "raw_text", None) or getattr(msg, "text", "") or ""
        markup = getattr(msg, "reply_markup", None)
        buttons = []
        if markup and getattr(markup, "rows", None):
            for row in markup.rows:
                for btn in row.buttons:
                    buttons.append((
                        getattr(btn, "text", ""),
                        getattr(btn, "data", None),
                        getattr(btn, "url", None),
                    ))
        return (text, tuple(buttons))

    async def _fetch(self, msg_id):
        if not msg_id:
            return None
        try:
            msgs = await self.client.get_messages(self.peer, ids=[msg_id])
        except Exception:
            return None
        msg = msgs[0] if msgs and msgs[0] else None
        if msg is not None:
            self._update_keyboard(msg)
            self._store(msg.id, msg, self._signature(msg))
        return msg

    async def _send(self, text, bot_msg_id=None) -> bool:
        try:
            await self.client.send_message(self.peer, text, reply_to=bot_msg_id)
            return True
        except Exception:
            if bot_msg_id is None:
                return False
        try:
            await self.client.send_message(self.peer, text)
            return True
        except Exception:
            return False

    async def send_wait(self, text, bot_msg_id=None, timeout=None):
        waiter = self._new_waiter(
            tracked=bot_msg_id,
            after_id=max(bot_msg_id or 0, self.last_bot_id),
            base_sig=self._cached_sig(bot_msg_id),
        )
        if not await self._send(text, bot_msg_id):
            self._drop_waiter(waiter)
            return None
        if timeout is None:
            timeout = self.REPLY_TIMEOUT if bot_msg_id else self.FIRST_TIMEOUT
        result = await self._await_waiter(waiter, timeout)
        return self._best_known(result)

    async def _run_callback(self, msg_id, data, call):
        base_sig = self._cached_sig(msg_id)
        waiter = self._new_waiter(
            tracked=msg_id,
            after_id=max(msg_id or 0, self.last_bot_id),
            base_sig=base_sig,
        )
        state = {"answer": None, "alerted": False}

        async def fire():
            try:
                answer = await self.client(
                    functions.messages.GetBotCallbackAnswerRequest(self.peer, msg_id, data=data)
                )
            except Exception:
                answer = None
            state["answer"] = answer

            alert_text = getattr(answer, "message", None) if answer else None
            if call is not None and not state["alerted"]:
                state["alerted"] = True
                if alert_text:
                    await self._answer(call, alert_text, bool(getattr(answer, "alert", False)))
                else:
                    await self._answer(call)

            if not waiter.future.done():
                self.loop.call_later(
                    self.ANSWER_QUIET,
                    lambda: asyncio.ensure_future(verify_or_release()),
                )

        async def verify_or_release():
            if waiter.future.done():
                return
            latest = await self._fetch(msg_id)
            if waiter.future.done():
                return
            if latest is not None and not self._is_placeholder(latest):
                sig = self._signature(latest)
                if base_sig is None or sig != base_sig:
                    waiter.future.set_result(latest)
                    return
            waiter.future.set_result(None)

        asyncio.ensure_future(fire())
        updated = await self._await_waiter(waiter, self.CALLBACK_TIMEOUT)

        if updated is None and not waiter.deleted:
            latest = await self._fetch(msg_id)
            if latest is not None and not self._is_placeholder(latest):
                if base_sig is None or self._signature(latest) != base_sig:
                    updated = latest

        return self._best_known(updated), waiter.deleted, state

    async def _answer(self, call, text=None, alert=False) -> None:
        if call is None:
            return
        try:
            if text:
                await call.answer(text, show_alert=alert)
            else:
                await call.answer()
        except Exception:
            pass

    async def _edit_target(self, target, text, markup) -> None:
        inline = self.get_inline()
        if inline is None or target is None:
            return
        try:
            await inline.edit(target, text, reply_markup=markup)
        except Exception:
            pass

    def _find_session(self, msg_id):
        key = self.bot_index.get(msg_id)
        if key is not None:
            session = self.sessions.get(key)
            if session is not None:
                return key, session
            self.bot_index.pop(msg_id, None)
        for key, session in self.sessions.items():
            if session.get("bot_msg_id") == msg_id:
                self.bot_index[msg_id] = key
                return key, session
        return None, None

    def _bind_bot_id(self, key, session, msg_id) -> None:
        old = session.get("bot_msg_id")
        if old and old != msg_id:
            self.bot_index.pop(old, None)
        session["bot_msg_id"] = msg_id
        if key is not None:
            self.bot_index[msg_id] = key

    def _drop_session(self, key) -> None:
        session = self.sessions.pop(key, None)
        if session is not None:
            self.bot_index.pop(session.get("bot_msg_id"), None)
        self._cancel_followup(key)

    def _sync_target(self, session, call):
        target = session.get("form")
        if target is not None and getattr(target, "inline_message_id", None) is None:
            iid = getattr(call, "inline_message_id", None)
            if iid:
                target.inline_message_id = iid
        return target

    def _cancel_followup(self, key) -> None:
        task = self.followups.pop(key, None)
        if task is not None:
            try:
                task.cancel()
            except Exception:
                pass

    def _schedule_followup(self, key, msg_id, base_sig=None) -> None:
        if key is None or not msg_id or key not in self.sessions:
            return
        self._cancel_followup(key)
        self.followups[key] = asyncio.ensure_future(
            self._followup(key, msg_id, base_sig)
        )

    async def _followup(self, key, msg_id, base_sig) -> None:
        deadline = time.monotonic() + self.FOLLOWUP_WINDOW
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0.05:
                    return
                waiter = self._new_waiter(tracked=msg_id, after_id=msg_id, base_sig=base_sig)
                try:
                    updated = await asyncio.wait_for(asyncio.shield(waiter.future), remaining)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    return
                finally:
                    self._drop_waiter(waiter)

                session = self.sessions.get(key)
                if session is None or updated is None:
                    return

                updated = self._best_known(updated)
                msg_id = updated.id
                base_sig = self._signature(updated)

                text = self._render_html(updated)
                markup = self.build_markup(updated.reply_markup, updated.id)
                await self._edit_target(self._sync_target(session, None), text, markup)
                self._bind_bot_id(key, session, updated.id)
                session["text"] = text
                if not markup:
                    return
                deadline = time.monotonic() + self.FOLLOWUP_WINDOW
        except asyncio.CancelledError:
            return
        except Exception:
            return
        finally:
            if self.followups.get(key) is asyncio.current_task():
                self.followups.pop(key, None)

    async def _apply(self, call, msg_id, updated, deleted=False, answer_call=True):
        key, session = self._find_session(msg_id)
        if key is not None:
            self._cancel_followup(key)

        if updated is None:
            if answer_call:
                await self._answer(call)
            if session is None:
                return
            if deleted:
                await self._edit_target(self._sync_target(session, call), "<b>Готово</b>", [])
                self._drop_session(key)
                return
            self._schedule_followup(key, msg_id, self._cached_sig(msg_id))
            return

        markup = self.build_markup(updated.reply_markup, updated.id)
        text = self._render_html(updated)
        target = self._sync_target(session, call) if session is not None else call

        await self._edit_target(target, text, markup)

        if session is not None:
            self._bind_bot_id(key, session, updated.id)
            session["text"] = text

        if answer_call:
            await self._answer(call)

        if not markup:
            if session is not None:
                self._drop_session(key)
            return

        self._schedule_followup(key, updated.id, self._signature(updated))

    async def proxy_callback(self, call, data, msg_id) -> None:
        key, _ = self._find_session(msg_id)
        self._cancel_followup(key)
        updated, deleted, state = await self._run_callback(msg_id, data, call)
        await self._apply(call, msg_id, updated, deleted, answer_call=not state["alerted"])

    async def proxy_text_button(self, call, text, msg_id) -> None:
        key, _ = self._find_session(msg_id)
        self._cancel_followup(key)
        await self._answer(call)
        if self.keyboard_single_use:
            self.keyboard_rows = []
            self.keyboard_single_use = False
        updated = await self.send_wait(text, msg_id)
        await self._apply(call, msg_id, updated, answer_call=False)

    async def proxy_input(self, call, value, msg_id) -> None:
        value = (value or "").strip()
        if not value:
            return
        key, _ = self._find_session(msg_id)
        self._cancel_followup(key)
        updated = await self.send_wait(value, msg_id)
        await self._apply(call, msg_id, updated, answer_call=False)

    async def proxy_refresh(self, call, msg_id) -> None:
        key, _ = self._find_session(msg_id)
        self._cancel_followup(key)
        latest = self._best_known(await self._fetch(msg_id))
        if latest is None:
            await self._answer(call, "Сообщение недоступно", True)
            return
        await self._apply(call, msg_id, latest)

    async def proxy_close(self, call, msg_id) -> None:
        key, session = self._find_session(msg_id)
        self._cancel_followup(key)
        target = self._sync_target(session, call) if session is not None else call
        text = (session or {}).get("text") or "<b>Закрыто</b>"
        await self._edit_target(target, text, [])
        if key is not None:
            self._drop_session(key)
        await self._answer(call)

    @watcher(no_commands=True, only_reply=True)
    async def evo_watcher(self, event) -> None:
        message = event.message
        if message.sender_id != self.tg_id or not message.text:
            return

        reply_id = message.reply_to_msg_id
        if not reply_id:
            return

        chat_id = utils.get_chat_id(message)
        key = (chat_id, reply_id)
        session = self.sessions.get(key)
        if not session:
            return

        bot_msg_id = session.get("bot_msg_id")
        if not bot_msg_id:
            return

        self._cancel_followup(key)
        response = self._best_known(await self.send_wait(message.text, bot_msg_id))
        if response is None:
            return

        session = self.sessions.get(key)
        if session is None:
            return

        markup = self.build_markup(response.reply_markup, response.id)
        html_text = self._render_html(response)

        self._bind_bot_id(key, session, response.id)
        session["user_msg_id"] = message.id
        session["text"] = html_text

        await self._edit_target(session.get("form"), html_text, markup)

        if not markup:
            self._drop_session(key)
            return

        self._schedule_followup(key, response.id, self._signature(response))

    @command("ns", required=OWNER)
    async def ns_cmd(self, event) -> None:
        """Использовать бота"""
        message = event.message
        args = self.get_args(event)
        if not args:
            await utils.answer(message, "<b><emoji document_id=5210956306952758910>👀</emoji> Напишите команду</b>")
            return

        chat_id = utils.get_chat_id(message)

        msg = await self.send_wait(args)
        if msg is None:
            await utils.answer(message, "<b><emoji document_id=5210952531676504517>❌</emoji> Бот не ответил</b>")
            return

        markup = self.build_markup(msg.reply_markup, msg.id)
        html_text = self._render_html(msg)

        if not markup:
            await utils.answer(message, html_text or "")
            return

        inline = self.get_inline()
        if inline is None or not getattr(inline, "_bot", None):
            await utils.answer(message, html_text or "")
            return

        sent = await inline.form(html_text, message, reply_markup=markup)
        if not sent:
            await utils.answer(message, html_text or "")
            return

        form_message_id = getattr(sent, "id", None)
        if form_message_id is None:
            return

        target = _EditTarget(
            utils.get_chat_id(sent),
            form_message_id,
            self._find_inline_message_id(sent),
        )
        key = (chat_id, form_message_id)
        session = {
            "form": target,
            "bot_msg_id": msg.id,
            "user_msg_id": message.id,
            "text": html_text,
        }
        self.sessions[key] = session
        self.bot_index[msg.id] = key

        fresh = self._best_known(msg)
        if fresh is not None and fresh is not msg:
            fresh_text = self._render_html(fresh)
            fresh_markup = self.build_markup(fresh.reply_markup, fresh.id)
            await self._edit_target(target, fresh_text, fresh_markup)
            self._bind_bot_id(key, session, fresh.id)
            session["text"] = fresh_text
            if not fresh_markup:
                self._drop_session(key)
                return
            msg = fresh

        self._schedule_followup(key, msg.id, self._signature(msg))

    def _find_inline_message_id(self, sent):
        inline = self.get_inline()
        if inline is None:
            return None
        units = getattr(inline, "_units", None)
        if not units:
            return None
        sent_id = getattr(sent, "id", None)
        for unit in units.values():
            tmsg = unit.get("telethon_msg")
            if tmsg is not None and getattr(tmsg, "id", None) == sent_id:
                iid = unit.get("inline_message_id")
                if iid:
                    return iid
        for unit in units.values():
            iid = unit.get("inline_message_id")
            if iid:
                return iid
        return None
