from __future__ import annotations
import asyncio
import logging
import os
import shutil
import tempfile

from ..core.loader import KitsuneModule, command, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..hydro_media import send_file as hydro_send_file
from ..validators import Integer

logger = logging.getLogger(__name__)


class Video2GIFKitsuneModule(KitsuneModule):
    name        = "Video2GIFKitsune"
    description = "Конвертирует видео в качественный GIF с двухпроходной палитрой. Адаптировал @Mikasu32"
    author      = "hikka_mods | adapted by @Mikasu32"
    version     = "1.0.0"
    icon        = "🎞"
    category    = "tools"

    strings_ru = {
        "success":     "✅ <b>GIF создан</b> · fps=<code>{fps}</code>, ширина=<code>{w}</code>",
        "error":       "❌ <b>Ошибка конвертации:</b> <code>{err}</code>",
        "no_video":    "❌ <b>Ответьте на видео или GIF</b>",
        "no_ffmpeg":   "❌ <b>FFmpeg не установлен.</b>\nУстановите: <code>apt install ffmpeg</code>",
        "processing":  "🔄 <b>Обрабатываю видео...</b>",
        "compressing": "📦 <b>Оптимизирую GIF...</b>",
        "bad_args":    "❌ <b>Неверные аргументы.</b>\nПример: <code>.gifc 15 480</code>",
    }

    strings_en = {
        "success":     "✅ <b>GIF created</b> · fps=<code>{fps}</code>, width=<code>{w}</code>",
        "error":       "❌ <b>Conversion failed:</b> <code>{err}</code>",
        "no_video":    "❌ <b>Reply to a video or GIF</b>",
        "no_ffmpeg":   "❌ <b>FFmpeg is not installed.</b>\nInstall: <code>apt install ffmpeg</code>",
        "processing":  "🔄 <b>Processing video...</b>",
        "compressing": "📦 <b>Optimizing GIF...</b>",
        "bad_args":    "❌ <b>Bad arguments.</b>\nExample: <code>.gifc 15 480</code>",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ffmpeg_available: bool = False
        self.config = ModuleConfig(
            ConfigValue(
                "default_fps",
                15,
                "FPS по умолчанию (1-30)",
                validator=Integer(minimum=1, maximum=30),
            ),
            ConfigValue(
                "default_width",
                480,
                "Ширина GIF по умолчанию (120-1024)",
                validator=Integer(minimum=120, maximum=1024),
            ),
            ConfigValue(
                "timeout",
                180,
                "Таймаут конвертации в секундах",
                validator=Integer(minimum=30, maximum=900),
            ),
        )

    async def on_load(self) -> None:
        self._ffmpeg_available = shutil.which("ffmpeg") is not None
        if not self._ffmpeg_available:
            logger.warning("Video2GIFKitsune: ffmpeg not found in PATH")

    @staticmethod
    def _parse_args(raw: str, default_fps: int, default_width: int) -> tuple[int, int] | None:
        if not raw.strip():
            return default_fps, default_width
        parts = raw.split()
        try:
            fps = int(parts[0]) if len(parts) >= 1 else default_fps
            width = int(parts[1]) if len(parts) >= 2 else default_width
        except ValueError:
            return None
        fps = max(1, min(fps, 30))
        width = max(120, min(width, 1024))
        if width % 2 == 1:
            width += 1
        return fps, width

    @command("gifc", required=OWNER, aliases=["video2gif", "togif"])
    async def gifc_cmd(self, event) -> None:
        if not self._ffmpeg_available:
            await event.edit(self.strings("no_ffmpeg"), parse_mode="html")
            return

        reply = await event.message.get_reply_message()
        if not reply or not (getattr(reply, "video", None) or getattr(reply, "gif", None) or getattr(reply, "video_note", None)):
            await event.edit(self.strings("no_video"), parse_mode="html")
            return

        cfg = self.config
        default_fps = cfg["default_fps"] if cfg else 15
        default_width = cfg["default_width"] if cfg else 480
        timeout = cfg["timeout"] if cfg else 180

        parsed = self._parse_args(self.get_args(event), default_fps, default_width)
        if parsed is None:
            await event.edit(self.strings("bad_args"), parse_mode="html")
            return
        fps, width = parsed

        await event.edit(self.strings("processing"), parse_mode="html")

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = os.path.join(tmpdir, "video.mp4")
            palette_path = os.path.join(tmpdir, "palette.png")
            gif_path = os.path.join(tmpdir, "output.gif")

            try:
                await reply.download_media(file=video_path)
            except Exception as exc:
                logger.exception("Video2GIFKitsune: download failed")
                await event.edit(
                    self.strings("error").format(err=str(exc)[:200]),
                    parse_mode="html",
                )
                return

            vf = f"fps={fps},scale={width}:-2:flags=lanczos"

            try:
                proc_p = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "error",
                    "-y",
                    "-i", video_path,
                    "-vf", f"{vf},palettegen=stats_mode=diff",
                    palette_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr_p = await asyncio.wait_for(proc_p.communicate(), timeout=timeout)

                if proc_p.returncode != 0 or not os.path.exists(palette_path):
                    err = (stderr_p.decode(errors="replace").strip().splitlines() or ["palettegen failed"])[-1][:200]
                    await event.edit(
                        self.strings("error").format(err=err),
                        parse_mode="html",
                    )
                    return

                await event.edit(self.strings("compressing"), parse_mode="html")

                proc_g = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "error",
                    "-y",
                    "-i", video_path,
                    "-i", palette_path,
                    "-lavfi", f"{vf} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5",
                    "-f", "gif",
                    gif_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr_g = await asyncio.wait_for(proc_g.communicate(), timeout=timeout)

            except asyncio.TimeoutError:
                await event.edit(
                    self.strings("error").format(err=f"timeout ({timeout}s)"),
                    parse_mode="html",
                )
                return
            except Exception as exc:
                logger.exception("Video2GIFKitsune: ffmpeg launch failed")
                await event.edit(
                    self.strings("error").format(err=str(exc)[:200]),
                    parse_mode="html",
                )
                return

            if proc_g.returncode != 0 or not os.path.exists(gif_path) or os.path.getsize(gif_path) == 0:
                err = (stderr_g.decode(errors="replace").strip().splitlines() or ["gif encode failed"])[-1][:200]
                await event.edit(
                    self.strings("error").format(err=err),
                    parse_mode="html",
                )
                return

            try:
                await hydro_send_file(
                    self.client,
                    event.message.peer_id,
                    gif_path,
                    caption=self.strings("success").format(fps=fps, w=width),
                    parse_mode="html",
                    reply_to=reply.id,
                )
                await event.message.delete()
            except Exception as exc:
                logger.exception("Video2GIFKitsune: send_file failed")
                await event.edit(
                    self.strings("error").format(err=str(exc)[:200]),
                    parse_mode="html",
                )
