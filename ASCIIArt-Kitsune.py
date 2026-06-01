from __future__ import annotations
import asyncio
import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

from ..core.loader import KitsuneModule, command, ModuleConfig, ConfigValue
from ..core.security import OWNER
from ..validators import Integer, String

logger = logging.getLogger(__name__)


class AsciiArtKitsuneModule(KitsuneModule):
    name = "AsciiArtKitsune"
    description = "Конвертирует изображение в ASCII-арт. Адаптировал @Mikasu32"
    author = "@hikka_mods | Kitsune by @Mikasu32"
    version = "1.0.0"
    icon = "🎨"
    category = "tools"

    strings_ru = {
        "no_media": "❌ <b>Ответь на сообщение с изображением!</b>",
        "loading": "🎨 <b>Конвертирую изображение в ASCII...</b>",
        "error": "👎 <b>Ошибка при конвертации:</b> <code>{err}</code>",
        "done": "✅ <b>Ваш ASCII-арт готов!</b>",
        "no_pil": (
            "❌ <b>Не установлена библиотека Pillow.</b>\n"
            "Установи её командой: <code>pip install Pillow</code>"
        ),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "width",
                default=100,
                doc="Ширина выходного ASCII-арта в символах (10–400)",
                validator=Integer(minimum=10, maximum=400),
            ),
            ConfigValue(
                "chars",
                default="@#S%?*+;:,. ",
                doc="Набор символов от самого тёмного к самому светлому",
                validator=String(min_len=2, max_len=64),
            ),
        )

    @staticmethod
    def _is_image(msg) -> bool:
        if msg is None:
            return False
        if getattr(msg, "photo", None):
            return True
        doc = getattr(msg, "document", None)
        if doc is None:
            return False
        mime = ""
        try:
            mime = (msg.file.mime_type or "") if msg.file else ""
        except Exception:
            mime = ""
        return mime.startswith("image/")

    def _render(self, image_bytes: bytes, width: int, chars: str) -> str:
        from PIL import Image
        chars_count = len(chars)
        if chars_count < 2:
            chars = "@#S%?*+;:,. "
            chars_count = len(chars)
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("L")
            w, h = img.size
            if w <= 0 or h <= 0:
                raise RuntimeError("invalid image dimensions")
            aspect = h / w
            new_height = max(1, int(aspect * width * 0.55))
            img = img.resize((width, new_height), Image.NEAREST)
            pixels = list(img.getdata())
            step = max(1, 256 // chars_count)
            lines = []
            row_chars = []
            for idx, pixel in enumerate(pixels):
                ch_idx = min(chars_count - 1, pixel // step)
                row_chars.append(chars[ch_idx])
                if (idx + 1) % width == 0:
                    lines.append("".join(row_chars))
                    row_chars.clear()
            if row_chars:
                lines.append("".join(row_chars))
            return "\n".join(lines)

    @command("cascii", required=OWNER, aliases=["asciiart"])
    async def cascii_cmd(self, event) -> None:
        """Ответь на сообщение с картинкой — получишь ASCII-арт текстовым файлом. Псевдоним: .asciiart"""
        reply = await event.message.get_reply_message()
        if not self._is_image(reply):
            await event.reply(self.strings("no_media"), parse_mode="html")
            return

        try:
            import PIL
        except ImportError:
            await event.reply(self.strings("no_pil"), parse_mode="html")
            return

        status = await event.reply(self.strings("loading"), parse_mode="html")

        try:
            data = await reply.download_media(bytes)
            if not data:
                raise RuntimeError("empty media")
        except Exception as e:
            logger.warning("AsciiArtKitsune: download failed: %s", e)
            await status.edit(
                self.strings("error").format(err=str(e)[:200]),
                parse_mode="html",
            )
            return

        width = int(self.config["width"]) if self.config else 100
        chars = self.config["chars"] if self.config else "@#S%?*+;:,. "

        loop = asyncio.get_running_loop()
        try:
            ascii_art = await loop.run_in_executor(
                None, self._render, data, width, chars,
            )
        except Exception as e:
            logger.exception("AsciiArtKitsune: render failed")
            await status.edit(
                self.strings("error").format(err=str(e)[:200]),
                parse_mode="html",
            )
            return

        tmp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".txt", delete=False,
            ) as fp:
                fp.write(ascii_art)
                tmp_path = Path(fp.name)
            await self.client.send_file(
                event.peer_id,
                str(tmp_path),
                caption=self.strings("done"),
                parse_mode="html",
                force_document=True,
                reply_to=getattr(event.message, "reply_to_msg_id", None),
            )
            try:
                await status.delete()
            except Exception:
                pass
        except Exception as e:
            logger.exception("AsciiArtKitsune: send failed")
            await status.edit(
                self.strings("error").format(err=str(e)[:200]),
                parse_mode="html",
            )
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
