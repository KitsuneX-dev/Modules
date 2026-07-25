# meta developer: @Nazomi_Modules
# Адаптация под Kitsune @Mikasu32
__version__ = (3, 4, 0)

import asyncio
from telethon.tl.types import (
    ChatAdminRights,
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
    def __init__(self, chat_id, message_id, inline_message_id=None):
        self.chat_id = chat_id
        self.message_id = message_id
        self.inline_message_id = inline_message_id


class NazomiEvrywhEVOK(KitsuneModule):
    name        = "NazomiEvrywhEVOK"
    description = "Модуль для использования бота везде"
    author      = "@Nazomi_Modules | Kitsune-адаптация: @Mikasu32"
    version     = "3.4.0"
    icon        = "🌐"
    category    = "evo"

    BOT_ID = 5522271758

    WAIT_WORDS = ("Ожидайте", "ожидайте", "Загрузка", "загрузка", "Подождите", "подождите")
    WAIT_SYMBOLS = ("⏳", "⌛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🔄")
    PLACEHOLDER_MAX_LEN = 60

    SETTLE_DELAY = 1.1
    CALLBACK_SETTLE = 0.6
    FIRST_TIMEOUT = 25.0
    REPLY_TIMEOUT = 20.0
    CALLBACK_TIMEOUT = 12.0

    BTN_TEXT_MAX = 48
    ROW_MAX = 5
    KEYBOARD_SCAN_LIMIT = 40

    REFRESH_BTN = "🔄 Обновить"
    INPUT_BTN = "✍️ Написать"
    INPUT_HINT = "✍️ Введи текст для бота"
    CLOSE_BTN = "🔻 Закрыть"

    async def on_load(self) -> None:
        self.sessions = {}
        self.pending_future = None
        self.pending_handlers = []
        self.pending_timer = None

        self.keyboard_rows = []
        self.keyboard_single_use = False
        self.keyboard_msg_id = 0

        try:
            self.channel, _ = await utils.asset_channel(
                self.client,
                "NazomiEvrywhEVOK",
                description="Чат для использования команд",
                silent=True,
                archive=True,
            )
            if not self.db.get(self.name, "done_1", False):
                try:
                    await self.client(functions.channels.InviteToChannelRequest(self.channel, [self.BOT_ID]))
                    self.db.set_sync(self.name, "done_1", True)
                except Exception:
                    self.channel = None

            if self.channel is not None and not self.db.get(self.name, "done_2", False):
                try:
                    await self.client(functions.channels.EditAdminRequest(self.channel, self.BOT_ID, ChatAdminRights(ban_users=True), "EVO"))
                    self.db.set_sync(self.name, "done_2", True)
                except Exception:
                    pass
        except Exception:
            self.channel = None

        self.peer = self.channel if self.channel else self.BOT_ID

        self.loop = asyncio.get_running_loop()

        await self._restore_keyboard()

    async def on_unload(self) -> None:
        self.cancel_pending()

    def get_inline(self):
        return getattr(self.client, "_kitsune_inline", None)

    def remove(self, handler):
        try:
            self.client.remove_event_handler(handler)
        except Exception:
            pass

    def cancel_pending(self):
        if self.pending_timer is not None:
            try:
                self.pending_timer.cancel()
            except Exception:
                pass
            self.pending_timer = None

        for h in self.pending_handlers:
            self.remove(h)
        self.pending_handlers = []

        if self.pending_future and not self.pending_future.done():
            self.pending_future.cancel()
        self.pending_future = None

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
        text = getattr(msg, "text", "") or ""
        return text

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

    async def _collect(self, first_id, timeout):
        fut = self.loop.create_future()
        state = {"best": None, "timer": None}

        def schedule_settle():
            if state["timer"] is not None:
                state["timer"].cancel()

            def settle():
                if not fut.done():
                    fut.set_result(state["best"])

            state["timer"] = self.loop.call_later(self.SETTLE_DELAY, settle)

        def consider(msg):
            if msg is None:
                return
            self._update_keyboard(msg)
            if self._better(msg, state["best"]):
                state["best"] = msg
            if state["best"] is not None and not self._is_placeholder(state["best"]):
                schedule_settle()

        async def on_new(event):
            if fut.done():
                return
            consider(event.message)

        async def on_edit(event):
            if fut.done():
                return
            consider(event.message)

        self.client.add_event_handler(on_new, events.NewMessage(chats=self.peer, incoming=True, from_users=self.BOT_ID))
        self.client.add_event_handler(on_edit, events.MessageEdited(chats=self.peer, from_users=self.BOT_ID))
        handlers = [on_new, on_edit]
        self.pending_handlers = handlers
        self.pending_future = fut

        try:
            result = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            result = state["best"]
            probe_id = first_id or (result.id if result else None)
            if result is None and probe_id is not None:
                try:
                    msgs = await self.client.get_messages(self.peer, ids=[probe_id])
                    result = msgs[0] if msgs and msgs[0] else None
                    self._update_keyboard(result)
                except Exception:
                    result = None
        except asyncio.CancelledError:
            result = None
        finally:
            if state["timer"] is not None:
                try:
                    state["timer"].cancel()
                except Exception:
                    pass
            for h in handlers:
                self.remove(h)
            if self.pending_future is fut:
                self.pending_future = None
                self.pending_handlers = []

        if self._is_placeholder(result):
            return None
        return result

    async def send_wait(self, text, bot_msg_id=None):
        self.cancel_pending()
        await self.client.send_message(self.peer, text, reply_to=bot_msg_id)
        timeout = self.REPLY_TIMEOUT if bot_msg_id else self.FIRST_TIMEOUT
        return await self._collect(bot_msg_id, timeout)

    async def send_text(self, text, bot_msg_id=None):
        self.cancel_pending()
        try:
            await self.client.send_message(self.peer, text, reply_to=bot_msg_id)
        except Exception:
            try:
                await self.client.send_message(self.peer, text)
            except Exception:
                return None
        return await self._collect(bot_msg_id, self.REPLY_TIMEOUT)

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

    async def _edit_target(self, target, text, markup):
        inline = self.get_inline()
        if inline is None or target is None:
            return
        try:
            await inline.edit(target, text, reply_markup=markup)
        except Exception:
            pass

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

    async def _snapshot(self, msg_id):
        try:
            msgs = await self.client.get_messages(self.peer, ids=[msg_id])
            msg = msgs[0] if msgs and msgs[0] else None
            self._update_keyboard(msg)
            return msg, self._signature(msg)
        except Exception:
            return None, None

    async def _collect_callback(self, msg_id, data, call=None):
        before_msg, before_sig = await self._snapshot(msg_id)

        fut = self.loop.create_future()
        state = {
            "best": None,
            "timer": None,
            "answer": None,
            "tracked": msg_id,
            "deleted": False,
            "changed": False,
            "alerted": False,
        }

        def schedule_settle(delay):
            if state["timer"] is not None:
                state["timer"].cancel()

            def settle():
                if not fut.done():
                    fut.set_result(state["best"])

            state["timer"] = self.loop.call_later(delay, settle)

        def consider(msg):
            if msg is None:
                return
            self._update_keyboard(msg)
            if self._better(msg, state["best"]):
                state["best"] = msg
            best = state["best"]
            if best is None or self._is_placeholder(best):
                return
            if before_sig is not None and self._signature(best) == before_sig:
                schedule_settle(self.SETTLE_DELAY)
                return
            state["changed"] = True
            schedule_settle(self.CALLBACK_SETTLE)

        async def on_edit(event):
            if fut.done():
                return
            if event.message.id == state["tracked"] or self._has_markup(event.message):
                consider(event.message)

        async def on_new(event):
            if fut.done():
                return
            consider(event.message)

        async def on_delete(event):
            if state["tracked"] in event.deleted_ids and not fut.done():
                state["deleted"] = True
                self.loop.call_later(0.5, lambda: fut.set_result(state["best"]) if not fut.done() else None)

        self.client.add_event_handler(on_edit, events.MessageEdited(chats=self.peer, from_users=self.BOT_ID))
        self.client.add_event_handler(on_new, events.NewMessage(chats=self.peer, incoming=True, from_users=self.BOT_ID))
        self.client.add_event_handler(on_delete, events.MessageDeleted(chats=self.peer))

        async def fire_callback():
            try:
                answer = await self.client(functions.messages.GetBotCallbackAnswerRequest(self.peer, msg_id, data=data))
            except Exception:
                answer = None
            state["answer"] = answer

            alert_text = getattr(answer, "message", None) if answer else None
            if alert_text and call is not None and not state["alerted"]:
                try:
                    await call.answer(alert_text, show_alert=bool(getattr(answer, "alert", False)))
                    state["alerted"] = True
                except Exception:
                    pass

            if answer is not None:
                if state["best"] is None and not state["changed"]:
                    if not fut.done():
                        schedule_settle(self.CALLBACK_SETTLE)

        asyncio.create_task(fire_callback())

        try:
            updated = await asyncio.wait_for(fut, self.CALLBACK_TIMEOUT)
        except asyncio.TimeoutError:
            updated = state["best"]
        finally:
            if state["timer"] is not None:
                try:
                    state["timer"].cancel()
                except Exception:
                    pass
            self.remove(on_edit)
            self.remove(on_new)
            self.remove(on_delete)

        if self._is_placeholder(updated):
            updated = None

        if updated is None and not state["deleted"]:
            latest, latest_sig = await self._snapshot(msg_id)
            if latest is not None and not self._is_placeholder(latest):
                updated = latest

        return updated, state["answer"], state["deleted"], before_sig, state["alerted"]

    def _find_session(self, msg_id):
        for key, session in self.sessions.items():
            if session.get("bot_msg_id") == msg_id:
                return key, session
        return None, None

    def _sync_target(self, session, call):
        target = session.get("form")
        if target is not None and getattr(target, "inline_message_id", None) is None:
            iid = getattr(call, "inline_message_id", None)
            if iid:
                target.inline_message_id = iid
        return target

    async def _handle_response(self, call, msg_id, updated, cb_result, deleted=False, before_sig=None, already_alerted=False):
        alerted = already_alerted
        if not alerted and cb_result and getattr(cb_result, "message", None):
            try:
                await call.answer(cb_result.message, show_alert=bool(getattr(cb_result, "alert", False)))
                alerted = True
            except Exception:
                pass

        session_key, session = self._find_session(msg_id)

        if updated is None:
            if not alerted:
                try:
                    await call.answer()
                except Exception:
                    pass
            if deleted and session is not None:
                target = self._sync_target(session, call)
                await self._edit_target(target, "<b>Готово</b>", [])
                self.sessions.pop(session_key, None)
            return

        markup = self.build_markup(updated.reply_markup, updated.id)
        text = self._render_html(updated)

        if session is not None:
            target = self._sync_target(session, call)
            await self._edit_target(target, text, markup)
            session["bot_msg_id"] = updated.id
            session["text"] = text
        else:
            try:
                await self._edit_target(call, text, markup)
            except Exception:
                pass

        if not alerted:
            try:
                await call.answer()
            except Exception:
                pass

        if not markup and session is not None and session_key is not None:
            self.sessions.pop(session_key, None)

    async def proxy_callback(self, call, data, msg_id):
        updated, cb_result, deleted, before_sig, alerted = await self._collect_callback(msg_id, data, call)
        await self._handle_response(call, msg_id, updated, cb_result, deleted, before_sig, alerted)

    async def proxy_text_button(self, call, text, msg_id):
        try:
            await call.answer()
        except Exception:
            pass

        if self.keyboard_single_use:
            self.keyboard_rows = []
            self.keyboard_single_use = False

        updated = await self.send_text(text, msg_id)
        await self._handle_response(call, msg_id, updated, None, already_alerted=True)

    async def proxy_input(self, call, value, msg_id):
        value = (value or "").strip()
        if not value:
            return
        updated = await self.send_text(value, msg_id)
        await self._handle_response(call, msg_id, updated, None, already_alerted=True)

    async def proxy_refresh(self, call, msg_id):
        latest, _ = await self._snapshot(msg_id)
        if latest is None:
            try:
                await call.answer("Сообщение недоступно", show_alert=True)
            except Exception:
                pass
            return
        await self._handle_response(call, msg_id, latest, None)

    async def proxy_close(self, call, msg_id):
        session_key, session = self._find_session(msg_id)
        target = self._sync_target(session, call) if session is not None else call
        text = (session or {}).get("text") or "<b>Закрыто</b>"
        await self._edit_target(target, text, [])
        if session_key is not None:
            self.sessions.pop(session_key, None)
        try:
            await call.answer()
        except Exception:
            pass

    @watcher(no_commands=True, only_reply=True)
    async def evo_watcher(self, event) -> None:
        message = event.message
        if message.sender_id != self.tg_id:
            return

        if not message.text:
            return

        reply_id = message.reply_to_msg_id
        if not reply_id:
            return

        chat_id = utils.get_chat_id(message)
        session = self.sessions.get((chat_id, reply_id))
        if not session:
            return

        text = message.text
        bot_message_id = session.get("bot_msg_id")
        if not bot_message_id:
            return

        response = await self.send_wait(text, bot_message_id)

        if response is None:
            return

        session["bot_msg_id"] = response.id
        session["user_msg_id"] = message.id

        markup = self.build_markup(response.reply_markup, response.id)
        html_text = self._render_html(response)
        session["text"] = html_text

        await self._edit_target(session.get("form"), html_text, markup)

        if not markup:
            self.sessions.pop((chat_id, reply_id), None)

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

        form_chat_id = utils.get_chat_id(sent)
        form_message_id = getattr(sent, "id", None)
        if form_message_id is None:
            return

        inline_message_id = self._find_inline_message_id(sent)
        target = _EditTarget(form_chat_id, form_message_id, inline_message_id)
        self.sessions[(chat_id, form_message_id)] = {
            "form": target,
            "bot_msg_id": msg.id,
            "user_msg_id": message.id,
            "text": html_text,
        }
