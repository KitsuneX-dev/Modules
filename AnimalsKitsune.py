from __future__ import annotations
import asyncio
import logging
from typing import Optional

import aiohttp

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER

logger = logging.getLogger(__name__)

_CAT_API = "https://api.thecatapi.com/v1/images/search"
_DOG_API = "https://api.thedogapi.com/v1/images/search"


class AnimalsKitsuneModule(KitsuneModule):
    name = "AnimalsKitsune"
    description = "Случайные фото котиков и собачек. Адаптировал @Mikasu32"
    author = "@hikka_mods | Kitsune by @Mikasu32"
    version = "1.0.0"
    icon = "🐾"
    category = "fun"

    strings_ru = {
        "loading": "🕐 <b>Загружаю...</b>",
        "done_cat": "🐱 <b>Ваш котик!</b>",
        "done_dog": "🐶 <b>Ваша собачка!</b>",
        "error": "❌ <b>Не удалось получить картинку:</b> <code>{err}</code>",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        async with self._session_lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=20),
                )
            return self._session

    async def on_unload(self) -> None:
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass

    async def _fetch_image(self, api_url: str) -> str:
        session = await self._get_session()
        async with session.get(api_url) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            if not isinstance(data, list) or not data:
                raise RuntimeError("empty response")
            url = data[0].get("url")
            if not url:
                raise RuntimeError("no url in response")
            return url

    async def _send_animal(self, event, api_url: str, caption: str, as_doc: bool) -> None:
        status = await event.reply(self.strings("loading"), parse_mode="html")
        try:
            url = await self._fetch_image(api_url)
        except Exception as e:
            logger.warning("AnimalsKitsune: fetch failed: %s", e)
            await status.edit(
                self.strings("error").format(err=str(e)[:200]),
                parse_mode="html",
            )
            return

        try:
            await self.client.send_file(
                event.peer_id,
                url,
                caption=caption,
                parse_mode="html",
                force_document=as_doc,
            )
            try:
                await status.delete()
            except Exception:
                pass
        except Exception as e:
            logger.exception("AnimalsKitsune: send failed")
            await status.edit(
                self.strings("error").format(err=str(e)[:200]),
                parse_mode="html",
            )

    @command("cat", required=OWNER, aliases=["котик"])
    async def cat_cmd(self, event) -> None:
        """Отправить случайное фото кота. Псевдоним: .котик"""
        await self._send_animal(event, _CAT_API, self.strings("done_cat"), False)

    @command("dog", required=OWNER, aliases=["пёсик"])
    async def dog_cmd(self, event) -> None:
        """Отправить случайное фото собаки. Псевдоним: .пёсик"""
        await self._send_animal(event, _DOG_API, self.strings("done_dog"), False)

    @command("fcat", required=OWNER)
    async def fcat_cmd(self, event) -> None:
        """Отправить фото кота как файл (без сжатия)"""
        await self._send_animal(event, _CAT_API, self.strings("done_cat"), True)

    @command("fdog", required=OWNER)
    async def fdog_cmd(self, event) -> None:
        """Отправить фото собаки как файл (без сжатия)"""
        await self._send_animal(event, _DOG_API, self.strings("done_dog"), True)
