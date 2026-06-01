# meta developer: quote-sticker
# Kitsune adaptation: оптимизированный нативный порт.
# Рендеринг PIL вынесен в отдельный поток (asyncio.to_thread), чтобы
# не блокировать event-loop userbot'а. Шрифты ищутся по списку путей с
# надёжным fallback'ом.
from __future__ import annotations

import asyncio
import datetime
import io
import re
import textwrap
import typing

from PIL import Image, ImageDraw, ImageFont, ImageOps
from telethon.errors import ChatSendStickersForbiddenError

from kitsune.core.loader import KitsuneModule, command
from kitsune.core.security import OWNER

# ── шрифты ───────────────────────────────────────────────────────────────────

FONT_REG_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/system/fonts/DroidSans.ttf",
    "/system/fonts/Roboto-Regular.ttf",
)
FONT_BOLD_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/data/data/com.termux/files/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/system/fonts/Roboto-Bold.ttf",
)
FONT_EMOJI_PATHS = (
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
    "/data/data/com.termux/files/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "/data/data/com.termux/files/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/system/fonts/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/noto-color-emoji/NotoColorEmoji.ttf",
)

MAX_MESSAGES = 20


def _load_font(paths: tuple[str, ...], size: int):
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _load_emoji_font(size: int):
    for path in FONT_EMOJI_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return None


def _is_emoji(char: str) -> bool:
    cp = ord(char)
    return (
        0x1F300 <= cp <= 0x1FAFF or
        0x2600  <= cp <= 0x27BF  or
        0xFE00  <= cp <= 0xFE0F  or
        0x1F000 <= cp <= 0x1F02F or
        0x1F0A0 <= cp <= 0x1F0FF or
        0x1F100 <= cp <= 0x1F2FF or
        0x2300  <= cp <= 0x23FF  or
        0x2B00  <= cp <= 0x2BFF  or
        0x1F900 <= cp <= 0x1F9FF
    )


def _text_width(draw, text, font, emoji_font) -> int:
    """Считает реальную ширину строки с учётом эмодзи."""
    total = 0
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if ord(char) == 0xFE0F:
            i += 1
            continue
        if _is_emoji(char) and emoji_font is not None:
            seq = char
            j = i + 1
            while j < n and (
                ord(text[j]) == 0x200D or
                ord(text[j]) == 0xFE0F or
                0x1F3FB <= ord(text[j]) <= 0x1F3FF
            ):
                seq += text[j]
                j += 1
            try:
                bb = emoji_font.getbbox(seq)
                ew, eh = bb[2] - bb[0], bb[3] - bb[1]
                scale = font.size / max(eh, 1)
                total += max(1, int(ew * scale)) + 1
            except Exception:
                total += font.size
            i = j
        else:
            try:
                bb = draw.textbbox((0, 0), char, font=font)
                total += bb[2] - bb[0]
            except Exception:
                total += font.size // 2
            i += 1
    return total


