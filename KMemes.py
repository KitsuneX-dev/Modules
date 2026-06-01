# ---------------------------------------------------------------------------------
# Name: KMemes
# Description: Random memes (адаптация под Kitsune)
# Original author: @hikka_mods
# Adapted for Kitsune
# requires: aiohttp
# ---------------------------------------------------------------------------------

from __future__ import annotations

import logging
import random
import contextlib
import typing

import aiohttp

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER
from ..utils import escape_html

logger = logging.getLogger(__name__)

# Источники случайных мемов (отдают прямые ссылки на изображения/гифки).
# Заменяет внешнюю Hikka-библиотеку HModsLibrary.get_random_image().
_MEME_API_PRIMARY = "https://meme-api.com/gimme"
_MEME_SUBREDDITS = [
    "memes", "dankmemes", "wholesomememes",
    "me_irl", "funny", "MemeEconomy",
]


class KMemesModule(KitsuneModule):
    """Random memes"""

    name = "KMemes"
    description = "Случайные мемы"
    author = "hikka_mods (adapted for Kitsune)"
    version = "1.0.0"
    icon = "☄️"
    category = "fun"

    pip_requires = ["aiohttp"]

    strings_ru = {
        "name": "KMemes",
        "done": "☄️ Лови мем",
        "still": "🔄 Обновить",
        "dell": "❌ Закрыть",
        "loading": "☄️ <i>Ищу мем...</i>",
        "no_inline": "❌ <b>Inline-менеджер недоступен.</b>",
        "error": "❌ <b>Не удалось получить мем:</b>\n<code>{err}</code>",
    }

    strings_en = {
        "name": "KMemes",
        "done": "☄️ Catch the meme",
        "still": "🔄 Update",
        "dell": "❌ Close",
        "loading": "☄️ <i>Fetching meme...</i>",
        "no_inline": "❌ <b>Inline manager unavailable.</b>",
        "error": "❌ <b>Failed to fetch meme:</b>\n<code>{err}</code>",
    }

    def _inline(self):
        return getattr(self.client, "_kitsune_inline", None)

    async def get_random_image(self) -> str:
        """Возвращает прямую ссылку на случайный мем. Замена HModsLibrary."""
        subreddit = random.choice(_MEME_SUBREDDITS)
        urls = [
            f"{_MEME_API_PRIMARY}/{subreddit}",
            _MEME_API_PRIMARY,
        ]
        last_err: typing.Optional[Exception] = None
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        img = data.get("url")
                        if img:
                            return img
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    logger.debug("KMemes: источник %s не сработал: %s", url, exc)
                    continue
        raise RuntimeError(str(last_err) if last_err else "no meme source available")

    def _markup(self) -> list:
        return [
            [{"text": self.strings("still"), "callback": self._refresh}],
            [{"text": self.strings("dell"), "callback": self._close}],
        ]

    @command("kmemes", required=OWNER, aliases=["memes", "meme"])
    async def kmemes_cmd(self, event) -> None:
        """- Получить случайный мем"""
        inline = self._inline()
        if inline is None:
            await event.edit(self.strings("no_inline"), parse_mode="html")
            return

        await event.edit(self.strings("loading"), parse_mode="html")

        try:
            img = await self.get_random_image()
        except Exception as exc:
            logger.exception("KMemes: ошибка получения мема")
            await event.edit(
                self.strings("error").format(err=escape_html(str(exc))),
                parse_mode="html",
            )
            return

        try:
            await inline.form(
                self.strings("done"),
                event.message,
                reply_markup=self._markup(),
                gif=img,
            )
        except Exception:
            logger.exception("KMemes: ошибка inline.form")
            # Фолбэк — отправляем мем обычным фото
            with contextlib.suppress(Exception):
                peer = (
                    getattr(event.message, "peer_id", None)
                    or getattr(event, "chat_id", None)
                )
                await self.client.send_file(peer, img, caption=self.strings("done"))

        with contextlib.suppress(Exception):
            await event.message.delete()

    async def _refresh(self, call) -> None:
        """Callback кнопки «Обновить»."""
        inline = self._inline()
        if inline is None:
            with contextlib.suppress(Exception):
                await call.answer(self.strings("no_inline"), show_alert=True)
            return

        try:
            img = await self.get_random_image()
        except Exception as exc:
            logger.exception("KMemes: ошибка обновления мема")
            with contextlib.suppress(Exception):
                await call.answer(str(exc)[:180], show_alert=True)
            return

        # Сначала пробуем обновить медиа через бота, затем — текст/caption.
        bot = getattr(inline, "_bot", None)
        iid = getattr(call, "inline_message_id", None)
        edited = False
        if bot is not None and iid:
            with contextlib.suppress(Exception):
                from aiogram.types import (
                    InputMediaAnimation,
                    InlineKeyboardMarkup,
                    InlineKeyboardButton,
                )
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text=self.strings("still"),
                            switch_inline_query_current_chat="",
                        )],
                    ]
                )
                await bot.edit_message_media(
                    inline_message_id=iid,
                    media=InputMediaAnimation(
                        media=img, caption=self.strings("done")
                    ),
                )
                edited = True

        if not edited:
            with contextlib.suppress(Exception):
                await inline.edit(
                    call,
                    self.strings("done"),
                    reply_markup=self._markup(),
                )

        with contextlib.suppress(Exception):
            await call.answer("")

    async def _close(self, call) -> None:
        """Callback кнопки «Закрыть»."""
        with contextlib.suppress(Exception):
            await call.delete()
            return
        with contextlib.suppress(Exception):
            await call.answer("")
