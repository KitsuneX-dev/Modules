# meta developer: @codrago_m (adapted for Kitsune)
# scope: Kitsune
# Adapted & hardened for Kitsune UserBot.
# Original: ChatModule by @codrago_m (Hikka/Heroku). Rewritten 1-в-1 by logic,
# xdlib helpers re-implemented inline, prefixed with "K".

from __future__ import annotations

import asyncio
import contextlib
import logging
import typing
from datetime import datetime, timedelta, timezone

from telethon.tl import types
from telethon.tl import functions
from telethon.tl.functions import channels, messages
from telethon.tl.types import (
    ChatBannedRights,
    ChatAdminRights,
)

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER
from ..utils import answer, escape_html, get_args

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
#  ВСТРОЕННЫЕ ХЕЛПЕРЫ (замена внешней xdlib, которой нет в Kitsune)
# ────────────────────────────────────────────────────────────────────────────

class KParse:
    """Парсинг опций / времени (замена xdlib.parse)."""

    @staticmethod
    def opts(args: typing.Union[list, str]) -> dict:
        """Разбирает аргументы вида `-u value --user value -b` в dict.

        Поддерживает короткие (-x) и длинные (--xxx) флаги. Флаг без
        следующего значения считается булевым (True).
        """
        if isinstance(args, str):
            tokens = args.split()
        else:
            tokens = list(args)

        result: dict = {}
        i = 0
        n = len(tokens)
        while i < n:
            tok = tokens[i]
            if tok.startswith("--") and len(tok) > 2:
                key = tok[2:]
                if i + 1 < n and not tokens[i + 1].startswith("-"):
                    result[key] = tokens[i + 1]
                    i += 2
                else:
                    result[key] = True
                    i += 1
            elif tok.startswith("-") and len(tok) > 1 and not tok[1:].isdigit():
                key = tok[1:]
                if i + 1 < n and not (
                    tokens[i + 1].startswith("-") and not tokens[i + 1][1:].isdigit()
                ):
                    result[key] = tokens[i + 1]
                    i += 2
                else:
                    result[key] = True
                    i += 1
            else:
                i += 1
        return result

    @staticmethod
    def time(value: typing.Optional[str]) -> typing.Optional[int]:
        """`10m`, `2h`, `1d`, `30s`, `90` → секунды."""
        if not value or value is True:
            return None
        value = str(value).strip().lower()
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        try:
            if value[-1] in units:
                return int(float(value[:-1]) * units[value[-1]])
            return int(float(value))
        except (ValueError, IndexError):
            return None

    @staticmethod
    def minutes_to_hhmm(total_minutes: int) -> str:
        minutes_in_day = total_minutes % (24 * 60)
        hh = minutes_in_day // 60
        mm = minutes_in_day % 60
        return f"{hh:02d}:{mm:02d}"


class KFormat:
    """Форматирование (замена xdlib.format)."""

    @staticmethod
    def time(seconds: typing.Optional[int]) -> str:
        if not seconds:
            return "0s"
        seconds = int(seconds)
        parts = []
        for unit, length in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
            if seconds >= length:
                value, seconds = divmod(seconds, length)
                parts.append(f"{value}{unit}")
        return " ".join(parts) if parts else "0s"


# ── Битовые маски прав (замена xdlib.admin_rights / xdlib.banned_rights) ────

class KAdminRights:
    """Обёртка над ChatAdminRights с битовой маской."""

    RIGHTS_LIST = [
        "change_info",
        "post_messages",
        "edit_messages",
        "delete_messages",
        "ban_users",
        "invite_users",
        "pin_messages",
        "add_admins",
        "anonymous",
        "manage_call",
        "other",
        "manage_topics",
    ]

    def __init__(self, mask: int = 0) -> None:
        self.mask = int(mask)

    def has_index(self, idx: int) -> bool:
        return bool(self.mask & (1 << idx))

    def add(self, *names: str) -> "KAdminRights":
        for name in names:
            with contextlib.suppress(ValueError):
                idx = self.RIGHTS_LIST.index(name)
                self.mask |= (1 << idx)
        return self

    def to_int(self) -> int:
        return self.mask

    def to_dict(self) -> dict:
        return {
            name: self.has_index(idx)
            for idx, name in enumerate(self.RIGHTS_LIST)
        }

    def to_tl(self) -> ChatAdminRights:
        return ChatAdminRights(**self.to_dict())

    @classmethod
    def to_mask(cls, tl_rights: typing.Any) -> int:
        if tl_rights is None:
            return 0
        mask = 0
        for idx, name in enumerate(cls.RIGHTS_LIST):
            if getattr(tl_rights, name, False):
                mask |= (1 << idx)
        return mask


class KBannedRights:
    """Обёртка над ChatBannedRights с битовой маской.

    Важно: в TL `True` у banned_rights = ЗАПРЕЩЕНО. Здесь маска работает
    в "положительной" логике (бит выставлен = ограничение активно).
    """

    RIGHTS_LIST = [
        "view_messages",
        "send_messages",
        "send_media",
        "send_stickers",
        "send_gifs",
        "send_games",
        "send_inline",
        "embed_links",
        "send_polls",
        "change_info",
        "invite_users",
        "pin_messages",
        "until_date",
    ]

    MAX_MASK = (1 << 12) - 1  # без until_date

    def __init__(self, mask: int = 0) -> None:
        self.mask = int(mask)

    def has_index(self, idx: int) -> bool:
        return bool(self.mask & (1 << idx))

    def to_dict(self) -> dict:
        return {
            name: self.has_index(idx)
            for idx, name in enumerate(self.RIGHTS_LIST)
            if name != "until_date"
        }

    def to_tl(self, until_date=None) -> ChatBannedRights:
        d = self.to_dict()
        return ChatBannedRights(until_date=until_date, **d)

    @classmethod
    def to_mask(cls, tl_rights: typing.Any) -> int:
        if tl_rights is None:
            return 0
        mask = 0
        for idx, name in enumerate(cls.RIGHTS_LIST):
            if name == "until_date":
                continue
            if getattr(tl_rights, name, False):
                mask |= (1 << idx)
        return mask


# ────────────────────────────────────────────────────────────────────────────
#  Основной модуль
# ────────────────────────────────────────────────────────────────────────────

