__version__ = (2, 6, 1)

"""
    █▀▄▀█ █▀█ █▀█ █ █▀ █ █ █▀▄▀█ █▀▄▀█ █▀▀ █▀█
    █ ▀ █ █▄█ █▀▄ █ ▄█ █▄█ █ ▀ █ █ ▀ █ ██▄ █▀▄
    Copyright 2022 t.me/morisummermods
    Licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
    Адаптировано под Kitsune UserBot (KitsuneModule / @command / @watcher / @inline_handler).
"""
# requires: requests bs4 spotipy
# meta developer: @morisummermods (adapted for Kitsune)

import asyncio
import logging
import re
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from telethon.tl.types import Message

from ..core.loader import KitsuneModule, command, watcher, inline_handler
from ..core.security import OWNER
from ..utils import answer, run_sync

try:
    from aiogram.types import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        InlineQueryResultArticle,
        InputTextMessageContent,
    )
    AIOGRAM_AVAILABLE = True
except Exception:  # pragma: no cover
    AIOGRAM_AVAILABLE = False

logger = logging.getLogger(__name__)

api_headers = {
    "User-Agent": "CompuServe Classic/1.22",
    "Accept": "application/json",
    "Host": "api.genius.com",
}
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/99.0.4844.82 Safari/537.36"
    )
}
host = "https://api.genius.com"
n = "\n"


def _get_lyrics(no_lyrics_text: str, song_url: str, remove_section_headers: bool = False) -> str:
    """Скрапит текст песни со страницы Genius (синхронно)."""
    page = requests.get(song_url, headers=headers, timeout=30)
    html = BeautifulSoup(page.text.replace("<br/>", "\n"), "html.parser")
    lyrics = "\n".join(
        [
            p.get_text()
            for p in html.find_all("div", attrs={"data-lyrics-container": "true"})
        ]
    )
    # Remove [Verse], [Bridge], etc.
    lyrics = re.sub(r"(\[.*?\])", r"</i><b>\g<1></b><i>", lyrics)
    if remove_section_headers:
        lyrics = re.sub(r"(\[.*?\])*", "", lyrics)
        lyrics = re.sub("\n{2}", "\n", lyrics)

    return lyrics or no_lyrics_text


def _search(q: str) -> list:
    """Поиск документов на Genius (синхронно)."""
    req = requests.get(
        (
            "https://api.genius.com/search"
            "?text_format=plain"
            f"&q={quote_plus(q)}"
            "&access_token=uhYUr-qrBp5V3o46lA8vcaL1DKXTWVs5SDsb_0CDCIcKxKLwtapqeqkdNu8JnA6w"
        ),
        headers=api_headers,
        timeout=30,
    ).json()

    return [
        {
            "artists": hit["result"]["artist_names"].replace("\u200b", ""),
            "title": hit["result"]["title"].replace("\u200b", ""),
            "pic": hit["result"]["header_image_thumbnail_url"],
            "url": hit["result"]["url"],
            "id": hit["result"]["id"],
        }
        for hit in req["response"]["hits"]
    ]


def _add_protocol(x: str) -> str:
    """Добавляет протокол https к ссылке."""
    return f"https:{x}" if x.startswith("//") else x


