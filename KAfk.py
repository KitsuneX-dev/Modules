# ---------------------------------------------------------------------------------
# Name: KAfk
# Description: Персональный AFK-ассистент: автоответ, пока вы не в сети
# Author: hikka_mods
# Адаптировано под Kitsune @Mikasu32
# ---------------------------------------------------------------------------------
# Оригинал: @hikka_mods | Адаптация, ускорение и стабилизация: @Mikasu32
# ---------------------------------------------------------------------------------

from __future__ import annotations

import datetime
import logging
import time

from telethon import types

from ..core.loader import KitsuneModule, command, watcher, ModuleConfig, ConfigValue
from ..core.security import OWNER
from ..utils import escape_html
from ..validators import Series, Integer

logger = logging.getLogger(__name__)

_DB = "kitsune.kafk"
_REPLY_COOLDOWN = 30         # антиспам: не чаще раза в N сек на пользователя


def _fmt_timedelta(delta: datetime.timedelta) -> str:
    total = int(delta.total_seconds())
    if total < 0:
        total = 0
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}м")
    parts.append(f"{seconds}с")
    return " ".join(parts)


class KAfkModule(KitsuneModule):
    name        = "KAfk"
    description = "AFK-ассистент с автоответом. Адаптировано под Kitsune @Mikasu32"
    author      = "hikka_mods | @Mikasu32"
    version     = "2.0.0"
    icon        = "🫶"
    category    = "tools"

    strings_ru = {
        "afk_on":            "🫶 <b>AFK-режим включён!</b>",
        "afk_on_reason":     "🫶 <b>AFK-режим включён!</b>\n\n<b>Причина:</b> <i>{reason}</i>",
        "afk_here_on":       "🫶 <b>AFK-режим включён в этом чате!</b>",
        "afk_here_on_reason":"🫶 <b>AFK-режим включён в этом чате!</b>\n\n<b>Причина:</b> <i>{reason}</i>",
        "afk_off":           "🤌 <b>AFK-режим отключён!</b>\n\n<b>Вы были AFK:</b> {time}",
        "afk_off_here":      "🤌 <b>AFK-режим отключён в этом чате!</b>\n\n<b>Вы были AFK:</b> {time}",
        "already_afk":       "❌ <b>Вы уже в AFK-режиме!</b>",
        "already_afk_here":  "❌ <b>Вы уже в AFK-режиме в этом чате!</b>",
        "not_afk":           "😐 <b>AFK-режим уже отключён.</b>",
        "not_afk_here":      "😐 <b>AFK-режим уже отключён в этом чате.</b>",
        "afk_message":       "🫤 <b>Сейчас я не в сети!</b>\n\n<i>В режиме AFK уже:</i> {time}",
        "afk_message_reason":"🫤 <b>Сейчас я не в сети!</b>\n<b>Причина:</b> <i>{reason}</i>\n\n<i>В режиме AFK уже:</i> {time}",
        "added_excluded":    "✅ <b>Чат</b> <code>{chat}</code> <b>добавлен в исключения.</b>",
        "removed_excluded":  "✅ <b>Чат</b> <code>{chat}</code> <b>убран из исключений.</b>",
        "excluded_list":     "📋 <b>Исключённые чаты:</b>\n{list}",
        "no_excluded":       "📋 <b>Список исключений пуст.</b>",
        "invalid_chat":      "❌ <b>Неверный ID чата.</b>",
        "already_excluded":  "❌ <b>Чат</b> <code>{chat}</code> <b>уже в исключениях.</b>",
        "not_excluded":      "❌ <b>Чат</b> <code>{chat}</code> <b>не в исключениях.</b>",
    }

    strings_en = {
        "afk_on":            "🫶 <b>AFK mode is on!</b>",
        "afk_on_reason":     "🫶 <b>AFK mode is on!</b>\n\n<b>Reason:</b> <i>{reason}</i>",
        "afk_here_on":       "🫶 <b>AFK mode is on in this chat!</b>",
        "afk_here_on_reason":"🫶 <b>AFK mode is on in this chat!</b>\n\n<b>Reason:</b> <i>{reason}</i>",
        "afk_off":           "🤌 <b>AFK mode is off!</b>\n\n<b>You were AFK for:</b> {time}",
        "afk_off_here":      "🤌 <b>AFK mode is off in this chat!</b>\n\n<b>You were AFK for:</b> {time}",
        "already_afk":       "❌ <b>You are already AFK!</b>",
        "already_afk_here":  "❌ <b>You are already AFK in this chat!</b>",
        "not_afk":           "😐 <b>AFK mode is already off.</b>",
        "not_afk_here":      "😐 <b>AFK mode is already off in this chat.</b>",
        "afk_message":       "🫤 <b>I'm currently away!</b>\n\n<i>AFK for:</i> {time}",
        "afk_message_reason":"🫤 <b>I'm currently away!</b>\n<b>Reason:</b> <i>{reason}</i>\n\n<i>AFK for:</i> {time}",
        "added_excluded":    "✅ <b>Chat</b> <code>{chat}</code> <b>added to exclusions.</b>",
        "removed_excluded":  "✅ <b>Chat</b> <code>{chat}</code> <b>removed from exclusions.</b>",
        "excluded_list":     "📋 <b>Excluded chats:</b>\n{list}",
        "no_excluded":       "📋 <b>No excluded chats.</b>",
        "invalid_chat":      "❌ <b>Invalid chat ID.</b>",
        "already_excluded":  "❌ <b>Chat</b> <code>{chat}</code> <b>is already excluded.</b>",
        "not_excluded":      "❌ <b>Chat</b> <code>{chat}</code> <b>is not excluded.</b>",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "excluded_chats",
                [],
                "Список ID чатов, где AFK не срабатывает",
                validator=Series(validator=Integer()),
            ),
        )
        # быстрый in-memory кэш состояния (чтобы watcher не лез в БД на каждое сообщение)
        self._global_afk: bool = False
        self._global_reason: str | None = None
        self._global_since: float | None = None
        self._here: dict[int, dict] = {}          # chat_id -> {reason, since}
        self._cooldown: dict[int, float] = {}      # user_id -> last reply ts

    async def on_load(self) -> None:
        self._me = await self.client.get_me()
        # восстанавливаем состояние из БД
        self._global_afk = bool(self.db.get(_DB, "global_afk", False))
        self._global_reason = self.db.get(_DB, "global_reason", None)
        self._global_since = self.db.get(_DB, "global_since", None)
        self._here = self.db.get(_DB, "here", {}) or {}
        # ключи JSON всегда строки → нормализуем в int
        self._here = {int(k): v for k, v in self._here.items()}
        logger.debug("KAfk loaded: global=%s here=%s", self._global_afk, list(self._here))

    # ------------------------------------------------------------------ helpers
    async def _persist_global(self) -> None:
        await self.db.set(_DB, "global_afk", self._global_afk)
        await self.db.set(_DB, "global_reason", self._global_reason)
        await self.db.set(_DB, "global_since", self._global_since)

    async def _persist_here(self) -> None:
        await self.db.set(_DB, "here", {str(k): v for k, v in self._here.items()})

    def _excluded(self) -> list[int]:
        if self.config and self.config["excluded_chats"]:
            return self.config["excluded_chats"]
        return []

    # ------------------------------------------------------------------ commands
    @command("afk", required=OWNER)
    async def afk_cmd(self, event) -> None:
        """Включить глобальный AFK-режим. Пример: .afk [причина]."""
        if self._global_afk:
            await event.edit(self.strings("already_afk"), parse_mode="html")
            return
        reason = self.get_args(event).strip() or None
        self._global_afk = True
        self._global_reason = reason
        self._global_since = time.time()
        await self._persist_global()
        text = (
            self.strings("afk_on_reason").format(reason=escape_html(reason))
            if reason else self.strings("afk_on")
        )
        await event.edit(text, parse_mode="html")

    @command("afkhere", required=OWNER)
    async def afkhere_cmd(self, event) -> None:
        """Включить AFK только в текущем чате. Пример: .afkhere [причина]."""
        chat_id = event.chat_id
        if chat_id in self._here:
            await event.edit(self.strings("already_afk_here"), parse_mode="html")
            return
        reason = self.get_args(event).strip() or None
        self._here[chat_id] = {"reason": reason, "since": time.time()}
        await self._persist_here()
        text = (
            self.strings("afk_here_on_reason").format(reason=escape_html(reason))
            if reason else self.strings("afk_here_on")
        )
        await event.edit(text, parse_mode="html")

    @command("unafk", required=OWNER)
    async def unafk_cmd(self, event) -> None:
        """Выключить глобальный AFK-режим и показать сколько времени вы были AFK. Пример: .unafk"""
        if not self._global_afk:
            await event.edit(self.strings("not_afk"), parse_mode="html")
            return
        elapsed = datetime.timedelta(seconds=time.time() - (self._global_since or time.time()))
        self._global_afk = False
        self._global_reason = None
        self._global_since = None
        await self._persist_global()
        await event.edit(
            self.strings("afk_off").format(time=_fmt_timedelta(elapsed)),
            parse_mode="html",
        )

    @command("unafkhere", required=OWNER)
    async def unafkhere_cmd(self, event) -> None:
        """Выключить AFK в текущем чате и показать сколько вы были AFK. Пример: .unafkhere"""
        chat_id = event.chat_id
        data = self._here.pop(chat_id, None)
        if data is None:
            await event.edit(self.strings("not_afk_here"), parse_mode="html")
            return
        await self._persist_here()
        elapsed = datetime.timedelta(seconds=time.time() - (data.get("since") or time.time()))
        await event.edit(
            self.strings("afk_off_here").format(time=_fmt_timedelta(elapsed)),
            parse_mode="html",
        )

    # ------------------------------------------------------------------ exclusions
    @command("afkexclude", required=OWNER, aliases=["afkex"])
    async def afkexclude_cmd(self, event) -> None:
        """Добавить или убрать чат из исключений AFK (без аргумента — текущий чат). Пример: .afkexclude или .afkexclude -100123456. Псевдоним: .afkex"""
        arg = self.get_args(event).strip()
        if arg:
            try:
                chat_id = int(arg)
            except ValueError:
                await event.edit(self.strings("invalid_chat"), parse_mode="html")
                return
        else:
            chat_id = event.chat_id

        excluded = list(self._excluded())
        if chat_id in excluded:
            excluded.remove(chat_id)
            self.config["excluded_chats"] = excluded
            await self.db.set("kitsune.config.kafk", "excluded_chats", excluded)
            await event.edit(
                self.strings("removed_excluded").format(chat=chat_id), parse_mode="html"
            )
        else:
            excluded.append(chat_id)
            self.config["excluded_chats"] = excluded
            await self.db.set("kitsune.config.kafk", "excluded_chats", excluded)
            await event.edit(
                self.strings("added_excluded").format(chat=chat_id), parse_mode="html"
            )

    @command("afkexcluded", required=OWNER, aliases=["afkexlist"])
    async def afkexcluded_cmd(self, event) -> None:
        """Показать список чатов, где AFK-автоответ не работает. Пример: .afkexcluded. Псевдоним: .afkexlist"""
        excluded = self._excluded()
        if not excluded:
            await event.edit(self.strings("no_excluded"), parse_mode="html")
            return
        lst = "\n".join(f"  • <code>{c}</code>" for c in excluded)
        await event.edit(self.strings("excluded_list").format(list=lst), parse_mode="html")

    # ------------------------------------------------------------------ watcher
    @watcher()
    async def afk_watcher(self, event) -> None:
        message = getattr(event, "message", None)
        if not isinstance(message, types.Message):
            return

        # реагируем только на чужие входящие
        sender_id = message.sender_id
        if not sender_id or sender_id == getattr(self._me, "id", 0):
            return

        chat_id = event.chat_id
        if chat_id in self._excluded():
            return

        is_private = bool(getattr(event, "is_private", False))
        is_mentioned = bool(getattr(message, "mentioned", False))

        # определяем активный AFK для этого контекста
        reason = None
        since = None
        here = self._here.get(chat_id)
        if here is not None:
            reason = here.get("reason")
            since = here.get("since")
        elif self._global_afk and (is_private or is_mentioned):
            reason = self._global_reason
            since = self._global_since
        else:
            return

        if since is None:
            return

        # антиспам по пользователю
        now = time.time()
        last = self._cooldown.get(sender_id, 0)
        if now - last < _REPLY_COOLDOWN:
            return

        # не отвечаем ботам/каналам/себе
        try:
            sender = await event.get_sender()
            if getattr(sender, "bot", False) or getattr(sender, "verified", False):
                return
        except Exception:
            pass

        self._cooldown[sender_id] = now

        elapsed = datetime.timedelta(seconds=now - since)
        text = (
            self.strings("afk_message_reason").format(
                reason=escape_html(reason), time=_fmt_timedelta(elapsed)
            )
            if reason
            else self.strings("afk_message").format(time=_fmt_timedelta(elapsed))
        )

        try:
            reply = await message.reply(text, parse_mode="html")
        except Exception:
            logger.debug("KAfk: failed to send AFK reply", exc_info=True)
            return

