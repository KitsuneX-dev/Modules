"""
Hentai — случайные loli / fem / sfw / furry / nsfw медиа для Kitsune UserBot.

Команды:
    .loli   — случайное loli (через @ferganteusbot /lh)
    .fem    — случайное femboy (через @ferganteusbot /fm)
    .sfw    — случайное SFW   (через @ferganteusbot /rc)
    .lolic  — случайное loli из канала-источника
    .furry  — случайное furry из канала-источника
    .nsfw   — случайное NSFW из канала-источника

Источники-каналы и диапазоны настраиваются через .cfg hentai ...
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import random
import typing

from telethon import functions

from ..core.loader import KitsuneModule, command, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..validators import String, Integer

logger = logging.getLogger(__name__)

BOT_USERNAME = "@ferganteusbot"
CONV_TIMEOUT = 30.0      # ожидание ответа от бота-источника
RESP_TIMEOUT = 30.0


class LoliHentaiModule(KitsuneModule):
    name        = "hentai"
    description = "Hentai медиа: loli / fem / sfw / furry / nsfw"
    author      = "@mqone + @codrago (адапт. для Kitsune)"
    version     = "3.0"
    icon        = "🔞"
    category    = "fun"

    strings_ru = {
        "loading":      "🔴 <b>Загружаю медиа...</b>",
        "loading_loli": "⏳ <b>Загрузка loli, ожидайте...</b>",
        "error_bot":    "❌ <b>Не удалось получить медиа.</b>\nРазблокируй и запусти <b>@ferganteusbot</b> (<code>/start</code>).",
        "timeout":      "⏰ <b>Бот-источник не ответил вовремя.</b> Попробуй ещё раз.",
        "not_found":    "❌ <b>Ничего не найдено.</b>",
        "no_channel":   "❌ <b>Источник не настроен/недоступен.</b>\nЗадай канал: <code>.cfg hentai {cfg}</code>",
        "error":        "❌ <b>Ошибка:</b> <code>{err}</code>",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "lolic_channel",
                default="hdjrkdjrkdkd",
                doc="Канал-источник для .lolic (username или ID).",
                validator=String(max_len=128),
            ),
            ConfigValue(
                "lolic_range",
                default=850,
                doc="Глубина случайной выборки для .lolic (кол-во сообщений).",
                validator=Integer(minimum=2, maximum=1_000_000),
            ),
            ConfigValue(
                "furry_channel",
                default="furrylov",
                doc="Канал-источник для .furry (username или ID).",
                validator=String(max_len=128),
            ),
            ConfigValue(
                "furry_range",
                default=12434,
                doc="Глубина случайной выборки для .furry (кол-во сообщений).",
                validator=Integer(minimum=2, maximum=1_000_000),
            ),
            ConfigValue(
                "nsfw_channel",
                default="hdjrkdjrkdkd",
                doc="Канал-источник для .nsfw (username или ID).",
                validator=String(max_len=128),
            ),
            ConfigValue(
                "nsfw_range",
                default=850,
                doc="Глубина случайной выборки для .nsfw (кол-во сообщений).",
                validator=Integer(minimum=2, maximum=1_000_000),
            ),
        )

    # ──────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────

    def _cfg(self, key: str, default: typing.Any = None) -> typing.Any:
        try:
            if self.config is not None and key in self.config:
                return self.config[key]
        except Exception:
            pass
        return default

    @staticmethod
    def _reply_to(event) -> typing.Optional[int]:
        try:
            return getattr(event.message, "reply_to_msg_id", None)
        except Exception:
            return None

    async def _via_bot(self, event, bot_command: str, loading_key: str) -> None:
        """Запросить медиа у бота-источника через conversation и переслать его."""
        await event.edit(self.strings(loading_key), parse_mode="html")
        reply_to = self._reply_to(event)
        try:
            async with self.client.conversation(
                BOT_USERNAME, timeout=CONV_TIMEOUT
            ) as conv:
                sent = await conv.send_message(bot_command)
                answer = await asyncio.wait_for(
                    conv.get_response(), timeout=RESP_TIMEOUT
                )
                try:
                    await sent.delete()
                except Exception:
                    pass

                if getattr(answer, "media", None):
                    await self.client.send_message(
                        event.chat_id,
                        message=answer,
                        reply_to=reply_to,
                    )
                    try:
                        await answer.delete()
                    except Exception:
                        pass
                    try:
                        await event.delete()
                    except Exception:
                        pass
                else:
                    await event.edit(self.strings("error_bot"), parse_mode="html")
        except asyncio.TimeoutError:
            await event.edit(self.strings("timeout"), parse_mode="html")
        except Exception as e:
            logger.exception("hentai: bot-source request failed")
            await event.edit(
                self.strings("error").format(err=self._esc(str(e))),
                parse_mode="html",
            )

    async def _from_channel(
        self, event, channel_key: str, range_key: str, cfg_hint: str
    ) -> None:
        """Достать случайное медиа из канала-источника и отправить его."""
        await event.edit(self.strings("loading"), parse_mode="html")
        await asyncio.sleep(0.3)  # лёгкая защита от флуда

        channel = str(self._cfg(channel_key, "") or "").strip()
        if not channel:
            await event.edit(
                self.strings("no_channel").format(cfg=cfg_hint),
                parse_mode="html",
            )
            return

        depth = int(self._cfg(range_key, 100) or 100)
        if depth < 2:
            depth = 2
        offset = random.randrange(1, depth, 2)
        reply_to = self._reply_to(event)

        try:
            result = await self.client(functions.messages.GetHistoryRequest(
                peer=channel,
                offset_id=0,
                offset_date=datetime.datetime.now(),
                add_offset=offset,
                limit=1, max_id=0, min_id=0, hash=0,
            ))
            messages = getattr(result, "messages", None) or []
            if messages and getattr(messages[0], "media", None):
                await self.client.send_file(
                    event.chat_id,
                    messages[0].media,
                    reply_to=reply_to,
                )
                try:
                    await event.delete()
                except Exception:
                    pass
            else:
                await event.edit(self.strings("not_found"), parse_mode="html")
        except Exception as e:
            logger.exception("hentai: channel fetch failed for %s", channel)
            low = str(e).lower()
            if "cannot find" in low or "no user" in low or "invalid" in low or "private" in low:
                await event.edit(
                    self.strings("no_channel").format(cfg=cfg_hint),
                    parse_mode="html",
                )
            else:
                await event.edit(
                    self.strings("error").format(err=self._esc(str(e))),
                    parse_mode="html",
                )

    @staticmethod
    def _esc(text: str) -> str:
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # ──────────────────────────────────────────────────
    # Commands
    # ──────────────────────────────────────────────────

    @command("loli", required=OWNER)
    async def loli_cmd(self, event) -> None:
        """случайное loli 🐰"""
        await self._via_bot(event, "/lh", "loading_loli")

    @command("fem", required=OWNER)
    async def fem_cmd(self, event) -> None:
        """случайное femboy 💕"""
        await self._via_bot(event, "/fm", "loading")

    @command("sfw", required=OWNER)
    async def sfw_cmd(self, event) -> None:
        """случайное SFW ☀️"""
        await self._via_bot(event, "/rc", "loading")

    @command("lolic", required=OWNER)
    async def lolic_cmd(self, event) -> None:
        """случайное loli из канала 🌸"""
        await self._from_channel(event, "lolic_channel", "lolic_range", "lolic_channel")

    @command("furry", required=OWNER)
    async def furry_cmd(self, event) -> None:
        """случайное furry 🦊"""
        await self._from_channel(event, "furry_channel", "furry_range", "furry_channel")

    @command("nsfw", required=OWNER)
    async def nsfw_cmd(self, event) -> None:
        """случайное NSFW 🔥"""
        await self._from_channel(event, "nsfw_channel", "nsfw_range", "nsfw_channel")
