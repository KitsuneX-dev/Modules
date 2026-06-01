__version__ = (1, 0, 0)

# meta developer: adapted for Kitsune UserBot
# Оригинальный модуль mlimits — автоматический перевод лимитов в боте MineEvo.
# Адаптировано под Kitsune API (KitsuneModule / @command / @watcher / inline-менеджер).

import asyncio
import contextlib
import inspect
import logging
import re

from telethon import errors, functions
from telethon.tl.types import ChatAdminRights, Message

from ..core.loader import KitsuneModule, command, watcher
from ..core.security import OWNER
from ..utils import answer, asset_channel, escape_html, get_args, get_args_raw
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)


class Kmlimits(KitsuneModule):
    """Модуль для автоматического перевода лимитов в боте MineEvo"""

    name = "Kmlimits"
    author = "adapted-for-kitsune"
    version = "1.0.0"
    icon = "💵"
    category = "games"

    # ----------------------------------------------------------------- helpers
    def _db_get(self, key, default=None):
        """Синхронное чтение из БД Kitsune (аналог hikka self.get)."""
        return self.db.get(self.name, key, default)

    async def _db_set(self, key, value):
        """Асинхронная запись в БД Kitsune (аналог hikka self.set)."""
        await self.db.set(self.name, key, value)

    def _get_prefix(self) -> str:
        dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
        return getattr(dispatcher, "_prefix", ".")

    def _get_inline(self):
        return getattr(self.client, "_kitsune_inline", None)

    @staticmethod
    def _args_split(message) -> list:
        """Аналог utils.get_args_split_by(message, ' ') из Hikka."""
        raw = get_args_raw(message)
        if not raw:
            return []
        return [p for p in raw.split(" ") if p != ""]

    # ----------------------------------------------------------------- on_load
    async def on_load(self) -> None:
        self.bb = False
        self.limitsx = False
        self.limitsxx = False

        # Инициализация значений конфига (аналог client_ready в Hikka).
        if self._db_get("dly") is None:
            await self._db_set("dly", 2.0)
        if self._db_get("ag", None) is None:
            await self._db_set("ag", False)
        if self._db_get("as", None) is None:
            await self._db_set("as", False)
        if self._db_get("fw", None) is None:
            await self._db_set("fw", False)

        # Создание рабочей группы для модуля и приглашение бота MineEvo.
        try:
            self._backup_channel, _ = await asset_channel(
                self.client,
                "mlimits",
                silent=True,
                archive=True,
                megagroup=True,
                description="Группа для работы модуля Kmlimits",
                db=self.db,
            )
        except Exception:
            logger.exception("Kmlimits: не удалось создать рабочий канал")
            self._backup_channel = None

        if self._backup_channel:
            with contextlib.suppress(Exception):
                await self.client(
                    functions.channels.InviteToChannelRequest(
                        self._backup_channel, ["@mine_evo_bot"]
                    )
                )
            with contextlib.suppress(Exception):
                await self.client(
                    functions.channels.EditAdminRequest(
                        channel=self._backup_channel,
                        user_id="@mine_evo_bot",
                        admin_rights=ChatAdminRights(
                            ban_users=True,
                            post_messages=True,
                            edit_messages=True,
                        ),
                        rank="EVO",
                    )
                )

    # ----------------------------------------------------------------- commands
    @command("mlp", required=OWNER)
    async def mlp_cmd(self, event):
        """- Перевод лимитов\n[ник игрока] [количество лимитов]"""
        message = event.message
        args = self._args_split(message)
        prefix = escape_html(self._get_prefix())
        fn = "mlp"
        cmd = f"{prefix}{fn}"
        if args:
            cmd = f"{prefix}{fn} {get_args_raw(message)}"

        if len(args) == 1:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nВведите количество лимитов</b>",
            )
        if not args:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nВведите ник игрока и и количество лимитов</b>",
            )
        if len(args) > 2:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nВы ввели слишком много аргументов</b>",
            )
        if len(args) == 2:
            player = args[0]
            await self._db_set("args1", args[1])
            await self._db_set("player", player)
            try:
                limits = int(args[1])
            except ValueError:
                await answer(
                    message,
                    f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nКоличество лимитов должно быть числом</b>",
                )
                return
            await self._db_set("limitsf", args[1])
            limitp = self._db_get("Sum", None)
            limitsf = self._db_get("limitsf")
            if limitp is None:
                await answer(
                    message,
                    f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nУстановите сумму для проверки лимита</b>",
                )
            else:
                limitsr = 0
                self.limitsx = True
                await asyncio.sleep(1)
                with contextlib.suppress(Exception):
                    await self.client.send_message(
                        "@mine_evo_bot", f"Перевести {player} {limitp}"
                    )
                await answer(
                    message,
                    f"<emoji document_id=5215239948420003628>💵</emoji> <b>Начинаю перевод лимитов игроку</b> <code>{player}</code> <b>:</b> {limits}",
                )
                if self.limitsx:
                    while self.limitsx:
                        dly = self._db_get("dly")
                        limits -= 1
                        limitsr += 1
                        limitss = self._db_get("limitss", "")
                        await self._db_set("limitsr", limitsr)
                        if limits == 0:
                            self.limitsx = False
                        try:
                            await self.client.send_message(
                                "mlimits", f"Перевести {player} {limitss}"
                            )
                            await asyncio.sleep(dly)
                        except errors.FloodWaitError as f:
                            self.limitsx = False
                            see = f.seconds + 5
                            if self._db_get("fw"):
                                await asyncio.sleep(see)
                                await self._mcon_run(message)

                    if limits <= 0:
                        await answer(
                            message,
                            f"<emoji document_id=5332533929020761310>✅</emoji> <b>Все лимиты игроку <code>{player}</code> переведены:</b> <code>{limitsf}</code>",
                        )
                    limits = args[1]
                    limmmm = int(limits) - int(limitsr)
                    await self._db_set("limmm", limmmm)
                else:
                    return

    @command("mstop", required=OWNER)
    async def mstop_cmd(self, event):
        """- Остановить перевод лимитов"""
        self.limitsx = False
        await answer(
            event.message,
            "<emoji document_id=5447644880824181073>⚠️</emoji> Вы остановили перевод лимитов",
        )

    @command("mcon", required=OWNER)
    async def mcon_cmd(self, event):
        """- Продолжить переводить лимиты после перезапуска/фв и т.д."""
        await self._mcon_run(event.message)

    async def _mcon_run(self, message):
        """Внутренняя логика продолжения перевода (используется и при FloodWait)."""
        limitsr = self._db_get("limitsr", 0)
        limitsf = self._db_get("limitsf", 0)
        player = self._db_get("player", "")
        args = self._db_get("args1", None)
        limitp = self._db_get("Sum", None)
        prefix = escape_html(self._get_prefix())
        fn = "mcon"
        cmd = f"{prefix}{fn}"
        if limitp is None:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nУстановите сумму для проверки лимита</b>",
            )
            return

        limmm = int(limitsf) - int(limitsr)
        limits = limmm
        if args:
            cmd = f"{prefix}{fn} {args}"
        if limits > 0:
            self.limitsx = True
            await asyncio.sleep(1)
            with contextlib.suppress(Exception):
                await self.client.send_message(
                    "@mine_evo_bot", f"Перевести {player} {limitp}"
                )
            with contextlib.suppress(Exception):
                await self.client.send_message(
                    message.chat_id,
                    f"<emoji document_id=5215239948420003628>💵</emoji> Продолжаю перевод лимитов игроку <code>{player}</code>\nОсталось перевести : <code>{limmm}</code>",
                    parse_mode="HTML",
                )
            while self.limitsx:
                dly = self._db_get("dly")
                limits -= 1
                limitsr += 1
                await self._db_set("limitsr", limitsr)
                if limits == 0:
                    self.limitsx = False
                limitss = self._db_get("limitss", "")
                try:
                    await self.client.send_message(
                        "mlimits", f"Перевести {player} {limitss}"
                    )
                    await asyncio.sleep(dly)
                except errors.FloodWaitError as f:
                    se = f.seconds
                    self.limitsx = False
                    see = se + 5
                    if self._db_get("fw"):
                        await asyncio.sleep(see)
                        await self._mcon_run(message)
            if limits <= 0:
                await answer(
                    message,
                    f"<emoji document_id=5332533929020761310>✅</emoji> <b>Все лимиты игроку <code>{player}</code> переведены:</b> <code>{limitsf}</code>",
                )
            limits = limmm
            limmmm = int(limits) - int(limitsr)
            await self._db_set("limmm", limmmm)
        else:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nВсе лимиты переведены</b>",
            )

    @command("lchk", required=OWNER)
    async def lchk_cmd(self, event):
        """- Посмотреть сколько осталось перевести лимитов и времени до конца перевода"""
        message = event.message
        player = self._db_get("player", "")
        limitsr = self._db_get("limitsr", 0)
        limitsf = self._db_get("limitsf", 0)
        limitsr = int(limitsf) - int(limitsr)
        dly = self._db_get("dly")
        time = limitsr * dly
        ss = int(time)
        sss = ss % 60
        mm = ss // 60
        hh = ss // 3600
        dd = ss // 86400
        ww = ss // 604800
        mmth = ss // 2592000
        y = ss // 31536000
        mmm = mm % 60
        hhh = hh % 24
        ddd = dd % 7
        www = ww % 4.28
        mmmth = mmth % 12
        y = round(y)
        mmm = round(mmm)
        sss = round(sss)
        hhh = round(hhh)
        ddd = round(ddd)
        www = round(www)
        mmmth = round(mmmth)
        mm = round(mm)
        hh = round(hh)
        dd = round(dd)
        ww = round(ww)
        mmth = round(mmth)
        if ss > 2592000:
            mmth = int(dd) / 30
        mmth = round(mmth, 1)
        if mm < 1:
            await answer(
                message,
                f"<b><emoji document_id=5215239948420003628>💵</emoji> Осталось переводить игроку <code>{player}</code> : <code>{limitsr}</code>/</b><code>{limitsf}</code>\n<emoji document_id=5981043230160981261>⏱</emoji> <b>Осталось времени</b> : <i>{sss}с.</i>",
            )
        if hh < 1 and mm > 0:
            await answer(
                message,
                f"<b><emoji document_id=5215239948420003628>💵</emoji> Осталось переводить игроку <code>{player}</code> : <code>{limitsr}</code>/</b><code>{limitsf}</code>\n<emoji document_id=5981043230160981261>⏱</emoji> <b>Осталось времени</b> : <i>{mmm}мин. {sss}с.</i>",
            )
        if dd < 1 and hh > 0:
            await answer(
                message,
                f"<b><emoji document_id=5215239948420003628>💵</emoji> Осталось переводить игроку <code>{player}</code> : <code>{limitsr}</code>/</b><code>{limitsf}</code>\n<emoji document_id=5981043230160981261>⏱</emoji> <b>Осталось времени</b> : <i>{hhh}ч. {mmm}мин. {sss}с.</i>",
            )
        if ww < 1 and dd > 0:
            await answer(
                message,
                f"<b><emoji document_id=5215239948420003628>💵</emoji> Осталось переводить игроку <code>{player}</code> : <code>{limitsr}</code>/</b><code>{limitsf}</code>\n<emoji document_id=5981043230160981261>⏱</emoji> <b>Осталось времени</b> : <i>{ddd}д. {hhh}ч. {mmm}мин. {sss}с.</i>",
            )
        if mmth < 1 and ww > 0:
            await answer(
                message,
                f"<b><emoji document_id=5215239948420003628>💵</emoji> Осталось переводить игроку <code>{player}</code> : <code>{limitsr}</code>/</b><code>{limitsf}</code>\n<emoji document_id=5981043230160981261>⏱</emoji> <b>Осталось времени</b> : <i>{www}нед. {ddd}д. {hhh}ч. {mmm}мин. {sss}с.</i>",
            )
        if y < 1 and mmth > 0:
            await answer(
                message,
                f"<b><emoji document_id=5215239948420003628>💵</emoji> Осталось переводить игроку <code>{player}</code> : <code>{limitsr}</code>/</b><code>{limitsf}</code>\n<emoji document_id=5981043230160981261>⏱</emoji> <b>Осталось времени</b> : <i>{mmmth}мес. {www}нед. {ddd}д. {hhh}ч. {mmm}мин. {sss}с.</i>",
            )
        if y > 0:
            await answer(
                message,
                f"<b><emoji document_id=5215239948420003628>💵</emoji> Осталось переводить игроку <code>{player}</code> : <code>{limitsr}</code>/</b><code>{limitsf}</code>\n<emoji document_id=5981043230160981261>⏱</emoji> <b>Осталось времени</b> : <i>{y}г. {mmmth}мес. {www}нед. {ddd}д. {hhh}ч. {mmm}мин. {sss}с.</i>",
            )

    # ----------------------------------------------------------------- watchers
    @watcher()
    async def lim_watcher(self, event):
        message = event.message
        try:
            if (
                getattr(message, "chat_id", None) == 5522271758
                and "можно перевести максимум" in (message.raw_text or "")
            ):
                pattern = "можно перевести максимум(.*?)$"
                match = re.search(pattern, message.raw_text, re.DOTALL)
                if match:
                    limitss = match.group(1)
                    limitsss = limitss.replace("$", "")
                    await self._db_set("limitss", limitsss)
        except Exception:
            logger.exception("Kmlimits.lim_watcher: ошибка обработки")

    @watcher()
    async def bosses_fw_watcher(self, event):
        message = event.message
        try:
            dly = self._db_get("dly")
            raw = message.raw_text or ""
            if self._db_get("as"):
                if self.limitsx:
                    if (
                        getattr(message, "chat_id", None) == 5522271758
                        and "🔶 Ты выбрал босса" in raw
                    ):
                        self.limitsx = False
                        self.bb = True
            if self._db_get("ag"):
                if self.bb:
                    if (
                        getattr(message, "chat_id", None) == 5522271758
                        and "для атаки выбери босса" in raw
                    ):
                        self.bb = False
                        await asyncio.sleep(dly)
                        await self._mcon_run(message)
        except Exception:
            logger.exception("Kmlimits.bosses_fw_watcher: ошибка обработки")

    @command("lautoset", required=OWNER)
    async def lautoset_cmd(self, event):
        """- Автоматически устанавливать лимит\n[Ник игрока] [Задержка]"""
        message = event.message
        args = self._args_split(message)
        prefix = escape_html(self._get_prefix())
        fn = "lautoset"
        cmd = f"{prefix}{fn}"
        if args:
            cmd = f"{prefix}{fn} {get_args_raw(message)}"
        if len(args) == 1:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nВведите задержку</b>",
            )
        if not args:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nВведите ник игрока и задержку</b>",
            )
        if len(args) > 2:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nВы ввели слишком много аргументов</b>",
            )
        if len(args) == 2:
            chel = args[0]
            time = args[1]
            dly = self._db_get("dly")
            limitsf = self._db_get("limitsf", None)
            limitsr = self._db_get("limitsr", None)
            try:
                limitsf = int(limitsf) - int(limitsr)
                kolvo = int(limitsf) / (int(time) / float(dly))
                kolvo = round(int(kolvo))
            except (TypeError, ValueError, ZeroDivisionError):
                await answer(
                    message,
                    f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nНекорректные данные для расчёта</b>",
                )
                return
            time = str(time)
            await self._db_set("qq", chel)
            await self._db_set("tt", time)
            limitp = self._db_get("Sum")
            self.limitsxx = True
            timee = time[-1]
            if timee in ["1"]:
                with contextlib.suppress(Exception):
                    await self.client.send_message(
                        message.peer_id,
                        f"<emoji document_id=5332533929020761310>✅</emoji> <b> Автоматическая установка лимита игроку <code>{chel}</code> раз в <code>{time}</code> секунду <code>{kolvo}</code> раз начата</b>",
                        parse_mode="HTML",
                    )
            if timee in ["2", "3", "4"]:
                with contextlib.suppress(Exception):
                    await self.client.send_message(
                        message.peer_id,
                        f"<emoji document_id=5332533929020761310>✅</emoji> <b> Автоматическая установка лимита игроку <code>{chel}</code> раз в <code>{time}</code> секунды <code>{kolvo}</code> раз начата</b>",
                        parse_mode="HTML",
                    )
            if timee in ["5", "6", "7", "8", "9", "0"]:
                with contextlib.suppress(Exception):
                    await self.client.send_message(
                        message.peer_id,
                        f"<emoji document_id=5332533929020761310>✅</emoji> <b> Автоматическая установка лимита игроку <code>{chel}</code> раз в <code>{time}</code> секунд <code>{kolvo}</code> раз начата </b>",
                        parse_mode="HTML",
                    )
            time = int(time)
            if self.limitsxx:
                while self.limitsxx:
                    kolvo -= 1
                    if kolvo == 0:
                        self.limitsxx = False
                    with contextlib.suppress(Exception):
                        await self.client.send_message(
                            "@mine_evo_bot", f"Перевести {chel} {limitp}"
                        )
                    await asyncio.sleep(time)

    @command("lastop", required=OWNER)
    async def lastop_cmd(self, event):
        """Остановить автоматическую установку лимита"""
        self.limitsxx = False
        await answer(
            event.message,
            "<emoji document_id=5332533929020761310>✅</emoji> Автоматическая установка лимита остановлена",
        )

    @command("lscfg", required=OWNER, aliases=["lsc"])
    async def lscfg_cmd(self, event):
        """- Установить значение в конфиг\n[Название] [Значение]\nНе работает с параметром cmt"""
        message = event.message
        args = self._args_split(message)
        prefix = escape_html(self._get_prefix())
        fn = "lscfg"
        cmd = f"{prefix}{fn}"
        if args:
            cmd = f"{prefix}{fn} {get_args_raw(message)}"
        else:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | {cmd}\nУкажите аргументы</b>",
            )
            return
        if len(args) == 1:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | {cmd}\nВы указали только один аргумент, а нужно два</b>",
            )
            return
        if len(args) > 2:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | {cmd}\nВы указали больше двух аргументов</b>",
            )
            return
        pp = args[0]
        zz = args[1]
        if pp == "dly":
            try:
                zz = float(zz)
                await self._db_set("dly", zz)
                await answer(
                    message,
                    f"<emoji document_id=5332533929020761310>✅</emoji><b>Успешно!\nПараметр {pp} изменён на {zz}</b> ",
                )
            except ValueError:
                await answer(
                    message,
                    f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nУкажите число в значении!</b>",
                )

        if pp == "sm":
            await self._db_set("Sum", zz)
            await answer(
                message,
                f"<emoji document_id=5332533929020761310>✅</emoji><b>Успешно!\nПараметр Sum изменён на {zz}</b> ",
            )

        if pp not in ["sm", "dly"]:
            await answer(
                message,
                f"<emoji document_id=5240241223632954241>🚫</emoji><b> Ошибка | <code>{cmd}</code>\nДанного параметра не существует!</b>",
            )

    # ----------------------------------------------------------------- inline config
    def _build_main_text(self) -> str:
        dpg = (
            " ▫️ <i>Продолжать перевод лимитов после убийства босса</i>\n"
            if self._db_get("ag")
            else ""
        )
        dps = (
            " ▫️ <i>Выключать перевод лимитов во время убийства босса</i>\n"
            if self._db_get("as")
            else ""
        )
        dpf = (
            " ▫️ <i>Продолжать перевод лимитов после FloodWait</i>\n"
            if self._db_get("fw")
            else ""
        )
        dpl = "<i>Включён</i>" if self.limitsx else "<i>Выключен</i>"
        return (
            f"<emoji document_id=5981043230160981261>⏱</emoji> <b>Задержка перевода лимитов: <code>{self._db_get('dly')}</code>\n"
            f"<b><emoji document_id=5215239948420003628>💵</emoji> Сумма проверки лимита</b>: {self._db_get('Sum')}\n"
            f"<emoji document_id=5416117059207572332>➡️</emoji> Перевод лимитов: </b><i>{dpl}</i>\n"
            f"➕ <b>Дополнительные параметры:</b>\n{dpg}{dps}{dpf}"
        )

    def _build_extra_text(self) -> str:
        dpg = (
            " ▫️ <i>Продолжать перевод лимитов после убийства босса</i>\n"
            if self._db_get("ag")
            else ""
        )
        dps = (
            " ▫️ <i>Выключать перевод лимитов во время убийства босса</i>\n"
            if self._db_get("as")
            else ""
        )
        dpf = (
            " ▫️ <i>Продолжать перевод лимитов после FloodWait</i>\n"
            if self._db_get("fw")
            else ""
        )
        return f"➕ <b>Дополнительные параметры:</b>:\n{dpg}{dps}{dpf}"

    def _main_markup(self) -> list:
        return [
            [
                {"text": "⏱ Задержка перевода лимитов", "callback": self.idly},
                {"text": "💵 Сумма проверки", "callback": self.lsm},
            ],
            [{"text": "➕ Дополнительные параметры", "callback": self.iddl}],
            [{"text": "🔻 Закрыть", "action": "close"}],
        ]

    def _extra_markup(self) -> list:
        return [
            [{"text": "Перевод лимитов после убийства босса", "callback": self.ibgl}],
            [
                {
                    "text": "Выкл/не выкл перевод лимитов во время убийства босса",
                    "callback": self.ibsl,
                }
            ],
            [{"text": "Перевод лимитов после FloodWait", "callback": self.ifsl}],
            [
                {"text": "🔙 Назад", "callback": self.ibackl},
                {"text": "🔻 Закрыть", "action": "close"},
            ],
        ]

    @command("mlcfg", required=OWNER)
    async def mlcfg_cmd(self, event):
        """Конфиг модуля Kmlimits"""
        inline = self._get_inline()
        if inline is None or not getattr(inline, "_bot", None):
            await answer(
                event.message,
                "<emoji document_id=5240241223632954241>🚫</emoji> <b>Inline-менеджер недоступен. Настройте inline-бота Kitsune.</b>",
            )
            return
        await inline.form(self._build_main_text(), event.message, self._main_markup())

    async def ibackl(self, call: InlineCall):
        inline = self._get_inline()
        if inline is None:
            await call.answer("Inline недоступен.", show_alert=True)
            return
        await inline.edit(call, self._build_main_text(), self._main_markup())

    async def idly(self, call: InlineCall):
        inline = self._get_inline()
        if inline is None:
            await call.answer("Inline недоступен.", show_alert=True)
            return
        prefix = self._get_prefix()
        text = (
            self._build_main_text()
            + f"\n\n<i><emoji document_id=5452069934089641166>❓</emoji> Чтобы изменить задержку перевода лимитов напишите:\n"
            f"</i><code>{prefix}lscfg dly [задержка]</code>"
        )
        await inline.edit(call, text, self._main_markup())

    async def lsm(self, call: InlineCall):
        inline = self._get_inline()
        if inline is None:
            await call.answer("Inline недоступен.", show_alert=True)
            return
        prefix = self._get_prefix()
        text = (
            self._build_main_text()
            + f"\n\n<i><emoji document_id=5452069934089641166>❓</emoji> Чтобы изменить сумму проверки лимитов напишите:\n"
            f"</i><code>{prefix}lscfg sm [Сумма]</code>"
        )
        await inline.edit(call, text, self._main_markup())

    async def iddl(self, call: InlineCall):
        inline = self._get_inline()
        if inline is None:
            await call.answer("Inline недоступен.", show_alert=True)
            return
        await inline.edit(call, self._build_extra_text(), self._extra_markup())

    async def ibgl(self, call: InlineCall):
        await self._db_set("ag", not self._db_get("ag"))
        inline = self._get_inline()
        if inline is None:
            await call.answer("Inline недоступен.", show_alert=True)
            return
        await inline.edit(call, self._build_extra_text(), self._extra_markup())

    async def ibsl(self, call: InlineCall):
        await self._db_set("as", not self._db_get("as"))
        inline = self._get_inline()
        if inline is None:
            await call.answer("Inline недоступен.", show_alert=True)
            return
        await inline.edit(call, self._build_extra_text(), self._extra_markup())

    async def ifsl(self, call: InlineCall):
        await self._db_set("fw", not self._db_get("fw"))
        inline = self._get_inline()
        if inline is None:
            await call.answer("Inline недоступен.", show_alert=True)
            return
        await inline.edit(call, self._build_extra_text(), self._extra_markup())
