from __future__ import annotations
import asyncio
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Union
from urllib.parse import urljoin

import aiohttp

from ..core.loader import KitsuneModule, command, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..validators import String

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s]+")


@dataclass
class _DLResult:
    dir_name: str
    media: Union[str, List[str]]
    type: str


class _TikTokClient:
    def __init__(self, host: str, session: aiohttp.ClientSession):
        self.host = host.rstrip("/") + "/"
        self.session = session
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) "
                "AppleWebKit/531.21.10 (KHTML, like Gecko) Version/4.0.4 "
                "Mobile/7B334b Safari/531.21.10"
            )
        }
        self.data_endpoint = "api"
        self._cache: dict[str, dict] = {}

    async def _make_request(self, endpoint: str, params: dict) -> dict:
        async with self.session.get(
            urljoin(self.host, endpoint),
            params=params,
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            return data.get("data", {}) if isinstance(data, dict) else {}

    @staticmethod
    def get_url(text: str) -> Optional[str]:
        urls = _URL_RE.findall(text or "")
        return urls[0] if urls else None

    async def fetch_data(self, link: str) -> dict:
        if link in self._cache:
            return self._cache[link]
        url = self.get_url(link) or link
        data = await self._make_request(self.data_endpoint, {"url": url, "hd": 1})
        if data:
            self._cache[link] = data
        return data

    async def _download_to_file(self, url: str, path: str) -> None:
        async with self.session.get(
            url,
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=300),
        ) as response:
            response.raise_for_status()
            with open(path, "wb") as fp:
                async for chunk in response.content.iter_chunked(64 * 1024):
                    if chunk:
                        fp.write(chunk)

    async def download_images(self, result: dict, base_dir: str) -> _DLResult:
        urls = result.get("images") or []
        if not urls:
            raise RuntimeError("No images in response")
        dir_path = os.path.join(base_dir, str(result.get("id") or "tiktok"))
        os.makedirs(dir_path, exist_ok=True)
        paths: List[str] = []
        tasks = []
        for i, u in enumerate(urls, start=1):
            p = os.path.join(dir_path, f"image_{i}.jpg")
            paths.append(p)
            tasks.append(self._download_to_file(u, p))
        await asyncio.gather(*tasks)
        return _DLResult(dir_name=dir_path, media=paths, type="images")

    async def download_video(self, result: dict, base_dir: str, hd: bool = True) -> _DLResult:
        video_url = result.get("hdplay") if hd else result.get("play")
        video_url = video_url or result.get("play") or result.get("hdplay")
        if not video_url:
            raise RuntimeError("No playable URL in response")
        os.makedirs(base_dir, exist_ok=True)
        filename = os.path.join(base_dir, f"{result.get('id') or 'tiktok'}.mp4")
        await self._download_to_file(video_url, filename)
        return _DLResult(dir_name=base_dir, media=filename, type="video")

    async def download_sound(self, result: dict, base_dir: str, ext: str = ".mp3") -> _DLResult:
        music = result.get("music_info") or {}
        play_url = music.get("play")
        if not play_url:
            raise RuntimeError("No music_info.play in response")
        os.makedirs(base_dir, exist_ok=True)
        title = (music.get("title") or result.get("id") or "tiktok_sound").strip()
        title = re.sub(r'[\\/:*?"<>|]+', "_", title)[:100]
        filename = os.path.join(base_dir, f"{title}{ext}")
        await self._download_to_file(play_url, filename)
        return _DLResult(dir_name=base_dir, media=filename, type="sound")


