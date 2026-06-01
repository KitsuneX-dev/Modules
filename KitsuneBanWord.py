# *      _                             __  __           _       _
# *     / \  _   _ _ __ ___  _ __ __ _|  \/  | ___   __| |_   _| | ___  ___ 
# *    / _ \| | | | '__/ _ \| '__/ _` | |\/| |/ _ \ / _` | | | | |/ _ \/ __|
# *   / ___ \ |_| | | | (_) | | | (_| | |  | | (_) | (_| | |_| | |  __/\__ \
# *  /_/   \_\__,_|_|  \___/|_|  \__,_|_|  |_|\___/ \__,_|\__,_|_|\___||___/
# *
# *                          © Copyright 2024
# *
# *                      https://t.me/AuroraModules
# *
# * 🔒 Code is licensed under GNU AGPLv3
# * 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# * ⛔️ You CANNOT edit this file without direct permission from the author.
# * ⛔️ You CANNOT distribute this file if you have modified it without the direct permission of the author.
#
# ============================================================================
#  Адаптация под UserBot Kitsune — оригинальная логика сохранена 1-в-1.
#  Original author: dend1yya (@AuroraModules)
#  Kitsune-port:    native Kitsune API (KitsuneModule / @command / @watcher)
# ============================================================================

# Name: KitsuneBanWord
# Author: dend1yya (Kitsune-port)
# Commands:
# .bwadd | .bword | .bwlist | .bwdel | .bwon | .bwoff
# scope: kitsune_only
# meta developer: @AuroraModules

# meta pic: https://i.postimg.cc/Hx3Zm8rB/logo.png
# meta banner: https://te.legra.ph/file/926b74bc3235fb03433ea.jpg

from __future__ import annotations

import contextlib
import logging
import typing
from datetime import timedelta

from ..core.loader import KitsuneModule, command, watcher, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..utils import get_args_raw, get_chat_id

logger = logging.getLogger(__name__)

_DB_KEY = "KitsuneBanWord"
_ALLOWED_ACTIONS: frozenset[str] = frozenset({"kick", "mute", "delete"})
_MUTE_DURATION = timedelta(hours=1)


