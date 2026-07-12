# meta developer: @mm_mods
# Kitsune adaptation: native port for KitsuneX-dev userbot
# requires: toml
import html
import json
import os
import re
import toml

from kitsune.core.loader import KitsuneModule, ModuleConfig, ConfigValue, command, watcher
from kitsune.core.security import OWNER

class KLiMERPMod(KitsuneModule):

    name        = "KLiMERPMod"
    description = "Модуль слегка улучшен @trololo_1 и адаптирован под Kitsune от @Mikasu32"
    author      = "@mm_mods"
    version     = "1.3-kitsune"

    DB_NAMESPACE = "KLiMERPMod"
    LEGACY_DB_NAMESPACE = "RPMod"

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
            "🍋 <b>KLiME</b> (1.3-kitsune)\n"
            "Модуль слегка улучшен @trololo_1, адаптирован под Kitsune от @Mikasu32\n"
            "Что изменилось?\n"
            "  • Исправлены лишние HTML-теги в списке.\n"
            "  • Исправлены переносы строк в rplist.\n"
            "  • Повреждённые старые записи очищаются автоматически.\n"
            "  • Нет проверки на валидность эмодзи — добавляй кастомные.\n"
            "  • Бэкапы хранятся в TOML.\n"
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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "action_decoration",
                "normal | без стилей",
                "Декорация действия РП-команды: normal/bold/italic/underlined/strikethrough/spoiler",
            ),
            ConfigValue(
                "replica_decoration",
                "normal | без стилей",
                "Декорация реплики РП-команды: normal/bold/italic/underlined/strikethrough/spoiler",
            ),
            ConfigValue(
                "speech_bubble",
                "💬",
                "Эмодзи речевого пузыря для «с репликой»",
            ),
        )

    async def on_load(self) -> None:
        defaults = {
            "exlist": [],
            "status": 1,
            "rpnicks": {},
            "useraccept": {"chats": [], "users": []},
            "nrpcommands": {},
        }
        for key, default in defaults.items():
            if self.db.get(self.DB_NAMESPACE, key) is not None:
                continue
            legacy_value = self.db.get(self.LEGACY_DB_NAMESPACE, key)
            await self.db.set(
                self.DB_NAMESPACE,
                key,
                legacy_value if legacy_value is not None else default,
            )

        # Старые версии могли сохранить HTML-теги и переводы строк прямо
        # внутри действия/эмодзи. Они ломали HTML-разметку и переносы rplist.
        stored_commands = self.db.get(self.DB_NAMESPACE, "nrpcommands") or {}
        clean_commands = self._sanitize_commands(stored_commands)
        if clean_commands != stored_commands:
            await self.db.set(self.DB_NAMESPACE, "nrpcommands", clean_commands)

        from telethon import events as tl_events
        self.client.add_event_handler(
            self._incoming_rp_handler,
            tl_events.NewMessage(incoming=True),
        )

    async def _incoming_rp_handler(self, event) -> None:
        try:
            status   = self.db.get(self.DB_NAMESPACE, "status") or 1
            commands = self.db.get(self.DB_NAMESPACE, "nrpcommands") or {}
            ex       = self.db.get(self.DB_NAMESPACE, "exlist") or []
            nicks    = self.db.get(self.DB_NAMESPACE, "rpnicks") or {}
            user_a   = self.db.get(self.DB_NAMESPACE, "useraccept") or {"chats": [], "users": []}

            if status != 1:
                return

            message = event.message
            if not message or not message.text:
                return

            chat = await message.get_chat()
            chat_id = getattr(chat, "id", None)
            if chat_id in ex:
                return

            sender_id = message.sender_id
            allowed_users = [int(x) for x in user_a.get("users", []) if str(x).lstrip("-").isdigit()]
            allowed_chats = [int(x) for x in user_a.get("chats", []) if str(x).lstrip("-").isdigit()]
            allowed = (
                sender_id in allowed_users
                or chat_id in allowed_chats
            )
            if not allowed:
                return

            me = await self.client.get_me()

            raw = message.raw_text or message.text or ""

            dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
            prefix = dispatcher._prefix if dispatcher else "."
            if raw.startswith(prefix):
                return

            if " " in raw and "\n" not in raw:
                args = raw.split(" ", 1)[0].casefold() + " " + raw.split(" ", 1)[1]
            elif "\n" in raw:
                parts_ln = raw.split("\n", 1)
                if " " in parts_ln[0]:
                    args = (
                        parts_ln[0].split(" ", 1)[0].casefold()
                        + " "
                        + parts_ln[0].split(" ", 1)[1]
                        + "\n"
                        + parts_ln[1]
                    )
                else:
                    args = parts_ln[0].casefold() + "\n" + parts_ln[1]
            else:
                args = raw.casefold()

            lines = args.splitlines()
            tags  = lines[0].split(" ")

            if tags[-1].startswith("@"):
                mention = tags[-1][1:]
                try:
                    target = await self.client.get_entity(int(mention) if mention.isdigit() else mention)
                except Exception:
                    return
                lines[0] = lines[0].rsplit(" ", 1)[0]
            else:
                reply = await message.get_reply_message()
                if not reply:
                    return
                try:
                    target = await self.client.get_entity(reply.sender_id)
                except Exception:
                    return

            detail = lines[0].split(" ", maxsplit=1)
            if len(detail) < 2:
                detail.append(" ")

            cmd_key = detail[0]
            if cmd_key not in commands:
                return

            cmd_data = commands[cmd_key]

            sender_entity = await self.client.get_entity(sender_id)
            actor_nick  = nicks.get(str(sender_id), sender_entity.first_name)
            target_nick = nicks.get(str(target.id), target.first_name)

            o1, c1 = self._decor_tags(self.config["action_decoration"])
            o2, c2 = self._decor_tags(self.config["replica_decoration"])
            bubble  = self.config["speech_bubble"]

            extra = " " + detail[1] if detail[1].strip() else ""

            text = ""
            if cmd_data[1]:
                text += html.escape(self._clean_field(cmd_data[1])) + " | "
            text += (
                f"<a href='tg://user?id={sender_id}'>{html.escape(str(actor_nick))}</a> "
                f"{o1}{html.escape(self._clean_field(cmd_data[0]))}{c1} "
                f"<a href='tg://user?id={target.id}'>{html.escape(str(target_nick))}</a>"
                f"{html.escape(extra)}"
            )

            if len(lines) >= 2:
                replica = "\n".join(lines[1:])
                text += (
                    f"\n{html.escape(str(bubble))} {self.strings('with-replica')} "
                    f"{o2}{html.escape(replica)}{c2}"
                )

            peer = await message.get_input_chat()
            await self.client.send_message(peer, text, parse_mode="html")

        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("_incoming_rp_handler error: %s", e)

    def _get_raw_args(self, event) -> str:
        text = event.message.raw_text or event.message.text or ""
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    def _decor_tags(self, style: str) -> tuple[str, str]:
        if "bold"          in style: return "<b>", "</b>"
        if "italic"        in style: return "<i>", "</i>"
        if "underline"     in style: return "<u>", "</u>"
        if "strikethrough" in style: return "<s>", "</s>"
        if "spoiler"       in style: return "<spoiler>", "</spoiler>"
        return "", ""

    @staticmethod
    def _clean_field(value) -> str:
        """Удаляет старую HTML-разметку и превращает поле в одну строку."""
        text = html.unescape(str(value or ""))
        text = re.sub(
            r"<\s*/?\s*(?:b|strong|i|em|u|s|strike|code|pre|blockquote|spoiler)\b[^>]*>",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return " ".join(text.replace("\u200b", "").split()).strip()

    def _sanitize_commands(self, commands) -> dict:
        """Нормализует структуру команд и отбрасывает повреждённые записи."""
        if not isinstance(commands, dict):
            return {}

        clean = {}
        for raw_name, raw_data in commands.items():
            if not isinstance(raw_data, (list, tuple)) or len(raw_data) < 2:
                continue
            name = self._clean_field(raw_name).casefold()
            action = self._clean_field(raw_data[0])
            emoji = self._clean_field(raw_data[1])
            if name and " " not in name and name != "all" and action:
                clean[name] = [action, emoji]
        return clean

    @command("dobrp", required=OWNER)
    async def dobrp_cmd(self, event) -> None:
        args = self._get_raw_args(event)
        dict_rp = self.db.get(self.DB_NAMESPACE, "nrpcommands") or {}

        try:
            parts = args.split("/")
            key_rp   = parts[0].strip().casefold()
            value_rp = self._clean_field(parts[1]) if len(parts) > 1 else ""

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
                emoji_rp = self._clean_field(
                    event.message.raw_text.split("/", maxsplit=2)[2]
                )
                if not emoji_rp:
                    await event.message.edit(self.strings("separator…"), parse_mode="html")
                    return
                dict_rp[key_rp] = [value_rp, emoji_rp]
                await self.db.set(self.DB_NAMESPACE, "nrpcommands", dict_rp)
                await event.message.edit(
                    self.strings("added1").format(
                        html.escape(key_rp), html.escape(emoji_rp)
                    ),
                    parse_mode="html",
                )
            else:
                dict_rp[key_rp] = [value_rp, ""]
                await self.db.set(self.DB_NAMESPACE, "nrpcommands", dict_rp)
                await event.message.edit(
                    self.strings("added2").format(html.escape(key_rp)),
                    parse_mode="html",
                )
        except Exception:
            await event.message.edit(self.strings("weresall"), parse_mode="html")

    @command("addrp", required=OWNER)
    async def addrp_cmd(self, event) -> None:
        await self.dobrp_cmd(event)

    @command("delrp", required=OWNER)
    async def delrp_cmd(self, event) -> None:
        dict_rp = self.db.get(self.DB_NAMESPACE, "nrpcommands") or {}
        key_rp  = self._get_raw_args(event).strip()

        if key_rp == "all":
            dict_rp.clear()
            await self.db.set(self.DB_NAMESPACE, "nrpcommands", dict_rp)
            await event.message.edit(self.strings("cleared"), parse_mode="html")
            return

        if not key_rp:
            await event.message.edit(self.strings("name?"), parse_mode="html")
            return

        if key_rp not in dict_rp:
            await event.message.edit(self.strings("notfound").format(key_rp), parse_mode="html")
            return

        dict_rp.pop(key_rp)
        await self.db.set(self.DB_NAMESPACE, "nrpcommands", dict_rp)
        await event.message.edit(self.strings("deleted").format(key_rp), parse_mode="html")

    @command("rptoggle", required=OWNER)
    async def rptoggle_cmd(self, event) -> None:
        status = self.db.get(self.DB_NAMESPACE, "status") or 1
        if status == 1:
            await self.db.set(self.DB_NAMESPACE, "status", 2)
            await event.message.edit(self.strings("off"), parse_mode="html")
        else:
            await self.db.set(self.DB_NAMESPACE, "status", 1)
            await event.message.edit(self.strings("on"), parse_mode="html")

    @command("rplist", required=OWNER)
    async def rplist_cmd(self, event) -> None:
        raw_commands = self.db.get(self.DB_NAMESPACE, "nrpcommands") or {}
        com = self._sanitize_commands(raw_commands)
        if com != raw_commands:
            await self.db.set(self.DB_NAMESPACE, "nrpcommands", com)

        count = len(com)
        header = f"📋 <b>РП-команды ({count}):</b>"

        if not com:
            await event.message.edit(header, parse_mode="html")
            return

        lines_html = []
        lines_plain = []
        for name, data in com.items():
            action, emoji = data
            plain_line = f"• {name} — {action}"
            if emoji:
                plain_line += f" | {emoji}"

            # Каждое динамическое поле экранируется отдельно. Так старый </b>
            # или другой пользовательский HTML не может сломать переносы Telegram.
            html_line = f"• <code>{html.escape(name)}</code> — {html.escape(action)}"
            if emoji:
                html_line += f" | {html.escape(emoji)}"

            lines_html.append(html_line)
            lines_plain.append(plain_line)

        # Без blockquote: Telegram иногда некорректно копирует длинные expandable-
        # цитаты. Обычные переводы строк сохраняют одну команду на одной строке.
        text = header + "\n\n" + "\n".join(lines_html)

        if len(text.encode("utf-16-le")) // 2 <= 4096:
            await event.message.edit(text, parse_mode="html")
        else:
            file_name = "KLiMERPList.txt"
            txt_content = f"РП-команды ({count}):\n\n" + "\n".join(lines_plain)
            with open(file_name, "w", encoding="utf-8", newline="\n") as file:
                file.write(txt_content)
            try:
                await event.message.edit(self.strings("rplist-toolong"), parse_mode="html")
                peer = await event.message.get_input_chat()
                await self.client.send_file(peer, file_name)
            finally:
                if os.path.exists(file_name):
                    os.remove(file_name)

    @command("rpnick", required=OWNER)
    async def rpnick_cmd(self, event) -> None:
        args  = self._get_raw_args(event).strip()
        reply = await event.message.get_reply_message()
        nicks = self.db.get(self.DB_NAMESPACE, "rpnicks") or {}

        if reply:
            user = await self.client.get_entity(reply.sender_id)
        else:
            user = await self.client.get_me()

        if not args:
            nicks.pop(str(user.id), None)
            await self.db.set(self.DB_NAMESPACE, "rpnicks", nicks)
            await event.message.edit(
                self.strings("nick-changed").format(user.id, user.first_name), parse_mode="html"
            )
            return

        nicks[str(user.id)] = args
        await self.db.set(self.DB_NAMESPACE, "rpnicks", nicks)
        await event.message.edit(
            self.strings("nick-changed").format(user.id, args), parse_mode="html"
        )

    @command("rpnicks", required=OWNER)
    async def rpnicks_cmd(self, event) -> None:
        nicks = self.db.get(self.DB_NAMESPACE, "rpnicks") or {}
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
        commands = self.db.get(self.DB_NAMESPACE, "nrpcommands") or {}
        file_name = "KLiMERPModBackUp.toml"

        reply = await event.message.get_reply_message()

        if not reply:
            try:
                await event.message.delete()
                peer = await event.message.get_input_chat()
                with open(file_name, "w", encoding="utf-8") as f:
                    toml.dump(commands, f)
                await self.client.send_file(peer, file_name)
                os.remove(file_name)
            except Exception as exc:
                await self.client.send_message(
                    await event.message.get_input_chat(),
                    f"<b>Ошибка:</b>\n<code>{exc}</code>",
                    parse_mode="html",
                )
            return

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

            clean_data = self._sanitize_commands(data)
            if len(clean_data) != len(data):
                await event.message.edit(self.strings("toml-minparse-failure"), parse_mode="html")
                return

            await self.db.set(self.DB_NAMESPACE, "nrpcommands", clean_data)
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
        args = self._get_raw_args(event).strip()
        ex   = self.db.get(self.DB_NAMESPACE, "exlist") or []

        if not args:
            entity = await event.message.get_chat()
            cid    = entity.id
            try:
                name = entity.title
            except AttributeError:
                name = entity.first_name
            if cid in ex:
                ex.remove(cid)
                await self.db.set(self.DB_NAMESPACE, "exlist", ex)
                await event.message.edit(
                    self.strings("chat-included").format(name), parse_mode="html"
                )
            else:
                ex.append(cid)
                await self.db.set(self.DB_NAMESPACE, "exlist", ex)
                await event.message.edit(
                    self.strings("chat-excluded").format(name), parse_mode="html"
                )
            return

        if args == "list":
            if not ex:
                await event.message.edit(self.strings("empty-exclude"), parse_mode="html")
                return
            sms = self.strings("excluded-chats")
            for cid in ex:
                try:
                    a = await self.client.get_entity(cid)
                    try:
                        name = a.title
                    except AttributeError:
                        name = a.first_name
                    sms += f"\n• <b><u>{name}</u> —</b> <code>{cid}</code>"
                except Exception:
                    sms += f"\n• <code>{cid}</code>"
            await event.message.edit(sms, parse_mode="html")
            return

        if args.lstrip("-").isdigit():
            cid = int(args)
            if cid in ex:
                ex.remove(cid)
                await self.db.set(self.DB_NAMESPACE, "exlist", ex)
                try:
                    a    = await self.client.get_entity(cid)
                    name = getattr(a, "title", None) or getattr(a, "first_name", str(cid))
                except Exception:
                    name = str(cid)
                await event.message.edit(
                    self.strings("chat-included").format(name), parse_mode="html"
                )
            else:
                try:
                    a = await self.client.get_entity(cid)
                except Exception:
                    await event.message.edit(self.strings("id-wrong"), parse_mode="html")
                    return
                ex.append(cid)
                await self.db.set(self.DB_NAMESPACE, "exlist", ex)
                name = getattr(a, "title", None) or getattr(a, "first_name", str(cid))
                await event.message.edit(
                    self.strings("chat-excluded").format(name), parse_mode="html"
                )
            return

        await event.message.edit(self.strings("s-t-wrong"), parse_mode="html")

    @command("useraccept", required=OWNER)
    async def useraccept_cmd(self, event) -> None:
        reply    = await event.message.get_reply_message()
        args     = self._get_raw_args(event).strip()
        user_a   = self.db.get(self.DB_NAMESPACE, "useraccept") or {"chats": [], "users": []}

        if args.lower() in ("-l", "л"):
            sms = self.strings("who-have")
            for k, v in user_a.items():
                sms += "\n" + self.strings("chats-s" if k == "chats" else "users-s")
                for uid in v:
                    try:
                        entity = await self.client.get_entity(int(uid))
                        name   = getattr(entity, "title", None) or getattr(entity, "first_name", str(uid))
                        sms   += f"\n• <b><u>{name}</u> —</b> <code>{uid}</code>"
                    except Exception:
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
                await self.db.set(self.DB_NAMESPACE, "useraccept", user_a)
                await event.message.edit(
                    self.strings("off-in-chat").format(chat.title), parse_mode="html"
                )
            else:
                user_a["chats"].append(cid)
                await self.db.set(self.DB_NAMESPACE, "useraccept", user_a)
                await event.message.edit(
                    self.strings("on-in-chat").format(chat.title), parse_mode="html"
                )
            return

        target_id = None
        if args.lstrip("-").isdigit():
            target_id = int(args)
        elif args.startswith("@") or (args and not args.startswith("-")):
            username = args.lstrip("@")
            try:
                entity = await self.client.get_entity(username)
                target_id = entity.id
            except Exception:
                await event.message.edit(self.strings("s-t-wrong"), parse_mode="html")
                return
        elif reply and reply.sender_id:
            target_id = int(reply.sender_id)

        if target_id is None:
            await event.message.edit(self.strings("s-t-wrong"), parse_mode="html")
            return

        target_id = int(target_id)
        norm_users = [int(x) for x in user_a["users"]]
        norm_chats = [int(x) for x in user_a["chats"]]

        if target_id in norm_users:
            user_a["users"] = [x for x in user_a["users"] if int(x) != target_id]
            await self.db.set(self.DB_NAMESPACE, "useraccept", user_a)
            await event.message.edit(
                self.strings("off-for-usr").format(target_id), parse_mode="html"
            )
        elif target_id in norm_chats:
            user_a["chats"] = [x for x in user_a["chats"] if int(x) != target_id]
            await self.db.set(self.DB_NAMESPACE, "useraccept", user_a)
            await event.message.edit(
                self.strings("off-in-chat").format(target_id), parse_mode="html"
            )
        else:
            from telethon.tl.types import Channel
            try:
                entity = await self.client.get_entity(target_id)
            except Exception:
                entity = None

            if entity and isinstance(entity, Channel):
                user_a["chats"].append(target_id)
                await self.db.set(self.DB_NAMESPACE, "useraccept", user_a)
                await event.message.edit(
                    self.strings("on-in-chat").format(target_id), parse_mode="html"
                )
            else:
                user_a["users"].append(target_id)
                await self.db.set(self.DB_NAMESPACE, "useraccept", user_a)
                await event.message.edit(
                    self.strings("on-for-usr").format(target_id), parse_mode="html"
                )

    @command("mmminfo", required=OWNER)
    async def mmminfo_cmd(self, event) -> None:
        await event.message.edit(self.strings("whatschanged"), parse_mode="html")

    @watcher()
    async def rp_watcher(self, event) -> None:
        try:
            status   = self.db.get(self.DB_NAMESPACE, "status") or 1
            commands = self.db.get(self.DB_NAMESPACE, "nrpcommands") or {}
            ex       = self.db.get(self.DB_NAMESPACE, "exlist") or []
            nicks    = self.db.get(self.DB_NAMESPACE, "rpnicks") or {}

            if status != 1:
                return

            message = event.message
            if not message or not message.text:
                return

            dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
            prefix = dispatcher._prefix if dispatcher else "."
            if message.text.startswith(prefix):
                return

            chat = await message.get_chat()
            chat_id = getattr(chat, "id", None)
            if chat_id in ex:
                return

            me = await self.client.get_me()

            sender_id = message.sender_id
            if sender_id != me.id:
                return

            raw = message.raw_text or message.text or ""

            if " " in raw and "\n" not in raw:
                args = raw.split(" ", 1)[0].casefold() + " " + raw.split(" ", 1)[1]
            elif "\n" in raw:
                parts_ln = raw.split("\n", 1)
                if " " in parts_ln[0]:
                    args = (
                        parts_ln[0].split(" ", 1)[0].casefold()
                        + " "
                        + parts_ln[0].split(" ", 1)[1]
                        + "\n"
                        + parts_ln[1]
                    )
                else:
                    args = parts_ln[0].casefold() + "\n" + parts_ln[1]
            else:
                args = raw.casefold()

            lines = args.splitlines()
            tags  = lines[0].split(" ")

            if tags[-1].startswith("@"):
                mention = tags[-1][1:]
                try:
                    if mention.isdigit():
                        target = await self.client.get_entity(int(mention))
                    else:
                        target = await self.client.get_entity(mention)
                except Exception:
                    return
                lines[0] = lines[0].rsplit(" ", 1)[0]
            else:
                reply = await message.get_reply_message()
                if not reply:
                    return
                try:
                    target = await self.client.get_entity(reply.sender_id)
                except Exception:
                    return

            detail = lines[0].split(" ", maxsplit=1)
            if len(detail) < 2:
                detail.append(" ")

            cmd_key = detail[0]
            if cmd_key not in commands:
                return

            cmd_data = commands[cmd_key]

            my_nick     = nicks.get(str(me.id),     me.first_name)
            target_nick = nicks.get(str(target.id), target.first_name)

            o1, c1 = self._decor_tags(self.config["action_decoration"])
            o2, c2 = self._decor_tags(self.config["replica_decoration"])
            bubble  = self.config["speech_bubble"]

            extra = " " + detail[1] if detail[1].strip() else ""

            text = ""
            if cmd_data[1]:
                text += html.escape(self._clean_field(cmd_data[1])) + " | "
            text += (
                f"<a href='tg://user?id={me.id}'>{html.escape(str(my_nick))}</a> "
                f"{o1}{html.escape(self._clean_field(cmd_data[0]))}{c1} "
                f"<a href='tg://user?id={target.id}'>{html.escape(str(target_nick))}</a>"
                f"{html.escape(extra)}"
            )

            if len(lines) >= 2:
                replica = "\n".join(lines[1:])
                text += (
                    f"\n{html.escape(str(bubble))} {self.strings('with-replica')} "
                    f"{o2}{html.escape(replica)}{c2}"
                )

            await message.edit(text, parse_mode="html")

        except Exception:
            pass
