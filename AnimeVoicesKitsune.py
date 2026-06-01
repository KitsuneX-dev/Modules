from __future__ import annotations
import asyncio
import logging
from typing import Optional, Tuple

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER

logger = logging.getLogger(__name__)

_CHANNEL = "AniVoicec"

_VOICES: dict[str, Tuple[int, str]] = {
    "smexk":       (27, "Смех Канеки"),
    "smexy":       (28, "Смех Ягами"),
    "znay":        (29, "Знай своё место, ничтожество"),
    "madara":      (30, "Учиха Мадара"),
    "sharingan":   (30, "Итачи Шаринган"),
    "imsasuke":    (32, "Учиха Саске"),
    "pain":        (6,  "Познайте боль"),
    "ras":         (8,  "Расширение территории"),
    "tensei":      (9,  "Shinra tensei"),
    "dazai":       (10, "Дазай"),
    "gay":         (11, "I'm gay"),
    "bankai":      (12, "Bankai"),
    "sate":        (13, "Sate sate sate"),
    "yoaimo":      (14, "Yoaimo"),
    "valhalla":    (16, "Валгалла"),
    "itachi":      (17, "Итачи о Хокаге"),
    "ghoul":       (18, "Я... Гуль"),
    "best":        (19, "Я стану лучшим"),
    "requiem":     (20, "Это реквием"),
    "king":        (21, "Король вернулся"),
    "equality":    (22, "Аянокоджи про равенство"),
    "forest":      (23, "Красота леса"),
    "bankaiichigo":(24, "Банкай Ичиго"),
}


