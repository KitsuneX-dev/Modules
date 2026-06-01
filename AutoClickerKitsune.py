from __future__ import annotations
import asyncio
import logging
from typing import Optional

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER

logger = logging.getLogger(__name__)

_MIN_INTERVAL = 3
_MAX_INTERVAL = 86400


class AutoClickerKitsuneModule(KitsuneModule):
    name = "AutoClickerKitsune"
    description = "Автоматический клик по inline-кнопке. Адаптировал @Mikasu32"
    author = "@codrago_m, @unneyon | Kitsune by @Mikasu32"
    version = "1.0.0"
    icon = "🖱"
    category = "tools"

    strings_ru = {
        "no_reply": "❌ <b>Ответь на сообщение с inline-кнопкой!</b>",
        "no_button": "❌ <b>В сообщении нет inline-кнопок.</b>",
        "bad_args": (
            "❌ <b>Аргументы:</b> <code>.clickon &lt;интервал_сек&gt; "
            "[строка] [колонка]</code>\n"
            "Например: <code>.clickon 30 0 0</code>"
        ),
        "bad_interval": (
            "❌ <b>Некорректный интервал.</b> Допустимо от <code>{lo}</code> "
            "до <code>{hi}</code> секунд."
        ),
        "out_of_range": (
            "❌ <b>Кнопка вне диапазона.</b> Доступно строк: <code>{rows}</code>"
        ),
        "started": (
            "✅ <b>AutoClicker запущен!</b>\n"
            "🔁 <b>Интервал:</b> <code>{interval}</code> сек\n"
            "📍 <b>Кнопка:</b> [{line}, {item}]"
        ),
        "already": (
            "ℹ <b>AutoClicker уже работает.</b> "
            "Останови его командой <code>.clickoff</code>."
        ),
        "stopped": "🛑 <b>AutoClicker остановлен.</b>",
        "not_running": "ℹ <b>AutoClicker не запущен.</b>",
        "click_failed": (
            "⚠️ <b>AutoClicker остановлен:</b> <code>{err}</code>"
        ),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._task: Optional[asyncio.Task] = None
        self._stop_event: asyncio.Event = asyncio.Event()

    async def on_unload(self) -> None:
        await self._stop_task()

    async def _stop_task(self) -> None:
        self._stop_event.set()
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    async def _click_loop(
        self,
        chat_id: int,
        msg_id: int,
        interval: int,
        line: int,
        item: int,
    ) -> None:
        while not self._stop_event.is_set():
            try:
                msg = await self.client.get_messages(chat_id, ids=msg_id)
                if msg is None:
                    logger.info("AutoClickerKitsune: message gone, stopping")
                    return
                buttons = msg.buttons or []
                if line >= len(buttons) or item >= len(buttons[line]):
                    logger.info("AutoClickerKitsune: buttons changed, stopping")
                    return
                btn = buttons[line][item]
                await btn.click()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("AutoClickerKitsune: click error: %s", e)
                try:
                    await self.client.send_message(
                        chat_id,
                        self.strings("click_failed").format(err=str(e)[:200]),
                        parse_mode="html",
                    )
                except Exception:
                    pass
                return
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=interval,
                )
                return
            except asyncio.TimeoutError:
                continue

    @command("clickon", required=OWNER)
    async def clickon_cmd(self, event) -> None:
        """Запустить автоклик по inline-кнопке. Ответь на сообщение с кнопкой: .clickon <сек> [строка] [колонка]. Пример: .clickon 30 0 0"""
        if self._task is not None and not self._task.done():
            await event.reply(self.strings("already"), parse_mode="html")
            return

        reply = await event.message.get_reply_message()
        if reply is None:
            await event.reply(self.strings("no_reply"), parse_mode="html")
            return
        if not reply.buttons:
            await event.reply(self.strings("no_button"), parse_mode="html")
            return

        raw = self.get_args(event).strip().split()
        if not raw:
            await event.reply(self.strings("bad_args"), parse_mode="html")
            return

        try:
            interval = int(raw[0])
        except ValueError:
            await event.reply(self.strings("bad_args"), parse_mode="html")
            return

        if interval < _MIN_INTERVAL or interval > _MAX_INTERVAL:
            await event.reply(
                self.strings("bad_interval").format(
                    lo=_MIN_INTERVAL, hi=_MAX_INTERVAL,
                ),
                parse_mode="html",
            )
            return

        line = 0
        item = 0
        if len(raw) >= 2 and raw[1].lstrip("-").isdigit():
            line = max(0, int(raw[1]))
        if len(raw) >= 3 and raw[2].lstrip("-").isdigit():
            item = max(0, int(raw[2]))

        if line >= len(reply.buttons):
            await event.reply(
                self.strings("out_of_range").format(rows=len(reply.buttons)),
                parse_mode="html",
            )
            return
        if item >= len(reply.buttons[line]):
            item = 0

        chat_id = event.chat_id
        msg_id = reply.id

        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(
            self._click_loop(chat_id, msg_id, interval, line, item),
            name="AutoClickerKitsune.loop",
        )

        await event.reply(
            self.strings("started").format(
                interval=interval, line=line, item=item,
            ),
            parse_mode="html",
        )

    @command("clickoff", required=OWNER)
    async def clickoff_cmd(self, event) -> None:
        """Остановить автоклик"""
        if self._task is None or self._task.done():
            await event.reply(self.strings("not_running"), parse_mode="html")
            return
        await self._stop_task()
        await event.reply(self.strings("stopped"), parse_mode="html")