class KChatModule(KitsuneModule):
    name = "KChatModule"
    description = "Управление чатами/каналами: id, права, бан/мут/кик, инфо и т.д."
    author = "@codrago_m (adapted for Kitsune)"
    version = "2.0"
    icon = "💬"
    category = "tools"

    # ── строки ──────────────────────────────────────────────────────────────
    strings_ru = {
        "my_id": "<emoji document_id=5447410659077661506>🤝</emoji> <b>Ваш ID:</b> <code>{id}</code>",
        "user_id": "<emoji document_id=5879770735999717115>👤</emoji> <b>ID пользователя:</b> <code>{id}</code>",
        "chat_id": "<emoji document_id=5818865088970362886>💬</emoji> <b>ID чата:</b> <code>{id}</code>",
        "no_user": "<emoji document_id=5210952531676504517>❌</emoji> <b>Пользователь не указан</b>",
        "no_rights": "<emoji document_id=5210952531676504517>❌</emoji> <b>Недостаточно прав</b>",
        "not_an_admin": "<emoji document_id=5210952531676504517>❌</emoji> <b>{user} не админ</b>",
        "admin_rights": "<emoji document_id=5778421585503203176>👑</emoji> <b>Права администратора {name}:</b>\n{rights}\n\n<b>Выдал:</b> <a href='tg://user?id={promoter_id}'>{promoter_name}</a>",
        "error": "<emoji document_id=5210952531676504517>❌</emoji> <b>Произошла ошибка</b>",
        "pinned": "<emoji document_id=5436040291507247633>📌</emoji> <b>Сообщение закреплено</b>",
        "pin_failed": "<emoji document_id=5210952531676504517>❌</emoji> <b>Не удалось закрепить</b>",
        "unpinned": "<emoji document_id=5436040291507247633>📌</emoji> <b>Сообщение откреплено</b>",
        "unpin_failed": "<emoji document_id=5210952531676504517>❌</emoji> <b>Не удалось открепить</b>",
        "failed_to_delete": "<emoji document_id=5210952531676504517>❌</emoji> <b>Не удалось удалить</b>",
        "successful_delete": "<emoji document_id=5436040291507247633>🗑</emoji> <b>Удалено</b>",
        "no_deleted_accounts": "<emoji document_id=5447410659077661506>✅</emoji> <b>Удалённых аккаунтов нет</b>",
        "kicked_deleted_accounts": "<emoji document_id=5447410659077661506>✅</emoji> <b>Удалённые аккаунты исключены</b>",
        "admin_list": "<emoji document_id=5778421585503203176>👑</emoji> <b>Создатель:</b> <a href='tg://user?id={id}'>{name}</a> [<code>{id}</code>]\n\n<b>Админов:</b> {admins_count}\n{admins}",
        "no_admins_in_chat": "<i>В чате нет администраторов</i>",
        "no_bots_in_chat": "<emoji document_id=5210952531676504517>❌</emoji> <b>В чате нет ботов</b>",
        "bot_list": "<emoji document_id=5773928687623385890>🤖</emoji> <b>Ботов:</b> {count}\n{bots}",
        "no_user_in_chat": "<emoji document_id=5210952531676504517>❌</emoji> <b>В чате нет пользователей</b>",
        "user_list": "<emoji document_id=5879770735999717115>👤</emoji> <b>Пользователей:</b> {count}\n{users}",
        "user_is_banned": "<emoji document_id=5210952531676504517>🔨</emoji> <b><a href='tg://user?id={id}'>{name}</a> забанен{time_info}</b>",
        "user_is_unbanned": "<emoji document_id=5447410659077661506>✅</emoji> <b><a href='tg://user?id={id}'>{name}</a> разбанен</b>",
        "user_is_kicked": "<emoji document_id=5210952531676504517>👋</emoji> <b><a href='tg://user?id={id}'>{name}</a> исключён</b>",
        "user_is_muted": "<emoji document_id=5210952531676504517>🔇</emoji> <b><a href='tg://user?id={id}'>{name}</a> замучен{time_info}</b>",
        "user_is_unmuted": "<emoji document_id=5447410659077661506>🔊</emoji> <b><a href='tg://user?id={id}'>{name}</a> размучен</b>",
        "reason": "<b>Причина:</b> {reason}",
        "forever": " навсегда",
        "channel_created": "<emoji document_id=5447410659077661506>✅</emoji> <b>Канал <a href='{link}'>{title}</a> создан</b>",
        "group_created": "<emoji document_id=5447410659077661506>✅</emoji> <b>Группа <a href='{link}'>{title}</a> создана</b>",
        "invalid_args": "<emoji document_id=5210952531676504517>❌</emoji> <b>Неверные аргументы</b>",
        "dnd": "<emoji document_id=5210952531676504517>🔕</emoji> <b>Чат заглушён и архивирован</b>",
        "dnd_failed": "<emoji document_id=5210952531676504517>❌</emoji> <b>Не удалось</b>",
        "user_invited": "<emoji document_id=5447410659077661506>✅</emoji> <b><a href='tg://user?id={id}'>{user}</a> приглашён</b>",
        "user_not_invited": "<emoji document_id=5210952531676504517>❌</emoji> <b>Не удалось пригласить</b>",
        "requests_checked": "<emoji document_id=5447410659077661506>✅</emoji> <b>Заявки обработаны:</b> {entities}",
        "owns": "<emoji document_id=5778421585503203176>👑</emoji> <b>Ваши чаты/каналы:</b> {num}\n{owns}",
        "promote": "<emoji document_id=5778421585503203176>👑</emoji> <b>Выдача прав <a href='tg://user?id={id}'>{name}</a></b>\n<b>Ранг:</b> <code>{rank}</code>\n\n<i>Выберите права и нажмите «Применить»</i>",
        "promoted": "<emoji document_id=5447410659077661506>✅</emoji> <b><a href='tg://user?id={id}'>{name}</a> получил права:</b> {rights}",
        "demoted": "<emoji document_id=5210952531676504517>❌</emoji> <b><a href='tg://user?id={id}'>{name}</a> разжалован</b>",
        "restrict": "<emoji document_id=5210952531676504517>🔒</emoji> <b>Ограничение <a href='tg://user?id={id}'>{name}</a></b>{time}\n\n<i>Выберите права и нажмите «Применить»</i>",
        "restricted": "<emoji document_id=5210952531676504517>🔒</emoji> <b><a href='tg://user?id={id}'>{name}</a> ограничен:</b> {rights}{duration}",
        "full_rights": "все права",
        "apply": "✅ Применить",
        "close": "❌ Закрыть",
        "no": "нет",
        "yes": "да",
        "no_inline": "<emoji document_id=5210952531676504517>❌</emoji> <b>Inline-бот недоступен</b>",
        "chatinfo": (
            "<b>📚 {title}</b> [<code>{id}</code>]\n"
            "<b>Тип:</b> {type_of}\n<b>Описание:</b> {about}\n"
            "<b>Админов:</b> {admins_count} | <b>Онлайн:</b> {online_count}\n"
            "<b>Участников:</b> {participants_count} | <b>Кикнуто:</b> {kicked_count}\n"
            "<b>Медленный режим:</b> {slowmode_seconds}\n<b>Звонок:</b> {call}\n"
            "<b>TTL:</b> {ttl_period}\n<b>Заявок:</b> {requests_pending}\n"
            "<b>Запросившие:</b> {recent_requesters}\n<b>Связанный чат:</b> {linked_chat_id}\n"
            "<b>Антиспам:</b> {antispam}\n<b>Участники скрыты:</b> {participants_hidden}\n"
            "<b>Ссылка:</b> {link}\n<b>Форум:</b> {is_forum}"
        ),
        "userinfo": (
            "<b>👤 {first_name} {last_name}</b> [<code>{user_id}</code>]\n"
            "<b>О себе:</b> {about}\n<b>Телефон:</b> {phone}\n"
            "<b>Юзернеймы:</b> {usernames}\n<b>Эмодзи-статус:</b> {emoji_status}\n"
            "<b>День рождения:</b> {birthday}\n<b>Подарков:</b> {stargifts_count}\n"
            "<b>Общих чатов:</b> {common_chats_count}\n{common_chats}\n"
            "<b>Часы работы:</b> {business_work_hours}\n<b>Личный канал:</b> {personal_channel}"
        ),
        "type_group": "Группа", "type_channel": "Канал", "type_unknown": "Неизвестно",
        "monday": "Пн", "tuesday": "Вт", "wednesday": "Ср", "thursday": "Чт",
        "friday": "Пт", "saturday": "Сб", "sunday": "Вс",
        # права (имена для кнопок/вывода)
        "change_info": "Изменение инфо", "post_messages": "Публикация",
        "edit_messages": "Редактирование", "delete_messages": "Удаление",
        "ban_users": "Бан", "invite_users": "Приглашения",
        "pin_messages": "Закрепление", "add_admins": "Добавление админов",
        "anonymous": "Анонимность", "manage_call": "Управление звонком",
        "other": "Прочее", "manage_topics": "Управление темами",
        "view_messages": "Просмотр", "send_messages": "Сообщения",
        "send_media": "Медиа", "send_stickers": "Стикеры",
        "send_gifs": "GIF", "send_games": "Игры", "send_inline": "Inline",
        "embed_links": "Ссылки", "send_polls": "Опросы",
    }

    strings_en = {
        "my_id": "<b>Your ID:</b> <code>{id}</code>",
        "user_id": "<b>User ID:</b> <code>{id}</code>",
        "chat_id": "<b>Chat ID:</b> <code>{id}</code>",
        "no_user": "<b>No user specified</b>",
        "no_rights": "<b>Not enough rights</b>",
        "not_an_admin": "<b>{user} is not an admin</b>",
        "admin_rights": "<b>{name} admin rights:</b>\n{rights}\n\n<b>Promoted by:</b> <a href='tg://user?id={promoter_id}'>{promoter_name}</a>",
        "error": "<b>An error occurred</b>",
        "pinned": "<b>Message pinned</b>",
        "pin_failed": "<b>Failed to pin</b>",
        "unpinned": "<b>Message unpinned</b>",
        "unpin_failed": "<b>Failed to unpin</b>",
        "failed_to_delete": "<b>Failed to delete</b>",
        "successful_delete": "<b>Deleted</b>",
        "no_deleted_accounts": "<b>No deleted accounts</b>",
        "kicked_deleted_accounts": "<b>Deleted accounts removed</b>",
        "admin_list": "<b>Creator:</b> <a href='tg://user?id={id}'>{name}</a> [<code>{id}</code>]\n\n<b>Admins:</b> {admins_count}\n{admins}",
        "no_admins_in_chat": "<i>No admins in chat</i>",
        "no_bots_in_chat": "<b>No bots in chat</b>",
        "bot_list": "<b>Bots:</b> {count}\n{bots}",
        "no_user_in_chat": "<b>No users in chat</b>",
        "user_list": "<b>Users:</b> {count}\n{users}",
        "user_is_banned": "<b><a href='tg://user?id={id}'>{name}</a> banned{time_info}</b>",
        "user_is_unbanned": "<b><a href='tg://user?id={id}'>{name}</a> unbanned</b>",
        "user_is_kicked": "<b><a href='tg://user?id={id}'>{name}</a> kicked</b>",
        "user_is_muted": "<b><a href='tg://user?id={id}'>{name}</a> muted{time_info}</b>",
        "user_is_unmuted": "<b><a href='tg://user?id={id}'>{name}</a> unmuted</b>",
        "reason": "<b>Reason:</b> {reason}",
        "forever": " forever",
        "channel_created": "<b>Channel <a href='{link}'>{title}</a> created</b>",
        "group_created": "<b>Group <a href='{link}'>{title}</a> created</b>",
        "invalid_args": "<b>Invalid arguments</b>",
        "dnd": "<b>Chat muted and archived</b>",
        "dnd_failed": "<b>Failed</b>",
        "user_invited": "<b><a href='tg://user?id={id}'>{user}</a> invited</b>",
        "user_not_invited": "<b>Failed to invite</b>",
        "requests_checked": "<b>Requests processed:</b> {entities}",
        "owns": "<b>Your chats/channels:</b> {num}\n{owns}",
        "promote": "<b>Promote <a href='tg://user?id={id}'>{name}</a></b>\n<b>Rank:</b> <code>{rank}</code>\n\n<i>Select rights and press Apply</i>",
        "promoted": "<b><a href='tg://user?id={id}'>{name}</a> got rights:</b> {rights}",
        "demoted": "<b><a href='tg://user?id={id}'>{name}</a> demoted</b>",
        "restrict": "<b>Restrict <a href='tg://user?id={id}'>{name}</a></b>{time}\n\n<i>Select rights and press Apply</i>",
        "restricted": "<b><a href='tg://user?id={id}'>{name}</a> restricted:</b> {rights}{duration}",
        "full_rights": "all rights",
        "apply": "✅ Apply",
        "close": "❌ Close",
        "no": "no",
        "yes": "yes",
        "no_inline": "<b>Inline bot is unavailable</b>",
        "chatinfo": (
            "<b>📚 {title}</b> [<code>{id}</code>]\n"
            "<b>Type:</b> {type_of}\n<b>About:</b> {about}\n"
            "<b>Admins:</b> {admins_count} | <b>Online:</b> {online_count}\n"
            "<b>Members:</b> {participants_count} | <b>Kicked:</b> {kicked_count}\n"
            "<b>Slowmode:</b> {slowmode_seconds}\n<b>Call:</b> {call}\n"
            "<b>TTL:</b> {ttl_period}\n<b>Requests:</b> {requests_pending}\n"
            "<b>Requesters:</b> {recent_requesters}\n<b>Linked chat:</b> {linked_chat_id}\n"
            "<b>Antispam:</b> {antispam}\n<b>Members hidden:</b> {participants_hidden}\n"
            "<b>Link:</b> {link}\n<b>Forum:</b> {is_forum}"
        ),
        "userinfo": (
            "<b>👤 {first_name} {last_name}</b> [<code>{user_id}</code>]\n"
            "<b>About:</b> {about}\n<b>Phone:</b> {phone}\n"
            "<b>Usernames:</b> {usernames}\n<b>Emoji status:</b> {emoji_status}\n"
            "<b>Birthday:</b> {birthday}\n<b>Gifts:</b> {stargifts_count}\n"
            "<b>Common chats:</b> {common_chats_count}\n{common_chats}\n"
            "<b>Work hours:</b> {business_work_hours}\n<b>Personal channel:</b> {personal_channel}"
        ),
        "type_group": "Group", "type_channel": "Channel", "type_unknown": "Unknown",
        "monday": "Mon", "tuesday": "Tue", "wednesday": "Wed", "thursday": "Thu",
        "friday": "Fri", "saturday": "Sat", "sunday": "Sun",
        "change_info": "Change info", "post_messages": "Post",
        "edit_messages": "Edit", "delete_messages": "Delete",
        "ban_users": "Ban", "invite_users": "Invite",
        "pin_messages": "Pin", "add_admins": "Add admins",
        "anonymous": "Anonymous", "manage_call": "Manage call",
        "other": "Other", "manage_topics": "Manage topics",
        "view_messages": "View", "send_messages": "Messages",
        "send_media": "Media", "send_stickers": "Stickers",
        "send_gifs": "GIF", "send_games": "Games", "send_inline": "Inline",
        "embed_links": "Links", "send_polls": "Polls",
    }

    # ── жизненный цикл ────────────────────────────────────────────────────────
    async def on_load(self) -> None:
        self._parse = KParse()
        self._format = KFormat()

    @property
    def _client(self):
        return self.client

    def _inline(self):
        return getattr(self.client, "_kitsune_inline", None)

    # ── вспомогательные методы (замена xdlib.chat / xdlib.user) ───────────────
    async def _get_rights(self, chat: typing.Any, user: typing.Any):
        """Возвращает объект с .participant (как xdlib.chat.get_rights)."""
        return await self.client(
            functions.channels.GetParticipantRequest(chat, user)
        )

    async def _get_entity(self, value: typing.Any):
        return await self.client.get_entity(value)

    @staticmethod
    def _name_of(ent: typing.Any) -> str:
        return (
            getattr(ent, "first_name", None)
            or getattr(ent, "title", None)
            or "None"
        )

    async def _get_chat_link(self, chat: typing.Any) -> typing.Optional[str]:
        with contextlib.suppress(Exception):
            username = getattr(chat, "username", None)
            if username:
                return f"https://t.me/{username}"
        return None

    # ────────────────────────────────────────────────────────────────────────
    #  КОМАНДЫ
    # ────────────────────────────────────────────────────────────────────────

    @command("id", required=OWNER)
    async def id_cmd(self, message):
        """[reply] - Узнать ID / Get the ID"""
        ids = [self.strings("my_id", id=self.tg_id)]
        if message.is_private:
            ids.append(self.strings("user_id", id=message.to_id.user_id))
            return await answer(message, "\n".join(ids))
        ids.append(self.strings("chat_id", id=message.chat_id))
        reply = await message.get_reply_message()
        if (
            reply
            and not getattr(reply, "is_private", False)
            and getattr(reply, "sender_id", None) != self.tg_id
        ):
            with contextlib.suppress(Exception):
                user_id = (await reply.get_sender()).id
                ids.append(self.strings("user_id", id=user_id))
        return await answer(message, "\n".join(ids))

    @command("rights", required=OWNER)
    async def rights_cmd(self, message):
        """[reply/-u username/id] - Права администратора пользователя"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        opts = self._parse.opts(get_args(message))
        reply = await message.get_reply_message()
        user = opts.get("u") or opts.get("user") or (
            reply.sender_id if reply else None
        )
        if not user:
            return await answer(message, self.strings("no_user"))
        try:
            rights = await self._get_rights(message.chat, user)
            participant = rights.participant
            user = await self._get_entity(user)
        except Exception as e:
            logger.error("rights: %s", e)
            return await answer(message, self.strings("error"))

        if not hasattr(participant, "admin_rights"):
            return await answer(
                message, self.strings("not_an_admin", user=self._name_of(user))
            )
        if participant.admin_rights:
            can_do = []
            ar = participant.to_dict().get("admin_rights") or {}
            for right, is_permitted in ar.items():
                if right == "_":
                    continue
                if is_permitted:
                    can_do.append(right)
            promoter = None
            if getattr(participant, "promoted_by", None):
                with contextlib.suppress(Exception):
                    promoter = await self._get_entity(participant.promoted_by)
            return await answer(
                message,
                self.strings(
                    "admin_rights",
                    rights="\n".join(
                        f"<emoji document_id=5409029658794537988>✅</emoji> {self.strings(right)}"
                        for right in can_do
                    ),
                    promoter_id=promoter.id if promoter else 0,
                    promoter_name=(
                        promoter.first_name if promoter else self.strings("no")
                    ),
                    name=self._name_of(user),
                ),
            )
        return await answer(
            message, self.strings("not_an_admin", user=self._name_of(user))
        )

    @command("leave", required=OWNER)
    async def leave_cmd(self, message):
        """Покинуть чат / Leave chat"""
        with contextlib.suppress(Exception):
            await message.delete()
        try:
            chat = await message.get_chat()
            await self.client(channels.LeaveChannelRequest(chat.id))
        except Exception as e:
            logger.error("leave: %s", e)

    @command("d", required=OWNER)
    async def d_cmd(self, message):
        """[a[1-100] b[1-100]] | [reply] - Удалить сообщения"""
        reply = await message.get_reply_message()
        args = get_args(message)
        try:
            if reply:
                with contextlib.suppress(Exception):
                    await reply.delete()
                with contextlib.suppress(Exception):
                    await message.delete()
                return
            # a b — кол-во сообщений до/после
            a = int(args[0]) if len(args) >= 1 and args[0].isdigit() else 0
            b = int(args[1]) if len(args) >= 2 and args[1].isdigit() else 0
            a = max(0, min(a, 100))
            b = max(0, min(b, 100))
            ids = []
            if a:
                async for msg in self.client.iter_messages(
                    message.chat_id, limit=a, max_id=message.id
                ):
                    ids.append(msg.id)
            if b:
                async for msg in self.client.iter_messages(
                    message.chat_id, limit=b, min_id=message.id
                ):
                    ids.append(msg.id)
            ids.append(message.id)
            if ids:
                await self.client.delete_messages(message.chat_id, ids)
        except Exception as e:
            logger.error("d: %s", e)
            with contextlib.suppress(Exception):
                await message.delete()

    @command("pin", required=OWNER)
    async def pin_cmd(self, message):
        """[reply] - Закрепить сообщение / Pin a message"""
        reply = await message.get_reply_message()
        if not reply:
            return await answer(message, self.strings("no_user"))
        try:
            await reply.pin(notify=True, pm_oneside=False)
        except Exception as e:
            logger.error("pin: %s", e)
            return await answer(message, self.strings("pin_failed"))
        await answer(message, self.strings("pinned"))

    @command("unpin", required=OWNER)
    async def unpin_cmd(self, message):
        """[reply] - Открепить сообщение / Unpin a message"""
        reply = await message.get_reply_message()
        if not reply:
            return await answer(message, self.strings("no_user"))
        try:
            await reply.unpin()
        except Exception as e:
            logger.error("unpin: %s", e)
            return await answer(message, self.strings("unpin_failed"))
        await answer(message, self.strings("unpinned"))

    @command("dgc", required=OWNER)
    async def dgc_cmd(self, message):
        """[-c id] - Удаляет группу/канал / Delete chat/channel"""
        opts = self._parse.opts(get_args(message))
        chat_id = opts.get("c") or opts.get("chat")
        try:
            if chat_id:
                chat = await self._get_entity(chat_id)
                if isinstance(chat, types.Channel):
                    await self.client(channels.DeleteChannelRequest(chat.id))
                elif isinstance(chat, types.Chat):
                    await self.client(messages.DeleteChatRequest(chat.id))
                else:
                    return await answer(message, self.strings("failed_to_delete"))
                return await answer(message, self.strings("successful_delete"))
            if isinstance(message.chat, types.Channel):
                await self.client(channels.DeleteChannelRequest(message.chat))
            elif isinstance(message.chat, types.Chat):
                await self.client(messages.DeleteChatRequest(message.chat))
            else:
                return await answer(message, self.strings("failed_to_delete"))
        except Exception as e:
            logger.error("dgc: %s", e)
            return await answer(message, self.strings("failed_to_delete"))

    @command("flush", required=OWNER)
    async def flush_cmd(self, message):
        """Очищает группу/канал от удаленных аккаунтов"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        chat = await message.get_chat()
        if not getattr(chat, "admin_rights", False):
            return await answer(message, self.strings("no_rights"))

        deleted = []
        try:
            async for user in self.client.iter_participants(chat):
                if getattr(user, "deleted", False):
                    deleted.append(user)
        except Exception as e:
            logger.error("flush iter: %s", e)
            return await answer(message, self.strings("error"))

        if not deleted:
            return await answer(message, self.strings("no_deleted_accounts"))

        async def _kick(u):
            with contextlib.suppress(Exception):
                await self.client.kick_participant(chat, u)

        await asyncio.gather(*[_kick(u) for u in deleted])
        return await answer(message, self.strings("kicked_deleted_accounts"))

    @command("admins", required=OWNER)
    async def admins_cmd(self, message):
        """Показывает админов в группе/канале"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        try:
            from telethon.tl.types import ChannelParticipantsAdmins

            admins = await self.client.get_participants(
                message.chat, filter=ChannelParticipantsAdmins
            )
        except Exception as e:
            logger.error("admins: %s", e)
            return await answer(message, self.strings("error"))

        creator = None
        for admin in admins:
            part = getattr(admin, "participant", None)
            if part and type(part).__name__ == "ChannelParticipantCreator":
                creator = admin
                break

        def _rank(admin):
            part = getattr(admin, "participant", None)
            return getattr(part, "rank", None) or "admin"

        return await answer(
            message,
            self.strings(
                "admin_list",
                id=creator.id if creator else 0,
                name=creator.first_name if creator else self.strings("no"),
                admins_count=len(admins) or 0,
                admins=(
                    "\n".join(
                        f"<emoji document_id=5774022692642492953>✅</emoji> "
                        f"<a href='tg://user?id={a.id}'>{escape_html(self._name_of(a))}</a> "
                        f"[<code>{a.id}</code>] / <code>{escape_html(_rank(a))}</code>"
                        for a in admins
                    )
                    if admins
                    else f"\n{self.strings('no_admins_in_chat')}"
                ),
            ),
        )

    @command("bots", required=OWNER)
    async def bots_cmd(self, message):
        """Показывает ботов в группе/канале"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        try:
            from telethon.tl.types import ChannelParticipantsBots

            bots = await self.client.get_participants(
                message.chat, filter=ChannelParticipantsBots
            )
        except Exception:
            bots = [
                u async for u in self.client.iter_participants(message.chat)
                if getattr(u, "bot", False)
            ]
        if not bots:
            return await answer(message, self.strings("no_bots_in_chat"))
        await answer(
            message,
            self.strings(
                "bot_list",
                count=len(bots),
                bots="\n".join(
                    f"<emoji document_id=5774022692642492953>✅</emoji> "
                    f"<a href='tg://user?id={b.id}'>{escape_html(self._name_of(b))}</a> "
                    f"[<code>{b.id}</code>]"
                    for b in bots
                ),
            ),
        )

    @command("users", required=OWNER)
    async def users_cmd(self, message):
        """Показывает простых участников чата/канала"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        try:
            users = [
                u async for u in self.client.iter_participants(message.chat)
                if not getattr(u, "bot", False)
                and not getattr(u, "deleted", False)
            ]
        except Exception as e:
            logger.error("users: %s", e)
            return await answer(message, self.strings("error"))
        if not users:
            return await answer(message, self.strings("no_user_in_chat"))
        text = self.strings(
            "user_list",
            count=len(users),
            users="\n".join(
                f"<emoji document_id=5774022692642492953>✅</emoji> "
                f"<a href='tg://user?id={u.id}'>{escape_html(self._name_of(u))}</a> "
                f"[<code>{u.id}</code>]"
                for u in users[:100]
            ),
        )
        await answer(message, text)

    @command("ban", required=OWNER)
    async def ban_cmd(self, message):
        """[-u] [-t] [-r] - Забанить участника навсегда или временно"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        opts = self._parse.opts(get_args(message))
        reason = opts.get("r")
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        if not user:
            return await answer(message, self.strings("no_user"))
        try:
            user = await self._get_entity(user)
        except Exception as e:
            logger.error("ban entity: %s", e)
            return await answer(message, self.strings("error"))

        seconds = self._parse.time(opts.get("t")) if opts.get("t") else None
        until_date = (
            (datetime.now(timezone.utc) + timedelta(seconds=seconds))
            if seconds else None
        )
        time_info = f" {self._format.time(seconds)}" if seconds else None
        try:
            await self.client.edit_permissions(
                message.chat, user, until_date=until_date, view_messages=False
            )
        except Exception as e:
            logger.error("ban: %s", e)
            return await answer(message, self.strings("error"))
        strings = [
            self.strings(
                "user_is_banned",
                id=user.id,
                name=self._name_of(user),
                time_info=time_info or self.strings("forever"),
            )
        ]
        if reason and reason is not True:
            strings.append(self.strings("reason", reason=escape_html(reason)))
        return await answer(message, "\n".join(strings))

    @command("unban", required=OWNER)
    async def unban_cmd(self, message):
        """[-u] - Разбанить пользователя"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        opts = self._parse.opts(get_args(message))
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        if not user:
            return await answer(message, self.strings("no_user"))
        try:
            user = await self._get_entity(user)
            await self.client.edit_permissions(
                message.chat, user, view_messages=True
            )
        except Exception as e:
            logger.error("unban: %s", e)
            return await answer(message, self.strings("error"))
        return await answer(
            message,
            self.strings("user_is_unbanned", id=user.id, name=self._name_of(user)),
        )

    @command("kick", required=OWNER)
    async def kick_cmd(self, message):
        """[-u] [-r] - Кикнуть участника"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        opts = self._parse.opts(get_args(message))
        reason = opts.get("r")
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        if not user:
            return await answer(message, self.strings("no_user"))
        try:
            user = await self._get_entity(user)
            await self.client.kick_participant(message.chat, user)
        except Exception as e:
            logger.error("kick: %s", e)
            return await answer(message, self.strings("error"))
        strings = [
            self.strings("user_is_kicked", id=user.id, name=self._name_of(user))
        ]
        if reason and reason is not True:
            strings.append(self.strings("reason", reason=escape_html(reason)))
        return await answer(message, "\n".join(strings))

    @command("mute", required=OWNER)
    async def mute_cmd(self, message):
        """[-u] [-t] [-r] - Замутить участника навсегда или временно"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        opts = self._parse.opts(get_args(message))
        reason = opts.get("r")
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        if not user:
            return await answer(message, self.strings("no_user"))
        try:
            user = await self._get_entity(user)
        except Exception as e:
            logger.error("mute entity: %s", e)
            return await answer(message, self.strings("error"))

        seconds = self._parse.time(opts.get("t")) if opts.get("t") else None
        until_date = (
            (datetime.now(timezone.utc) + timedelta(seconds=seconds))
            if seconds else None
        )
        time_info = f" {self._format.time(seconds)}" if seconds else None
        try:
            await self.client.edit_permissions(
                message.chat, user, until_date=until_date, send_messages=False
            )
        except Exception as e:
            logger.error("mute: %s", e)
            return await answer(message, self.strings("error"))
        strings = [
            self.strings(
                "user_is_muted",
                id=user.id,
                name=self._name_of(user),
                time_info=time_info or self.strings("forever"),
            )
        ]
        if reason and reason is not True:
            strings.append(self.strings("reason", reason=escape_html(reason)))
        return await answer(message, "\n".join(strings))

    @command("unmute", required=OWNER)
    async def unmute_cmd(self, message):
        """[-u] - Размутить участника"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        opts = self._parse.opts(get_args(message))
        reply = await message.get_reply_message()
        user = opts.get("u") or (reply.sender_id if reply else None)
        if not user:
            return await answer(message, self.strings("no_user"))
        try:
            user = await self._get_entity(user)
            await self.client.edit_permissions(
                message.chat, user, send_messages=True
            )
        except Exception as e:
            logger.error("unmute: %s", e)
            return await answer(message, self.strings("error"))
        return await answer(
            message,
            self.strings("user_is_unmuted", id=user.id, name=self._name_of(user)),
        )

    @command("create", required=OWNER)
    async def create_cmd(self, message):
        """[-g|--group name] [-c|--channel name] - Создать группу/канал"""
        opts = self._parse.opts(get_args(message))
        group_name = opts.get("g") or opts.get("group")
        channel_name = opts.get("c") or opts.get("channel")
        try:
            if channel_name and channel_name is not True:
                result = await self.client(
                    channels.CreateChannelRequest(
                        title=channel_name, broadcast=True, about=""
                    )
                )
                chat = result.chats[0]
                return await answer(
                    message,
                    self.strings(
                        "channel_created",
                        link=await self._get_chat_link(chat) or "",
                        title=escape_html(channel_name),
                    ),
                )
            if group_name and group_name is not True:
                result = await self.client(
                    channels.CreateChannelRequest(
                        title=group_name, megagroup=True, about=""
                    )
                )
                chat = result.chats[0]
                return await answer(
                    message,
                    self.strings(
                        "group_created",
                        link=await self._get_chat_link(chat) or "",
                        title=escape_html(group_name),
                    ),
                )
        except Exception as e:
            logger.error("create: %s", e)
            return await answer(message, self.strings("error"))
        return await answer(message, self.strings("invalid_args"))

    @command("dnd", required=OWNER)
    async def dnd_cmd(self, message):
        """Отключает звук и архивирует чат"""
        try:
            chat = await message.get_chat()
            from telethon.tl.functions.account import UpdateNotifySettingsRequest
            from telethon.tl.functions.folders import EditPeerFoldersRequest
            from telethon.tl.types import (
                InputPeerNotifySettings,
                InputFolderPeer,
            )

            peer = await self.client.get_input_entity(chat)
            await self.client(
                UpdateNotifySettingsRequest(
                    peer=peer,
                    settings=InputPeerNotifySettings(mute_until=2 ** 31 - 1),
                )
            )
            await self.client(
                EditPeerFoldersRequest(
                    folder_peers=[InputFolderPeer(peer=peer, folder_id=1)]
                )
            )
            return await answer(message, self.strings("dnd"))
        except Exception as e:
            logger.error("dnd: %s", e)
            return await answer(message, self.strings("dnd_failed"))

    @command("invite", required=OWNER)
    async def invite_cmd(self, message):
        """-u username/id - Пригласить пользователя (-b пригласить инлайн бота)"""
        opts = self._parse.opts(get_args(message))
        if opts.get("b") or opts.get("bot"):
            inline = self._inline()
            if not inline or not getattr(inline, "_bot", None):
                return await answer(message, self.strings("no_inline"))
            try:
                bot_id = getattr(inline, "_bot_id", None)
                if not bot_id:
                    me = await inline._bot.get_me()
                    bot_id = me.id
                entity = await self._get_entity(bot_id)
                await self.client(
                    channels.InviteToChannelRequest(message.chat, [entity])
                )
                return await answer(
                    message,
                    self.strings(
                        "user_invited",
                        user=self._name_of(entity),
                        id=entity.id,
                    ),
                )
            except Exception as e:
                logger.error("invite bot: %s", e)
                return await answer(message, self.strings("user_not_invited"))

        reply = await message.get_reply_message()
        user = opts.get("u") or opts.get("user") or (
            reply.sender_id if reply else None
        )
        if not user:
            return await answer(message, self.strings("no_user"))
        try:
            entity = await self._get_entity(user)
            await self.client(
                channels.InviteToChannelRequest(message.chat, [entity])
            )
            return await answer(
                message,
                self.strings(
                    "user_invited", user=self._name_of(entity), id=entity.id
                ),
            )
        except Exception as e:
            logger.error("invite: %s", e)
            return await answer(message, self.strings("user_not_invited"))

    @command("inspect", required=OWNER)
    async def inspect_cmd(self, message):
        """[-i] - Получить информацию о сущности"""
        opts = self._parse.opts(get_args(message))
        reply = await message.get_reply_message()
        target = (
            opts.get("i")
            or (reply.sender_id if reply else None)
            or message.chat_id
        )
        if target is True:
            target = message.chat_id
        if not target:
            return await answer(message, self.strings("no_user"))
        try:
            ent = await self._get_entity(target)
        except Exception as e:
            logger.error("inspect entity: %s", e)
            return await answer(message, self.strings("error"))

        if isinstance(ent, types.Channel):
            return await self._inspect_channel(message, ent)
        if isinstance(ent, types.User):
            return await self._inspect_user(message, ent)
        return await answer(message, self.strings("error"))

    async def _inspect_channel(self, message, ent):
        try:
            full = await self.client(
                functions.channels.GetFullChannelRequest(ent)
            )
            fc = full.full_chat
            photo = getattr(fc, "chat_photo", None)
            photo = photo if not isinstance(photo, types.PhotoEmpty) else None

            slowmode = getattr(fc, "slowmode_seconds", 0)
            ttl = getattr(fc, "ttl_period", 0)
            recent = getattr(fc, "recent_requesters", None) or []

            text = self.strings(
                "chatinfo",
                id=ent.id,
                title=escape_html(getattr(ent, "title", "")),
                about=escape_html(getattr(fc, "about", "") or "") or self.strings("no"),
                admins_count=getattr(fc, "admins_count", 0) or 0,
                online_count=getattr(fc, "online_count", 0) or 0,
                participants_count=getattr(fc, "participants_count", 0) or 0,
                kicked_count=getattr(fc, "kicked_count", 0) or 0,
                slowmode_seconds=(
                    self._format.time(slowmode) if slowmode else self.strings("no")
                ),
                call=self.strings("yes") if (hasattr(fc, "call") and fc.call) else self.strings("no"),
                ttl_period=self._format.time(ttl) if ttl else self.strings("no"),
                requests_pending=getattr(fc, "requests_pending", 0) or 0,
                recent_requesters=(
                    ", ".join(f"<code>{u}</code>" for u in recent)
                    or self.strings("no")
                ),
                linked_chat_id=getattr(fc, "linked_chat_id", None) or self.strings("no"),
                antispam=self.strings("yes") if getattr(fc, "antispam", False) else self.strings("no"),
                participants_hidden=(
                    self.strings("yes")
                    if getattr(fc, "participants_hidden", False)
                    else self.strings("no")
                ),
                link=await self._get_chat_link(ent) or self.strings("no"),
                is_forum=self.strings("yes") if getattr(ent, "forum", False) else self.strings("no"),
                type_of=(
                    self.strings("type_group")
                    if getattr(ent, "megagroup", False)
                    else self.strings("type_channel")
                ),
            )
            file = (
                types.InputMediaPhoto(
                    types.InputPhoto(photo.id, photo.access_hash, photo.file_reference)
                )
                if photo and hasattr(photo, "id")
                else None
            )
            if file:
                return await answer(message, text, file=file)
            return await answer(message, text)
        except Exception as e:
            logger.error("inspect_channel: %s", e)
            return await answer(message, self.strings("error"))

    async def _inspect_user(self, message, ent):
        try:
            full = await self.client(functions.users.GetFullUserRequest(ent))
            fu = full.full_user
            photo = getattr(fu, "profile_photo", None)
            photo = photo if not isinstance(photo, types.PhotoEmpty) else None

            usernames = []
            if getattr(ent, "usernames", None):
                usernames = [u.username for u in ent.usernames]
            elif getattr(ent, "username", None):
                usernames = [ent.username]

            birthday = getattr(fu, "birthday", None)
            birthday_str = self.strings("no")
            if birthday:
                birthday_str = (
                    f"{getattr(birthday, 'day', '') or ''}."
                    f"{getattr(birthday, 'month', '') or ''}."
                    f"{getattr(birthday, 'year', '') or ''}"
                )

            personal_channel_str = self.strings("no")
            pc_id = getattr(fu, "personal_channel_id", None)
            if pc_id:
                with contextlib.suppress(Exception):
                    pc = await self._get_entity(pc_id)
                    personal_channel_str = (
                        f"<a href='{await self._get_chat_link(pc) or ''}'>"
                        f"{escape_html(getattr(pc, 'title', ''))}</a>"
                    )

            text = self.strings(
                "userinfo",
                common_chats_count=getattr(fu, "common_chats_count", 0) or 0,
                phone=escape_html(getattr(ent, "phone", "") or "") or self.strings("no"),
                common_chats=self.strings("no"),
                user_id=ent.id,
                first_name=escape_html(getattr(ent, "first_name", "") or "") or self.strings("no"),
                last_name=escape_html(getattr(ent, "last_name", "") or "") or "",
                about=escape_html(getattr(fu, "about", "") or "") or self.strings("no"),
                emoji_status=(
                    f"<emoji document_id={ent.emoji_status.document_id}>🌙</emoji>"
                    if getattr(ent, "emoji_status", None)
                    and hasattr(ent.emoji_status, "document_id")
                    else self.strings("no")
                ),
                business_work_hours=self.strings("no"),
                birthday=birthday_str,
                stargifts_count=getattr(fu, "stargifts_count", None) or self.strings("no"),
                usernames=(
                    ", ".join(f"@{u}" for u in usernames)
                    if usernames else self.strings("no")
                ),
                personal_channel=personal_channel_str,
            )
            file = (
                types.InputMediaPhoto(
                    types.InputPhoto(photo.id, photo.access_hash, photo.file_reference)
                )
                if photo and hasattr(photo, "id")
                else None
            )
            if file:
                return await answer(message, text, file=file)
            return await answer(message, text)
        except Exception as e:
            logger.error("inspect_user: %s", e)
            return await answer(message, self.strings("error"))

    @command("requests", required=OWNER)
    async def requests_cmd(self, message):
        """[-a] [-d] - Управлять заявками на вступление (id,id,...)"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        opts = self._parse.opts(get_args(message))
        approve_list = [x for x in str(opts.get("a", "")).split(",") if x and x != "True"]
        dismiss_list = [x for x in str(opts.get("d", "")).split(",") if x and x != "True"]
        all_list = approve_list + dismiss_list
        all_targets = []
        for ent in all_list:
            with contextlib.suppress(Exception):
                t = await self._get_entity(
                    int(ent.strip()) if ent.strip().isdigit() else ent.strip()
                )
                all_targets.append(t)

        async def _process(value, approve):
            with contextlib.suppress(Exception):
                user = await self._get_entity(
                    int(value) if value.isdigit() else value
                )
                await self.client(
                    functions.messages.HideChatJoinRequestRequest(
                        peer=message.chat, user_id=user, approved=approve
                    )
                )

        tasks = [_process(v, True) for v in approve_list]
        tasks += [_process(v, False) for v in dismiss_list]
        if tasks:
            await asyncio.gather(*tasks)

        return await answer(
            message,
            self.strings(
                "requests_checked",
                entities=", ".join(
                    escape_html(
                        getattr(ent, "first_name", None)
                        or getattr(ent, "username", None)
                        or str(getattr(ent, "id", "unknown"))
                    )
                    for ent in all_targets
                ) or self.strings("no"),
            ),
        )

    @command("owns", required=OWNER)
    async def owns_cmd(self, message):
        """Получить все свои чаты/каналы"""
        owns = []
        try:
            async for dialog in self.client.iter_dialogs():
                ent = dialog.entity
                if (dialog.is_channel or dialog.is_group) and getattr(
                    ent, "creator", False
                ):
                    owns.append(ent)
        except Exception as e:
            logger.error("owns: %s", e)
            return await answer(message, self.strings("error"))

        return await answer(
            message,
            self.strings(
                "owns",
                num=len(owns),
                owns="\n".join(
                    f"<emoji document_id=5458833171846029357>✅</emoji> "
                    f"{escape_html(getattr(o, 'title', ''))} "
                    f"[<code>{str(o.id).replace('-100', '')}</code>]"
                    for o in owns
                ),
            ),
        )

    # ── promote / restrict с inline-кнопками ──────────────────────────────────

    @command("promote", required=OWNER)
    async def promote_cmd(self, message):
        """[-r rank] [-u] [-f] - Выдать админку участнику"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        reply = await message.get_reply_message()
        opts = self._parse.opts(get_args(message))
        user = opts.get("u") or (reply.sender_id if reply else None)
        if not user:
            return await answer(message, self.strings("no_user"))
        try:
            user = await self._get_entity(user)
            chat = await message.get_chat()
            rights = await self._get_rights(message.chat, user)
        except Exception as e:
            logger.error("promote prep: %s", e)
            return await answer(message, self.strings("error"))

        rank = opts.get("r") if (opts.get("r") and opts.get("r") is not True) else "K Admin"

        if (
            not getattr(chat, "admin_rights", None)
            or not getattr(chat.admin_rights, "add_admins", False)
            or (
                getattr(rights.participant, "promoted_by", self.tg_id) != self.tg_id
                and not getattr(chat, "creator", False)
            )
        ):
            return await answer(message, self.strings("no_rights"))

        full = opts.get("f")
        if full:
            try:
                my_rights = [
                    r for r, y in chat.admin_rights.to_dict().items()
                    if y and r != "_"
                ]
                perms = KAdminRights(0).add(*my_rights)
                await self._set_admin(chat, user, perms.to_int(), rank)
            except Exception as e:
                logger.error("promote full: %s", e)
                return await answer(message, self.strings("error"))
            return await answer(
                message,
                self.strings(
                    "promoted",
                    id=user.id,
                    name=self._name_of(user),
                    rights=self.strings("full_rights"),
                ),
            )

        mask = (
            KAdminRights.to_mask(rights.participant.admin_rights)
            if hasattr(rights.participant, "admin_rights")
            else 0
        )
        text = self.strings(
            "promote", id=user.id, name=self._name_of(user), rank=rank
        )
        kb = await self._build_markup(user.id, chat.id, mask, rank, mode="admin")
        await self._send_with_markup(message, text, kb)

    @command("restrict", required=OWNER)
    async def restrict_cmd(self, message):
        """[-t time] [-u] - Ограничить участника"""
        if message.is_private:
            return await answer(message, self.strings("no_rights"))
        reply = await message.get_reply_message()
        opts = self._parse.opts(get_args(message))
        user = opts.get("u") or (reply.sender_id if reply else None)
        if not user:
            return await answer(message, self.strings("no_user"))
        try:
            user = await self._get_entity(user)
            chat = await message.get_chat()
        except Exception as e:
            logger.error("restrict prep: %s", e)
            return await answer(message, self.strings("error"))

        if not getattr(chat, "admin_rights", None) or not getattr(
            chat.admin_rights, "ban_users", False
        ):
            return await answer(message, self.strings("no_rights"))

        duration = opts.get("t", None)
        if duration and duration is not True:
            duration = self._format.time(self._parse.time(duration))
        else:
            duration = None

        try:
            rights = await self._get_rights(chat, user)
            mask = (
                KBannedRights.MAX_MASK
                - KBannedRights.to_mask(rights.participant.banned_rights)
                if hasattr(rights.participant, "banned_rights")
                else 0
            )
        except Exception:
            mask = 0
        rank = "-"

        text = self.strings(
            "restrict",
            id=user.id,
            name=self._name_of(user),
            time=f" {duration}" if duration else self.strings("forever"),
        )
        kb = await self._build_markup(
            user.id, chat.id, mask, rank, mode="restrict",
            duration=f" {duration}" if duration else None,
        )
        await self._send_with_markup(message, text, kb)

    # ── работа с правами (замена xdlib.admin.set_rights / chat.set_restrictions)
    async def _set_admin(self, chat, user, mask: int, rank: str) -> bool:
        try:
            rights = KAdminRights(mask).to_tl()
            await self.client(
                functions.channels.EditAdminRequest(
                    channel=chat,
                    user_id=user,
                    admin_rights=rights,
                    rank=rank if rank and rank != "-" else "",
                )
            )
            return True
        except Exception as e:
            logger.error("_set_admin: %s", e)
            return False

    async def _set_restrictions(self, chat, user, mask: int, duration=None) -> bool:
        try:
            until = None
            if duration:
                seconds = self._parse.time(str(duration).strip())
                if seconds:
                    until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            rights = KBannedRights(mask).to_tl(until_date=until)
            await self.client(
                functions.channels.EditBannedRequest(
                    channel=chat,
                    participant=user,
                    banned_rights=rights,
                )
            )
            return True
        except Exception as e:
            logger.error("_set_restrictions: %s", e)
            return False

    # ── inline markup / callbacks ─────────────────────────────────────────────
    async def _send_with_markup(self, message, text: str, kb: list) -> None:
        inline = self._inline()
        if inline is None or not getattr(inline, "_bot", None):
            # fallback: обычный ответ без кнопок
            await answer(message, text + "\n\n" + self.strings("no_inline"))
            return
        try:
            await inline.form(text, message, kb)
        except Exception as e:
            logger.error("_send_with_markup: %s", e)
            await answer(message, text)

    async def _build_markup(
        self,
        user_id: int,
        chat_id: int,
        mask: int,
        rank: str,
        duration: typing.Optional[str] = None,
        mode: str = "admin",
    ) -> list:
        rights_cls = KAdminRights if mode == "admin" else KBannedRights
        rights_names = rights_cls.RIGHTS_LIST
        rights = rights_cls(mask)
        try:
            chat = await self._get_entity(chat_id)
        except Exception:
            chat = None

        buttons = []
        for idx, name in enumerate(rights_names):
            if name == "until_date":
                continue
            if mode != "admin" and chat is not None:
                default_banned = getattr(
                    getattr(chat, "default_banned_rights", None), name, True
                )
                if default_banned:
                    continue
            buttons.append({
                "text": f"{'🟢' if rights.has_index(idx) else '🔴'} {self.strings(name)}",
                "callback": self._toggle_right,
                "args": (user_id, chat_id, mask, idx, rank, mode, duration),
            })

        # chunks из utils работает со строками; для списка кнопок — вручную по 2:
        markup = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

        markup.append([{
            "text": self.strings("apply"),
            "callback": self._apply_rights,
            "args": (user_id, chat_id, mask, rank, mode, duration),
        }])
        markup.append([{"text": self.strings("close"), "action": "close"}])
        return markup

    async def _toggle_right(
        self, call, user_id, chat_id, mask, idx, rank, mode, duration
    ):
        inline = self._inline()
        if inline is None:
            with contextlib.suppress(Exception):
                await call.answer(self.strings("no_inline"), show_alert=True)
            return

        new_mask = mask ^ (1 << idx)
        new_markup = await self._build_markup(
            user_id, chat_id, new_mask, rank, mode=mode, duration=duration
        )
        try:
            user = await self._get_entity(user_id)
        except Exception:
            user = None

        if mode == "admin":
            text = self.strings(
                "promote",
                id=user_id,
                name=self._name_of(user) if user else "None",
                rank=rank,
            )
        else:
            text = self.strings(
                "restrict",
                id=user_id,
                name=self._name_of(user) if user else "None",
                time=f" {duration}" if duration else self.strings("forever"),
            )
        await inline.edit(call, text, new_markup)

    async def _apply_rights(
        self, call, user_id, chat_id, mask, rank, mode, duration=None
    ):
        inline = self._inline()
        try:
            user = await self._get_entity(user_id)
            chat = await self._get_entity(chat_id)
        except Exception as e:
            logger.error("_apply_rights entity: %s", e)
            if inline:
                await inline.edit(
                    call, self.strings("error"),
                    [[{"text": self.strings("close"), "action": "close"}]],
                )
            return

        if mode == "admin":
            ok = await self._set_admin(chat, user, mask, rank)
            rights_items = KAdminRights(mask).to_dict()
        else:
            ok = await self._set_restrictions(chat, user, mask, duration=duration)
            rights_items = KBannedRights(mask).to_dict()

        rights_list = [r for r, v in rights_items.items() if v]

        close_kb = [[{"text": self.strings("close"), "action": "close"}]]
        if ok:
            if mode == "admin" and mask:
                key = "promoted"
            elif mode == "admin" and not mask:
                key = "demoted"
            else:
                key = "restricted"
            text = self.strings(
                key,
                id=user_id,
                name=self._name_of(user),
                rights=", ".join(self.strings(r) for r in rights_list)
                if rights_list else self.strings("no"),
                duration=f" {duration}" if duration else self.strings("forever"),
                time=f" {duration}" if duration else self.strings("forever"),
            )
        else:
            text = self.strings("error")

        if inline:
            await inline.edit(call, text, close_kb)
