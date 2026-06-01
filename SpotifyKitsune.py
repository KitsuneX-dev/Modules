from __future__ import annotations
import asyncio
import contextlib
import functools
import io
import logging
import os
import re
import shlex
import shutil
import textwrap
import time
import typing

from telethon.errors import FloodWaitError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import Message

from ..core.loader import KitsuneModule, command, watcher, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..validators import Boolean, Choice, Integer, String

logger = logging.getLogger(__name__)
logging.getLogger("spotipy").setLevel(logging.CRITICAL)

_SCOPE = (
    "user-read-playback-state playlist-read-private "
    "playlist-read-collaborative user-modify-playback-state "
    "user-library-modify playlist-modify-public playlist-modify-private"
)

_DEFAULT_CLIENT_ID = "e0708753ab60499c89ce263de9b4f57a"
_DEFAULT_CLIENT_SECRET = "80c927166c664ee98a43a2c0e2981b4a"
_DEFAULT_REDIRECT_URI = "https://thefsch.github.io/spotify/"


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _short(text: str, limit: int = 60) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


class _Banners:
    def __init__(
        self,
        title: str,
        artists: typing.Union[str, list],
        duration: int,
        progress: int,
        track_cover: bytes,
        font_bytes: bytes,
        blur: int,
    ):
        self.title = title or "Unknown"
        self.artists = (
            ", ".join(artists) if isinstance(artists, list) else (artists or "Unknown Artist")
        )
        self.duration = max(int(duration or 0), 1)
        self.progress = max(int(progress or 0), 0)
        self.track_cover = track_cover
        self.font_bytes = font_bytes
        self.blur_intensity = max(int(blur or 0), 0)

    def _font(self, size, ImageFont):
        return ImageFont.truetype(io.BytesIO(self.font_bytes), size)

    def _cover(self, size, radius, Image, ImageDraw):
        cover = Image.open(io.BytesIO(self.track_cover)).convert("RGBA")
        cover = cover.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        d = ImageDraw.Draw(mask)
        d.rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(cover, (0, 0), mask=mask)
        return out

    def _bg(self, w, h, Image, ImageFilter, ImageEnhance):
        bg = Image.open(io.BytesIO(self.track_cover)).convert("RGBA")
        bg = bg.resize((w, h), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=self.blur_intensity))
        bg = ImageEnhance.Brightness(bg).enhance(0.35)
        return bg

    @staticmethod
    def _bar(draw, x, y, w, h, pct, fg="white", bg="#6b6b6b"):
        draw.rounded_rectangle((x, y, x + w, y + h), radius=h / 2, fill=bg)
        fill = int(w * pct)
        if fill > 0:
            draw.rounded_rectangle((x, y, x + fill, y + h), radius=h / 2, fill=fg)

    def horizontal(self):
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
        W, H = 1500, 600
        padding = 60
        cover_size = 480
        title_font = self._font(55, ImageFont)
        artist_font = self._font(45, ImageFont)
        time_font = self._font(25, ImageFont)
        img = self._bg(W, H, Image, ImageFilter, ImageEnhance)
        draw = ImageDraw.Draw(img)
        cover = self._cover(cover_size, 30, Image, ImageDraw)
        img.paste(cover, (padding, (H - cover_size) // 2), cover)
        text_x = padding + cover_size + 60
        text_y_start = 100
        text_w = W - text_x - padding
        wrapper = textwrap.TextWrapper(width=23)
        lines = wrapper.wrap(self.title)
        if len(lines) > 2:
            lines = lines[:2]
            lines[-1] += "..."
        cur_y = text_y_start
        line_h = title_font.getbbox("Ah")[3] + 15
        for line in lines:
            draw.text((text_x, cur_y), line, font=title_font, fill="white")
            cur_y += line_h
        artist = self.artists
        while artist_font.getlength(artist) > text_w and len(artist) > 0:
            artist = artist[:-1]
        if len(artist) < len(self.artists):
            artist += "…"
        draw.text((text_x, cur_y + 10), artist, font=artist_font, fill="#b3b3b3")
        cur_t = f"{(self.progress // 1000 // 60):02}:{(self.progress // 1000 % 60):02}"
        dur_t = f"{(self.duration // 1000 // 60):02}:{(self.duration // 1000 % 60):02}"
        cur_w = time_font.getlength(cur_t)
        dur_w = time_font.getlength(dur_t)
        bar_y = 480
        bar_h = 8
        gap = 25
        draw.text((text_x, bar_y - 12), cur_t, font=time_font, fill="white")
        bar_start = text_x + cur_w + gap
        bar_end = text_x + text_w - dur_w - gap
        bar_w = bar_end - bar_start
        pct = self.progress / self.duration if self.duration > 0 else 0
        self._bar(draw, bar_start, bar_y, bar_w, bar_h, pct)
        draw.text((bar_end + gap, bar_y - 12), dur_t, font=time_font, fill="white")
        out = io.BytesIO()
        img.save(out, format="PNG")
        out.seek(0)
        out.name = "banner.png"
        return out

    def vertical(self):
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
        W, H = 1000, 1500
        padding = 80
        cover_size = 800
        title_font = self._font(60, ImageFont)
        artist_font = self._font(45, ImageFont)
        time_font = self._font(35, ImageFont)
        img = self._bg(W, H, Image, ImageFilter, ImageEnhance)
        draw = ImageDraw.Draw(img)
        cover = self._cover(cover_size, 40, Image, ImageDraw)
        cover_x = (W - cover_size) // 2
        cover_y = 120
        img.paste(cover, (cover_x, cover_y), cover)
        text_y = cover_y + cover_size + 120
        text_w = W - padding * 2
        wrapper = textwrap.TextWrapper(width=23)
        lines = wrapper.wrap(self.title)
        if len(lines) > 2:
            lines = lines[:2]
            lines[-1] += "..."
        cur_y = text_y
        line_h = title_font.getbbox("Ah")[3] + 15
        for line in lines:
            tw = title_font.getlength(line)
            draw.text(((W - tw) / 2, cur_y), line, font=title_font, fill="white")
            cur_y += line_h
        artist = self.artists
        while artist_font.getlength(artist) > text_w and len(artist) > 0:
            artist = artist[:-1]
        if len(artist) < len(self.artists):
            artist += "…"
        aw = artist_font.getlength(artist)
        draw.text(((W - aw) / 2, cur_y + 15), artist, font=artist_font, fill="#b3b3b3")
        bar_y = text_y + 260
        if len(lines) > 1:
            bar_y += 60
        bar_h = 8
        bar_w = W - padding * 2
        pct = self.progress / self.duration if self.duration > 0 else 0
        self._bar(draw, padding, bar_y, bar_w, bar_h, pct)
        cur_t = f"{(self.progress // 1000 // 60):02}:{(self.progress // 1000 % 60):02}"
        dur_t = f"{(self.duration // 1000 // 60):02}:{(self.duration // 1000 % 60):02}"
        draw.text((padding, bar_y + 40), cur_t, font=time_font, fill="white")
        dw = time_font.getlength(dur_t)
        draw.text((W - padding - dw, bar_y + 40), dur_t, font=time_font, fill="white")
        out = io.BytesIO()
        img.save(out, format="PNG")
        out.seek(0)
        out.name = "banner.png"
        return out


def _tokenized(func):
    @functools.wraps(func)
    async def wrapped(self, event, *a, **kw):
        if not self._access_token() or not self.sp:
            await event.reply(self.strings("need_auth"), parse_mode="html")
            return
        return await func(self, event, *a, **kw)
    return wrapped


def _error_handler(func):
    @functools.wraps(func)
    async def wrapped(self, event, *a, **kw):
        try:
            return await func(self, event, *a, **kw)
        except Exception as exc:
            err = str(exc)
            logger.exception("SpotifyKitsune.%s failed", func.__name__)
            if "NO_ACTIVE_DEVICE" in err:
                msg = "No active device"
            elif "PREMIUM_REQUIRED" in err:
                msg = "Spotify Premium is required"
            elif "Insufficient client scope" in err:
                msg = "Insufficient permissions, please re-authenticate"
            else:
                msg = f"{type(exc).__name__}: {err[:120]}"
            with contextlib.suppress(Exception):
                await event.reply(self.strings("err").format(_escape(msg)), parse_mode="html")
    return wrapped


class SpotifyKitsuneModule(KitsuneModule):
    name = "SpotifyKitsune"
    description = "Карточка с играющим треком в Spotify, авто-био, поиск и скачивание. Адаптировал @Mikasu32"
    author = "ke_mods | Kitsune by @Mikasu32"
    version = "1.1.0"
    icon = "🎧"
    category = "media"

    strings_ru = {
        "need_auth": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Сначала выполни</b> <code>.sauth</code><b>.</b>"
        ),
        "err": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Произошла ошибка.</b>\n<code>{}</code>"
        ),
        "on-repeat": (
            "<emoji document_id=5258420634785947640>🔄</emoji> "
            "<b>Включён повтор трека.</b>"
        ),
        "off-repeat": (
            "<emoji document_id=5260687119092817530>🔄</emoji> "
            "<b>Повтор трека отключён.</b>"
        ),
        "skipped": (
            "<emoji document_id=6037622221625626773>➡️</emoji> "
            "<b>Трек пропущен.</b>"
        ),
        "playing": (
            "<emoji document_id=5773626993010546707>▶️</emoji> "
            "<b>Играет...</b>"
        ),
        "back": (
            "<emoji document_id=6039539366177541657>⬅️</emoji> "
            "<b>Переключено на предыдущий трек.</b>"
        ),
        "paused": (
            "<emoji document_id=5774077015388852135>❌</emoji> <b>Пауза.</b>"
        ),
        "restarted": (
            "<emoji document_id=5843596438373667352>✅️</emoji> "
            "<b>Воспроизведение трека с начала...</b>"
        ),
        "liked": (
            "<emoji document_id=5258179403652801593>❤️</emoji> "
            "<b>Текущий трек добавлен в избранное.</b>"
        ),
        "unlike": (
            "<emoji document_id=5774077015388852135>❌</emoji> "
            "<b>Лайк убран.</b>"
        ),
        "already_authed": (
            "<emoji document_id=5778527486270770928>❌</emoji> <b>Уже авторизован.</b>"
        ),
        "authed": (
            "<emoji document_id=5776375003280838798>✅</emoji> "
            "<b>Авторизация успешна.</b>"
        ),
        "deauth": (
            "<emoji document_id=5877341274863832725>🚪</emoji> "
            "<b>Выход из аккаунта выполнен.</b>"
        ),
        "auth": (
            '<emoji document_id=5778168620278354602>🔗</emoji> '
            '<a href="{}">Перейди по ссылке</a>, разреши доступ, затем выполни '
            '<code>.scode https://...</code> с полученной ссылкой.'
        ),
        "no_music": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Сейчас музыка не играет.</b>"
        ),
        "dl_err": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Не удалось скачать трек.</b>"
        ),
        "volume_changed": (
            "<emoji document_id=5890997763331591703>🔊</emoji> "
            "<b>Громкость изменена на {}%.</b>"
        ),
        "volume_invalid": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Громкость должна быть числом от 0 до 100.</b>"
        ),
        "no_volume_arg": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Укажи громкость от 0 до 100.</b>"
        ),
        "searching_tracks": (
            "<emoji document_id=5841359499146825803>🕔</emoji> "
            "<b>Ищу треки по запросу <i>{}</i>...</b>"
        ),
        "no_search_query": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Укажи поисковый запрос.</b>"
        ),
        "no_tracks_found": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>По запросу <i>{}</i> ничего не найдено.</b>"
        ),
        "search_results_inline": (
            "<emoji document_id=5776375003280838798>✅</emoji> "
            "<b>Найдено {count} результатов по запросу <i>{query}</i>.</b>\n"
            "<b>Выбери трек:</b>"
        ),
        "downloading_search_track": (
            "<emoji document_id=5841359499146825803>🕔</emoji> "
            "<b>Скачиваю {}...</b>"
        ),
        "download_success": (
            "<emoji document_id=5776375003280838798>✅</emoji> "
            "<b>Трек {} - {} успешно скачан.</b>"
        ),
        "device_list": (
            "<emoji document_id=5956561916573782596>📄</emoji> "
            "<b>Доступные устройства:</b>\n{}"
        ),
        "no_devices_found": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Устройства не найдены.</b>"
        ),
        "device_changed": (
            "<emoji document_id=5776375003280838798>✅</emoji> "
            "<b>Воспроизведение переключено на {}.</b>"
        ),
        "invalid_device_id": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Некорректный ID устройства. Используй <code>.sdevice</code>.</b>"
        ),
        "autobio": (
            "<emoji document_id=6319076999105087378>🎧</emoji> "
            "<b>Авто-био Spotify {}</b>"
        ),
        "no_ytdlp": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>yt-dlp не найден. Установи его: "
            "<code>{}sh pip install yt-dlp</code></b>"
        ),
        "snowt_failed": (
            "\n\n<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Не удалось скачать.</b>"
        ),
        "uploading_banner": (
            "\n\n<emoji document_id=5841359499146825803>🕔</emoji> "
            "<i>Готовлю баннер...</i>"
        ),
        "downloading_track": (
            "\n\n<emoji document_id=5841359499146825803>🕔</emoji> "
            "<i>Скачиваю трек...</i>"
        ),
        "no_playlists": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Плейлисты не найдены.</b>"
        ),
        "playlists_list": (
            "<emoji document_id=5956561916573782596>📄</emoji> "
            "<b>Твои плейлисты:</b>\n\n{}"
        ),
        "added_to_playlist": (
            "<emoji document_id=5776375003280838798>✅</emoji> "
            "<b>Трек {} добавлен в {}.</b>"
        ),
        "removed_from_playlist": (
            "<emoji document_id=5776375003280838798>✅</emoji> "
            "<b>Трек {} удалён из {}.</b>"
        ),
        "invalid_playlist_index": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Некорректный номер плейлиста.</b>"
        ),
        "no_cached_playlists": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Сначала выполни <code>.splaylists</code>.</b>"
        ),
        "playlist_created": (
            "<emoji document_id=5776375003280838798>✅</emoji> "
            "<b>Плейлист {} создан.</b>"
        ),
        "playlist_deleted": (
            "<emoji document_id=5776375003280838798>✅</emoji> "
            "<b>Плейлист {} удалён.</b>"
        ),
        "no_playlist_name": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Укажи название плейлиста.</b>"
        ),
        "no_spotipy": (
            "<emoji document_id=5778527486270770928>❌</emoji> "
            "<b>Не установлены зависимости.</b>\n"
            "<code>{prefix}sh pip install spotipy pillow requests</code>"
        ),
    }

    _DB_KEY = "kitsune.spotify"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "show_banner",
                True,
                "Показывать баннер с треком при .snow",
                validator=Boolean(),
            ),
            ConfigValue(
                "custom_text",
                (
                    "<emoji document_id=6007938409857815902>🎧</emoji> "
                    "<b>Сейчас играет:</b> {track} — {artists}\n"
                    "<emoji document_id=5877465816030515018>🔗</emoji> "
                    "<b><a href='{songlink}'>song.link</a></b>"
                ),
                "Кастомный текст. Плейсхолдеры: {track}, {artists}, {album}, "
                "{playlist}, {playlist_owner}, {spotify_url}, {songlink}, "
                "{progress}, {duration}, {device}.",
                validator=String(max_len=2000),
            ),
            ConfigValue(
                "font",
                "https://raw.githubusercontent.com/kamekuro/assets/master/fonts/Onest-Bold.ttf",
                "URL .ttf-шрифта для баннера",
                validator=String(max_len=300),
            ),
            ConfigValue(
                "auto_bio_template",
                "🎧 {title} - {artist}",
                "Шаблон авто-био. Плейсхолдеры: {artist}, {title}",
                validator=String(max_len=200),
            ),
            ConfigValue(
                "ytdlp_path",
                "yt-dlp",
                "Путь к yt-dlp бинарю",
                validator=String(max_len=300),
            ),
            ConfigValue(
                "cookies_path",
                "",
                "Путь к cookies для yt-dlp",
                validator=String(max_len=300),
            ),
            ConfigValue(
                "banner_version",
                "horizontal",
                "Тип баннера: horizontal или vertical",
                validator=Choice(["horizontal", "vertical"]),
            ),
            ConfigValue(
                "blur_intensity",
                40,
                "Сила размытия фона баннера",
                validator=Integer(minimum=0, maximum=200),
            ),
            ConfigValue(
                "bio_update_delay",
                30,
                "Интервал обновления авто-био (секунд)",
                validator=Integer(minimum=10, maximum=600),
            ),
            ConfigValue(
                "client_id",
                _DEFAULT_CLIENT_ID,
                "Spotify client_id (можно заменить на свой)",
                validator=String(max_len=200),
            ),
            ConfigValue(
                "client_secret",
                _DEFAULT_CLIENT_SECRET,
                "Spotify client_secret (можно заменить на свой)",
                validator=String(max_len=200),
            ),
            ConfigValue(
                "redirect_uri",
                _DEFAULT_REDIRECT_URI,
                "Redirect URI (должен совпадать с настройками Spotify-приложения)",
                validator=String(max_len=300),
            ),
        )
        self.sp = None
        self.sp_auth = None
        self._sp_store: dict[int, list] = {}
        self.bio_task: typing.Optional[asyncio.Task] = None
        self._font_cache: typing.Optional[bytes] = None
        self._cover_cache: dict[str, bytes] = {}

    async def on_load(self) -> None:
        self._build_sp_auth()
        if not self._init_spotify_client():
            await self._set("acs_tkn", None)
        if self._get("autobio", False) and self.sp:
            await self._start_autobio()

    async def on_unload(self) -> None:
        task = self.bio_task
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task
        self.bio_task = None

    def _build_sp_auth(self) -> None:
        try:
            import spotipy
            self.sp_auth = spotipy.oauth2.SpotifyOAuth(
                client_id=self.config["client_id"],
                client_secret=self.config["client_secret"],
                redirect_uri=self.config["redirect_uri"],
                scope=_SCOPE,
            )
        except ImportError:
            self.sp_auth = None

    def _get(self, key: str, default=None):
        return self.db.get(self._DB_KEY, key, default)

    async def _set(self, key: str, value) -> None:
        await self.db.set(self._DB_KEY, key, value)

    def _access_token(self):
        tok = self._get("acs_tkn") or {}
        return tok.get("access_token") if isinstance(tok, dict) else None

    def _init_spotify_client(self) -> bool:
        try:
            import spotipy
        except ImportError:
            self.sp = None
            return False
        token = self._access_token()
        if not token:
            self.sp = None
            return False
        try:
            self.sp = spotipy.Spotify(auth=token)
            return True
        except Exception:
            self.sp = None
            return False

    def _check_deps(self, event) -> bool:
        try:
            import spotipy  # noqa
            from PIL import Image  # noqa
            import requests  # noqa
            return True
        except ImportError:
            dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
            prefix = dispatcher._prefix if dispatcher else "."
            asyncio.ensure_future(
                event.reply(
                    self.strings("no_spotipy").format(prefix=prefix),
                    parse_mode="html",
                )
            )
            return False

    @command("sauth", required=OWNER)
    async def sauth_cmd(self, event) -> None:
        """Начать авторизацию Spotify — получишь ссылку для входа (делается один раз)"""
        if not self._check_deps(event):
            return
        if self._access_token() and not self.sp:
            await event.reply(self.strings("already_authed"), parse_mode="html")
            return
        if self.sp_auth is None:
            self._build_sp_auth()
        if self.sp_auth is None:
            await event.reply(self.strings("no_spotipy").format(prefix=self._prefix()), parse_mode="html")
            return
        url = self.sp_auth.get_authorize_url()
        await event.reply(self.strings("auth").format(url), parse_mode="html", link_preview=False)

    @command("scode", required=OWNER)
    async def scode_cmd(self, event) -> None:
        """Вставить ссылку после авторизации Spotify. Пример: .scode https://..."""
        if not self._check_deps(event):
            return
        args = self.get_args(event).strip()
        if not args:
            await event.reply("❌ Укажи ссылку.", parse_mode="html")
            return
        url = args.split()[0]
        try:
            if self.sp_auth is None:
                self._build_sp_auth()
            code = self.sp_auth.parse_auth_response_url(url)
            token = await asyncio.to_thread(
                self.sp_auth.get_access_token, code, True, False
            )
            await self._set("acs_tkn", token)
            await self._set("NextRefresh", time.time() + 45 * 60)
            self._init_spotify_client()
            await event.reply(self.strings("authed"), parse_mode="html")
        except Exception as exc:
            await event.reply(
                self.strings("err").format(_escape(str(exc)[:200])),
                parse_mode="html",
            )

    @command("unauth", required=OWNER)
    async def unauth_cmd(self, event) -> None:
        """Выйти из аккаунта Spotify и сбросить токен"""
        await self._set("acs_tkn", None)
        await self._set("NextRefresh", None)
        self.sp = None
        await event.reply(self.strings("deauth"), parse_mode="html")

    @command("stokrefresh", required=OWNER, aliases=["stokr"])
    @_tokenized
    async def stokrefresh_cmd(self, event) -> None:
        """Вручную обновить токен авторизации Spotify. Псевдоним: .stokr"""
        await self._refresh_token_safely()
        await event.reply(self.strings("authed"), parse_mode="html")

    async def _refresh_token_safely(self) -> bool:
        tok = self._get("acs_tkn") or {}
        rt = tok.get("refresh_token")
        if not rt or self.sp_auth is None:
            return False
        try:
            new_tok = await asyncio.to_thread(self.sp_auth.refresh_access_token, rt)
            await self._set("acs_tkn", new_tok)
            await self._set("NextRefresh", time.time() + 45 * 60)
            self._init_spotify_client()
            return True
        except Exception as exc:
            logger.warning("Spotify refresh failed: %s", exc)
            return False

    @command("snext", required=OWNER)
    @_error_handler
    @_tokenized
    async def snext_cmd(self, event) -> None:
        """Пропустить текущий трек вперёд"""
        await asyncio.to_thread(self.sp.next_track)
        await event.reply(self.strings("skipped"), parse_mode="html")

    @command("sback", required=OWNER)
    @_error_handler
    @_tokenized
    async def sback_cmd(self, event) -> None:
        """Вернуться к предыдущему треку"""
        await asyncio.to_thread(self.sp.previous_track)
        await event.reply(self.strings("back"), parse_mode="html")

    @command("spause", required=OWNER)
    @_error_handler
    @_tokenized
    async def spause_cmd(self, event) -> None:
        """Поставить воспроизведение на паузу"""
        await asyncio.to_thread(self.sp.pause_playback)
        await event.reply(self.strings("paused"), parse_mode="html")

    @command("sresume", required=OWNER)
    @_error_handler
    @_tokenized
    async def sresume_cmd(self, event) -> None:
        """Возобновить воспроизведение"""
        await asyncio.to_thread(self.sp.start_playback)
        await event.reply(self.strings("playing"), parse_mode="html")

    @command("sbegin", required=OWNER)
    @_error_handler
    @_tokenized
    async def sbegin_cmd(self, event) -> None:
        """Перемотать текущий трек на начало"""
        await asyncio.to_thread(self.sp.seek_track, 0)
        await event.reply(self.strings("restarted"), parse_mode="html")

    @command("srepeat", required=OWNER)
    @_error_handler
    @_tokenized
    async def srepeat_cmd(self, event) -> None:
        """Включить повтор текущего трека"""
        await asyncio.to_thread(self.sp.repeat, "track")
        await event.reply(self.strings("on-repeat"), parse_mode="html")

    @command("sderepeat", required=OWNER)
    @_error_handler
    @_tokenized
    async def sderepeat_cmd(self, event) -> None:
        """Выключить повтор текущего трека"""
        await asyncio.to_thread(self.sp.repeat, "context")
        await event.reply(self.strings("off-repeat"), parse_mode="html")

    @command("slike", required=OWNER)
    @_error_handler
    @_tokenized
    async def slike_cmd(self, event) -> None:
        """Лайкнуть текущий трек (добавить в избранное)"""
        cur = await asyncio.to_thread(self.sp.current_playback)
        if not cur or not cur.get("item"):
            await event.reply(self.strings("no_music"), parse_mode="html")
            return
        await asyncio.to_thread(
            self.sp.current_user_saved_tracks_add, [cur["item"]["id"]]
        )
        await event.reply(self.strings("liked"), parse_mode="html")

    @command("sunlike", required=OWNER)
    @_error_handler
    @_tokenized
    async def sunlike_cmd(self, event) -> None:
        """Убрать лайк с текущего трека"""
        cur = await asyncio.to_thread(self.sp.current_playback)
        if not cur or not cur.get("item"):
            await event.reply(self.strings("no_music"), parse_mode="html")
            return
        await asyncio.to_thread(
            self.sp.current_user_saved_tracks_delete, [cur["item"]["id"]]
        )
        await event.reply(self.strings("unlike"), parse_mode="html")

    @command("svolume", required=OWNER, aliases=["sv"])
    @_error_handler
    @_tokenized
    async def svolume_cmd(self, event) -> None:
        """Установить громкость от 0 до 100. Пример: .svolume 75 Псевдоним: .sv"""
        args = self.get_args(event).strip()
        if not args:
            await event.reply(self.strings("no_volume_arg"), parse_mode="html")
            return
        try:
            vol = int(args)
        except ValueError:
            await event.reply(self.strings("volume_invalid"), parse_mode="html")
            return
        if not 0 <= vol <= 100:
            await event.reply(self.strings("volume_invalid"), parse_mode="html")
            return
        await asyncio.to_thread(self.sp.volume, vol)
        await event.reply(self.strings("volume_changed").format(vol), parse_mode="html")

    @command("sdevice", required=OWNER, aliases=["sd"])
    @_error_handler
    @_tokenized
    async def sdevice_cmd(self, event) -> None:
        """Без аргументов — список устройств. С номером — переключить: .sdevice 1 Псевдоним: .sd"""
        args = self.get_args(event).strip()
        devices = (await asyncio.to_thread(self.sp.devices)).get("devices") or []
        if not args:
            if not devices:
                await event.reply(self.strings("no_devices_found"), parse_mode="html")
                return
            lines = []
            for i, d in enumerate(devices, start=1):
                active = "(active)" if d.get("is_active") else ""
                lines.append(
                    f"<b>{i}.</b> {_escape(d.get('name', '?'))} "
                    f"({_escape(d.get('type', '?'))}) {active}"
                )
            await event.reply(
                self.strings("device_list").format("\n".join(lines)),
                parse_mode="html",
            )
            return
        device_id = None
        device_name = ""
        try:
            n = int(args)
            if 1 <= n <= len(devices):
                device_id = devices[n - 1]["id"]
                device_name = devices[n - 1]["name"]
        except ValueError:
            for d in devices:
                if d.get("id") == args:
                    device_id = d["id"]
                    device_name = d["name"]
                    break
        if not device_id:
            await event.reply(self.strings("invalid_device_id"), parse_mode="html")
            return
        await asyncio.to_thread(self.sp.transfer_playback, device_id)
        await event.reply(
            self.strings("device_changed").format(_escape(device_name)),
            parse_mode="html",
        )

    @command("splaylists", required=OWNER, aliases=["spls"])
    @_error_handler
    @_tokenized
    async def splaylists_cmd(self, event) -> None:
        """Показать список твоих плейлистов Spotify. Псевдоним: .spls"""
        me = await asyncio.to_thread(self.sp.me)
        user_id = me["id"]
        playlists = await asyncio.to_thread(self.sp.current_user_playlists)
        editable = [
            p for p in (playlists.get("items") or [])
            if (p.get("owner") or {}).get("id") == user_id or p.get("collaborative")
        ]
        await self._set("last_playlists", editable)
        if not editable:
            await event.reply(self.strings("no_playlists"), parse_mode="html")
            return
        lines = []
        for i, p in enumerate(editable, start=1):
            name = _escape(p.get("name") or "?")
            url = (p.get("external_urls") or {}).get("spotify", "#")
            count = (p.get("tracks") or {}).get("total", 0)
            lines.append(f"<b>{i}.</b> <a href='{url}'>{name}</a> ({count} tracks)")
        await event.reply(
            self.strings("playlists_list").format("\n".join(lines)),
            parse_mode="html",
            link_preview=False,
        )

    @command("splaylistadd", required=OWNER, aliases=["spla"])
    @_error_handler
    @_tokenized
    async def splaylistadd_cmd(self, event) -> None:
        """Добавить текущий трек в плейлист по номеру из .splaylists. Пример: .splaylistadd 2 Псевдоним: .spla"""
        await self._playlist_modify(event, action="add")

    @command("splaylistrem", required=OWNER, aliases=["splr"])
    @_error_handler
    @_tokenized
    async def splaylistrem_cmd(self, event) -> None:
        """Удалить текущий трек из плейлиста по номеру. Пример: .splaylistrem 2 Псевдоним: .splr"""
        await self._playlist_modify(event, action="rem")

    async def _playlist_modify(self, event, action: str) -> None:
        args = self.get_args(event).strip()
        if not args.isdigit():
            await event.reply(self.strings("invalid_playlist_index"), parse_mode="html")
            return
        idx = int(args) - 1
        playlists = self._get("last_playlists", [])
        if not playlists:
            await event.reply(self.strings("no_cached_playlists"), parse_mode="html")
            return
        if not 0 <= idx < len(playlists):
            await event.reply(self.strings("invalid_playlist_index"), parse_mode="html")
            return
        cur = await asyncio.to_thread(self.sp.current_playback)
        if not cur or not cur.get("item"):
            await event.reply(self.strings("no_music"), parse_mode="html")
            return
        track_uri = cur["item"]["uri"]
        track_name = cur["item"]["name"]
        artists = ", ".join(a["name"] for a in cur["item"]["artists"])
        full = f"{artists} - {track_name}"
        pl_id = playlists[idx]["id"]
        pl_name = playlists[idx]["name"]
        if action == "add":
            await asyncio.to_thread(self.sp.playlist_add_items, pl_id, [track_uri])
            await event.reply(
                self.strings("added_to_playlist").format(_escape(full), _escape(pl_name)),
                parse_mode="html",
            )
        else:
            await asyncio.to_thread(
                self.sp.playlist_remove_all_occurrences_of_items, pl_id, [track_uri]
            )
            await event.reply(
                self.strings("removed_from_playlist").format(_escape(full), _escape(pl_name)),
                parse_mode="html",
            )

    @command("splaylistcreate", required=OWNER, aliases=["splc"])
    @_error_handler
    @_tokenized
    async def splaylistcreate_cmd(self, event) -> None:
        """Создать новый плейлист. Пример: .splaylistcreate Мой плейлист Псевдоним: .splc"""
        name = self.get_args(event).strip()
        if not name:
            await event.reply(self.strings("no_playlist_name"), parse_mode="html")
            return
        me = await asyncio.to_thread(self.sp.me)
        await asyncio.to_thread(self.sp.user_playlist_create, me["id"], name)
        await event.reply(
            self.strings("playlist_created").format(_escape(name)),
            parse_mode="html",
        )

    @command("splaylistdelete", required=OWNER, aliases=["spld"])
    @_error_handler
    @_tokenized
    async def splaylistdelete_cmd(self, event) -> None:
        """Удалить плейлист по номеру из .splaylists. Пример: .splaylistdelete 3 Псевдоним: .spld"""
        args = self.get_args(event).strip()
        if not args.isdigit():
            await event.reply(self.strings("invalid_playlist_index"), parse_mode="html")
            return
        idx = int(args) - 1
        playlists = self._get("last_playlists", [])
        if not playlists or not 0 <= idx < len(playlists):
            await event.reply(self.strings("invalid_playlist_index"), parse_mode="html")
            return
        pl_id = playlists[idx]["id"]
        pl_name = playlists[idx]["name"]
        await asyncio.to_thread(self.sp.current_user_unfollow_playlist, pl_id)
        await event.reply(
            self.strings("playlist_deleted").format(_escape(pl_name)),
            parse_mode="html",
        )

    @command("sbio", required=OWNER)
    @_tokenized
    async def sbio_cmd(self, event) -> None:
        """Включить или выключить авто-обновление биографии профиля с текущим треком"""
        state = not bool(self._get("autobio", False))
        await self._set("autobio", state)
        if state:
            try:
                full = await self.client(GetFullUserRequest("me"))
                about = getattr(full.full_user, "about", "") or ""
            except Exception:
                about = ""
            await self._set("original_bio", about)
            await self._set("last_bio", "")
            await self._start_autobio()
        else:
            task = self.bio_task
            if task and not task.done():
                task.cancel()
            self.bio_task = None
            await self._restore_original_bio()
        await event.reply(
            self.strings("autobio").format("on" if state else "off"),
            parse_mode="html",
        )

    async def _start_autobio(self) -> None:
        task = self.bio_task
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task
        self.bio_task = asyncio.create_task(self._autobio_loop())

    async def _autobio_loop(self) -> None:
        while self._get("autobio", False):
            try:
                if not self.sp and not self._init_spotify_client():
                    await self._set("autobio", False)
                    await self._restore_original_bio()
                    break
                cur = await asyncio.to_thread(self.sp.current_playback)
                if not cur or not cur.get("is_playing"):
                    if self._get("last_bio", ""):
                        await self._restore_original_bio(clear_original=False)
                    await asyncio.sleep(10)
                    continue
                item = cur.get("item") or {}
                title = item.get("name") or ""
                artists = ", ".join(
                    a.get("name", "") for a in item.get("artists", []) if a.get("name")
                )
                if not title:
                    await asyncio.sleep(10)
                    continue
                bio = self.config["auto_bio_template"].format(
                    title=title, artist=artists or "Unknown Artist"
                ).strip()
                if len(bio) > 70:
                    bio = bio[:69] + "…"
                if bio != self._get("last_bio", ""):
                    await self.client(UpdateProfileRequest(about=bio))
                    await self._set("last_bio", bio)
            except FloodWaitError as e:
                await asyncio.sleep(getattr(e, "seconds", 30) + 1)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("autobio error: %s", exc)
            await asyncio.sleep(int(self.config["bio_update_delay"] or 30))

    async def _restore_original_bio(
        self, *, clear_original: bool = True, clear_last: bool = True
    ) -> None:
        original = self._get("original_bio", None)
        if original is None:
            return
        with contextlib.suppress(Exception):
            await self.client(UpdateProfileRequest(about=original))
        if clear_original:
            await self._set("original_bio", None)
        if clear_last:
            await self._set("last_bio", "")

    def _format_track_text(self, cur: dict) -> tuple[str, dict]:
        item = cur["item"]
        track = item["name"]
        track_id = item["id"]
        artists = ", ".join(a["name"] for a in item["artists"])
        album_name = item.get("album", {}).get("name", "Unknown Album")
        duration_ms = item.get("duration_ms", 0) or 0
        progress_ms = cur.get("progress_ms", 0) or 0
        duration = f"{duration_ms // 1000 // 60}:{duration_ms // 1000 % 60:02}"
        progress = f"{progress_ms // 1000 // 60}:{progress_ms // 1000 % 60:02}"
        spotify_url = f"https://open.spotify.com/track/{track_id}"
        songlink = f"https://song.link/s/{track_id}"
        try:
            dev = cur.get("device") or {}
            device = (
                (dev.get("name", "") + " " + dev.get("type", "").lower())
                .replace("computer", "")
                .replace("smartphone", "")
                .strip()
            )
        except Exception:
            device = ""
        playlist_name = ""
        playlist_owner = ""
        try:
            ctx = cur.get("context") or {}
            ctx_uri = ctx.get("uri") or ""
            if "playlist" in ctx_uri and self.sp is not None:
                pid = ctx_uri.split(":")[-1]
                pl = self.sp.playlist(pid)
                playlist_name = pl.get("name") or ""
                owner = pl.get("owner") or {}
                if owner.get("display_name"):
                    playlist_owner = (
                        f'<a href="https://open.spotify.com/user/{owner.get("id", "")}">'
                        f'{_escape(owner["display_name"])}</a>'
                    )
        except Exception:
            pass
        sdata = {
            "track": _escape(track),
            "artists": _escape(artists),
            "album": _escape(album_name),
            "duration": duration,
            "progress": progress,
            "device": _escape(device),
            "spotify_url": spotify_url,
            "songlink": songlink,
            "playlist": _escape(playlist_name),
            "playlist_owner": playlist_owner,
        }
        try:
            text = self.config["custom_text"].format(**sdata)
        except KeyError:
            text = (
                f"🎧 <b>Сейчас играет:</b> {_escape(track)} — {_escape(artists)}\n"
                f"🔗 <a href='{songlink}'>song.link</a>"
            )
        return text, {
            **sdata,
            "duration_ms": duration_ms,
            "progress_ms": progress_ms,
            "track": track,
            "artists": artists,
        }

    def _font_bytes(self) -> bytes:
        if self._font_cache:
            return self._font_cache
        import requests
        try:
            r = requests.get(self.config["font"], timeout=15)
            r.raise_for_status()
            self._font_cache = r.content
            return self._font_cache
        except Exception:
            return b""

    def _cover_bytes(self, url: str) -> bytes:
        if not url:
            return b""
        if url in self._cover_cache:
            return self._cover_cache[url]
        import requests
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            self._cover_cache[url] = r.content
            if len(self._cover_cache) > 30:
                self._cover_cache.pop(next(iter(self._cover_cache)))
            return r.content
        except Exception:
            return b""

    @command("snow", required=OWNER, aliases=["sn"])
    @_error_handler
    @_tokenized
    async def snow_cmd(self, event) -> None:
        """Показать карточку с текущим играющим треком. Псевдоним: .sn"""
        cur = await asyncio.to_thread(self.sp.current_playback)
        if not cur or not cur.get("is_playing", False) or not cur.get("item"):
            await event.reply(self.strings("no_music"), parse_mode="html")
            return
        text, meta = self._format_track_text(cur)
        if not self.config["show_banner"]:
            await event.reply(text, parse_mode="html", link_preview=False)
            return
        cover_url = (
            cur.get("item", {}).get("album", {}).get("images", [{}])[0].get("url", "")
        )
        tmp = await event.reply(
            text + self.strings("uploading_banner"),
            parse_mode="html",
            link_preview=False,
        )
        try:
            cover_bytes = await asyncio.to_thread(self._cover_bytes, cover_url)
            font_bytes = await asyncio.to_thread(self._font_bytes)
            if not cover_bytes or not font_bytes:
                await tmp.edit(text, parse_mode="html", link_preview=False)
                return
            banner = _Banners(
                title=meta["track"],
                artists=meta["artists"],
                duration=meta["duration_ms"],
                progress=meta["progress_ms"],
                track_cover=cover_bytes,
                font_bytes=font_bytes,
                blur=int(self.config["blur_intensity"] or 0),
            )
            if self.config["banner_version"] == "vertical":
                file = await asyncio.to_thread(banner.vertical)
            else:
                file = await asyncio.to_thread(banner.horizontal)
            await self.client.send_file(
                event.chat_id,
                file,
                caption=text,
                parse_mode="html",
                reply_to=getattr(event.message, "reply_to_msg_id", None) or event.message.id,
            )
            with contextlib.suppress(Exception):
                await tmp.delete()
        except Exception:
            logger.exception("snow banner failed")
            with contextlib.suppress(Exception):
                await tmp.edit(text, parse_mode="html", link_preview=False)

    @command("snowt", required=OWNER, aliases=["snt"])
    @_error_handler
    @_tokenized
    async def snowt_cmd(self, event) -> None:
        """Показать карточку трека и скачать его как MP3. Псевдоним: .snt"""
        cur = await asyncio.to_thread(self.sp.current_playback)
        if not cur or not cur.get("is_playing", False) or not cur.get("item"):
            await event.reply(self.strings("no_music"), parse_mode="html")
            return
        text, meta = self._format_track_text(cur)
        msg = await event.reply(
            text + self.strings("downloading_track"),
            parse_mode="html",
            link_preview=False,
        )
        ok = await self._download_track(
            event.chat_id,
            f"{meta['artists']} {meta['track']}",
            caption=text,
            track_name=meta["track"],
            artists=meta["artists"],
            reply_to=getattr(event.message, "reply_to_msg_id", None) or event.message.id,
        )
        if ok:
            with contextlib.suppress(Exception):
                await msg.delete()
        else:
            with contextlib.suppress(Exception):
                await msg.edit(text + self.strings("snowt_failed"), parse_mode="html")

    @command("ssearch", required=OWNER, aliases=["sq"])
    @_error_handler
    @_tokenized
    async def ssearch_cmd(self, event) -> None:
        """Найти треки по названию и скачать выбранный. Пример: .ssearch Imagine Dragons Believer Псевдоним: .sq"""
        args = self.get_args(event).strip()
        if not args:
            await event.reply(self.strings("no_search_query"), parse_mode="html")
            return
        last = self._get("last_search_results", []) or []
        if args.isdigit() and last:
            n = int(args)
            if 1 <= n <= len(last):
                t = last[n - 1]
                tname = t.get("name", "Unknown")
                artists = ", ".join(
                    a.get("name", "") for a in t.get("artists", []) if a.get("name")
                ) or "Unknown Artist"
                msg = await event.reply(
                    self.strings("downloading_search_track").format(_escape(tname)),
                    parse_mode="html",
                )
                ok = await self._download_track(
                    event.chat_id,
                    f"{artists} {tname}",
                    track_name=tname,
                    artists=artists,
                    reply_to=getattr(event.message, "reply_to_msg_id", None) or event.message.id,
                )
                if ok:
                    with contextlib.suppress(Exception):
                        await msg.delete()
                await self._set("last_search_results", [])
                return

        await event.reply(
            self.strings("searching_tracks").format(_escape(args)),
            parse_mode="html",
        )

        results = await asyncio.to_thread(
            self.sp.search, q=args, limit=5, type="track"
        )
        items = ((results or {}).get("tracks") or {}).get("items") or []
        if not items:
            await event.reply(
                self.strings("no_tracks_found").format(_escape(args)),
                parse_mode="html",
            )
            return
        await self._set("last_search_results", items)
        text = self.strings("search_results_inline").format(
            count=len(items), query=_escape(args)
        )
        markup = self._build_search_keyboard(items, event)
        inline = getattr(self.client, "inline", None)
        if inline is not None and hasattr(inline, "form"):
            try:
                await inline.form(text, message=event.message, reply_markup=markup)
                return
            except Exception:
                logger.exception("Spotify ssearch inline form failed, fallback to text")
        lines = [text, ""]
        prefix = self._prefix()
        for i, t in enumerate(items, start=1):
            tname = t.get("name", "Unknown")
            arts = ", ".join(
                a.get("name", "") for a in t.get("artists", []) if a.get("name")
            )
            lines.append(f"<b>{i}.</b> {_escape(tname)} — {_escape(arts)}")
        lines.append("")
        lines.append(f"Скачать: <code>{prefix}ssearch &lt;номер&gt;</code>")
        await event.reply("\n".join(lines), parse_mode="html", link_preview=False)

    def _build_search_keyboard(self, tracks: list, event) -> list:
        keyboard = []
        chat_id = event.chat_id
        reply_to = getattr(event.message, "reply_to_msg_id", None) or event.message.id
        for t in tracks:
            tname = t.get("name", "Unknown")
            arts = ", ".join(
                a.get("name", "") for a in t.get("artists", []) if a.get("name")
            ) or "Unknown Artist"
            label = _short(f"{tname} — {arts}")
            keyboard.append([{
                "text": label,
                "callback": self._inline_download_track,
                "args": (tname, arts, chat_id, reply_to),
            }])
        return keyboard

    async def _inline_download_track(self, call, track_name, artists, chat_id, reply_to):
        with contextlib.suppress(Exception):
            await call.answer()
        with contextlib.suppress(Exception):
            await call.edit(
                self.strings("downloading_search_track").format(_escape(track_name)).lstrip(),
                reply_markup=None,
            )
        ok = await self._download_track(
            chat_id,
            f"{artists} {track_name}",
            track_name=track_name,
            artists=artists,
            reply_to=reply_to,
        )
        if ok:
            with contextlib.suppress(Exception):
                await call.delete()
        else:
            with contextlib.suppress(Exception):
                await call.edit(self.strings("dl_err"), reply_markup=None)

    def _prefix(self) -> str:
        dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
        return dispatcher._prefix if dispatcher else "."

    async def _download_track(
        self,
        chat_id,
        query: str,
        *,
        caption: typing.Optional[str] = None,
        track_name: typing.Optional[str] = None,
        artists: typing.Optional[str] = None,
        reply_to: typing.Optional[int] = None,
    ) -> bool:
        ytdlp_path = (self.config["ytdlp_path"] or "yt-dlp").strip() or "yt-dlp"
        if not shutil.which(ytdlp_path) and not os.path.isfile(ytdlp_path):
            with contextlib.suppress(Exception):
                await self.client.send_message(
                    chat_id,
                    self.strings("no_ytdlp").format(self._prefix()),
                    parse_mode="html",
                )
            return False

        if caption is None:
            safe_t = _escape(track_name or "Unknown")
            safe_a = _escape(artists or "Unknown Artist")
            caption = self.strings("download_success").format(safe_t, safe_a)

        import tempfile
        with tempfile.TemporaryDirectory(prefix="kitsune_spotify_") as dl_dir:
            squery = query.replace('"', "").replace("'", "")
            cookies = (self.config["cookies_path"] or "").strip()
            cmd_parts = [
                ytdlp_path, "-x",
                "--audio-format", "mp3",
                "--add-metadata",
                "--audio-quality", "0",
                "-o", os.path.join(dl_dir, "%(title)s [%(id)s].%(ext)s"),
            ]
            if cookies:
                cmd_parts += ["--cookies", cookies]
            cmd_parts.append(f"ytsearch1:{squery}")
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd_parts,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode:
                    err = (stderr.decode(errors="ignore") if stderr else "")[-300:]
                    logger.warning("Spotify yt-dlp failed: %s", err)
            except FileNotFoundError:
                with contextlib.suppress(Exception):
                    await self.client.send_message(
                        chat_id,
                        self.strings("no_ytdlp").format(self._prefix()),
                        parse_mode="html",
                    )
                return False
            except Exception:
                logger.exception("Spotify yt-dlp launch failed")
                return False

            files = [f for f in os.listdir(dl_dir) if f.endswith(".mp3")]
            if not files:
                return False
            target_file = os.path.join(dl_dir, files[0])
            try:
                await self.client.send_file(
                    chat_id,
                    target_file,
                    caption=caption,
                    parse_mode="html",
                    reply_to=reply_to,
                    voice_note=False,
                )
                return True
            except Exception:
                logger.exception("Spotify send_file failed")
                return False

    async def _watcher_token_refresh(self, event) -> None:
        if not self.sp:
            return
        nxt = self._get("NextRefresh") or 0
        try:
            if not nxt or float(nxt) < time.time():
                ok = await self._refresh_token_safely()
                if not ok:
                    await self._set("NextRefresh", time.time() + 300)
        except Exception:
            logger.exception("Spotify watcher refresh failed")

    @watcher(lambda message: bool(getattr(message, "out", False)))
    async def spotify_token_watcher(self, event) -> None:
        try:
            await self._watcher_token_refresh(event)
        except Exception:
            logger.exception("Spotify watcher failed")
