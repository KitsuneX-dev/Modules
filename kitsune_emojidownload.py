# ---------------------------------------------------------------------------------
# Name: Kitsune-EmojiDownload
# Description: Скачивание (получение) эмодзи из реплая через @emojidownloadbot
# Original author: @codrago_m
# Адаптировано под Kitsune @Mikasu32
# ---------------------------------------------------------------------------------
# 🔒 Licensed under the GNU AGPLv3
# 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------

from __future__ import annotations

import asyncio
import logging

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER

logger = logging.getLogger(__name__)


def _esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class KitsuneEmojiDownloadModule(KitsuneModule):
    name        = "Kitsune-EmojiDownload"
    description = "Получение эмодзи из реплая. Адаптировано под Kitsune @Mikasu32"
    author      = "@codrago_m | adapt @Mikasu32"
    version     = "2.0.0"
    icon        = "😎"

    # Бот-помощник, через которого извлекается эмодзи
    _BOT = "@emojidownloadbot"
    # Таймаут ожидания ответа от бота, чтобы команда не висела вечно
    _RESPONSE_TIMEOUT = 30.0

    strings_ru = {
        "no_reply":     "<emoji document_id=5328145443106873128>✖️</emoji> <b>Где реплай на эмодзи?</b>",
        "no_premium":   "<emoji document_id=5328145443106873128>✖️</emoji> <b>Извини, модуль работает только для Premium-пользователей.</b>",
        "no_response":  "<emoji document_id=5328145443106873128>✖️</emoji> <b>Бот не ответил вовремя, попробуй ещё раз.</b>",
        "error":        "<emoji document_id=5328145443106873128>✖️</emoji> <b>Ошибка:</b> <code>{err}</code>",
    }

    strings_en = {
        "no_reply":     "<emoji document_id=5328145443106873128>✖️</emoji> <b>Where is the reply to your emoji?</b>",
        "no_premium":   "<emoji document_id=5328145443106873128>✖️</emoji> <b>Sorry, the module works only for Premium users.</b>",
        "no_response":  "<emoji document_id=5328145443106873128>✖️</emoji> <b>The bot did not respond in time, please try again.</b>",
        "error":        "<emoji document_id=5328145443106873128>✖️</emoji> <b>Error:</b> <code>{err}</code>",
    }

    async def on_load(self) -> None:
        """При загрузке тихо «расхлопываем» (запускаем) бота-помощника.

        Делаем это в фоне и максимально безопасно, чтобы любые сетевые
        проблемы не помешали загрузке модуля и не уронили юзербот.
        """
        asyncio.create_task(self._warmup_bot())

    async def _warmup_bot(self) -> None:
        try:
            # /start активирует бота и заглушает уведомления от него
            try:
                from telethon.tl.functions.messages import StartBotRequest
                entity = await self.client.get_entity(self._BOT)
                await self.client(StartBotRequest(
                    bot=entity, peer=entity, start_param=""
                ))
            except Exception:
                # если уже запущен / StartBot недоступен — просто шлём /start
                await self.client.send_message(self._BOT, "/start")
            # отключаем уведомления от бота, как в оригинале (utils.dnd)
            try:
                from telethon.tl.functions.account import UpdateNotifySettingsRequest
                from telethon.tl.types import InputPeerNotifySettings, InputNotifyPeer
                peer = await self.client.get_input_entity(self._BOT)
                await self.client(UpdateNotifySettingsRequest(
                    peer=InputNotifyPeer(peer),
                    settings=InputPeerNotifySettings(mute_until=2**31 - 1),
                ))
            except Exception:
                logger.debug("Kitsune-EmojiDownload: не удалось замьютить бота", exc_info=True)
        except Exception:
            logger.debug("Kitsune-EmojiDownload: warmup бота не удался", exc_info=True)

    @command("emojidown", required=OWNER, aliases=["edown", "emojidownload"])
    async def emojidown_cmd(self, event) -> None:
        """[reply] — получить эмодзи из реплая."""
        try:
            reply = await event.message.get_reply_message()
            if reply is None or not getattr(reply, "id", None):
                await event.edit(self.strings("no_reply"), parse_mode="html")
                return

            # Проверка Premium — модуль работает только с премиум-эмодзи
            try:
                me = getattr(self.client, "tg_me", None) or await self.client.get_me()
            except Exception:
                me = None
            if not getattr(me, "premium", False):
                await event.edit(self.strings("no_premium"), parse_mode="html")
                return

            try:
                emoji_msg = await self._fetch_emoji(reply)
            except asyncio.TimeoutError:
                await event.edit(self.strings("no_response"), parse_mode="html")
                return

            if emoji_msg is None:
                await event.edit(self.strings("no_response"), parse_mode="html")
                return

            # Удаляем команду и отправляем полученное сообщение с эмодзи
            try:
                await event.message.delete()
            except Exception:
                logger.debug("emojidown: не удалось удалить команду", exc_info=True)

            await self._send_emoji(event, emoji_msg)

        except Exception as exc:
            logger.exception("emojidown command failed")
            await self._safe_error(event, exc)

    async def _fetch_emoji(self, reply):
        """Диалог с ботом: пересылаем реплай и ждём ответ.

        Используем telethon conversation с таймаутом, помечаем прочитанным.
        """
        async with self.client.conversation(
            self._BOT, timeout=self._RESPONSE_TIMEOUT
        ) as conv:
            await conv.send_message(reply)
            response = await asyncio.wait_for(
                conv.get_response(), timeout=self._RESPONSE_TIMEOUT
            )
            try:
                await conv.mark_read()
            except Exception:
                pass
            return response

    async def _send_emoji(self, event, emoji_msg) -> None:
        """Отправляем полученное сообщение с эмодзи в исходный чат.

        Пытаемся сохранить форматирование/медиа, иначе отправляем текст.
        """
        peer = getattr(event, "peer_id", None) or getattr(event, "chat_id", None)
        try:
            if getattr(emoji_msg, "media", None):
                await self.client.send_file(
                    peer,
                    emoji_msg.media,
                    caption=emoji_msg.message or "",
                    formatting_entities=emoji_msg.entities,
                )
            else:
                await self.client.send_message(
                    peer,
                    emoji_msg.message or "",
                    formatting_entities=emoji_msg.entities,
                )
        except Exception:
            # последний запасной вариант — простая пересылка
            logger.debug("emojidown: send_file/message failed, пробуем forward", exc_info=True)
            try:
                await self.client.forward_messages(peer, emoji_msg)
            except Exception as exc:
                logger.exception("emojidown: не удалось доставить эмодзи")
                raise exc

    async def _safe_error(self, event, exc: Exception) -> None:
        try:
            await event.edit(self.strings("error").format(err=_esc(exc)), parse_mode="html")
        except Exception:
            logger.debug("Kitsune-EmojiDownload: не удалось отправить сообщение об ошибке", exc_info=True)
