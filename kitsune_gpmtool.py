# ---------------------------------------------------------------------------------
# Name: Kitsune-GPMTool
# Description: Пересылка сообщений из каналов, где это запрещено (no-forward / GPM)
# Original author: @kmodules
# Адаптировано под Kitsune @Mikasu32
# ---------------------------------------------------------------------------------
# 🔒 Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------

from __future__ import annotations

import io
import logging
import re

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER

logger = logging.getLogger(__name__)

# https://t.me/<channel>/<id>  или  https://t.me/c/<internal>/<id>
_LINK_RE = re.compile(
    r"^https?://t\.me/(?:(c)/(\d+)|([A-Za-z0-9_]+))/(\d+)/?$"
)


def _esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class KitsuneGPMToolModule(KitsuneModule):
    name        = "Kitsune-GPMTool"
    description = (
        "Пересылает сообщения из каналов, где это запрещено. "
        "Адаптировано под Kitsune @Mikasu32"
    )
    author      = "@kmodules | adapt @Mikasu32"
    version     = "2.0.0"
    icon        = "🤑"

    strings_ru = {
        "no_args": (
            "<emoji document_id=5116151848855667552>🚫</emoji> "
            "<b>Укажите ссылку правильно.</b>\n\n"
            "<blockquote>Пример: <code>.gpm https://t.me/channel/9</code></blockquote>"
        ),
        "invalid_args": (
            "<emoji document_id=5116151848855667552>🚫</emoji>"
            "<b> Неверный формат ссылки.</b>"
        ),
        "msg_not_found": (
            "<emoji document_id=5116151848855667552>🚫</emoji>"
            "<b> Сообщение не найдено.</b>"
        ),
        "no_premium": (
            "<emoji document_id=5121063440311386962>👎</emoji>"
            "<b> У вас нет Telegram Premium. </b>\n\n"
            "<blockquote>Сообщение отправлено без премиум-эмодзи.</blockquote>"
        ),
        "loading": (
            "<emoji document_id=5434105584834067115>🤑</emoji>"
            "<b> Загрузка...</b>"
        ),
        "error": (
            "<emoji document_id=5116151848855667552>🚫</emoji> "
            "<b>Ошибка:</b> <code>{err}</code>"
        ),
    }

    strings_en = {
        "no_args": (
            "<emoji document_id=5116151848855667552>🚫</emoji> "
            "<b>Specify the link correctly.</b>\n\n"
            "<blockquote>Example: <code>.gpm https://t.me/channel/9</code></blockquote>"
        ),
        "invalid_args": (
            "<emoji document_id=5116151848855667552>🚫</emoji>"
            "<b> Invalid link format.</b>"
        ),
        "msg_not_found": (
            "<emoji document_id=5116151848855667552>🚫</emoji>"
            "<b> Message not found.</b>"
        ),
        "no_premium": (
            "<emoji document_id=5121063440311386962>👎</emoji>"
            "<b> You don't have Telegram Premium. </b>\n\n"
            "<blockquote>The message was sent without premium emoji.</blockquote>"
        ),
        "loading": (
            "<emoji document_id=5434105584834067115>🤑</emoji>"
            "<b> Loading...</b>"
        ),
        "error": (
            "<emoji document_id=5116151848855667552>🚫</emoji> "
            "<b>Error:</b> <code>{err}</code>"
        ),
    }

    # --------------------------------------------------------------- parse link
    @staticmethod
    def _parse_link(args: str):
        """Возвращает (channel, msg_id) или None при невалидной ссылке.

        Поддерживает публичные (@username) и приватные (t.me/c/...) каналы.
        """
        match = _LINK_RE.match(args.strip())
        if not match:
            return None
        is_private, internal_id, username, msg_id = match.groups()
        try:
            msg_id_int = int(msg_id)
        except (TypeError, ValueError):
            return None
        if is_private:
            # приватный канал: telethon ждёт -100<internal_id>
            try:
                channel = int(f"-100{internal_id}")
            except ValueError:
                return None
        else:
            channel = username
        return channel, msg_id_int

    # ----------------------------------------------------------------- commands
    @command("gpm", required=OWNER, aliases=["forward", "fwd"])
    async def gpm_cmd(self, event) -> None:
        """<ссылка t.me/channel/id> — переслать сообщение из закрытого канала."""
        status = None
        try:
            args = self.get_args(event).strip()
            if not args:
                await event.edit(self.strings("no_args"), parse_mode="html")
                return

            parsed = self._parse_link(args)
            if parsed is None:
                await event.edit(self.strings("invalid_args"), parse_mode="html")
                return
            channel, msg_id = parsed

            status = await event.edit(self.strings("loading"), parse_mode="html")

            # параллельных вызовов не делаем намеренно: get_me кэшируется,
            # а get_messages зависит от доступа к каналу
            me = getattr(self.client, "tg_me", None)
            if me is None:
                try:
                    me = await self.client.get_me()
                except Exception:
                    me = None
            has_premium = bool(getattr(me, "premium", False))

            try:
                copied = await self.client.get_messages(channel, ids=msg_id)
            except Exception:
                logger.debug("gpm: get_messages failed", exc_info=True)
                copied = None

            if not copied:
                await event.edit(self.strings("msg_not_found"), parse_mode="html")
                return

            peer = getattr(event, "peer_id", None) or getattr(event, "chat_id", None)
            caption = copied.message or ""
            entities = getattr(copied, "entities", None)

            if getattr(copied, "media", None):
                await self._send_with_media(peer, copied, caption, entities)
            else:
                await self.client.send_message(
                    peer,
                    caption,
                    formatting_entities=entities,
                    link_preview=False,
                )

            # удаляем команду/статус
            try:
                await event.message.delete()
            except Exception:
                logger.debug("gpm: не удалось удалить команду", exc_info=True)

            # предупреждение об отсутствии премиума (не в «Избранном»)
            if not has_premium and peer is not None:
                try:
                    await self.client.send_message(
                        peer, self.strings("no_premium"), parse_mode="html"
                    )
                except Exception:
                    logger.debug("gpm: не удалось отправить no_premium", exc_info=True)

        except Exception as exc:
            logger.exception("gpm command failed")
            await self._safe_error(event, exc, status)

    # ------------------------------------------------------------------ helpers
    async def _send_with_media(self, peer, copied, caption: str, entities) -> None:
        """Скачиваем медиа в память (без диска) и отправляем заново.

        Загрузка в BytesIO быстрее и безопаснее, чем во временный файл:
        не нужно чистить диск и нет файловых гонок.
        """
        media = copied.media
        # определяем спец-типы для корректной отправки
        from telethon.tl.types import (
            DocumentAttributeAudio,
            DocumentAttributeVideo,
        )

        voice_note = False
        video_note = False
        try:
            document = getattr(media, "document", None)
            attributes = getattr(document, "attributes", []) or []
            for attr in attributes:
                if isinstance(attr, DocumentAttributeAudio) and getattr(attr, "voice", False):
                    voice_note = True
                if isinstance(attr, DocumentAttributeVideo) and getattr(attr, "round_message", False):
                    video_note = True
        except Exception:
            logger.debug("gpm: не удалось разобрать атрибуты медиа", exc_info=True)

        # пытаемся переотправить медиа напрямую (быстрее всего — без скачивания)
        try:
            await self.client.send_file(
                peer,
                media,
                caption=caption,
                formatting_entities=entities,
                voice_note=voice_note,
                video_note=video_note,
            )
            return
        except Exception:
            logger.debug("gpm: прямая отправка media не удалась, качаем в память", exc_info=True)

        # запасной путь: скачиваем в BytesIO и отправляем
        buffer = io.BytesIO()
        try:
            await self.client.download_media(copied, file=buffer)
        except Exception as exc:
            logger.exception("gpm: download_media failed")
            raise exc
        buffer.seek(0)
        # сохраняем имя файла, если оно было
        try:
            buffer.name = getattr(copied.file, "name", None) or "file"
        except Exception:
            buffer.name = "file"

        await self.client.send_file(
            peer,
            buffer,
            caption=caption,
            formatting_entities=entities,
            voice_note=voice_note,
            video_note=video_note,
        )

    async def _safe_error(self, event, exc: Exception, status=None) -> None:
        text = self.strings("error").format(err=_esc(exc))
        try:
            if status is not None:
                await status.edit(text, parse_mode="html")
            else:
                await event.edit(text, parse_mode="html")
        except Exception:
            logger.debug("Kitsune-GPMTool: не удалось отправить сообщение об ошибке", exc_info=True)
