# ---------------------------------------------------------------------------------
#  🦊 Kitsune Module — Kitsune-Iris
# ---------------------------------------------------------------------------------
#  Name:        Kitsune-Iris
#  Description: Автофарминг коинов в Iris-боте + утилиты (передача, мешок).
#               Адаптировано под Kitsune @Mikasu32
#  Author:      lotosiiik, byateblan, xadjilut (adapted & optimized for Kitsune)
#  Version:     2.1.0
#  Commands:    .farmon .farmoff .farm .give .baghis .bag .irishelp
# ---------------------------------------------------------------------------------
#  🔒  Licensed under the GNU AGPLv3
# ---------------------------------------------------------------------------------
from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta

from telethon.tl.types import Message
from telethon.tl.functions.messages import (
    GetScheduledHistoryRequest,
    DeleteScheduledMessagesRequest,
)

from ..core.loader import KitsuneModule, command, watcher, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..utils import escape_html
from ..validators import Boolean

logger = logging.getLogger(__name__)

_IRIS_ID: int = 5443619563          # численный id чата Iris (для watcher'а)
_IRIS_BOT: str = "@iris_black_bot"  # бот для команд give/bag/baghis
_FARM_TEXT: str = "Фарма"
_DB_OWNER: str = "kitsune.iris"     # пространство имён в БД Kitsune