class AnimeVoicesKitsuneModule(KitsuneModule):
    name = "AnimeVoicesKitsune"
    description = "🎤 Популярные голоса аниме. Адаптировал @Mikasu32"
    author = "@lotosiiik, @byateblan | Kitsune by @Mikasu32"
    version = "1.0.0"
    icon = "🎤"
    category = "fun"

    strings_ru = {
        "list_header": "🎤 <b>Доступные голоса AnimeVoices:</b>\n",
        "list_line": "  • <code>{cmd}{name}</code> — {desc}",
        "loading": "🎵 <b>Загружаю...</b>",
        "error": "❌ <b>Не удалось отправить голос:</b> <code>{err}</code>",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cache: dict[int, object] = {}
        self._cache_lock = asyncio.Lock()

    async def _resolve_voice(self, msg_id: int):
        async with self._cache_lock:
            cached = self._cache.get(msg_id)
            if cached is not None:
                return cached
            try:
                msg = await self.client.get_messages(_CHANNEL, ids=msg_id)
            except Exception as e:
                logger.warning(
                    "AnimeVoicesKitsune: get_messages(%s, %s) failed: %s",
                    _CHANNEL, msg_id, e,
                )
                return None
            if msg is None or not getattr(msg, "media", None):
                return None
            self._cache[msg_id] = msg
            return msg

    async def _send_voice(self, event, msg_id: int) -> None:
        reply = await event.message.get_reply_message()
        reply_to = reply.id if reply else None
        peer = event.peer_id

        try:
            await event.message.delete()
        except Exception:
            pass

        source = await self._resolve_voice(msg_id)
        try:
            if source is not None:
                await self.client.send_file(
                    peer,
                    source,
                    voice_note=True,
                    reply_to=reply_to,
                )
            else:
                fallback_url = f"https://t.me/{_CHANNEL}/{msg_id}"
                await self.client.send_file(
                    peer,
                    fallback_url,
                    voice_note=True,
                    reply_to=reply_to,
                )
        except Exception as e:
            logger.warning("AnimeVoicesKitsune: send failed: %s", e)
            try:
                await self.client.send_message(
                    peer,
                    self.strings("error").format(err=str(e)[:200]),
                    parse_mode="html",
                )
            except Exception:
                pass

    @command("voices", required=OWNER, aliases=["animevoices"])
    async def voices_cmd(self, event) -> None:
        """Показать список всех доступных аниме-голосов. Псевдоним: .animevoices"""
        dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
        prefix = dispatcher._prefix if dispatcher else "."
        lines = [self.strings("list_header")]
        for name, (_, desc) in _VOICES.items():
            lines.append(self.strings("list_line").format(
                cmd=prefix, name=name, desc=desc,
            ))
        await event.reply("\n".join(lines), parse_mode="html")

    @command("smexk",        required=OWNER)
    async def smexk_cmd(self, event):
        """Отправить голосовое: Смех Канеки"""
        await self._send_voice(event, _VOICES["smexk"][0])

    @command("smexy",        required=OWNER)
    async def smexy_cmd(self, event):
        """Отправить голосовое: Смех Ягами"""
        await self._send_voice(event, _VOICES["smexy"][0])

    @command("znay",         required=OWNER)
    async def znay_cmd(self, event):
        """Отправить голосовое: Знай своё место, ничтожество"""
        await self._send_voice(event, _VOICES["znay"][0])

    @command("madara",       required=OWNER)
    async def madara_cmd(self, event):
        """Отправить голосовое: Учиха Мадара"""
        await self._send_voice(event, _VOICES["madara"][0])

    @command("sharingan",    required=OWNER)
    async def sharingan_cmd(self, event):
        """Отправить голосовое: Итачи Шаринган"""
        await self._send_voice(event, _VOICES["sharingan"][0])

    @command("imsasuke",     required=OWNER)
    async def imsasuke_cmd(self, event):
        """Отправить голосовое: Учиха Саске"""
        await self._send_voice(event, _VOICES["imsasuke"][0])

    @command("pain",         required=OWNER)
    async def pain_cmd(self, event):
        """Отправить голосовое: Познайте боль"""
        await self._send_voice(event, _VOICES["pain"][0])

    @command("ras",          required=OWNER)
    async def ras_cmd(self, event):
        """Отправить голосовое: Расширение территории"""
        await self._send_voice(event, _VOICES["ras"][0])

    @command("tensei",       required=OWNER)
    async def tensei_cmd(self, event):
        """Отправить голосовое: Shinra tensei"""
        await self._send_voice(event, _VOICES["tensei"][0])

    @command("dazai",        required=OWNER)
    async def dazai_cmd(self, event):
        """Отправить голосовое: Дазай"""
        await self._send_voice(event, _VOICES["dazai"][0])

    @command("gay",          required=OWNER)
    async def gay_cmd(self, event):
        """Отправить голосовое: I'm gay"""
        await self._send_voice(event, _VOICES["gay"][0])

    @command("bankai",       required=OWNER)
    async def bankai_cmd(self, event):
        """Отправить голосовое: Bankai"""
        await self._send_voice(event, _VOICES["bankai"][0])

    @command("sate",         required=OWNER)
    async def sate_cmd(self, event):
        """Отправить голосовое: Sate sate sate"""
        await self._send_voice(event, _VOICES["sate"][0])

    @command("yoaimo",       required=OWNER)
    async def yoaimo_cmd(self, event):
        """Отправить голосовое: Yoaimo"""
        await self._send_voice(event, _VOICES["yoaimo"][0])

    @command("valhalla",     required=OWNER)
    async def valhalla_cmd(self, event):
        """Отправить голосовое: Валгалла"""
        await self._send_voice(event, _VOICES["valhalla"][0])

    @command("itachi",       required=OWNER)
    async def itachi_cmd(self, event):
        """Отправить голосовое: Итачи о Хокаге"""
        await self._send_voice(event, _VOICES["itachi"][0])

    @command("ghoul",        required=OWNER)
    async def ghoul_cmd(self, event):
        """Отправить голосовое: Я... Гуль"""
        await self._send_voice(event, _VOICES["ghoul"][0])

    @command("best",         required=OWNER)
    async def best_cmd(self, event):
        """Отправить голосовое: Я стану лучшим"""
        await self._send_voice(event, _VOICES["best"][0])

    @command("requiem",      required=OWNER)
    async def requiem_cmd(self, event):
        """Отправить голосовое: Это реквием"""
        await self._send_voice(event, _VOICES["requiem"][0])

    @command("king",          required=OWNER)
    async def king_cmd(self, event):
        """Отправить голосовое: Король вернулся"""
        await self._send_voice(event, _VOICES["king"][0])

    @command("equality",     required=OWNER)
    async def equality_cmd(self, event):
        """Отправить голосовое: Аянокоджи про равенство"""
        await self._send_voice(event, _VOICES["equality"][0])

    @command("forest",       required=OWNER)
    async def forest_cmd(self, event):
        """Отправить голосовое: Красота леса"""
        await self._send_voice(event, _VOICES["forest"][0])

    @command("bankaiichigo", required=OWNER)
    async def bankaiichigo_cmd(self, event):
        """Отправить голосовое: Банкай Ичиго"""
        await self._send_voice(event, _VOICES["bankaiichigo"][0])
