from __future__ import annotations
import asyncio
import logging
import os
import shutil
import tempfile

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER
from ..hydro_media import send_file as hydro_send_file

logger = logging.getLogger(__name__)


class VoiceDLKitsuneModule(KitsuneModule):
    name        = "VoiceDLKitsune"
    description = "Скачивает голосовые сообщения в формате MP3. Адаптировал @Mikasu32"
    author      = "hikka_mods | adapted by @Mikasu32"
    version     = "1.0.0"
    icon        = "🎙"
    category    = "tools"

    strings_ru = {
        "success":   "✅ <b>Голосовое скачано как MP3</b>",
        "error":     "❌ <b>Ошибка скачивания:</b> <code>{err}</code>",
        "no_voice":  "❌ <b>Ответьте на голосовое сообщение</b>",
        "no_ffmpeg": "❌ <b>FFmpeg не установлен.</b>\nУстановите: <code>apt install ffmpeg</code>",
        "loading":   "⏳ <b>Конвертирую голосовое...</b>",
    }

    strings_en = {
        "success":   "✅ <b>Voice downloaded as MP3</b>",
        "error":     "❌ <b>Download error:</b> <code>{err}</code>",
        "no_voice":  "❌ <b>Reply to a voice message</b>",
        "no_ffmpeg": "❌ <b>FFmpeg is not installed.</b>\nInstall: <code>apt install ffmpeg</code>",
        "loading":   "⏳ <b>Converting voice...</b>",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ffmpeg_available: bool = False

    async def on_load(self) -> None:
        self._ffmpeg_available = shutil.which("ffmpeg") is not None
        if not self._ffmpeg_available:
            logger.warning("VoiceDLKitsune: ffmpeg not found in PATH")

    @command("voicedl", required=OWNER, aliases=["vdl", "vmp3"])
    async def voicedl_cmd(self, event) -> None:
        if not self._ffmpeg_available:
            await event.edit(self.strings("no_ffmpeg"), parse_mode="html")
            return

        reply = await event.message.get_reply_message()
        if not reply or not getattr(reply, "voice", None):
            await event.edit(self.strings("no_voice"), parse_mode="html")
            return

        await event.edit(self.strings("loading"), parse_mode="html")

        with tempfile.TemporaryDirectory() as tmpdir:
            ogg_path = os.path.join(tmpdir, "voice.ogg")
            mp3_path = os.path.join(tmpdir, "voice.mp3")

            try:
                await reply.download_media(file=ogg_path)
            except Exception as exc:
                logger.exception("VoiceDLKitsune: download failed")
                await event.edit(
                    self.strings("error").format(err=str(exc)[:200]),
                    parse_mode="html",
                )
                return

            try:
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "error",
                    "-y",
                    "-i", ogg_path,
                    "-vn",
                    "-codec:a", "libmp3lame",
                    "-q:a", "2",
                    "-ar", "44100",
                    mp3_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            except asyncio.TimeoutError:
                await event.edit(
                    self.strings("error").format(err="timeout (120s)"),
                    parse_mode="html",
                )
                return
            except Exception as exc:
                logger.exception("VoiceDLKitsune: ffmpeg launch failed")
                await event.edit(
                    self.strings("error").format(err=str(exc)[:200]),
                    parse_mode="html",
                )
                return

            if proc.returncode != 0 or not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
                err_msg = (stderr.decode(errors="replace").strip().splitlines() or ["ffmpeg failed"])[-1][:200]
                await event.edit(
                    self.strings("error").format(err=err_msg),
                    parse_mode="html",
                )
                return

            try:
                await hydro_send_file(
                    self.client,
                    event.message.peer_id,
                    mp3_path,
                    caption=self.strings("success"),
                    parse_mode="html",
                    reply_to=reply.id,
                )
                await event.message.delete()
            except Exception as exc:
                logger.exception("VoiceDLKitsune: send_file failed")
                await event.edit(
                    self.strings("error").format(err=str(exc)[:200]),
                    parse_mode="html",
                )