class KitsuneBanWordMod(KitsuneModule):
    """Kitsune-port: модуль для управления запрещёнными словами в чате."""

    name = "KitsuneBanWord"
    description = "Manage banned words in a chat (kick / mute / delete) — Kitsune-port."
    author = "dend1yya"
    version = "1.0.0-kitsune"
    icon = "🛡"
    category = "moderation"

    strings_en = {
        "word_added": "<b><emoji document_id=5873153278023307367>📄</emoji> Banword successfully added:</b> <code>{}</code>",
        "kick": "<b><emoji document_id=5442879640379076105>👤</emoji> | User @{username} used a banned word and was kicked. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protected by AuroraModules</i>",
        "mute": "<b><emoji document_id=5442879640379076105>👤</emoji> | User @{username} used a banned word and was muted for 1 hour. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protected by AuroraModules</i>",
        "word_removed": "<b><emoji document_id=5445267414562389170>🗑</emoji> Banned word removed:</b> <code>{}</code>",
        "none_bw": "<b><emoji document_id=5287613115180006030>🤬</emoji> The list of prohibited words is empty.</b>",
        "bword_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Banned words are enabled in this chat</b>",
        "bword_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Prohibited words are disabled.</b>",
        "action_set": "<b><emoji document_id=5255999175174137421>🛡</emoji> Action set:</b> <code>{}</code>",
        "no_action": "<b><emoji document_id=5980953710157632545>❌</emoji> Action not specified. Use: kick, mute, delete</b>",
        "no_word": "<b><emoji document_id=5443038326535759644>💬</emoji> Word not specified</b>",
        "already_added": "<b><emoji document_id=5443038326535759644>💬</emoji> This word is already in the list.</b>",
        "not_found": "<b><emoji document_id=5443038326535759644>💬</emoji> This word is not in the list.</b>",
        "already_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Banned words are already enabled here.</b>",
        "already_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Banned words are already disabled here.</b>",
        "list_header": "<b><emoji document_id=5870984130560266604>💬</emoji> Banned Words:</b>\n<i>{}</i>",
    }

    strings_ru = {
        "word_added": "<b><emoji document_id=5873153278023307367>📄</emoji> Запрещённое слово добавлено:</b> <code>{}</code>",
        "kick": "<b><emoji document_id=5442879640379076105>👤</emoji> | Пользователь @{username} использовал запрещённое слово и был кикнут. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protected by AuroraModules</i>",
        "mute": "<b><emoji document_id=5442879640379076105>👤</emoji> | Пользователь @{username} использовал запрещённое слово и был замучен на 1 час. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protected by AuroraModules</i>",
        "word_removed": "<b><emoji document_id=5445267414562389170>🗑</emoji> Запрещённое слово удалено:</b> <code>{}</code>",
        "none_bw": "<b><emoji document_id=5287613115180006030>🤬</emoji> Список запрещённых слов пуст.</b>",
        "bword_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Банворды включены в этом чате.</b>",
        "bword_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Банворды выключены в этом чате.</b>",
        "action_set": "<b><emoji document_id=5255999175174137421>🛡</emoji> Действие установлено:</b> <code>{}</code>",
        "no_action": "<b><emoji document_id=5980953710157632545>❌</emoji> Действие не указано. Используйте: kick, mute, delete.</b>",
        "no_word": "<b><emoji document_id=5443038326535759644>💬</emoji> Слово не указано.</b>",
        "already_added": "<b><emoji document_id=5443038326535759644>💬</emoji> Это слово уже в списке.</b>",
        "not_found": "<b><emoji document_id=5443038326535759644>💬</emoji> Этого слова нет в списке.</b>",
        "already_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Банворды уже включены в этом чате.</b>",
        "already_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Банворды уже выключены в этом чате.</b>",
        "list_header": "<b><emoji document_id=5870984130560266604>💬</emoji> Запрещённые слова:</b>\n<i>{}</i>",
    }

    strings_uz = {
        "word_added": "<b><emoji document_id=5873153278023307367>📄</emoji> Taqiqlangan so'z qo'shildi:</b> <code>{}</code>",
        "kick": "<b><emoji document_id=5442879640379076105>👤</emoji> | Foydalanuvchi @{username} taqiqlangan soʻzni ishlatgan va haydalgan. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protected by AuroraModules</i>",
        "mute": "<b><emoji document_id=5442879640379076105>👤</emoji> | Foydalanuvchi @{username} taqiqlangan soʻzni ishlatgan va 1 soatga o'chirilgan. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protected by AuroraModules</i>",
        "word_removed": "<b><emoji document_id=5445267414562389170>🗑</emoji> Taqiqlangan soʻz olib tashlandi:</b> <code>{}</code>",
        "none_bw": "<b><emoji document_id=5287613115180006030>🤬</emoji> Taqiqlangan so'zlar ro'yxati bo'sh.</b>",
        "bword_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Bu chatda banwords yoqilgan.</b>",
        "bword_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Banwords o'chirilgan.</b>",
        "action_set": "<b><emoji document_id=5255999175174137421>🛡</emoji> Harakat muvaffaqiyatli o'rnatildi:</b> <code>{}</code>",
        "no_action": "<b><emoji document_id=5980953710157632545>❌</emoji> Harakat belgilanmagan, foydalaning: kick, mute, delete</b>",
        "no_word": "<b><emoji document_id=5443038326535759644>💬</emoji> So'z belgilanmagan</b>",
        "already_added": "<b><emoji document_id=5443038326535759644>💬</emoji> Bu so'z allaqachon ro'yxatda.</b>",
        "not_found": "<b><emoji document_id=5443038326535759644>💬</emoji> Bu so'z ro'yxatda yo'q.</b>",
        "already_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Banwords bu chatda allaqachon yoqilgan.</b>",
        "already_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Banwords bu chatda allaqachon o'chirilgan.</b>",
        "list_header": "<b><emoji document_id=5870984130560266604>💬</emoji> Taqiqlangan so'zlar:</b>\n<i>{}</i>",
    }

    strings_de = {
        "word_added": "<b><emoji document_id=5873153278023307367>📄</emoji> Verbotenes Wort hinzugefügt:</b> <code>{}</code>",
        "kick": "<b><emoji document_id=5442879640379076105>👤</emoji> | Benutzer @{username} hat ein verbotenes Wort verwendet und wurde rausgeworfen. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protected by AuroraModules</i>",
        "mute": "<b><emoji document_id=5442879640379076105>👤</emoji> | Benutzer @{username} hat ein verbotenes Wort verwendet und wurde für 1 Stunde stummgeschaltet. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protected by AuroraModules</i>",
        "word_removed": "<b><emoji document_id=5445267414562389170>🗑</emoji> Verbotenes Wort entfernt:</b> <code>{}</code>",
        "none_bw": "<b><emoji document_id=5287613115180006030>🤬</emoji> Die Liste der verbotenen Wörter ist leer.</b>",
        "bword_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Banwords sind in diesem Chat aktiviert.</b>",
        "bword_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Banwords sind in diesem Chat deaktiviert.</b>",
        "action_set": "<b><emoji document_id=5255999175174137421>🛡</emoji> Aktion erfolgreich festgelegt:</b> <code>{}</code>",
        "no_action": "<b><emoji document_id=5980953710157632545>❌</emoji> Aktion nicht angegeben, verwenden: kick, mute, delete</b>",
        "no_word": "<b><emoji document_id=5443038326535759644>💬</emoji> Das Wort ist nicht angegeben.</b>",
        "already_added": "<b><emoji document_id=5443038326535759644>💬</emoji> Dieses Wort ist bereits in der Liste.</b>",
        "not_found": "<b><emoji document_id=5443038326535759644>💬</emoji> Dieses Wort ist nicht in der Liste.</b>",
        "already_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Banwords sind hier bereits aktiviert.</b>",
        "already_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Banwords sind hier bereits deaktiviert.</b>",
        "list_header": "<b><emoji document_id=5870984130560266604>💬</emoji> Verbotene Wörter:</b>\n<i>{}</i>",
    }

    strings_es = {
        "word_added": "<b><emoji document_id=5873153278023307367>📄</emoji> Palabra prohibida añadida con éxito:</b> <code>{}</code>",
        "kick": "<b><emoji document_id=5442879640379076105>👤</emoji> | El usuario @{username} utilizó una palabra prohibida y fue expulsado. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protegido por AuroraModules</i>",
        "mute": "<b><emoji document_id=5442879640379076105>👤</emoji> | El usuario @{username} utilizó una palabra prohibida y fue silenciado por 1 hora. <emoji document_id=5253780051471642059>🛡</emoji></b>\n<i><emoji document_id=5231165412275668380>🥰</emoji> | Protegido por AuroraModules</i>",
        "word_removed": "<b><emoji document_id=5445267414562389170>🗑</emoji> Palabra prohibida eliminada:</b> <code>{}</code>",
        "none_bw": "<b><emoji document_id=5287613115180006030>🤬</emoji> La lista de palabras prohibidas está vacía.</b>",
        "bword_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Las palabras prohibidas están activadas en este chat</b>",
        "bword_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Las palabras prohibidas están desactivadas.</b>",
        "action_set": "<b><emoji document_id=5255999175174137421>🛡</emoji> Acción configurada:</b> <code>{}</code>",
        "no_action": "<b><emoji document_id=5980953710157632545>❌</emoji> Acción no especificada. Usa: kick, mute, delete</b>",
        "no_word": "<b><emoji document_id=5443038326535759644>💬</emoji> Palabra no especificada</b>",
        "already_added": "<b><emoji document_id=5443038326535759644>💬</emoji> Esta palabra ya está en la lista.</b>",
        "not_found": "<b><emoji document_id=5443038326535759644>💬</emoji> Esta palabra no está en la lista.</b>",
        "already_enabled": "<b><emoji document_id=5398001711786762757>✅</emoji> Las palabras prohibidas ya están activadas aquí.</b>",
        "already_disabled": "<b><emoji document_id=5388785832956016892>❌</emoji> Las palabras prohibidas ya están desactivadas aquí.</b>",
        "list_header": "<b><emoji document_id=5870984130560266604>💬</emoji> Palabras prohibidas:</b>\n<i>{}</i>",
    }

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "BAN_ACTION",
                "delete",
                "Действие при нахождении запрещённого слова: kick, mute, delete",
            ),
        )
        # Кэш для горячего пути watcher'а — пересобирается лениво при изменениях.
        self._cache_dirty: bool = True
        self._enabled_chats_cache: set[str] = set()
        self._banned_words_cache: tuple[str, ...] = ()

    async def on_load(self) -> None:
        # Подтягиваем сохранённое действие из БД, если оно было задано ранее.
        with contextlib.suppress(Exception):
            saved = self.db.get(_DB_KEY, "ban_action", None)
            if saved in _ALLOWED_ACTIONS and self.config is not None:
                self.config["BAN_ACTION"] = saved
        self._cache_dirty = True

    # ------------------------------------------------------------------ #
    #  Внутренние хелперы (хранилище + кэш)                              #
    # ------------------------------------------------------------------ #
    def _refresh_cache(self) -> None:
        """Пересобирает кэш списков из БД (вызывается лениво)."""
        self._enabled_chats_cache = set(self.db.get(_DB_KEY, "enabled_chats", []))
        self._banned_words_cache = tuple(self.db.get(_DB_KEY, "banned_words", []))
        self._cache_dirty = False

    def _get_enabled_chats(self) -> list[str]:
        return list(self.db.get(_DB_KEY, "enabled_chats", []))

    def _get_banned_words(self) -> list[str]:
        return list(self.db.get(_DB_KEY, "banned_words", []))

    @property
    def _action(self) -> str:
        return self.config["BAN_ACTION"] if self.config is not None else "delete"

    # ------------------------------------------------------------------ #
    #  Watcher — горячий путь, максимально дешёвый                       #
    # ------------------------------------------------------------------ #
    @watcher()
    async def banword_watcher(self, event) -> None:
        try:
            message = getattr(event, "message", None) or event
            text = getattr(message, "raw_text", None) or getattr(message, "text", "") or ""
            if not text:
                return

            if self._cache_dirty:
                self._refresh_cache()

            if not self._enabled_chats_cache or not self._banned_words_cache:
                return

            chat_id = get_chat_id(message)
            if chat_id is None or str(chat_id) not in self._enabled_chats_cache:
                return

            # Быстрая проверка вхождения запрещённых слов (как в оригинале —
            # подстрочное совпадение). Прерываемся на первом найденном.
            if not any(word in text for word in self._banned_words_cache):
                return

            await self._punish(message, chat_id)
        except Exception:
            # Watcher НИКОГДА не должен ронять юзербот.
            logger.exception("BanWord: watcher failed")

    async def _punish(self, message: typing.Any, chat_id: int) -> None:
        action = self._action
        client = getattr(message, "client", None) or self.client
        sender_id = getattr(message, "sender_id", None)

        if action == "delete":
            with contextlib.suppress(Exception):
                await message.delete()
            return

        if sender_id is None:
            # Без отправителя можем лишь удалить.
            with contextlib.suppress(Exception):
                await message.delete()
            return

        username = await self._username(message, sender_id)

        if action == "kick":
            try:
                entity = await client.get_input_entity(chat_id)
                await client.kick_participant(entity, sender_id)
            except Exception:
                logger.debug("BanWord: kick failed", exc_info=True)
                return
            with contextlib.suppress(Exception):
                await message.respond(
                    self.strings("kick").format(username=username),
                    parse_mode="html",
                )

        elif action == "mute":
            try:
                entity = await client.get_input_entity(chat_id)
                await client.edit_permissions(
                    entity,
                    sender_id,
                    until_date=_MUTE_DURATION,
                    send_messages=False,
                )
            except Exception:
                logger.debug("BanWord: mute failed", exc_info=True)
                return
            with contextlib.suppress(Exception):
                await message.respond(
                    self.strings("mute").format(username=username),
                    parse_mode="html",
                )

    @staticmethod
    async def _username(message: typing.Any, sender_id: int) -> str:
        """Безопасно достать @username отправителя."""
        sender = getattr(message, "sender", None)
        if sender is not None and getattr(sender, "username", None):
            return sender.username
        with contextlib.suppress(Exception):
            sender = await message.get_sender()
            if sender is not None and getattr(sender, "username", None):
                return sender.username
        return str(sender_id)

    # ------------------------------------------------------------------ #
    #  Команды                                                           #
    # ------------------------------------------------------------------ #
    @command("bwadd", required=OWNER)
    async def bwadd_cmd(self, event) -> None:
        """Adds a banned word | Добавляет запрещённое слово."""
        args = get_args_raw(event.message)
        if not args:
            await event.edit(self.strings("no_word"), parse_mode="html")
            return
        banned_words = self._get_banned_words()
        if args in banned_words:
            await event.edit(self.strings("already_added"), parse_mode="html")
            return
        banned_words.append(args)
        await self.db.set(_DB_KEY, "banned_words", banned_words)
        self._cache_dirty = True
        await event.edit(self.strings("word_added").format(args), parse_mode="html")

    @command("bwdel", required=OWNER)
    async def bwdel_cmd(self, event) -> None:
        """Removes a banned word | Удаляет запрещённое слово."""
        args = get_args_raw(event.message)
        if not args:
            await event.edit(self.strings("no_word"), parse_mode="html")
            return
        banned_words = self._get_banned_words()
        if args not in banned_words:
            await event.edit(self.strings("not_found"), parse_mode="html")
            return
        banned_words.remove(args)
        await self.db.set(_DB_KEY, "banned_words", banned_words)
        self._cache_dirty = True
        await event.edit(self.strings("word_removed").format(args), parse_mode="html")

    @command("bwon", required=OWNER)
    async def bwon_cmd(self, event) -> None:
        """Enables banwords in chat | Включает банворды в чате."""
        chat_id = str(get_chat_id(event.message))
        enabled_chats = self._get_enabled_chats()
        if chat_id in enabled_chats:
            await event.edit(self.strings("already_enabled"), parse_mode="html")
            return
        enabled_chats.append(chat_id)
        await self.db.set(_DB_KEY, "enabled_chats", enabled_chats)
        self._cache_dirty = True
        await event.edit(self.strings("bword_enabled"), parse_mode="html")

    @command("bwoff", required=OWNER)
    async def bwoff_cmd(self, event) -> None:
        """Disables banwords in chat | Отключает банворды в чате."""
        chat_id = str(get_chat_id(event.message))
        enabled_chats = self._get_enabled_chats()
        if chat_id not in enabled_chats:
            await event.edit(self.strings("already_disabled"), parse_mode="html")
            return
        enabled_chats.remove(chat_id)
        await self.db.set(_DB_KEY, "enabled_chats", enabled_chats)
        self._cache_dirty = True
        await event.edit(self.strings("bword_disabled"), parse_mode="html")

    @command("bword", required=OWNER)
    async def bword_cmd(self, event) -> None:
        """Sets the action (kick, mute, delete) | Устанавливает действие (kick, mute, delete)."""
        args = (get_args_raw(event.message) or "").strip().lower()
        if args not in _ALLOWED_ACTIONS:
            await event.edit(self.strings("no_action"), parse_mode="html")
            return
        if self.config is not None:
            self.config["BAN_ACTION"] = args
        await self.db.set(_DB_KEY, "ban_action", args)
        await event.edit(self.strings("action_set").format(args), parse_mode="html")

    @command("bwlist", required=OWNER)
    async def bwlist_cmd(self, event) -> None:
        """Displays a list of prohibited words | Выводит список запрещённых слов."""
        banned_words = self._get_banned_words()
        if not banned_words:
            await event.edit(self.strings("none_bw"), parse_mode="html")
            return
        word_list = "\n".join(f"• {word}" for word in banned_words)
        await event.edit(
            self.strings("list_header").format(word_list),
            parse_mode="html",
        )
