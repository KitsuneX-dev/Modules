# ---------------------------------------------------------------------------------
#  🦊 Kitsune Module — Kitsune-Pinterest
# ---------------------------------------------------------------------------------
#  Name:        Kitsune-Pinterest
#  Description: Скачивает медиа (видео/фото) с Pinterest прямо в чат.
#               Адаптировано под Kitsune @Mikasu32
#  Author:      codrago (adapted for Kitsune)
#  Version:     2.0.0
#  Commands:    .pinterest
# ---------------------------------------------------------------------------------
#  🔒  Licensed under the GNU AGPLv3
#  🌐  https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
from __future__ import annotations

import io
import re

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER
from ..utils import answer_file, escape_html

# pip-зависимости подтянутся автоматически при первой загрузке модуля.
# aiohttp обычно уже есть в Kitsune, но указываем явно на всякий случай.


_PIN_RE = re.compile(r"https?://(?:[a-z]{2}\.)?(?:pinterest\.[a-z.]+|pin\.it)/\S+", re.I)
_DOWNLOAD_API = "https://pinterestdownloader.com?share_url={url}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Регексы для вытаскивания прямой ссылки на медиа из HTML страницы пина.
_VIDEO_RE = re.compile(r'contentUrl"\s*:\s*"([^"]+\.mp4[^"]*)"', re.I)
_VIDEO_RE2 = re.compile(r'"url"\s*:\s*"(https://[^"]+\.mp4[^"]*)"', re.I)
_IMAGE_OG = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.I)
_IMAGE_736 = re.compile(r'"(https://i\.pinimg\.com/originals/[^"]+)"', re.I)


class Pinterest(KitsuneModule):
    name = "Kitsune-Pinterest"
    description = "Скачивает медиа с Pinterest прямо в Telegram. Адаптировано под Kitsune @Mikasu32"
    author = "codrago"
    version = "2.0.0"
    icon = "📌"
    category = "downloaders"
    pip_requires = ["aiohttp"]

    strings_ru = {
        "no_args": (
            "<emoji document_id=5328145443106873128>✖️</emoji> "
            "<b>Дай ссылку на пин:</b> <code>.pinterest https://pin.it/...</code>"
        ),
        "bad_link": (
            "<emoji document_id=5319088379281815108>🤷‍♀️</emoji> "
            "<b>Это не похоже на ссылку Pinterest.</b>"
        ),
        "loading": "<emoji document_id=5325547803936572038>⏳</emoji> <i>Скачиваю медиа...</i>",
        "caption": (
            "<emoji document_id=5319172556345851345>✨</emoji> "
            "<b>Скачано с Pinterest</b>"
        ),
        "fallback": (
            "<emoji document_id=5316719099227684154>🌕</emoji> "
            "<b>Не удалось вытащить медиа напрямую.</b>\n"
            'Скачать вручную: <a href="{link}">тык сюда</a>'
        ),
        "error": (
            "<emoji document_id=5328145443106873128>✖️</emoji> "
            "<b>Ошибка:</b> <code>{err}</code>"
        ),
    }

    strings_en = {
        "no_args": (
            "<emoji document_id=5328145443106873128>✖️</emoji> "
            "<b>Give a pin link:</b> <code>.pinterest https://pin.it/...</code>"
        ),
        "bad_link": (
            "<emoji document_id=5319088379281815108>🤷‍♀️</emoji> "
            "<b>This is not a Pinterest link.</b>"
        ),
        "loading": "<emoji document_id=5325547803936572038>⏳</emoji> <i>Downloading media...</i>",
        "caption": (
            "<emoji document_id=5319172556345851345>✨</emoji> "
            "<b>Downloaded from Pinterest</b>"
        ),
        "fallback": (
            "<emoji document_id=5316719099227684154>🌕</emoji> "
            "<b>Couldn't fetch media directly.</b>\n"
            'Download manually: <a href="{link}">tap here</a>'
        ),
        "error": (
            "<emoji document_id=5328145443106873128>✖️</emoji> "
            "<b>Error:</b> <code>{err}</code>"
        ),
    }

    async def _fetch_text(self, session, url: str) -> str:
        import aiohttp

        async with session.get(
            url,
            headers=_HEADERS,
            timeout=aiohttp.ClientTimeout(total=20),
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def _fetch_bytes(self, session, url: str) -> bytes:
        import aiohttp

        async with session.get(
            url,
            headers=_HEADERS,
            timeout=aiohttp.ClientTimeout(total=60),
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            return await resp.read()

    @staticmethod
    def _extract_media(html: str) -> tuple[str | None, bool]:
        """Возвращает (url, is_video). url=None если ничего не найдено."""
        for rx in (_VIDEO_RE, _VIDEO_RE2):
            m = rx.search(html)
            if m:
                return m.group(1).replace("\\/", "/"), True
        for rx in (_IMAGE_OG, _IMAGE_736):
            m = rx.search(html)
            if m:
                return m.group(1).replace("\\/", "/"), False
        return None, False

    @command("pinterest", required=OWNER, aliases=["pin", "pint"])
    async def pinterest_cmd(self, event) -> None:
        """Скачать видео или фото с Pinterest прямо в Telegram. Пример: .pinterest https://pin.it/... Псевдоним: .pin, .pint"""
        args = self.get_args(event).strip()
        if not args:
            await event.edit(self.strings("no_args"), parse_mode="html")
            return

        match = _PIN_RE.search(args)
        if not match:
            await event.edit(self.strings("bad_link"), parse_mode="html")
            return
        url = match.group(0)
        fallback_link = _DOWNLOAD_API.format(url=url)

        await event.edit(self.strings("loading"), parse_mode="html")

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                html = await self._fetch_text(session, url)
                media_url, is_video = self._extract_media(html)

                if not media_url:
                    await event.edit(
                        self.strings("fallback", link=fallback_link),
                        parse_mode="html",
                        link_preview=False,
                    )
                    return

                data = await self._fetch_bytes(session, media_url)
        except Exception as exc:  # noqa: BLE001 — показываем ошибку пользователю
            await event.edit(
                self.strings("error", err=escape_html(str(exc))),
                parse_mode="html",
            )
            return

        ext = "mp4" if is_video else (media_url.rsplit(".", 1)[-1][:4] or "jpg")
        buf = io.BytesIO(data)
        buf.name = f"pinterest.{ext}"

        await answer_file(
            event,
            buf,
            caption=self.strings("caption"),
            parse_mode="html",
            force_document=False,
        )
