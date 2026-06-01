# meta developer: @mm_mods
# Kitsune adaptation: native port for Kitsune userbot
# Оптимизировано: единый watcher, кэширование сущностей, корректный on_unload.
from __future__ import annotations

import logging
import os
import time
import typing

from kitsune.core.loader import KitsuneModule, ModuleConfig, ConfigValue, command, watcher
from kitsune.core.security import OWNER

logger = logging.getLogger(__name__)

_DB = "KRPMod"


class KRPMod(KitsuneModule):

    name        = "KLiMERPMod"
    description = "РП-команды (LIME). Оптимизированный нативный порт под Kitsune."
    author      = "@mm_mods"
    version     = "2.0-kitsune"
    icon        = "🍋"
    category    = "fun"

    pip_requires: typing.ClassVar[list[str]] = ["toml"]

    strings_ru = {
        "separator…":     "🤐 <b>Разделитель есть, а эмодзи нет.</b>",
        "name?":          "🧐 <b>Где имя РП-команды?</b>",
        "action?":        "🧐 <b>Где действие РП-команды?</b>",
        "aarf":           "🤢 <b>РП-команды не могут называться «all».</b>",
        "space":          "🤐 <b>Многословные команды не поддерживаются.</b>",
        "added1":         "🤩 <b>Команда '<code>{}</code>' добавлена с эмодзи '{}'!</b>",
        "added2":         "☺️ <b>Команда '<code>{}</code>' добавлена!</b>",
        "weresall":       "🤐 <b>Нет разделителя или вообще ничего не введено.</b>",
        "cleared":        "🍃 <b>РП-команды очищены!</b>",
        "arg?":           "🧐 <b>Где аргумент?</b>",
        "deleted":        "🗑️ <b>РП-команда <code>{}</code> удалена!</b>",
        "notfound":       "🧐 <b>Команда <code>{}</code> не найдена!</b>",
        "on":             "😀 <b>РП-команды включены!</b>",
        "off":            "😴 <b>РП-команды выключены!</b>",
        "s-t-wrong":      "😟 <b>Что-то пошло не так!</b>",
        "nick-changed":   "🏷️ <b>Ник {} сменён на <code>{}</code>!</b>",
        "count":          "📋 <b>У вас <code>{}</code> команд</b>",
        "error-with-type": "❌ <b>Ошибка: <code>{}</code></b>",
        "actualised":     "👍🏻 <b>РП-команды обновлены из бэкапа!</b>",
        "chat-excluded":  "➖ <b>Чат {} исключён!</b>",
        "chat-included":  "➕ <b>Чат {} включён!</b>",
        "id-wrong":       "🔢 <b>Неверный ID!</b>",
        "empty-exclude":  "🪁 <b>Список исключённых чатов пуст!</b>",
        "excluded-chats": "📃 <b>Исключённые чаты:</b>",
        "on-in-chat":     "📗💬 <b>РП-команды включены для участников этого чата!</b>",
        "off-in-chat":    "📕💬 <b>РП-команды выключены для участников этого чата!</b>",
        "who-have":       "📄 <b>Кто имеет доступ к РП-командам:</b>",
        "chats-s":        "💬 <b>Чаты:</b>",
        "users-s":        "👤 <b>Пользователи:</b>",
        "on-for-usr":     "📗 <b>РП-команды включены для <code>{}</code>!</b>",
        "off-for-usr":    "📕 <b>РП-команды выключены для <code>{}</code>!</b>",
        "whatschanged": (
            "🍋 <b>KLIME</b> (2.0-kitsune)\n"
            "Оптимизированный нативный порт под Kitsune.\n"
            "Что изменилось?\n"
            "  • Один watcher вместо двух обработчиков — нет двойных срабатываний.\n"
            "  • Кэш сущностей/«себя» — реакция в разы быстрее.\n"
            "  • Корректная выгрузка (on_unload).\n"
            "  • Нет ограничений и проверки эмодзи — добавляй кастомные.\n"
            "  • Бэкап в формате TOML.\n"
            "  • Настройки в config Kitsune.\n"
            "Наслаждайтесь!"
        ),
        "with-replica":   "С репликой:",
        "arg-unknown":    "🤌🏻 <b>Неизвестный аргумент!</b>",
        "done":           "✅ <b>Готово!</b>",
        "less-then-2":    "▫️ <b>Меньше 2 аргументов!</b>",
        "toml-minparse-failure": "😦 <b>Ошибка разбора TOML!</b>\nЭто точно бэкап?",
        "toml-parse-failure":    "💀 <b>Ошибка разбора TOML!</b>\nБэкап повреждён.",
        "itsnotafile":    "❌ <b>Это не файл.</b>",
        "no-nicks":       "🪁 <b>Список ников пуст!</b>",
        "rplist-toolong": (
            "📄 <b>Слишком много символов — лимит Telegram 4096.</b>\n"
            "Был создан TXT-файл со всеми РП-командами."
        ),
    }

    # Сколько секунд кэшировать резолв сущности.
    _ENTITY_CACHE_TTL = 300.0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "action_decoration",
                "normal | без стилей",
                "Декорация действия РП-команды: normal/bold/italic/underline/strikethrough/spoiler",
            ),
            ConfigValue(
                "replica_decoration",
                "normal | без стилей",
                "Декорация реплики РП-команды: normal/bold/italic/underline/strikethrough/spoiler",
            ),
            ConfigValue(
                "speech_bubble",
                "💬",
                "Эмодзи речевого пузыря для «с репликой»",
            ),
        )
        # Кэши.
        self._me_id: int | None = None
        self._me_name: str = ""
        self._entity_cache: dict[typing.Any, tuple[typing.Any, float]] = {}

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def on_load(self) -> None:
        defaults = {
            "exlist":     [],
            "status":     1,
            "rpnicks":    {},
            "useraccept": {"chats": [], "users": []},
            "nrpcommands": {},
        }
        for key, value in defaults.items():
            if self.db.get(_DB, key) is None:
                await self.db.set(_DB, key, value)

        # Прогреваем кэш «себя» один раз при загрузке.
        try:
            me = await self.client.get_me()
            self._me_id   = int(me.id)
            self._me_name = me.first_name or ""
        except Exception:
            logger.debug("KLiMERPMod: get_me() при on_load не удался", exc_info=True)

    async def on_unload(self) -> None:
        # Watcher снимается лоадером автоматически; чистим только наши кэши.
        self._entity_cache.clear()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_raw_args(self, event) -> str:
        text = event.message.raw_text or event.message.text or ""
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    @staticmethod
    def _decor_tags(style: str) -> tuple[str, str]:
        style = style or ""
        if "bold"          in style: return "<b>", "</b>"
        if "italic"        in style: return "<i>", "</i>"
        if "underline"     in style: return "<u>", "</u>"
        if "strikethrough" in style: return "<s>", "</s>"
        if "spoiler"       in style: return '<span class="tg-spoiler">', "</span>"
        return "", ""

    async def _me(self) -> tuple[int, str]:
        """Кэшированный (id, first_name) владельца."""
        if self._me_id is None:
            me = await self.client.get_me()
            self._me_id   = int(me.id)
            self._me_name = me.first_name or ""
        return self._me_id, self._me_name

    async def _resolve_entity(self, key: typing.Any):
        """Резолв сущности c кэшем TTL. Возвращает entity или None."""
        now = time.monotonic()
        cached = self._entity_cache.get(key)
        if cached is not None and now < cached[1]:
            return cached[0]
        try:
            entity = await self.client.get_entity(key)
        except Exception:
            return None
        self._entity_cache[key] = (entity, now + self._ENTITY_CACHE_TTL)
        return entity

    @staticmethod
    def _parse_rp_line(raw: str) -> list[str]:
        """Аккуратно приводит первое слово к нижнему регистру, остальное оставляет."""
        if " " in raw and "\n" not in raw:
            head, tail = raw.split(" ", 1)
            return [head.casefold() + " " + tail]
        if "\n" in raw:
            first, rest = raw.split("\n", 1)
            if " " in first:
                head, tail = first.split(" ", 1)
                first = head.casefold() + " " + tail
            else:
                first = first.casefold()
            return (first + "\n" + rest).splitlines()
        return [raw.casefold()]

    def _build_rp_text(
        self,
        actor_id: int, actor_nick: str,
        target_id: int, target_nick: str,
        cmd_data: list, detail: list[str], lines: list[str],
    ) -> str:
        o1, c1 = self._decor_tags(self.config["action_decoration"])
        o2, c2 = self._decor_tags(self.config["replica_decoration"])
        bubble = self.config["speech_bubble"]

        extra = " " + detail[1] if len(detail) > 1 and detail[1].strip() else ""

        text = ""
        if cmd_data[1]:
            text += cmd_data[1] + " | "
        text += (
            f"<a href='tg://user?id={actor_id}'>{actor_nick}</a> "
            f"{o1}{cmd_data[0]}{c1} "
            f"<a href='tg://user?id={target_id}'>{target_nick}</a>{extra}"
        )
        if len(lines) >= 2:
            replica = "\n".join(lines[1:])
            text += f"\n{bubble} {self.strings('with-replica')} {o2}{replica}{c2}"
        return text

    # ── watcher (единственный обработчик РП-сообщений) ────────────────────────

    @watcher()
    async def rp_watcher(self, event) -> None:
        """Обрабатывает и собственные исходящие РП-команды, и команды
        разрешённых пользователей (входящие). Заменяет прежние
        _incoming_rp_handler + rp_watcher, исключая двойные срабатывания."""
        try:
            if (self.db.get(_DB, "status") or 1) != 1:
                return

            message = event.message
            if not message or not message.text:
                return

            raw = (message.raw_text or message.text or "").strip()
            if not raw:
                return

            # Не реагируем на команды userbot'а.
            dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
            prefix = dispatcher._prefix if dispatcher else "."
            if raw.startswith(prefix):
                return

            commands = self.db.get(_DB, "nrpcommands") or {}
            if not commands:
                return

            ex   = self.db.get(_DB, "exlist") or []
            chat_id = getattr(message, "chat_id", None)
            if chat_id in ex:
                return

            me_id, me_name = await self._me()
            sender_id = message.sender_id

            # Определяем актора и допуск.
            if sender_id == me_id:
                actor_id, actor_name = me_id, me_name
                is_own = True
            else:
                # Чужие сообщения — только если явно разрешены.
                user_a = self.db.get(_DB, "useraccept") or {"chats": [], "users": []}
                allowed_users = {int(x) for x in user_a.get("users", []) if str(x).lstrip("-").isdigit()}
                allowed_chats = {int(x) for x in user_a.get("chats", []) if str(x).lstrip("-").isdigit()}
                if sender_id not in allowed_users and chat_id not in allowed_chats:
                    return
                sender_entity = await self._resolve_entity(sender_id)
                actor_id   = sender_id
                actor_name = getattr(sender_entity, "first_name", None) or str(sender_id)
                is_own = False

            # Разбор строки.
            lines = self._parse_rp_line(raw)
            tags  = lines[0].split(" ")

            target = None
            if tags[-1].startswith("@"):
                mention = tags[-1][1:]
                key = int(mention) if mention.isdigit() else mention
                target = await self._resolve_entity(key)
                if target is None:
                    return
                lines[0] = lines[0].rsplit(" ", 1)[0]
            else:
                reply = await message.get_reply_message()
                if not reply:
                    return
                target = await self._resolve_entity(reply.sender_id)
                if target is None:
                    return

            detail = lines[0].split(" ", maxsplit=1)
            cmd_key = detail[0]
            if cmd_key not in commands:
                return

            cmd_data = commands[cmd_key]
            nicks = self.db.get(_DB, "rpnicks") or {}
            actor_nick  = nicks.get(str(actor_id), actor_name)
            target_nick = nicks.get(str(target.id), getattr(target, "first_name", None) or str(target.id))

            text = self._build_rp_text(
                actor_id, actor_nick, target.id, target_nick,
                cmd_data, detail, lines,
            )

            if is_own:
                # Редактируем собственное сообщение.
                await message.edit(text, parse_mode="html")
            else:
                # Отправляем новое сообщение в тот же чат.
                await self.client.send_message(chat_id, text, parse_mode="html")

        except Exception:
            logger.debug("KLiMERPMod: rp_watcher error", exc_info=True)

    # ── команды ──────────────────────────────────────────────────────────────

    @command("dobrp", required=OWNER, aliases=["addrp"])
    async def dobrp_cmd(self, event) -> None:
        """*dobrp команда/действие[/эмодзи] — добавить РП-команду. Пример: *dobrp обнял/обнимает/🤗"""
        args = self._get_raw_args(event)
        dict_rp = self.db.get(_DB, "nrpcommands") or {}

        try:
            parts = args.split("/")
            key_rp   = parts[0].strip().casefold()
            value_rp = parts[1].strip() if len(parts) > 1 else ""

            if " " in key_rp:
                await event.message.edit(self.strings("space"), parse_mode="html")
                return
            if not key_rp:
                await event.message.edit(self.strings("name?"), parse_mode="html")
                return
            if not value_rp:
                await event.message.edit(self.strings("action?"), parse_mode="html")
                return
            if key_rp == "all":
                await event.message.edit(self.strings("aarf"), parse_mode="html")
                return

            if len(parts) >= 3:
                emoji_rp = "/".join(parts[2:]).strip()
                if not emoji_rp:
                    await event.message.edit(self.strings("separator…"), parse_mode="html")
                    return
                dict_rp[key_rp] = [value_rp, emoji_rp]
                await self.db.set(_DB, "nrpcommands", dict_rp)
                await event.message.edit(
                    self.strings("added1").format(key_rp, emoji_rp), parse_mode="html"
                )
            else:
                dict_rp[key_rp] = [value_rp, ""]
                await self.db.set(_DB, "nrpcommands", dict_rp)
                await event.message.edit(
                    self.strings("added2").format(key_rp), parse_mode="html"
                )
        except Exception:
            await event.message.edit(self.strings("weresall"), parse_mode="html")

    @command("delrp", required=OWNER)
    async def delrp_cmd(self, event) -> None:
        """*delrp имя — удалить РП-команду. *delrp all — удалить все."""
        dict_rp = self.db.get(_DB, "nrpcommands") or {}
        key_rp  = self._get_raw_args(event).strip().casefold()

        if key_rp == "all":
            dict_rp.clear()
            await self.db.set(_DB, "nrpcommands", dict_rp)
            await event.message.edit(self.strings("cleared"), parse_mode="html")
            return

        if not key_rp:
            await event.message.edit(self.strings("name?"), parse_mode="html")
            return

        if key_rp not in dict_rp:
            await event.message.edit(self.strings("notfound").format(key_rp), parse_mode="html")
            return

        dict_rp.pop(key_rp)
        await self.db.set(_DB, "nrpcommands", dict_rp)
        await event.message.edit(self.strings("deleted").format(key_rp), parse_mode="html")

    @command("rptoggle", required=OWNER)
    async def rptoggle_cmd(self, event) -> None:
        """*rptoggle — включить/выключить обработку РП-команд глобально."""
        status = self.db.get(_DB, "status") or 1
        if status == 1:
            await self.db.set(_DB, "status", 2)
            await event.message.edit(self.strings("off"), parse_mode="html")
        else:
            await self.db.set(_DB, "status", 1)
            await event.message.edit(self.strings("on"), parse_mode="html")

    @command("rplist", required=OWNER)
    async def rplist_cmd(self, event) -> None:
        """*rplist — показать список всех сохранённых РП-команд."""
        com = self.db.get(_DB, "nrpcommands") or {}
        count = len(com)
        header = self.strings("count").format(count)

        if not com:
            await event.message.edit(header, parse_mode="html")
            return

        lines_html, lines_plain = [], []
        for nm, data in com.items():
            action, emoji = data[0], data[1]
            if emoji:
                lines_html.append(f"• <b><code>{nm}</code> — {action} |</b> {emoji}")
                lines_plain.append(f"• {nm} — {action} | {emoji}")
            else:
                lines_html.append(f"• <b><code>{nm}</code> — {action}</b>")
                lines_plain.append(f"• {nm} — {action}")

        text = header + "\n<blockquote expandable>" + "\n".join(lines_html) + "</blockquote>"

        if len(text) <= 4096:
            await event.message.edit(text, parse_mode="html")
            return

        file_name = "RPList.txt"
        txt_content = f"РП-команды ({count}):\n\n" + "\n".join(lines_plain)
        try:
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(txt_content)
            await event.message.edit(self.strings("rplist-toolong"), parse_mode="html")
            peer = await event.message.get_input_chat()
            await self.client.send_file(peer, file_name)
        finally:
            if os.path.exists(file_name):
                os.remove(file_name)

    @command("rpnick", required=OWNER)
    async def rpnick_cmd(self, event) -> None:
        """*rpnick ник — задать РП-псевдоним себе (или реплай на юзера). Без аргумента — сбросить."""
        args  = self._get_raw_args(event).strip()
        reply = await event.message.get_reply_message()
        nicks = self.db.get(_DB, "rpnicks") or {}

        if reply:
            user = await self._resolve_entity(reply.sender_id)
            if user is None:
                await event.message.edit(self.strings("s-t-wrong"), parse_mode="html")
                return
        else:
            user = await self.client.get_me()

        if not args:
            nicks.pop(str(user.id), None)
            await self.db.set(_DB, "rpnicks", nicks)
            await event.message.edit(
                self.strings("nick-changed").format(user.id, user.first_name), parse_mode="html"
            )
            return

        nicks[str(user.id)] = args
        await self.db.set(_DB, "rpnicks", nicks)
        await event.message.edit(
            self.strings("nick-changed").format(user.id, args), parse_mode="html"
        )

    @command("rpnicks", required=OWNER)
    async def rpnicks_cmd(self, event) -> None:
        """*rpnicks — показать все заданные РП-псевдонимы."""
        nicks = self.db.get(_DB, "rpnicks") or {}
        if not nicks:
            await event.message.edit(self.strings("no-nicks"), parse_mode="html")
            return
        lines = "\n".join(
            f"• <code>{uid}</code> — <b>{nick}</b>"
            for uid, nick in nicks.items()
        )
        await event.message.edit(lines, parse_mode="html")

    @command("rpback", required=OWNER)
    async def rpback_cmd(self, event) -> None:
        """*rpback — выгрузить бэкап РП-команд в TOML. Реплай на файл — восстановить из бэкапа."""
        import toml
        commands = self.db.get(_DB, "nrpcommands") or {}
        file_name = "KLiMERPModBackUp.toml"
        reply = await event.message.get_reply_message()

        # Без реплики — выгружаем бэкап.
        if not reply:
            try:
                peer = await event.message.get_input_chat()
                await event.message.delete()
                with open(file_name, "w", encoding="utf-8") as f:
                    toml.dump(commands, f)
                await self.client.send_file(peer, file_name)
            except Exception as exc:
                try:
                    peer = await event.message.get_input_chat()
                    await self.client.send_message(
                        peer, f"<b>Ошибка:</b>\n<code>{exc}</code>", parse_mode="html"
                    )
                except Exception:
                    pass
            finally:
                if os.path.exists(file_name):
                    os.remove(file_name)
            return

        # С репликой — восстанавливаем из файла.
        try:
            if not reply.document:
                await event.message.edit(self.strings("itsnotafile"), parse_mode="html")
                return
            await reply.download_media(file_name)
            with open(file_name, "r", encoding="utf-8") as f:
                try:
                    data = toml.load(f)
                except toml.TomlDecodeError:
                    await event.message.edit(self.strings("toml-parse-failure"), parse_mode="html")
                    return

            for key in data:
                if not isinstance(data[key], list) or len(data[key]) != 2:
                    await event.message.edit(self.strings("toml-minparse-failure"), parse_mode="html")
                    return

            await self.db.set(_DB, "nrpcommands", data)
            await event.message.edit(self.strings("actualised"), parse_mode="html")
        except Exception as exc:
            await event.message.edit(
                self.strings("error-with-type").format(exc), parse_mode="html"
            )
        finally:
            if os.path.exists(file_name):
                os.remove(file_name)

    @command("rpblock", required=OWNER)
    async def rpblock_cmd(self, event) -> None:
        """*rpblock — исключить/включить текущий чат из РП. *rpblock ID — по ID. *rpblock list — список."""
        args = self._get_raw_args(event).strip()
        ex   = self.db.get(_DB, "exlist") or []

        if not args:
            entity = await event.message.get_chat()
            cid    = entity.id
            name   = getattr(entity, "title", None) or getattr(entity, "first_name", str(cid))
            if cid in ex:
                ex.remove(cid)
                await self.db.set(_DB, "exlist", ex)
                await event.message.edit(self.strings("chat-included").format(name), parse_mode="html")
            else:
                ex.append(cid)
                await self.db.set(_DB, "exlist", ex)
                await event.message.edit(self.strings("chat-excluded").format(name), parse_mode="html")
            return

        if args == "list":
            if not ex:
                await event.message.edit(self.strings("empty-exclude"), parse_mode="html")
                return
            sms = self.strings("excluded-chats")
            for cid in ex:
                a = await self._resolve_entity(cid)
                if a is not None:
                    name = getattr(a, "title", None) or getattr(a, "first_name", str(cid))
                    sms += f"\n• <b><u>{name}</u> —</b> <code>{cid}</code>"
                else:
                    sms += f"\n• <code>{cid}</code>"
            await event.message.edit(sms, parse_mode="html")
            return

        if args.lstrip("-").isdigit():
            cid = int(args)
            if cid in ex:
                ex.remove(cid)
                await self.db.set(_DB, "exlist", ex)
                a = await self._resolve_entity(cid)
                name = (getattr(a, "title", None) or getattr(a, "first_name", str(cid))) if a else str(cid)
                await event.message.edit(self.strings("chat-included").format(name), parse_mode="html")
            else:
                a = await self._resolve_entity(cid)
                if a is None:
                    await event.message.edit(self.strings("id-wrong"), parse_mode="html")
                    return
                ex.append(cid)
                await self.db.set(_DB, "exlist", ex)
                name = getattr(a, "title", None) or getattr(a, "first_name", str(cid))
                await event.message.edit(self.strings("chat-excluded").format(name), parse_mode="html")
            return

        await event.message.edit(self.strings("s-t-wrong"), parse_mode="html")

    @command("useraccept", required=OWNER)
    async def useraccept_cmd(self, event) -> None:
        """*useraccept — разрешить/запретить чату или юзеру (реплай/@id) запускать РП. -l — список."""
        reply    = await event.message.get_reply_message()
        args     = self._get_raw_args(event).strip()
        user_a   = self.db.get(_DB, "useraccept") or {"chats": [], "users": []}

        if args.lower() in ("-l", "л"):
            sms = self.strings("who-have")
            for k, v in user_a.items():
                sms += "\n" + self.strings("chats-s" if k == "chats" else "users-s")
                for uid in v:
                    entity = await self._resolve_entity(int(uid))
                    if entity is not None:
                        name = getattr(entity, "title", None) or getattr(entity, "first_name", str(uid))
                        sms += f"\n• <b><u>{name}</u> —</b> <code>{uid}</code>"
                    else:
                        sms += f"\n• <code>{uid}</code>"
            await event.message.edit(sms, parse_mode="html")
            return

        if not args and not reply:
            if not event.is_group:
                await event.message.edit(self.strings("s-t-wrong"), parse_mode="html")
                return
            chat = await event.message.get_chat()
            cid  = chat.id
            if cid in user_a["chats"]:
                user_a["chats"].remove(cid)
                await self.db.set(_DB, "useraccept", user_a)
                await event.message.edit(self.strings("off-in-chat").format(chat.title), parse_mode="html")
            else:
                user_a["chats"].append(cid)
                await self.db.set(_DB, "useraccept", user_a)
                await event.message.edit(self.strings("on-in-chat").format(chat.title), parse_mode="html")
            return

        target_id = None
        if args.lstrip("-").isdigit():
            target_id = int(args)
        elif args.startswith("@") or (args and not args.startswith("-")):
            entity = await self._resolve_entity(args.lstrip("@"))
            if entity is None:
                await event.message.edit(self.strings("s-t-wrong"), parse_mode="html")
                return
            target_id = entity.id
        elif reply and reply.sender_id:
            target_id = int(reply.sender_id)

        if target_id is None:
            await event.message.edit(self.strings("s-t-wrong"), parse_mode="html")
            return

        target_id  = int(target_id)
        norm_users = [int(x) for x in user_a["users"]]
        norm_chats = [int(x) for x in user_a["chats"]]

        if target_id in norm_users:
            user_a["users"] = [x for x in user_a["users"] if int(x) != target_id]
            await self.db.set(_DB, "useraccept", user_a)
            await event.message.edit(self.strings("off-for-usr").format(target_id), parse_mode="html")
        elif target_id in norm_chats:
            user_a["chats"] = [x for x in user_a["chats"] if int(x) != target_id]
            await self.db.set(_DB, "useraccept", user_a)
            await event.message.edit(self.strings("off-in-chat").format(target_id), parse_mode="html")
        else:
            from telethon.tl.types import Channel, Chat
            entity = await self._resolve_entity(target_id)
            if entity is not None and isinstance(entity, (Channel, Chat)):
                user_a["chats"].append(target_id)
                await self.db.set(_DB, "useraccept", user_a)
                await event.message.edit(self.strings("on-in-chat").format(target_id), parse_mode="html")
            else:
                user_a["users"].append(target_id)
                await self.db.set(_DB, "useraccept", user_a)
                await event.message.edit(self.strings("on-for-usr").format(target_id), parse_mode="html")

    @command("mmminfo", required=OWNER)
    async def mmminfo_cmd(self, event) -> None:
        """*mmminfo — показать changelog и отличия KLiMERPMod от оригинала."""
        await event.message.edit(self.strings("whatschanged"), parse_mode="html")