class Iris(KitsuneModule):
    name = "Kitsune-Iris"
    description = "Автофарминг коинов в Iris-боте. Адаптировано под Kitsune @Mikasu32"
    author = "lotosiiik"
    version = "2.1.0"
    icon = "🍀"
    category = "fun"

    strings_ru = {
        "farm_on": (
            "<emoji document_id=5314250708508220914>✅</emoji> "
            "<b>Автофарминг запущен.</b> <i>Первый цикл через 20 секунд...</i>"
        ),
        "farm_on_already": (
            "<emoji document_id=5325547803936572038>⏳</emoji> <i>Уже запущено.</i>"
        ),
        "farm_off": (
            "<emoji document_id=5210952531676504517>❌</emoji> "
            "<b>Автофарминг остановлен.</b>\n☢️ <b>Надюпано:</b> <code>{coins} i¢</code>"
        ),
        "farm_stat": "☢️ <b>Надюпано:</b> <code>{coins} i¢</code>",
        "give_usage": (
            "<emoji document_id=5210952531676504517>❌</emoji> "
            "<b>Использование:</b> <code>.give ириски|голд &lt;число&gt; @user [| причина]</code>"
        ),
        "give_bad_num": (
            "<emoji document_id=5210952531676504517>❌</emoji> "
            "<b>Число должно быть положительным.</b>"
        ),
        "no_target": (
            "<emoji document_id=5210952531676504517>❌</emoji> "
            "<b>Укажи получателя (@user) или ответь на сообщение.</b>"
        ),
        "timeout": (
            "<emoji document_id=5210952531676504517>❌</emoji> "
            "<b>Iris-бот не ответил вовремя.</b>"
        ),
        "help": (
            "🍀 <b>Помощь по модулю Iris</b>\n\n"
            "<code>.farmon</code> — включить автофарм\n"
            "<code>.farmoff</code> — выключить автофарм\n"
            "<code>.farm</code> — сколько нафармлено\n"
            "<code>.bag</code> — показать мешок\n"
            "<code>.baghis</code> — где побывали ириски\n"
            "<code>.give ириски|голд &lt;число&gt; @user [| причина]</code> — передать\n"
        ),
    }

    strings_en = {
        "farm_on": "<emoji document_id=5314250708508220914>✅</emoji> <b>Auto-farm started.</b>",
        "farm_on_already": "<emoji document_id=5325547803936572038>⏳</emoji> <i>Already running.</i>",
        "farm_off": "<emoji document_id=5210952531676504517>❌</emoji> <b>Auto-farm stopped.</b>\n☢️ <b>Farmed:</b> <code>{coins} i¢</code>",
        "farm_stat": "☢️ <b>Farmed:</b> <code>{coins} i¢</code>",
        "give_usage": "<b>Usage:</b> <code>.give iris|gold &lt;num&gt; @user [| reason]</code>",
        "give_bad_num": "<b>Number must be positive.</b>",
        "no_target": "<b>Specify a target (@user) or reply.</b>",
        "timeout": "<b>Iris bot didn't reply in time.</b>",
        "help": "🍀 <b>Iris module help</b> — see .farmon / .farmoff / .farm / .bag / .give",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "auto_farm",
                True,
                "Автоматически перезапускать фарм после старта userbot",
                validator=Boolean(),
            ),
        )

    # ------------------------------------------------------------------ lifecycle

    async def on_load(self) -> None:
        # Ничего вешать вручную не нужно: ответы Iris-бота ловит штатный
        # @watcher (см. on_iris_message). Раньше приходилось регистрировать
        # собственный telethon-обработчик, потому что dispatcher Kitsune
        # прогонял watcher'ы только по ИСХОДЯЩИМ сообщениям и пропускал
        # входящие ответы бота. Теперь dispatcher отдаёт watcher'ам сообщения
        # обоих направлений, поэтому хватает обычного @watcher с тегом chat_id.
        #
        # Если userbot перезапустили во время активного фарма — мягко
        # возобновляем цикл, чтобы отложенное "Фарма" не потерялось.
        if self.config and self.config["auto_farm"] and self._is_running():
            try:
                await self._schedule_farm(timedelta(seconds=20))
                logger.info("Iris: auto_farm — фарм возобновлён после перезапуска")
            except Exception:
                logger.debug("Iris: failed to resume farm on load", exc_info=True)

    # ------------------------------------------------------------------ helpers

    def _coins(self) -> int:
        return int(self.db.get(_DB_OWNER, "coins", 0))

    async def _add_coins(self, amount: int) -> None:
        await self.db.set(_DB_OWNER, "coins", self._coins() + amount)

    def _is_running(self) -> bool:
        return bool(self.db.get(_DB_OWNER, "status", False))

    async def _schedule_farm(self, delay: timedelta) -> None:
        await self.client.send_message(_IRIS_ID, _FARM_TEXT, schedule=delay)

    async def _clear_scheduled(self) -> None:
        """Удаляет наши отложенные сообщения в чате Iris (чтобы не плодить дубли)."""
        try:
            sched = await self.client(
                GetScheduledHistoryRequest(peer=_IRIS_ID, hash=0)
            )
            ids = [m.id for m in sched.messages]
            if ids:
                await self.client(
                    DeleteScheduledMessagesRequest(peer=_IRIS_ID, id=ids)
                )
        except Exception:
            logger.debug("Iris: failed to clear scheduled messages", exc_info=True)

    async def _ask_iris_bot(self, text: str) -> str:
        """Отправляет команду Iris-боту в ЛС и возвращает текст ответа."""
        async with self.client.conversation(_IRIS_BOT, timeout=30) as conv:
            msg = await conv.send_message(text)
            resp = await conv.get_response()
            await conv.mark_read()
            # подчищаем за собой, чтобы не засорять ЛС
            for m in (msg, resp):
                try:
                    await m.delete()
                except Exception:
                    pass
            return resp.text or ""

    # ------------------------------------------------------------------ commands

    @command("farmon", required=OWNER)
    async def farmon_cmd(self, event) -> None:
        """Запустить автофарминг коинов в Iris-боте. Пример: .farmon"""
        if self._is_running():
            await event.edit(self.strings("farm_on_already"), parse_mode="html")
            return
        await self.db.set(_DB_OWNER, "status", True)
        await self._schedule_farm(timedelta(seconds=20))
        await event.edit(self.strings("farm_on"), parse_mode="html")

    @command("farmoff", required=OWNER)
    async def farmoff_cmd(self, event) -> None:
        """Остановить автофарминг и показать суммарный заработок за сессию. Пример: .farmoff"""
        await self.db.set(_DB_OWNER, "status", False)
        # подчищаем отложенные "Фарма", иначе цикл перезапустится сам
        await self._clear_scheduled()
        coins = self._coins()
        if coins:
            await self.db.set(_DB_OWNER, "coins", 0)
        await event.edit(self.strings("farm_off", coins=coins), parse_mode="html")

    @command("farm", required=OWNER)
    async def farm_cmd(self, event) -> None:
        """Показать количество коинов, нафармленных за текущую сессию. Пример: .farm"""
        await event.edit(
            self.strings("farm_stat", coins=self._coins()), parse_mode="html"
        )

    @command("give", required=OWNER)
    async def give_cmd(self, event) -> None:
        """Передать ириски или голд другому пользователю. Пример: .give ириски 100 @user | причина"""
        raw = self.get_args(event).strip()
        if not raw:
            await event.edit(self.strings("give_usage"), parse_mode="html")
            return

        # отделяем причину (после "|")
        main_part, _, reason = raw.partition("|")
        reason = reason.strip()
        parts = main_part.split()

        if len(parts) < 2:
            await event.edit(self.strings("give_usage"), parse_mode="html")
            return

        kind_raw = parts[0].lower()
        if kind_raw in ("голд", "gold"):
            kind = " голд"
        elif kind_raw in ("ириски", "ирис", "iris"):
            kind = ""
        else:
            await event.edit(self.strings("give_usage"), parse_mode="html")
            return

        if not parts[1].isdigit() or int(parts[1]) <= 0:
            await event.edit(self.strings("give_bad_num"), parse_mode="html")
            return
        amount = int(parts[1])

        # получатель: из reply или из аргументов
        target: str | None = None
        if event.message.is_reply:
            replied = await event.message.get_reply_message()
            if replied and replied.sender_id:
                target = str(replied.sender_id)
        elif len(parts) >= 3:
            target = parts[2]

        if not target:
            await event.edit(self.strings("no_target"), parse_mode="html")
            return

        text = f"Передать{kind} {amount} {target}"
        if reason:
            text += f"\n{reason}"

        try:
            answer = await self._ask_iris_bot(text)
        except asyncio.TimeoutError:
            await event.edit(self.strings("timeout"), parse_mode="html")
            return
        await event.edit(escape_html(answer) or "—", parse_mode="html")

    @command("baghis", required=OWNER, aliases=["irishistory"])
    async def baghis_cmd(self, event) -> None:
        """Посмотреть историю перемещений ирисок (где побывали). Пример: .baghis. Псевдоним: .irishistory"""
        try:
            answer = await self._ask_iris_bot("где мои ириски")
        except asyncio.TimeoutError:
            await event.edit(self.strings("timeout"), parse_mode="html")
            return
        await event.edit(escape_html(answer) or "—", parse_mode="html")

    @command("bag", required=OWNER, aliases=["мешок"])
    async def bag_cmd(self, event) -> None:
        """Открыть мешок и посмотреть содержимое. Пример: .bag. Псевдоним: .мешок"""
        try:
            answer = await self._ask_iris_bot("Мешок")
        except asyncio.TimeoutError:
            await event.edit(self.strings("timeout"), parse_mode="html")
            return
        await event.edit(escape_html(answer) or "—", parse_mode="html")

    @command("irishelp", required=OWNER, aliases=["irishlp"])
    async def irishelp_cmd(self, event) -> None:
        """Показать справку по всем командам модуля Iris. Пример: .irishelp. Псевдоним: .irishlp"""
        await event.edit(self.strings("help"), parse_mode="html")

    # ------------------------------------------------------------------ watcher

    @watcher(chat_id=_IRIS_ID)
    async def on_iris_message(self, event) -> None:
        """Штатный watcher Kitsune: реагирует на сообщения в чате Iris.

        Благодаря тегу chat_id=_IRIS_ID dispatcher отдаёт сюда сообщения
        ТОЛЬКО из чата Iris и обоих направлений:
          • исходящее "Фарма" (наша отложка сработала) -> планируем след. цикл;
          • входящие ответы самого Iris-бота -> считаем коины / переносим цикл.
        Раньше входящие ответы терялись — теперь их видит штатный watcher.
        """
        message = event.message
        if not isinstance(message, Message):
            return
        if not self._is_running():
            return

        text = message.raw_text or ""

        # наша же отложенка "Фарма" сработала -> планируем следующий цикл
        if message.out and text == _FARM_TEXT:
            delay = timedelta(minutes=random.randint(1, 20))
            await self._schedule_farm(delay)
            return

        # дальше нас интересуют только входящие сообщения от самого Iris-бота
        if message.out or message.sender_id != _IRIS_ID:
            return

        if "НЕЗАЧЁТ!" in text:
            await self._handle_fail(text)
            return

        if "ЗАЧЁТ" in text or "УДАЧА" in text:
            await self._handle_reward(text)

    async def _handle_fail(self, text: str) -> None:
        """Бот сказал ждать — пересоздаём отложку с задержкой из его сообщения."""
        nums = [int(x) for x in text.split() if x.isdigit()]
        jitter = random.randint(20, 60)
        if len(nums) == 4:
            delta = timedelta(hours=nums[1], minutes=nums[2], seconds=nums[3] + jitter)
        elif len(nums) == 3:
            delta = timedelta(minutes=nums[1], seconds=nums[2] + jitter)
        elif len(nums) == 2:
            delta = timedelta(seconds=nums[1] + jitter)
        else:
            return

        # удаляем старые отложенные сообщения, чтобы не плодить дубли
        await self._clear_scheduled()
        await self._schedule_farm(delta)

    async def _handle_reward(self, text: str) -> None:
        """Парсим прибавку коинов вида '+123'."""
        for token in text.split():
            if token.startswith("+") and token[1:].isdigit():
                await self._add_coins(int(token[1:]))
                return
