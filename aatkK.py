# meta developer: @cybernacist
# Адаптация под Kitsune @Mikasu32
__version__ = (3, 1, 5)

import asyncio
import re
import regex
from telethon.tl.types import Message

from ..core.loader import KitsuneModule, command, watcher, ModuleConfig, ConfigValue
from ..core.security import OWNER
from .. import utils
from .. import validators


class aatkK(KitsuneModule):
    name        = "aatkK"
    description = "авто атака боссов"
    author      = "@cybernacist | Kitsune-адаптация: @Mikasu32"
    version     = "3.1.5"
    icon        = "⚔️"
    category    = "evo"

    pip_requires = ["regex"]

    DB_PREFIX = "kitsune.config"

    BOSS_BOT_ID = 5522271758

    ANCHOR_WORDS = ("Атаковать", "Обновить", "Получить", "К боссам")

    OPTIONS = {
        "atkspeeds": {
            "title": "⏱ Задержка (наземные)",
            "hint": "✍️ Введи задержку атаки для наземных боссов (в секундах)",
            "unit": "сек",
            "kind": "float",
        },
        "atkspeedl": {
            "title": "🕊 Задержка (летающие)",
            "hint": "✍️ Введи задержку атаки для летающих боссов (в секундах)",
            "unit": "сек",
            "kind": "float",
        },
        "minhp": {
            "title": "❤️ Порог хп",
            "hint": "✍️ Введи минимальное здоровье для ухода в отхил (в хп)",
            "unit": "хп",
            "kind": "int",
        },
        "atkcd": {
            "title": "⏳ Время отхила",
            "hint": "✍️ Введи задержку на отхил (в секундах)",
            "unit": "сек",
            "kind": "float",
        },
        "repairhits": {
            "title": "🔨 Ударов до починки",
            "hint": "✍️ Введи кол-во ударов до автопочинки (в ударах)",
            "unit": "уд",
            "kind": "int",
        },
        "lgun": {
            "title": "🏹 Дальнее оружие",
            "hint": "✍️ Введи эмодзи дальнобойного оружия через запятую",
            "unit": "",
            "kind": "list",
        },
        "sgun": {
            "title": "⛏ Ближнее оружие",
            "hint": "✍️ Введи эмодзи ближнего оружия через запятую",
            "unit": "",
            "kind": "list",
        },
    }

    TOGGLES = {
        "repairstatus": "🧰 Автопочинка",
        "returntoboss": "🔁 Возврат к боссам",
        "achangegun": "🔀 Смена оружия",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue("atkspeeds", 1.05, "Задержка атаки (для стандартных)", validator=validators.Float()),
            ConfigValue("atkspeedl", 4.75, "Задержка атаки (для летающих)", validator=validators.Float()),
            ConfigValue("minhp", 300, "Минимальное здоровье для ухода в отхил (в хп)", validator=validators.Integer()),
            ConfigValue("atkcd", 60.0, "Задержка на отхил (в секундах)", validator=validators.Float()),
            ConfigValue("repairhits", 400, "Кол-во ударов до автопочинки (в ударах)", validator=validators.Integer()),
            ConfigValue("repairstatus", False, "Статус автопочинки", validator=validators.Boolean()),
            ConfigValue("returntoboss", True, "Авто-возврат к боссам", validator=validators.Boolean()),
            ConfigValue("achangegun", False, "Сменять оружие для летающих и назад на наземных", validator=validators.Boolean()),
            ConfigValue("lgun", ["🏹", "🏹"], "Эмодзи дальнобойного(второстепенного) оружия для смены", validator=validators.Series(validators.String())),
            ConfigValue("sgun", ["⛏", "⛏️"], "Эмодзи ближнего(основного) оружия для смены", validator=validators.Series(validators.String())),
        )
        self.bossik_message_id = None
        self.chat_id = None
        self.task = None
        self.stop = False
        self.aatkstatus = True
        self.lbossi = {"🦇", "🐦‍🔥", "👻", "🐉", "🐲", "👾", "👽", "🛸", "🛰"}
        self.attacks = 0
        self._clicks = set()

    async def on_load(self) -> None:
        pass

    async def on_unload(self) -> None:
        self.stop = True
        task = self.task
        self.task = None
        if task and not task.done():
            task.cancel()
        for click in list(self._clicks):
            if not click.done():
                click.cancel()
        self._clicks.clear()

    def _inline(self):
        return getattr(self.client, "_kitsune_inline", None)

    async def _save(self, key: str) -> None:
        try:
            await self.db.set(f"{self.DB_PREFIX}.{self.name.lower()}", key, self.config[key])
        except Exception:
            return
        try:
            await self.db.force_save()
        except Exception:
            pass

    def _fmt(self, key: str) -> str:
        value = self.config[key]
        if isinstance(value, bool):
            return "включено" if value else "выключено"
        if isinstance(value, list):
            return ", ".join(str(v) for v in value) if value else "—"
        unit = self.OPTIONS.get(key, {}).get("unit", "")
        return f"{value} {unit}".strip()

    def _parse(self, key: str, raw: str):
        kind = self.OPTIONS.get(key, {}).get("kind", "str")
        raw = (raw or "").strip()
        if kind == "float":
            return float(raw.replace(",", "."))
        if kind == "int":
            return int(float(raw.replace(",", ".")))
        if kind == "list":
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            if not parts:
                raise ValueError("empty")
            return parts
        return raw

    def _main_text(self) -> str:
        lines = [
            f"▫️ <b>{self.OPTIONS[key]['title']}</b>: <code>{utils.escape_html(self._fmt(key))}</code>"
            for key in self.OPTIONS
        ]
        for key, title in self.TOGGLES.items():
            lines.append(f"▫️ <b>{title}</b>: <code>{self._fmt(key)}</code>")
        status = "включена" if self.aatkstatus else "выключена"
        return (
            "⚔️ <b>Настройки автоатаки</b>\n"
            f"<b>Автоатака:</b> <code>{status}</code>\n\n"
            + "\n".join(lines)
        )

    def _main_markup(self, iid: str = ""):
        rows = [
            [
                {"text": self.OPTIONS["atkspeeds"]["title"], "callback": self._cb_option, "args": ("atkspeeds",)},
                {"text": self.OPTIONS["atkspeedl"]["title"], "callback": self._cb_option, "args": ("atkspeedl",)},
            ],
            [
                {"text": self.OPTIONS["minhp"]["title"], "callback": self._cb_option, "args": ("minhp",)},
                {"text": self.OPTIONS["atkcd"]["title"], "callback": self._cb_option, "args": ("atkcd",)},
            ],
            [
                {"text": self.OPTIONS["repairhits"]["title"], "callback": self._cb_option, "args": ("repairhits",)},
                {"text": self._toggle_text("repairstatus"), "callback": self._cb_toggle, "args": ("repairstatus",)},
            ],
            [
                {"text": self._toggle_text("returntoboss"), "callback": self._cb_toggle, "args": ("returntoboss",)},
                {"text": self._toggle_text("achangegun"), "callback": self._cb_toggle, "args": ("achangegun",)},
            ],
            [
                {"text": self.OPTIONS["lgun"]["title"], "callback": self._cb_option, "args": ("lgun",)},
                {"text": self.OPTIONS["sgun"]["title"], "callback": self._cb_option, "args": ("sgun",)},
            ],
            [
                {
                    "text": f"⚔️ Автоатака: {'вкл' if self.aatkstatus else 'выкл'}",
                    "callback": self._cb_aatk,
                },
                {"text": "🛑 Стоп цикл", "callback": self._cb_stop},
            ],
            [
                {"text": "♻️ Сбросить всё", "callback": self._cb_reset_all},
                {"text": "🔻 Закрыть", "callback": self._cb_close},
            ],
        ]
        return rows

    def _toggle_text(self, key: str) -> str:
        return f"{self.TOGGLES[key]}: {'вкл' if self.config[key] else 'выкл'}"

    def _option_text(self, key: str) -> str:
        meta = self.OPTIONS[key]
        return (
            f"⚙️ <b>{meta['title']}</b>\n"
            f"<i>ℹ️ {utils.escape_html(self.config.get_doc(key))}</i>\n\n"
            f"<b>Стандартное:</b> <code>{utils.escape_html(self._fmt_default(key))}</code>\n"
            f"<b>Текущее:</b> <code>{utils.escape_html(self._fmt(key))}</code>\n\n"
            f"{meta['hint']}"
        )

    def _fmt_default(self, key: str) -> str:
        default = self.config.get_default(key)
        if isinstance(default, list):
            return ", ".join(str(v) for v in default) if default else "—"
        unit = self.OPTIONS.get(key, {}).get("unit", "")
        return f"{default} {unit}".strip()

    def _option_markup(self, key: str, iid: str = ""):
        return [
            [{
                "text": "✍️ Ввести значение",
                "input": self.OPTIONS[key]["hint"],
                "handler": self._input_value,
                "args": (key, iid),
            }],
            [{"text": "♻️ Значение по умолчанию", "callback": self._cb_default, "args": (key,)}],
            [
                {"text": "👈 Назад", "callback": self._cb_main},
                {"text": "🔻 Закрыть", "callback": self._cb_close},
            ],
        ]

    async def _show_main(self, call) -> None:
        inline = self._inline()
        if inline is None:
            return
        await inline.edit(call, self._main_text(), self._main_markup(getattr(call, "inline_message_id", "")))

    async def _show_option(self, call, key: str) -> None:
        inline = self._inline()
        if inline is None:
            return
        iid = getattr(call, "inline_message_id", "") or ""
        await inline.edit(call, self._option_text(key), self._option_markup(key, iid))

    async def _cb_main(self, call) -> None:
        await self._show_main(call)

    async def _cb_option(self, call, key: str) -> None:
        await self._show_option(call, key)

    async def _cb_toggle(self, call, key: str) -> None:
        self.config[key] = not self.config[key]
        await self._save(key)
        await self._show_main(call)

    async def _cb_aatk(self, call) -> None:
        self.aatkstatus = not self.aatkstatus
        await self._show_main(call)

    async def _cb_stop(self, call) -> None:
        self.stop = True
        if self.task and not self.task.done():
            self.task.cancel()
        try:
            await call.answer("Атака остановлена", show_alert=False)
        except Exception:
            pass
        await self._show_main(call)

    async def _cb_default(self, call, key: str) -> None:
        self.config[key] = self.config.get_default(key)
        await self._save(key)
        await self._show_option(call, key)

    async def _cb_reset_all(self, call) -> None:
        for key in self.config.keys():
            self.config[key] = self.config.get_default(key)
            await self._save(key)
        try:
            await call.answer("Настройки сброшены", show_alert=False)
        except Exception:
            pass
        await self._show_main(call)

    async def _cb_close(self, call) -> None:
        try:
            await call._edit("✖️")
        except Exception:
            pass

    async def _input_value(self, call, query: str, key: str, iid: str = "") -> None:
        inline = self._inline()
        if inline is None:
            return
        try:
            self.config[key] = self._parse(key, query)
        except (ValueError, TypeError, validators.ValidationError):
            text = self._option_text(key) + "\n\n❌ <b>Некорректное значение</b>"
            target_iid = iid or getattr(call, "inline_message_id", "") or ""
            if target_iid:
                await inline.edit(call, text, self._option_markup(key, target_iid), inline_message_id=target_iid)
            else:
                await inline.edit(call, text, self._option_markup(key))
            return
        await self._save(key)
        target_iid = iid or getattr(call, "inline_message_id", "") or ""
        if target_iid:
            await inline.edit(call, self._option_text(key), self._option_markup(key, target_iid), inline_message_id=target_iid)
        else:
            await inline.edit(call, self._option_text(key), self._option_markup(key))

    @command("aatk", required=OWNER)
    async def aatk_cmd(self, event) -> None:
        """включить/выключить автоатаку"""
        m = event.message
        self.aatkstatus = not self.aatkstatus
        status = "включена" if self.aatkstatus else "выключена"
        await m.edit(f"Автоатака {status}")

    @command("aatkstop", required=OWNER)
    async def aatkstop_cmd(self, event) -> None:
        """принудительно остановить цикл атаки"""
        m = event.message
        self.stop = True
        if self.task and not self.task.done():
            self.task.cancel()
        await m.edit("Атака остановлена")

    @command("aasettings", required=OWNER, aliases=["aacfg"])
    async def aasettings_cmd(self, event) -> None:
        """меню настроек автоатаки"""
        m = event.message
        inline = self._inline()
        if inline is None or not getattr(inline, "_bot", None):
            await utils.answer(
                m,
                "❌ <b>Inline-менеджер недоступен.</b>\nНастрой бота через <code>.setbot</code>",
            )
            return
        await utils.answer(m, "⚔️ <b>Загрузка...</b>")
        await inline.form(self._main_text(), m, self._main_markup())

    @watcher(no_commands=True)
    async def aatk_watcher(self, event) -> None:
        message: Message = event.message
        if not self.aatkstatus:
            return
        if not isinstance(message, Message) or not message.raw_text:
            return
        if message.chat_id == self.BOSS_BOT_ID and ("Выбери босса" in message.raw_text or "Босс" in message.raw_text):
            self.bossik_message_id = message.id
            self.chat_id = message.chat_id
            self.stop = False
            self._ensure_loop()
        if message.chat_id == self.BOSS_BOT_ID and "💞 Здоровье полностью восстановлено" in message.raw_text:
            try:
                await message.delete()
            except Exception:
                pass

    def _ensure_loop(self) -> None:
        if self.task and not self.task.done():
            return
        self.task = asyncio.ensure_future(self.attack_loop())
        self.task.add_done_callback(self._loop_done)

    def _loop_done(self, task) -> None:
        if self.task is task:
            self.task = None
        if task.cancelled():
            return
        try:
            task.exception()
        except Exception:
            pass

    def _forget_click(self, task) -> None:
        self._clicks.discard(task)
        if task.cancelled():
            return
        try:
            task.exception()
        except Exception:
            pass

    async def _click(self, button, timeout: float) -> bool:
        try:
            task = asyncio.ensure_future(button.click())
        except Exception:
            return False
        self._clicks.add(task)
        task.add_done_callback(self._forget_click)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            return True
        except Exception:
            return False
        return True

    @staticmethod
    def _buttons(message):
        try:
            return message.buttons or []
        except Exception:
            return []

    def _find_button(self, message, *words):
        for row in self._buttons(message):
            for button in row:
                text = getattr(button, "text", "") or ""
                if any(word in text for word in words):
                    return button
        return None

    def _is_anchor(self, message) -> bool:
        return self._find_button(message, *self.ANCHOR_WORDS) is not None

    async def _get_message(self, message_id):
        if not message_id or self.chat_id is None:
            return None
        try:
            msg = await self.client.get_messages(self.chat_id, ids=message_id)
        except Exception:
            return None
        if not msg or getattr(msg, "empty", False):
            return None
        return msg

    async def _relocate(self):
        if self.chat_id is None:
            return None
        try:
            messages = await self.client.get_messages(self.chat_id, limit=20)
        except Exception:
            return None
        for msg in messages or []:
            if not msg or getattr(msg, "empty", False):
                continue
            if not self._is_anchor(msg):
                continue
            self.bossik_message_id = msg.id
            return msg
        return None

    async def _boss_message(self):
        msg = await self._get_message(self.bossik_message_id)
        if msg is not None:
            return msg
        return await self._relocate()

    async def _reward_message(self, fallback_id):
        if self.chat_id is None:
            return None
        try:
            messages = await self.client.get_messages(self.chat_id, limit=3)
        except Exception:
            messages = []
        for msg in messages or []:
            if msg and "Награда получена:" in (msg.raw_text or ""):
                return msg
        return await self._get_message(fallback_id)

    async def _handle_reward(self, msg) -> None:
        button = self._find_button(msg, "Получить")
        if button is not None:
            await self._click(button, 1)
            await asyncio.sleep(1)
        source = await self._reward_message(msg.id)
        if source is None:
            return
        self.bossik_message_id = source.id
        if not self.config["returntoboss"]:
            return
        back = self._find_button(source, "К боссам")
        if back is None:
            return
        await self._click(back, 1)
        await asyncio.sleep(1)

    async def attack_loop(self):
        misses = 0
        try:
            while not self.stop:
                if not self.aatkstatus:
                    return
                boss_emoji = None
                try:
                    msg = await self._boss_message()
                    if msg is None:
                        misses += 1
                        await asyncio.sleep(0.5 if misses < 10 else min(5.0, 0.5 * misses))
                        continue
                    misses = 0
                    raw_text = msg.raw_text or ""
                    if "Твоя статистика боя" in raw_text:
                        await asyncio.sleep(0.5)
                        await self._handle_reward(msg)
                        continue
                    health_match = re.search(r"(?:❤\s*)?(?:Твоё здоровье|Ты)\s*:\s*([\d,.]+)", raw_text, flags=re.IGNORECASE)
                    if health_match:
                        health_str = health_match.group(1).replace(",", "")
                        health = int(float(health_str))
                        if health <= self.config["minhp"]:
                            await asyncio.sleep(self.config["atkcd"])
                            msg = await self._boss_message()
                            if msg is None:
                                continue
                            refresh = self._find_button(msg, "Обновить")
                            if refresh is not None:
                                await self._click(refresh, 0.3)
                            continue
                    attack = self._find_button(msg, "Атаковать")
                    if attack is not None:
                        full_text = getattr(attack, "text", "") or ""
                        gun_emoji = full_text.split()[0] if full_text else ""
                        boss_emoji_match = regex.match(r"(\X)", raw_text)
                        boss_emoji = boss_emoji_match.group(1) if boss_emoji_match else None
                        if self.config["achangegun"]:
                            if boss_emoji in self.lbossi and gun_emoji not in self.config["lgun"]:
                                await self.change_gun(lgun=True, emoji=boss_emoji)
                            elif boss_emoji not in self.lbossi and gun_emoji not in self.config["sgun"]:
                                await self.change_gun(lgun=False, emoji=boss_emoji)
                        await self._click(attack, 0.1)
                        self.attacks += 1
                    if self.config["repairstatus"] and self.attacks >= self.config["repairhits"]:
                        self.attacks = 0
                        await self.repair_ekip()
                    atk_cd = self.config["atkspeedl"] if boss_emoji in self.lbossi else self.config["atkspeeds"]
                    await asyncio.sleep(atk_cd)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await asyncio.sleep(self.config["atkspeeds"])
        except asyncio.CancelledError:
            pass

    async def repair_ekip(self):
        try:
            await self.client.send_message(self.chat_id, "экип")
            reply = None
            for _ in range(5):
                messages = await self.client.get_messages(self.chat_id, limit=5)
                for msg in messages:
                    if msg.raw_text and "🧰" in msg.raw_text and "Экипировка" in msg.raw_text:
                        reply = msg
                        break
                if reply:
                    break
                await asyncio.sleep(1)
            if not reply:
                return
            slots = self._find_button(reply, "Слоты")
            if slots is not None:
                await self._click(slots, 0.3)
            await asyncio.sleep(1.5)
            updated = await self._get_message(reply.id)
            if updated is not None:
                repair = self._find_button(updated, "Починить всё")
                if repair is not None:
                    await self._click(repair, 0.3)
            messages = await self.client.get_messages(self.chat_id, limit=10)
            for msg in messages:
                if msg.text == "экип" or "Это твоя активная" in (msg.raw_text or ""):
                    try:
                        await msg.delete()
                    except Exception:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def change_gun(self, lgun: bool, emoji: str = None):
        try:
            await self.client.send_message(self.chat_id, "экип")
            reply = None
            for _ in range(20):
                msgs = await self.client.get_messages(self.chat_id, limit=8)
                for m in msgs:
                    if m.raw_text and "🧰" in m.raw_text and "Экипировка" in m.raw_text:
                        reply = m
                        break
                if reply:
                    break
                await asyncio.sleep(0.5)
            if not reply:
                return
            target_list = self.config["lgun"] if lgun else self.config["sgun"]
            target_button = self._find_button(reply, *target_list)
            if target_button is None:
                self.config["achangegun"] = False
                return
            await self._click(target_button, 0.3)
            found = False
            for _ in range(20):
                updated = await self._get_message(reply.id)
                if updated is not None:
                    take = self._find_button(updated, "🖐")
                    if take is not None:
                        await self._click(take, 0.3)
                        found = True
                        break
                await asyncio.sleep(0.3)
            if not found:
                return
            await asyncio.sleep(1)
            updated = await self._get_message(reply.id)
            if updated is not None and "Чтобы надеть эту" in (updated.raw_text or ""):
                try:
                    await asyncio.wait_for(updated.click(4), timeout=0.1)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass
            messages = await self.client.get_messages(self.chat_id, limit=10)
            for msg in messages:
                if msg.text == "экип" or "Чтобы надеть эту" in (msg.raw_text or ""):
                    try:
                        await msg.delete()
                    except Exception:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