class Klyrics(KitsuneModule):
    """Поиск текстов песен с Genius"""

    name = "Klyrics"
    author = "@morisummermods"
    version = "2.6.1"
    icon = "🎵"
    category = "fun"
    pip_requires = ["requests", "bs4", "spotipy"]

    strings_ru = {
        "name": "Klyrics",
        "type_name": "<b>🚫 Пожалуйста, введите имя композиции</b>",
        "genius": "🎵 Полный текст на Genius",
        "noSpotify": (
            "<b>🚫 Пожалуйста установи модуль SpotifyNow и пройди авторизацию.</b>\n"
            "🌃 Установка: <code>.dlmod https://mods.hikariatama.ru/spotify.py</code>"
        ),
        "notFound": "🚫 Результаты не найдены",
        "couldn'tFind": "К сожалению мы не нашли, что вы искали",
        "sauth": "<b>🚫 Выполни <code>.sauth</code> перед этим действием.</b>",
        "SpotifyError": "<b>🚫 Ошибка Спотифай</b>",
        "noResults": "<b>🚫 Результаты для <code>{}</code> не найдены</b>",
        "noLyrics": "<b>🚫 Не удалось найти текст</b>",
        "lyrics": "Текст песни <b>{}</b> от <b>{}</b>\n<i>{}",
        "loading": "Загрузка текста песни <b>{}</b> от <b>{}</b>...\n{}",
        "no_inline": "<b>🚫 Inline-менеджер недоступен. Настройте inline-бота Kitsune.</b>",
    }

    strings_en = {
        "name": "Klyrics",
        "type_name": "<b>🚫 Please type name of the song</b>",
        "genius": "🎵 Full lyrics on Genius",
        "noSpotify": (
            "<b>🚫 Please install SpotifyNow module and proceed auth</b>\n"
            "🌃 Install: <code>.dlmod https://mods.hikariatama.ru/spotify.py</code>"
        ),
        "notFound": "🚫 No results found",
        "couldn'tFind": "We couldn't find what are you looking for",
        "sauth": "<b>🚫 Execute <code>.sauth</code> before using this action.</b>",
        "SpotifyError": "<b>🚫 Spotify error</b>",
        "noResults": "<b>🚫 No results found for <code>{}</code></b>",
        "noLyrics": "<b>🚫 Couldn't find the lyrics</b>",
        "lyrics": "Lyrics for <b>{}</b> by <b>{}</b>\n<i>{}",
        "loading": "Loading lyrics for <b>{}</b> by <b>{}</b>...\n{}",
        "no_inline": "<b>🚫 Inline manager is unavailable. Set up the Kitsune inline bot.</b>",
    }

    # ----------------------------------------------------------------- helpers
    def _get_inline(self):
        return getattr(self.client, "_kitsune_inline", None)

    def _get_bot_id(self):
        inline = self._get_inline()
        if inline is None:
            return None
        return getattr(inline, "_bot_id", None)

    async def _send_lyrics_form(self, message, track: dict) -> None:
        """Формирует и отправляет inline-форму с текстом песни."""
        inline = self._get_inline()
        if inline is None or not getattr(inline, "_bot", None):
            await answer(message, self.strings("no_inline"))
            return
        lyrics = await run_sync(
            _get_lyrics, self.strings("noLyrics"), track["url"]
        )
        text = self.strings("lyrics").format(
            track["title"], track["artists"], lyrics
        )[:4092] + "</i>"
        await inline.form(
            text,
            message,
            [[{"text": self.strings("genius"), "url": track["url"]}]],
        )

    # ----------------------------------------------------------------- on_load
    async def on_load(self) -> None:
        # В Hikka здесь происходил join/react к каналу разработчика.
        # В Kitsune это некритично — оборачиваем в suppress.
        from telethon.tl.functions.channels import JoinChannelRequest
        import contextlib

        with contextlib.suppress(Exception):
            channel = await self.client.get_entity("t.me/morisummermods")
            await self.client(JoinChannelRequest(channel))
        with contextlib.suppress(Exception):
            post = (await self.client.get_messages("@morisummermods", ids=[13]))[0]
            await post.react("❤️")

    # ----------------------------------------------------------------- commands
    @command("lyrics", required=OWNER)
    async def lyrics_cmd(self, event):
        """Получить слова песни"""
        message = event.message
        text = self.get_args(event)
        reply = await message.get_reply_message()
        if not text:
            if reply:
                if (
                    getattr(reply, "media", None)
                    and getattr(reply.media, "document", None)
                    and getattr(reply.media.document, "attributes", None)
                ):
                    try:
                        text = reply.media.document.attributes[1].file_name.rsplit(
                            ".", 1
                        )[0]
                    except Exception:
                        text = reply.raw_text
                else:
                    try:
                        e = next(
                            entity
                            for entity in reply.entities
                            if type(entity).__name__ == "MessageEntityCode"
                        )
                        text = reply.raw_text[e.offset - 1 : e.offset + e.length]
                    except Exception:
                        text = reply.raw_text
            else:
                await answer(message, self.strings("type_name"))
                return
        try:
            tracks = await run_sync(_search, text)
        except Exception:
            logger.exception("Klyrics.lyrics_cmd: ошибка поиска")
            await answer(message, self.strings("noResults").format(text))
            return
        if tracks:
            track = tracks[0]
        else:
            await answer(message, self.strings("noResults").format(text))
            return
        await self._send_lyrics_form(message, track)

    @command("slyrics", required=OWNER)
    async def slyrics_cmd(self, event):
        """Получить слова песни прослушиваемой в Спотифай (нужен модуль SpotifyNow)"""
        message = event.message
        check = self.db.get("SpotifyNow", "acs_tkn", "404")
        if check == "404":
            await answer(message, self.strings("noSpotify"))
            return
        elif check is None:
            await answer(message, self.strings("sauth"))
            return
        try:
            import spotipy

            token_data = self.db.get("SpotifyNow", "acs_tkn")
            sp = spotipy.Spotify(auth=token_data["access_token"])
            current_playback = await run_sync(sp.current_playback)
        except Exception:
            logger.exception("Klyrics.slyrics_cmd: ошибка Spotify")
            await answer(message, self.strings("SpotifyError"))
            return
        try:
            track_name = current_playback["item"]["name"]
        except Exception:
            track_name = None
        try:
            artists = ", ".join(
                [artist["name"] for artist in current_playback["item"]["artists"]]
            )
        except Exception:
            artists = None
        text = f"{artists} {track_name}"
        try:
            tracks = await run_sync(_search, text)
        except Exception:
            logger.exception("Klyrics.slyrics_cmd: ошибка поиска")
            await answer(message, self.strings("noResults").format(text))
            return
        if tracks:
            track = tracks[0]
        else:
            await answer(message, self.strings("noResults").format(text))
            return
        await self._send_lyrics_form(message, track)

    # ----------------------------------------------------------------- inline search
    @inline_handler()
    async def lyrics_inline_handler(self, text: str, query) -> bool:
        """Inline-поиск текстов песен: @bot lyrics <название>"""
        if not AIOGRAM_AVAILABLE:
            return False
        # Активируем хендлер только по префиксу "lyrics ".
        if not text.lower().startswith("lyrics"):
            return False
        search_text = text[len("lyrics"):].strip()
        if not search_text:
            return False
        try:
            tracks = await run_sync(_search, search_text)
        except Exception:
            logger.exception("Klyrics.inline: ошибка поиска")
            tracks = []
        if not tracks:
            await query.answer(
                [
                    InlineQueryResultArticle(
                        id="-1",
                        title=self.strings("notFound"),
                        description=self.strings("couldn'tFind"),
                        thumb_url="https://img.icons8.com/stickers/100/000000/nothing-found.png",
                        input_message_content=InputTextMessageContent(
                            message_text=self.strings("noResults").format(search_text),
                            parse_mode="HTML",
                        ),
                    )
                ],
                cache_time=0,
            )
            return True
        res = [
            InlineQueryResultArticle(
                id=str(track["id"]),
                title=track["title"],
                description=track["artists"],
                thumb_url=_add_protocol(track["pic"]),
                input_message_content=InputTextMessageContent(
                    message_text=self.strings("loading").format(
                        track["title"], track["artists"], track["url"]
                    ),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                ),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=self.strings("genius"), url=track["url"]
                            )
                        ]
                    ]
                ),
            )
            for track in tracks[:50]
        ]
        await query.answer(res, cache_time=0)
        return True

    # ----------------------------------------------------------------- watcher
    @watcher()
    async def lyrics_watcher(self, event) -> None:
        """Перехватывает сообщение-заглушку 'Загрузка...' от inline-бота и подгружает текст."""
        message = event.message
        try:
            bot_id = self._get_bot_id()
            if (
                getattr(message, "out", False)
                and getattr(message, "via_bot_id", False)
                and bot_id is not None
                and message.via_bot_id == bot_id
                and (
                    "Loading lyrics for" in (getattr(message, "raw_text", "") or "")
                    or "Загрузка текста песни" in (getattr(message, "raw_text", "") or "")
                )
            ):
                e = message.entities
                track = {
                    "title": message.raw_text[e[0].offset : e[0].offset + e[0].length],
                    "artists": message.raw_text[
                        e[1].offset : e[1].offset + e[1].length
                    ],
                    "url": message.raw_text.splitlines()[1],
                }
                await self._send_lyrics_form(message, track)
        except Exception:
            logger.exception("Klyrics.lyrics_watcher: ошибка обработки")
