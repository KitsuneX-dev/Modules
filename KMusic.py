# ---------------------------------------------------------------------------------
# Name: KMusic
# Description: Поиск музыки через инлайн-ботов Telegram (Yandex.Music)
# Author: hikka_mods
# Адаптировано под Kitsune @Mikasu32
# ---------------------------------------------------------------------------------
# Оригинал: @hikka_mods | Адаптация, ускорение и стабилизация: @Mikasu32
# ---------------------------------------------------------------------------------

from __future__ import annotations

import asyncio
import logging

from ..core.loader import KitsuneModule, command, ModuleConfig, ConfigValue
from ..core.security import OWNER
from ..utils import escape_html
from ..validators import String, Integer

logger = logging.getLogger(__name__)


class KMusicModule(KitsuneModule):
    name        = "KMusic"
    description = "Поиск музыки через инлайн-ботов Telegram. Адаптировано под Kitsune @Mikasu32"
    author      = "hikka_mods | @Mikasu32"
    version     = "2.0.0"
    icon        = "🎵"
    category    = "media"

    strings_ru = {
        "no_query":  "🤷‍♂️ <b>Укажите запрос для поиска!</b>\n<code>{prefix}music название трека</code>",
        "searching": "⌨️ <b>Ищу в Yandex.Music...</b>",
        "not_found": "😫 <b>Трек не найден:</b> <code>{query}</code>",
        "error":     "⚠️ <b>Ошибка поиска:</b>\n<code>{err}</code>",
        "timeout":   "⏳ <b>Бот не ответил вовремя. Попробуйте ещё раз.</b>",
    }

    strings_en = {
        "no_query":  "🤷‍♂️ <b>Provide a search query!</b>\n<code>{prefix}music track name</code>",
        "searching": "⌨️ <b>Searching Yandex.Music...</b>",
        "not_found": "😫 <b>Track not found:</b> <code>{query}</code>",
        "error":     "⚠️ <b>Search error:</b>\n<code>{err}</code>",
        "timeout":   "⏳ <b>The bot did not respond in time. Try again.</b>",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "music_bot",
                "@murglar_bot",
                "Инлайн-бот для поиска музыки",
                validator=String(max_len=64),
            ),
            ConfigValue(
                "query_prefix",
                "s:ynd",
                "Префикс инлайн-запроса для бота (для @murglar_bot: s:ynd)",
                validator=String(max_len=32),
            ),
            ConfigValue(
                "timeout",
                25,
                "Таймаут ожидания ответа инлайн-бота (секунды)",
                validator=Integer(minimum=5, maximum=60),
            ),
        )

    def _prefix(self) -> str:
        dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
        return dispatcher._prefix if dispatcher else "."

    @command("music", required=OWNER, aliases=["m", "музыка"])
    async def music_cmd(self, event) -> None:
        """Найти и отправить трек через Yandex.Music. Пример: .music Imagine Dragons Believer. Псевдонимы: .m, .музыка"""
        query = self.get_args(event).strip()

        # Если запроса нет — берём текст из реплая
        if not query:
            reply = await event.message.get_reply_message()
            if reply and (reply.raw_text or "").strip():
                query = reply.raw_text.strip()

        if not query:
            await event.edit(
                self.strings("no_query").format(prefix=self._prefix()),
                parse_mode="html",
            )
            return

        await event.edit(self.strings("searching"), parse_mode="html")

        bot = (self.config["music_bot"] if self.config else "@murglar_bot") or "@murglar_bot"
        q_prefix = (self.config["query_prefix"] if self.config else "s:ynd") or "s:ynd"
        timeout = (self.config["timeout"] if self.config else 25) or 25

        try:
            results = await asyncio.wait_for(
                self.client.inline_query(bot, f"{q_prefix} {query}".strip()),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            await event.edit(self.strings("timeout"), parse_mode="html")
            return
        except Exception as exc:
            logger.exception("KMusic: inline query failed")
            await event.edit(
                self.strings("error").format(err=escape_html(str(exc))),
                parse_mode="html",
            )
            return

        if not results:
            await event.edit(
                self.strings("not_found").format(query=escape_html(query)),
                parse_mode="html",
            )
            return

        try:
            await results[0].click(
                entity=event.chat_id,
                hide_via=True,
                reply_to=event.message.reply_to_msg_id or None,
            )
            await event.message.delete()
        except Exception as exc:
            logger.exception("KMusic: click failed")
            await event.edit(
                self.strings("error").format(err=escape_html(str(exc))),
                parse_mode="html",
            )
