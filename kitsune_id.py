# ---------------------------------------------------------------------------------
# Name: Kitsune-ID
# Description: Инструмент для получения ID пользователей, чатов и каналов
# Original author: @codrago_m
# Адаптировано под Kitsune @Mikasu32
# ---------------------------------------------------------------------------------
# 🔒 Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------

from __future__ import annotations

import logging

try:
    from telethon.tl.types import User, Chat, Channel
except Exception:  # pragma: no cover - подстраховка, чтобы модуль не падал на импорте
    class User:  # type: ignore
        pass

    class Chat:  # type: ignore
        pass

    class Channel:  # type: ignore
        pass

from ..core.loader import KitsuneModule, command, ModuleConfig, ConfigValue
from ..core.security import OWNER

try:
    from ..validators import Boolean
except Exception:  # pragma: no cover - подстраховка на случай иной структуры
    Boolean = None

logger = logging.getLogger(__name__)


def _esc(value: object) -> str:
    """Безопасное экранирование HTML, чтобы юзербот не падал на спецсимволах."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class KitsuneIDModule(KitsuneModule):
    name        = "Kitsune-ID"
    description = "Инструмент для получения ID. Адаптировано под Kitsune @Mikasu32"
    author      = "@codrago_m | adapt @Mikasu32"
    version     = "2.0.0"
    icon        = "🆔"

    strings_ru = {
        "error_reply": "<emoji document_id=5328145443106873128>✖️</emoji> <b>Где твой реплай?</b>",
        "not_chat":    "<emoji document_id=5328145443106873128>✖️</emoji> <b>Это не чат!</b>",
        "not_found":   "<emoji document_id=5328145443106873128>✖️</emoji> <b>Не удалось получить сущность.</b>",
        "user_fmt": (
            "<emoji document_id=5301034196490268401>🪐</emoji> <b>Пользователь:</b> "
            "<code>{name}</code>\n"
            "<emoji document_id=5314260526803462610>😴</emoji> <b>User ID:</b> "
            "<code>{uid}</code>"
        ),
        "chat_fmt": (
            "<emoji document_id=5301034196490268401>🪐</emoji> <b>Чат:</b> "
            "<code>{name}</code>\n"
            "<emoji document_id=5314260526803462610>😴</emoji> <b>Chat ID:</b> "
            "<code>{cid}</code>"
        ),
        "me_fmt": (
            "<emoji document_id=5301034196490268401>🪐</emoji> <b>Твой ник:</b> "
            "<code>{name}</code>\n"
            "<emoji document_id=5314260526803462610>😴</emoji> <b>Твой ID:</b> "
            "<code>{uid}</code>"
        ),
        "chatid_fmt": (
            "<emoji document_id=5301034196490268401>🪐</emoji> <b>Чат:</b> "
            "<code>{name}</code>\n"
            "<emoji document_id=5314260526803462610>😴</emoji> <b>Chat ID:</b> "
            "<code>{cid}</code>"
        ),
    }

    strings_en = {
        "error_reply": "<emoji document_id=5328145443106873128>✖️</emoji> <b>Where is your reply?</b>",
        "not_chat":    "<emoji document_id=5328145443106873128>✖️</emoji> <b>This is not a chat!</b>",
        "not_found":   "<emoji document_id=5328145443106873128>✖️</emoji> <b>Failed to resolve entity.</b>",
        "user_fmt": (
            "<emoji document_id=5301034196490268401>🪐</emoji> <b>User:</b> "
            "<code>{name}</code>\n"
            "<emoji document_id=5314260526803462610>😴</emoji> <b>User ID:</b> "
            "<code>{uid}</code>"
        ),
        "chat_fmt": (
            "<emoji document_id=5301034196490268401>🪐</emoji> <b>Chat:</b> "
            "<code>{name}</code>\n"
            "<emoji document_id=5314260526803462610>😴</emoji> <b>Chat ID:</b> "
            "<code>{cid}</code>"
        ),
        "me_fmt": (
            "<emoji document_id=5301034196490268401>🪐</emoji> <b>Your Nick:</b> "
            "<code>{name}</code>\n"
            "<emoji document_id=5314260526803462610>😴</emoji> <b>Your ID:</b> "
            "<code>{uid}</code>"
        ),
        "chatid_fmt": (
            "<emoji document_id=5301034196490268401>🪐</emoji> <b>Chat:</b> "
            "<code>{name}</code>\n"
            "<emoji document_id=5314260526803462610>😴</emoji> <b>Chat ID:</b> "
            "<code>{cid}</code>"
        ),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        validator = Boolean() if Boolean is not None else None
        self.config = ModuleConfig(
            ConfigValue(
                "bot_api_id",
                default=True,
                doc="Возвращать ID каналов/чатов в формате Bot API (с префиксом -100)",
                validator=validator,
            ),
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _entity_name(entity: object) -> str:
        """Универсальное имя для User / Chat / Channel."""
        if isinstance(entity, User):
            parts = [getattr(entity, "first_name", None), getattr(entity, "last_name", None)]
            name = " ".join(p for p in parts if p)
            return name or (f"@{entity.username}" if getattr(entity, "username", None) else "—")
        return getattr(entity, "title", None) or "—"

    def _format_chat_id(self, raw_id: int) -> str:
        """ID чата/канала с учётом настройки bot_api_id."""
        try:
            use_bot_api = bool(self.config["bot_api_id"]) if self.config else True
        except Exception:
            use_bot_api = True
        if use_bot_api:
            text = str(raw_id)
            # уже в формате -100..., не дублируем префикс
            if not text.startswith("-100"):
                return f"-100{abs(raw_id)}"
            return text
        return str(raw_id)

    @staticmethod
    def _extract_chat_raw_id(event) -> int | None:
        """Достаём числовой id чата надёжно из разных источников."""
        peer = getattr(event, "peer_id", None) or getattr(
            getattr(event, "message", None), "peer_id", None
        )
        if peer is not None:
            for attr in ("channel_id", "chat_id", "user_id"):
                val = getattr(peer, attr, None)
                if val:
                    return int(val)
        chat = getattr(event, "chat", None)
        if chat is not None and getattr(chat, "id", None):
            return int(chat.id)
        cid = getattr(event, "chat_id", None)
        return int(cid) if cid else None

    # ----------------------------------------------------------------- commands
    @command("userid", required=OWNER, aliases=["uid"])
    async def userid_cmd(self, event) -> None:
        """[reply / username / id] — получить ID пользователя или чата."""
        try:
            args = self.get_args(event).strip()
            reply = await event.message.get_reply_message()

            entity = None
            try:
                if args:
                    target = int(args) if args.lstrip("-").isdigit() else args
                    entity = await self.client.get_entity(target)
                elif reply is not None and getattr(reply, "sender_id", None):
                    entity = await self.client.get_entity(reply.sender_id)
                else:
                    entity = await self.client.get_entity(event.sender_id)
            except (ValueError, TypeError):
                # запасной путь — собственный sender_id
                try:
                    entity = await self.client.get_entity(event.sender_id)
                except Exception:
                    logger.exception("userid: get_entity fallback failed")

            if entity is None:
                await event.edit(self.strings("not_found"), parse_mode="html")
                return

            name = _esc(self._entity_name(entity))
            if isinstance(entity, User):
                text = self.strings("user_fmt").format(name=name, uid=entity.id)
            else:
                cid = self._format_chat_id(entity.id)
                text = self.strings("chat_fmt").format(name=name, cid=cid)

            await event.edit(text, parse_mode="html")
        except Exception as exc:  # отказоустойчивость — не роняем юзербот
            logger.exception("userid command failed")
            await self._safe_error(event, exc)

    @command("id", required=OWNER)
    async def id_cmd(self, event) -> None:
        """— получить свой ID."""
        try:
            try:
                me = await self.client.get_me()
            except Exception:
                me = await self.client.get_entity(event.sender_id)

            parts = [getattr(me, "first_name", None), getattr(me, "last_name", None)]
            name = _esc(" ".join(p for p in parts if p) or "—")
            await event.edit(
                self.strings("me_fmt").format(name=name, uid=getattr(me, "id", event.sender_id)),
                parse_mode="html",
            )
        except Exception as exc:
            logger.exception("id command failed")
            await self._safe_error(event, exc)

    @command("chatid", required=OWNER, aliases=["cid"])
    async def chatid_cmd(self, event) -> None:
        """— получить ID текущего чата/канала."""
        try:
            raw_id = self._extract_chat_raw_id(event)
            if raw_id is None:
                await event.edit(self.strings("not_chat"), parse_mode="html")
                return

            title = None
            chat = getattr(event, "chat", None)
            if chat is not None:
                title = getattr(chat, "title", None)
            if title is None:
                try:
                    entity = await self.client.get_entity(raw_id)
                    title = self._entity_name(entity)
                except Exception:
                    title = "—"

            cid = self._format_chat_id(raw_id)
            await event.edit(
                self.strings("chatid_fmt").format(name=_esc(title), cid=cid),
                parse_mode="html",
            )
        except Exception as exc:
            logger.exception("chatid command failed")
            await self._safe_error(event, exc)

    # ------------------------------------------------------------------ utility
    async def _safe_error(self, event, exc: Exception) -> None:
        """Аккуратно сообщаем об ошибке, не давая исключению уронить юзербот."""
        try:
            await event.edit(
                f"<emoji document_id=5328145443106873128>✖️</emoji> "
                f"<b>Ошибка:</b> <code>{_esc(exc)}</code>",
                parse_mode="html",
            )
        except Exception:
            logger.debug("Kitsune-ID: не удалось отправить сообщение об ошибке", exc_info=True)