class TikTokDownloaderKitsuneModule(KitsuneModule):
    name = "TikTokDownloaderKitsune"
    description = "Скачивание видео, фото и звуков TikTok без водяного знака. Адаптировал @Mikasu32"
    author = "hikka_mods | Kitsune by @Mikasu32"
    version = "1.1.0"
    icon = "🎵"
    category = "downloader"

    strings_ru = {
        "downloading": (
            "<emoji document_id=5436024756610546212>⚡</emoji> "
            "<b>Загружаю...</b>"
        ),
        "success_photo": (
            "<emoji document_id=5436246187944460315>❤️</emoji> "
            "<b>Фотография(-и) успешно загружены.</b>"
        ),
        "success_video": (
            "<emoji document_id=5436246187944460315>❤️</emoji> "
            "<b>Видео успешно загружено.</b>"
        ),
        "success_sound": (
            "<emoji document_id=5436246187944460315>❤️</emoji> "
            "<b>Звук успешно загружен.</b>"
        ),
        "error": "❌ <b>Ошибка при загрузке:</b>\n<code>{}</code>",
        "no_url": (
            "❌ <b>Укажите ссылку на TikTok:</b> "
            "<code>{prefix}tt https://...</code>"
        ),
        "no_url_sound": (
            "❌ <b>Укажите ссылку на TikTok-видео со звуком:</b> "
            "<code>{prefix}ttsound https://...</code>"
        ),
        "sound_hint": (
            "Убедитесь, что ссылка ведёт именно на видео или фото со звуком — "
            "прямая ссылка на звук не сработает."
        ),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "api_host",
                "https://www.tikwm.com/",
                "API endpoint для скачивания TikTok без водяного знака",
                validator=String(max_len=200),
            ),
        )
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    async def on_unload(self) -> None:
        if self._session is not None and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        async with self._session_lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
        return self._session

    def _prefix(self) -> str:
        dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
        return dispatcher._prefix if dispatcher else "."

    @command("tt", required=OWNER, aliases=["тт"])
    async def tt_cmd(self, event) -> None:
        """Скачать видео или фото с TikTok без водяного знака. Пример: .tt https://vm.tiktok.com/... Псевдоним: .тт"""
        args = self.get_args(event).strip()
        if not args:
            await event.reply(
                self.strings("no_url").format(prefix=self._prefix()),
                parse_mode="html",
            )
            return

        url = _TikTokClient.get_url(args) or args
        msg = await event.reply(self.strings("downloading"), parse_mode="html")

        session = await self._get_session()
        client = _TikTokClient(self.config["api_host"], session)
        with tempfile.TemporaryDirectory(prefix="kitsune_tt_") as tmpdir:
            try:
                data = await client.fetch_data(url)
                if not data:
                    raise RuntimeError("Empty response from API")
                if data.get("images"):
                    result = await client.download_images(data, tmpdir)
                    caption = self.strings("success_photo")
                else:
                    result = await client.download_video(data, tmpdir, hd=True)
                    caption = self.strings("success_video")

                reply_to = (
                    getattr(event.message, "reply_to_msg_id", None)
                    or event.message.id
                )

                if isinstance(result.media, list):
                    await self.client.send_file(
                        event.chat_id,
                        result.media,
                        caption=caption,
                        parse_mode="html",
                        reply_to=reply_to,
                    )
                else:
                    await self.client.send_file(
                        event.chat_id,
                        result.media,
                        caption=caption,
                        parse_mode="html",
                        reply_to=reply_to,
                        supports_streaming=True,
                    )
                try:
                    await msg.delete()
                except Exception:
                    pass
                try:
                    await event.message.delete()
                except Exception:
                    pass
            except Exception as exc:
                logger.exception("TikTokDownloaderKitsune.tt: failure")
                err = f"{type(exc).__name__}: {exc}"[:300]
                try:
                    await msg.edit(self.strings("error").format(self._escape(err)), parse_mode="html")
                except Exception:
                    pass

    @command("ttsound", required=OWNER, aliases=["ттзвук"])
    async def ttsound_cmd(self, event) -> None:
        """Скачать только звук из TikTok-видео. Пример: .ttsound https://vm.tiktok.com/... Псевдоним: .ттзвук"""
        args = self.get_args(event).strip()
        if not args:
            await event.reply(
                self.strings("no_url_sound").format(prefix=self._prefix()),
                parse_mode="html",
            )
            return

        url = _TikTokClient.get_url(args) or args
        msg = await event.reply(self.strings("downloading"), parse_mode="html")

        session = await self._get_session()
        client = _TikTokClient(self.config["api_host"], session)
        with tempfile.TemporaryDirectory(prefix="kitsune_ttsound_") as tmpdir:
            try:
                data = await client.fetch_data(url)
                if not data:
                    raise RuntimeError("Empty response from API")
                result = await client.download_sound(data, tmpdir)
                reply_to = (
                    getattr(event.message, "reply_to_msg_id", None)
                    or event.message.id
                )
                await self.client.send_file(
                    event.chat_id,
                    result.media,
                    caption=self.strings("success_sound"),
                    parse_mode="html",
                    reply_to=reply_to,
                )
                try:
                    await msg.delete()
                except Exception:
                    pass
                try:
                    await event.message.delete()
                except Exception:
                    pass
            except Exception as exc:
                logger.exception("TikTokDownloaderKitsune.ttsound: failure")
                err = f"{type(exc).__name__}: {exc}"[:300]
                hint = "\n\n" + self.strings("sound_hint")
                try:
                    await msg.edit(
                        self.strings("error").format(self._escape(err)) + hint,
                        parse_mode="html",
                    )
                except Exception:
                    pass

    @staticmethod
    def _escape(text: str) -> str:
        return (
            (text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
