# ---------------------------------------------------------------------------------
# Name: KPtichki
# Description: Генератор птиц (адаптация под Kitsune)
# Original author: @FAmods
# Adapted for Kitsune
# requires: aiohttp pillow
# ---------------------------------------------------------------------------------

from __future__ import annotations

import json
import random
import logging
import contextlib
import typing
from io import BytesIO

import aiohttp
from PIL import Image, ImageDraw, ImageFont

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER
from ..utils import escape_html, get_args_raw, run_sync

logger = logging.getLogger(__name__)


class KPtichkiModule(KitsuneModule):
    """Генератор птиц"""

    name = "KPtichki"
    description = "Генератор птиц"
    author = "FAmods (adapted for Kitsune)"
    version = "1.0.0"
    icon = "🦅"
    category = "fun"

    pip_requires = ["aiohttp", "Pillow"]

    strings_ru = {
        "name": "KPtichki",
        "no_args": "🦅 <b>Нужно</b> <code>{prefix}{cmd} {hint}</code>",
        "generation": "🦅 <i>Генерирую птичку...</i>",
        "error": "🦅 <b>Ошибка генерации:</b>\n<code>{err}</code>",
    }

    strings_en = {
        "name": "KPtichki",
        "no_args": "🦅 <b>Usage</b> <code>{prefix}{cmd} {hint}</code>",
        "generation": "🦅 <i>Generating bird...</i>",
        "error": "🦅 <b>Generation error:</b>\n<code>{err}</code>",
    }

    async def on_load(self) -> None:
        self.assets_link = "https://famods.fajox.one/assets"
        self.font_url = f"{self.assets_link}/impact.ttf"
        self.birds_url = f"{self.assets_link}/birds/birds.json"

    def _prefix(self) -> str:
        dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
        if dispatcher and getattr(dispatcher, "_prefix", None):
            return dispatcher._prefix
        with contextlib.suppress(Exception):
            return self.db.get("kitsune.core", "prefix", ".")
        return "."

    async def fetch_bytes(self, url: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                return await resp.read()

    async def get_bird_url(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.birds_url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                birds_list = json.loads(await resp.text())
        return f"{self.assets_link}/birds/{random.choice(birds_list)}.png"

    def _render_bird(self, img_bytes: bytes, font_bytes: bytes, text: str, fmt: str) -> BytesIO:
        text = text.upper()

        img = Image.open(BytesIO(img_bytes)).convert("RGBA")
        img.thumbnail((512, 512))
        width, height = img.size
        draw = ImageDraw.Draw(img)

        font_size = 55
        min_font_size = 12
        max_width_fraction = 0.9

        font = ImageFont.truetype(BytesIO(font_bytes), font_size)
        text_width = font.getlength(text)

        if text_width > max_width_fraction * width:
            scale = (max_width_fraction * width) / text_width
            font_size = max(int(font_size * scale), min_font_size)
            font = ImageFont.truetype(BytesIO(font_bytes), font_size)

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) / 2
        y = height - text_height - (height * 0.05)

        draw.text(
            (x, y),
            text,
            font=font,
            fill="white",
            stroke_width=2,
            stroke_fill="black",
        )

        output = BytesIO()
        img.save(output, format=fmt.upper())
        output.seek(0)
        output.name = f"ptitchka.{fmt.lower()}"
        return output

    async def generate_bird(self, text: str, fmt: str) -> BytesIO:
        # Параллельно тянем картинку птицы и шрифт
        bird_url = await self.get_bird_url()
        import asyncio
        img_bytes, font_bytes = await asyncio.gather(
            self.fetch_bytes(bird_url),
            self.fetch_bytes(self.font_url),
        )
        # PIL-рендер — блокирующий, выносим в executor
        return await run_sync(self._render_bird, img_bytes, font_bytes, text, fmt)

    async def _make_bird(self, event, cmd_name: str, fmt: str, mime_type: str) -> None:
        text = get_args_raw(event.message)
        if not text:
            await event.edit(
                self.strings("no_args").format(
                    prefix=escape_html(self._prefix()),
                    cmd=cmd_name,
                    hint="[текст]",
                ),
                parse_mode="html",
            )
            return

        await event.edit(self.strings("generation"), parse_mode="html")

        try:
            file = await self.generate_bird(text, fmt=fmt)
        except Exception as exc:
            logger.exception("KPtichki: ошибка генерации птицы")
            await event.edit(
                self.strings("error").format(err=escape_html(str(exc))),
                parse_mode="html",
            )
            return

        peer = getattr(event.message, "peer_id", None) or getattr(event, "chat_id", None)
        reply_to = getattr(getattr(event.message, "reply_to", None), "reply_to_msg_id", None)

        try:
            await self.client.send_file(
                peer,
                file=file,
                mime_type=mime_type,
                reply_to=reply_to,
            )
        except Exception as exc:
            logger.exception("KPtichki: ошибка отправки файла")
            await event.edit(
                self.strings("error").format(err=escape_html(str(exc))),
                parse_mode="html",
            )
            return

        with contextlib.suppress(Exception):
            await event.message.delete()

    @command("kptichka", required=OWNER, aliases=["ptichka"])
    async def kptichka_cmd(self, event) -> None:
        """[текст] - Сгенерировать стикер с птицей"""
        await self._make_bird(event, "kptichka", "webp", "image/webp")

    @command("kptichka_img", required=OWNER, aliases=["ptichka_img"])
    async def kptichka_img_cmd(self, event) -> None:
        """[текст] - Сгенерировать фото с птицей"""
        await self._make_bird(event, "kptichka_img", "png", "image/png")