def _draw_text_with_emoji(draw, img, pos, text, font, emoji_font, fill):
    x, y = pos
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if ord(char) == 0xFE0F:
            i += 1
            continue
        if _is_emoji(char) and emoji_font is not None:
            seq = char
            j = i + 1
            while j < n and (
                ord(text[j]) == 0x200D or
                ord(text[j]) == 0xFE0F or
                0x1F3FB <= ord(text[j]) <= 0x1F3FF
            ):
                seq += text[j]
                j += 1
            try:
                bb = emoji_font.getbbox(seq)
                ew, eh = bb[2] - bb[0], bb[3] - bb[1]
                emoji_img = Image.new("RGBA", (ew + 4, eh + 4), (0, 0, 0, 0))
                emoji_draw = ImageDraw.Draw(emoji_img)
                emoji_draw.text((0, -bb[1]), seq, font=emoji_font, embedded_color=True)
                size = font.size
                scale = size / max(eh, 1)
                new_w = max(1, int(ew * scale))
                new_h = max(1, int(eh * scale))
                emoji_img = emoji_img.crop((0, 0, ew, eh)).resize((new_w, new_h), Image.LANCZOS)
                img.paste(emoji_img, (x, y + (size - new_h) // 2), emoji_img)
                x += new_w + 1
            except Exception:
                pass
            i = j
        else:
            try:
                bb = draw.textbbox((0, 0), char, font=font)
                draw.text((x, y), char, font=font, fill=fill)
                x += bb[2] - bb[0]
            except Exception:
                x += font.size // 2
            i += 1


class KQuoteModule(KitsuneModule):
    name        = "Kquote"
    description = "Превращает сообщение(я) в стикер-цитату"
    author      = "ты"
    version     = "4.0.0"
    icon        = "🖼️"
    category    = "tools"

    pip_requires: typing.ClassVar[list[str]] = ["PIL"]
    system_requires: typing.ClassVar[list[str]] = []

    BG      = (23,  33,  43,  255)
    BUBBLE  = (36,  47,  61,  255)
    ACCENT  = (100, 181, 246, 255)
    TEXT_C  = (224, 224, 224, 255)
    TIME_C  = (120, 144, 156, 255)
    AVATAR_COLORS = [
        (229,  57,  53, 255),
        (156,  39, 176, 255),
        ( 30, 136, 229, 255),
        (  0, 137, 123, 255),
        (251, 140,   0, 255),
        (216,  27,  96, 255),
    ]

    @command("q", required=OWNER)
    async def quote_cmd(self, event) -> None:
        """.q [N] — стикер из сообщения (или N последних сообщений выше)."""
        args  = (event.text or "").strip().split()
        count = 1
        if len(args) >= 2:
            try:
                count = max(1, min(int(args[1]), MAX_MESSAGES))
            except ValueError:
                pass

        reply = await event.get_reply_message()

        if count == 1:
            if not reply:
                await event.reply("❌ Ответь на сообщение или укажи .q N для последних N сообщений.")
                return
            messages = [reply]
        else:
            fetched  = await event.client.get_messages(event.chat_id, limit=count, max_id=event.id)
            messages = list(reversed(fetched))
            if not messages:
                await event.reply("❌ Не удалось получить сообщения.")
                return

        text_messages = [m for m in messages if m and (m.text or m.message)]
        if not text_messages:
            await event.reply("❌ Нет текстовых сообщений.")
            return

        msg_data     = []
        avatar_cache = {}

        for m in text_messages:
            text = self._strip_markdown(m.text or m.message or "")
            if not text:
                continue
            sender = await m.get_sender()
            if sender:
                first = getattr(sender, "first_name", "") or ""
                last  = getattr(sender, "last_name",  "") or ""
                name  = (first + " " + last).strip() or "Unknown"
                uid   = sender.id
            else:
                name, uid = "Unknown", 0
            if uid not in avatar_cache:
                avatar_cache[uid] = await self._get_avatar(event.client, sender)
            msg_data.append({"name": name, "uid": uid, "text": text, "avatar": avatar_cache[uid], "date": m.date})

        if not msg_data:
            await event.reply("❌ Нет текстовых сообщений.")
            return

        await event.delete()

        buf = await self._render_to_buffer(msg_data)
        try:
            await event.client.send_file(
                event.chat_id, buf,
                reply_to=reply.id if reply else None,
                force_document=False,
            )
        except ChatSendStickersForbiddenError:
            await event.reply("❌ В этом чате запрещены стикеры.")
        except Exception as e:
            await event.reply(f"❌ Ошибка отправки: {e}")

    @command("fq", required=OWNER)
    async def fakequote_cmd(self, event) -> None:
        """.fq @user1 текст\\n@user2 текст — фейковые цитаты, по одной на строку."""
        raw   = (event.text or "").strip()
        parts = raw.split(maxsplit=1)
        if len(parts) < 2:
            await event.reply(
                "❌ Использование:\n"
                "`.fq @user1 привет`\n"
                "`@user2 дарова`\n"
                "`@user3 хеллоу`"
            )
            return

        body = parts[1]
        raw_lines = body.splitlines()

        entries = []
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("@"):
                entries.append(line)
            elif entries:
                entries[-1] += " " + line

        if not entries:
            await event.reply("❌ Не найдено строк вида `@username текст`.")
            return

        parsed = []
        for entry in entries:
            sp = entry.split(maxsplit=1)
            if len(sp) < 2:
                await event.reply(f"❌ Строка без текста: `{entry}`\nФормат: `@username текст`")
                return
            parsed.append((sp[0], sp[1].strip()))

        entity_cache = {}
        avatar_cache = {}
        msg_data     = []

        for username, text in parsed:
            if username not in entity_cache:
                try:
                    entity_cache[username] = await event.client.get_entity(username)
                except Exception:
                    await event.reply(f"❌ Не удалось найти пользователя {username}.")
                    return

            target = entity_cache[username]
            uid    = target.id

            if uid not in avatar_cache:
                avatar_cache[uid] = await self._get_avatar(event.client, target)

            first = getattr(target, "first_name", "") or ""
            last  = getattr(target, "last_name",  "") or ""
            name  = (first + " " + last).strip() or username

            msg_data.append({
                "name":   name,
                "uid":    uid,
                "text":   text,
                "avatar": avatar_cache[uid],
                "date":   datetime.datetime.now(),
            })

        await event.delete()

        buf = await self._render_to_buffer(msg_data)
        try:
            await event.client.send_file(event.chat_id, buf, force_document=False)
        except ChatSendStickersForbiddenError:
            await event.reply("❌ В этом чате запрещены стикеры.")
        except Exception as e:
            await event.reply(f"❌ Ошибка отправки: {e}")

    # ── рендер (выполняется в отдельном потоке) ───────────────────────────────

    async def _render_to_buffer(self, msg_data: list) -> io.BytesIO:
        """Рендерит изображение в отдельном потоке, чтобы не блокировать loop."""
        return await asyncio.to_thread(self._render_to_buffer_sync, msg_data)

    def _render_to_buffer_sync(self, msg_data: list) -> io.BytesIO:
        img = self._render_many(msg_data)
        buf = io.BytesIO()
        img.save(buf, format="WebP", quality=95)
        buf.seek(0)
        buf.name = "sticker.webp"
        return buf

    def _render_many(self, msg_data: list) -> Image.Image:
        PAD        = 16
        AVA_SIZE   = 56
        FS_NAME    = 16
        FS_TEXT    = 15
        FS_TIME    = 12
        MAX_W      = 512
        BUBBLE_GAP = 12
        LINE_H     = FS_TEXT + 6
        INNER_H    = 10
        INNER_W    = 12
        RADIUS     = 18

        fn   = _load_font(FONT_BOLD_PATHS, FS_NAME)
        ft   = _load_font(FONT_REG_PATHS,  FS_TEXT)
        ftim = _load_font(FONT_REG_PATHS,  FS_TIME)

        emoji_font = _load_emoji_font(FS_TEXT)

        bx_start   = PAD + AVA_SIZE + 10
        max_bw     = MAX_W - bx_start - PAD

        char_w     = FS_TEXT * 0.55
        wrap_chars = max(10, int((max_bw - INNER_W * 2) / char_w))

        _tmp = Image.new("RGBA", (1, 1))
        _drw = ImageDraw.Draw(_tmp)

        bubbles = []
        for m in msg_data:
            lines    = textwrap.wrap(m["text"], width=wrap_chars) or [""]
            name_h   = FS_NAME + 4
            name_w   = _drw.textbbox((0, 0), m["name"], font=fn)[2]
            time_str = m["date"].strftime("%H:%M") if m["date"] else datetime.datetime.now().strftime("%H:%M")
            time_w   = _drw.textbbox((0, 0), time_str, font=ftim)[2]
            max_line_w = max(
                (_text_width(_drw, line, ft, emoji_font) for line in lines),
                default=0
            )
            content_w = max(name_w, max_line_w, time_w + 4)
            bw       = min(content_w + INNER_W * 2, max_bw)
            text_h   = LINE_H * len(lines)
            bubble_h = INNER_H + name_h + text_h + 2 + FS_TIME + INNER_H
            row_h    = max(bubble_h, AVA_SIZE)
            bubbles.append({
                **m,
                "lines":    lines,
                "bubble_h": bubble_h,
                "bw":       bw,
                "row_h":    row_h,
                "time_str": time_str,
            })

        total_h      = PAD + sum(b["row_h"] for b in bubbles) + BUBBLE_GAP * (len(bubbles) - 1) + PAD
        max_bubble_w = max(b["bw"] for b in bubbles)
        total_w      = min(bx_start + max_bubble_w + PAD, MAX_W)

        img  = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        cy = PAD
        for b in bubbles:
            row_h = b["row_h"]
            ax    = PAD
            ay    = cy + (row_h - AVA_SIZE) // 2

            if b["avatar"] is not None:
                ava = self._circle_crop(b["avatar"], AVA_SIZE)
                img.paste(ava, (ax, ay), ava)
            else:
                color = self.AVATAR_COLORS[b["uid"] % len(self.AVATAR_COLORS)]
                ava_img  = Image.new("RGBA", (AVA_SIZE, AVA_SIZE), (0, 0, 0, 0))
                ava_draw = ImageDraw.Draw(ava_img)
                ava_draw.ellipse([0, 0, AVA_SIZE, AVA_SIZE], fill=color)
                initial = b["name"][0].upper() if b["name"] else "?"
                ib = ava_draw.textbbox((0, 0), initial, font=fn)
                iw, ih = ib[2] - ib[0], ib[3] - ib[1]
                ava_draw.text(
                    ((AVA_SIZE - iw) // 2, (AVA_SIZE - ih) // 2),
                    initial, font=fn, fill=(255, 255, 255, 255)
                )
                img.paste(ava_img, (ax, ay), ava_img)

            bx = bx_start
            by = cy
            bw = b["bw"]
            bh = b["bubble_h"]

            bubble_img  = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            bubble_draw = ImageDraw.Draw(bubble_img)
            bubble_draw.rounded_rectangle(
                [0, 0, bw, bh], radius=RADIUS,
                fill=(30, 30, 30, 210)
            )
            img.alpha_composite(bubble_img, (bx, by))

            draw = ImageDraw.Draw(img)

            draw.text((bx + INNER_W, by + INNER_H), b["name"], font=fn, fill=self.ACCENT)

            name_h = FS_NAME + 4
            ty = by + INNER_H + name_h
            for line in b["lines"]:
                _draw_text_with_emoji(draw, img, (bx + INNER_W, ty), line, ft, emoji_font, fill=self.TEXT_C)
                ty += LINE_H

            tw = draw.textbbox((0, 0), b["time_str"], font=ftim)[2]
            draw.text(
                (bx + bw - INNER_W - tw, by + bh - INNER_H - FS_TIME),
                b["time_str"], font=ftim, fill=self.TIME_C
            )

            cy += row_h + BUBBLE_GAP

        # Telegram: одна сторона = 512, вторая <= 512
        w, h = img.size
        if h > w:
            new_h, new_w = 512, max(1, int(w * 512 / h))
        else:
            new_w, new_h = 512, max(1, int(h * 512 / w))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        return img

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _get_avatar(self, client, sender) -> Image.Image | None:
        if sender is None:
            return None
        try:
            photos = await client.get_profile_photos(sender.id, limit=1)
            if not photos:
                return None
            buf = io.BytesIO()
            await client.download_media(photos[0], file=buf)
            buf.seek(0)
            return Image.open(buf).convert("RGBA")
        except Exception:
            return None

    def _circle_crop(self, img: Image.Image, size: int) -> Image.Image:
        img  = img.convert("RGBA")
        img  = ImageOps.fit(img, (size, size), method=Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
        result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        result.paste(img, (0, 0), mask)
        return result

    def _strip_markdown(self, text: str) -> str:
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'\(tg:[^)]+\)', '', text)
        text = re.sub(r'[*_`]{1,3}', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()
