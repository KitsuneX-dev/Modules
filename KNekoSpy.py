from __future__ import annotations

import asyncio
import contextlib
import inspect
import io
import logging
import time
import typing

from telethon import events
from telethon.tl.types import (
    Channel,
    Chat,
    DocumentAttributeAnimated,
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeSticker,
    DocumentAttributeVideo,
    Message,
    MessageMediaDocument,
    MessageMediaPhoto,
    PeerChannel,
    PeerChat,
    PeerUser,
    UpdateDeleteChannelMessages,
    UpdateDeleteMessages,
    UpdateEditChannelMessage,
    UpdateEditMessage,
    UpdateNewChannelMessage,
    UpdateNewMessage,
    User,
)

try:
    from ..core.loader import KitsuneModule, command, watcher, ConfigValue, ModuleConfig
except ImportError:
    try:
        from ..modules.loader import KitsuneModule, command, watcher, ConfigValue, ModuleConfig
    except ImportError:
        from ..loader import KitsuneModule, command, watcher, ConfigValue, ModuleConfig

try:
    from ..core.security import OWNER
except ImportError:
    from ..security import OWNER

from ..utils import escape_html, get_chat_id, get_display_name
from ..validators import Boolean, Float, Series

logger = logging.getLogger(__name__)

rei = "<emoji document_id=5409143295039252230>👩‍🎤</emoji>"

groups = "<emoji document_id=6037355667365300960>👥</emoji>"

pm = "<emoji document_id=6048540195995782913>👤</emoji>"


class KNekoSpy(KitsuneModule):
    name = "KNekoSpy"
    description = "Сохраняет удалённые и/или изменённые сообщения от выбранных пользователей (адаптировано под Kitsune @Mikasu32)"
    author = "hikarimods | Kitsune port by @Mikasu32"
    version = "1.0.32"
    icon = "👩‍🎤"
    category = "tools"

    strings_en = {
        "name": "KNekoSpy",
        "state": f"{rei} <b>Spy mode is now {{}}</b>",
        "spybl": f"{rei} <b>Current chat added to blacklist for spying</b>",
        "spybl_removed": f"{rei} <b>Current chat removed from blacklist for spying</b>",
        "spybl_clear": f"{rei} <b>Ignore list for spying cleared</b>",
        "spywl": f"{rei} <b>Current chat added to whitelist for spying</b>",
        "spywl_removed": f"{rei} <b>Current chat removed from whitelist for spying</b>",
        "spywl_clear": f"{rei} <b>Include list for spying cleared</b>",
        "whitelist": f"\n{rei} <b>Tracking only messages from:</b>\n{{}}",
        "whitelist_empty": f"\n{rei} <b>Whitelist is empty, nothing is tracked. Add a chat with</b> <code>spywl</code>",
        "always_track": f"\n{rei} <b>Always tracking messages from:</b>\n{{}}",
        "blacklist": f"\n{rei} <b>Ignoring messages from:</b>\n{{}}",
        "chat": f"{groups} <b>Tracking messages in groups</b>\n",
        "pm": f"{pm} <b>Tracking messages in personal messages</b>\n",
        "mode_off": f"{pm} <b>Not tracking messages </b><code>{{}}spymode</code>\n",
        "deleted_pm": (
            '🗑 <b><a href="{}">{}</a> deleted <a href="{message_url}">message</a> in'
            " pm. Content:</b>\n{}"
        ),
        "deleted_chat": (
            '🗑 <b><a href="{message_url}">Message</a> in chat <a href="{}">{}</a> by <a'
            ' href="{}">{}</a> has been deleted. Content:</b>\n{}'
        ),
        "edited_pm": (
            '🔏 <b><a href="{}">{}</a> edited <a href="{message_url}">message</a>'
            " in pm."
            " Old content:</b>\n{}"
        ),
        "edited_chat": (
            '🔏 <b><a href="{message_url}">Message</a> in chat <a href="{}">{}</a>'
            " by <a"
            ' href="{}">{}</a> has been edited. Old content:</b>\n{}'
        ),
        "on": "on",
        "off": "off",
        "cfg_enable_pm": "Enable spy mode in Personal messages",
        "cfg_enable_groups": "Enable spy mode in Groups",
        "cfg_whitelist": "List of chats to include messages from",
        "cfg_blacklist": "List of chats to exclude messages from",
        "cfg_always_track": (
            "List of chats to always track messages from, no matter what"
        ),
        "cfg_log_edits": "Log information about messages being edited",
        "cfg_ignore_inline": "Ignore inline messages (sent using @via bots)",
        "cfg_fw_protect": "Interval of messages sending to prevent floodwait",
        "sd_media": (
            "🔥 <b><a href='tg://user?id={}'>{}</a> sent you a self-destructing"
            " media</b>"
        ),
        "save_sd": (
            "<emoji document_id=5420315771991497307>🔥</emoji> <b>Saving"
            " self-destructing media</b>\n"
        ),
        "cfg_save_sd": "Save self-destructing media",
    }

    strings_ru = {
        "on": "включен",
        "off": "выключен",
        "state": f"{rei} <b>Режим слежения теперь {{}}</b>",
        "spybl": f"{rei} <b>Текущий чат добавлен в черный список для слежения</b>",
        "spybl_removed": (
            f"{rei} <b>Текущий чат удален из черного списка для слежения</b>"
        ),
        "spybl_clear": f"{rei} <b>Черный список для слежения очищен</b>",
        "spywl": f"{rei} <b>Текущий чат добавлен в белый список для слежения</b>",
        "spywl_removed": (
            f"{rei} <b>Текущий чат удален из белого списка для слежения</b>"
        ),
        "spywl_clear": f"{rei} <b>Белый список для слежения очищен</b>",
        "whitelist": (
            f"\n{rei} <b>Слежу только"
            " за сообщениями от пользователей / групп:</b>\n{}"
        ),
        "whitelist_empty": (
            f"\n{rei} <b>Белый список пуст, слежение ни за кем не ведётся."
            " Добавьте чат командой</b> <code>spywl</code>"
        ),
        "always_track": (
            f"\n{rei} <b>Всегда слежу за сообщениями от пользователей /"
            " групп:</b>\n{}"
        ),
        "blacklist": (
            f"\n{rei} <b>Игнорирую сообщений от пользователей / групп:</b>\n{{}}"
        ),
        "chat": f"{groups} <b>Слежу за сообщениями в группах</b>\n",
        "pm": f"{pm} <b>Слежу за сообщениями в личных сообщениях</b>\n",
        "deleted_pm": (
            '🗑 <b><a href="{}">{}</a> удалил <a href="{message_url}">сообщение</a> в'
            " личке. Содержимое:</b>\n{}"
        ),
        "deleted_chat": (
            '🗑 <b><a href="{message_url}">Сообщение</a> в чате <a href="{}">{}</a> от'
            ' <a href="{}">{}</a> было удалено. Содержимое:</b>\n{}'
        ),
        "edited_pm": (
            '🔏 <b><a href="{}">{}</a> отредактировал <a'
            ' href="{message_url}">сообщение</a> в личке. Старое содержимое:</b>\n{}'
        ),
        "edited_chat": (
            '🔏 <b><a href="{message_url}">Сообщение</a> в чате <a href="{}">{}</a> от'
            ' <a href="{}">{}</a> было отредактировано. Старое содержимое:</b>\n{}'
        ),
        "mode_off": f"{pm} <b>Не отслеживаю сообщения </b><code>{{}}spymode</code>\n",
        "cfg_enable_pm": "Включить режим шпиона в личных сообщениях",
        "cfg_enable_groups": "Включить режим шпиона в группах",
        "cfg_whitelist": "Список чатов, от которых нужно сохранять сообщения",
        "cfg_blacklist": "Список чатов, от которых нужно игнорировать сообщения",
        "cfg_always_track": (
            "Список чатов, от которых всегда следует отслеживать сообщения,"
            " несмотря ни на что"
        ),
        "cfg_log_edits": "Сохранять отредактированные сообщения",
        "cfg_ignore_inline": "Игнорировать сообщения из инлайн-режима",
        "cfg_fw_protect": "Защита от флудвейтов при пересылке",
        "cfg_save_sd": "Сохранять самоуничтожающееся медиа",
        "sd_media": (
            "🔥 <b><a href='tg://user?id={}'>{}</a> отправил вам самоуничтожающееся"
            " медиа</b>"
        ),
        "save_sd": (
            "<emoji document_id=5420315771991497307>🔥</emoji> <b>Сохраняю"
            " самоуничтожающиеся медиа</b>\n"
        ),
    }

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self._tl_channel = None
        self._channel = None
        self.config = ModuleConfig(
            ConfigValue(
                "enable_pm",
                True,
                lambda: self.strings("cfg_enable_pm"),
                validator=Boolean(),
            ),
            ConfigValue(
                "enable_groups",
                False,
                lambda: self.strings("cfg_enable_groups"),
                validator=Boolean(),
            ),
            ConfigValue(
                "whitelist",
                [],
                lambda: self.strings("cfg_whitelist"),
                validator=Series(),
            ),
            ConfigValue(
                "blacklist",
                [],
                lambda: self.strings("cfg_blacklist"),
                validator=Series(),
            ),
            ConfigValue(
                "always_track",
                [],
                lambda: self.strings("cfg_always_track"),
                validator=Series(),
            ),
            ConfigValue(
                "log_edits",
                True,
                lambda: self.strings("cfg_log_edits"),
                validator=Boolean(),
            ),
            ConfigValue(
                "ignore_inline",
                True,
                lambda: self.strings("cfg_ignore_inline"),
                validator=Boolean(),
            ),
            ConfigValue(
                "fw_protect",
                3.0,
                lambda: self.strings("cfg_fw_protect"),
                validator=Float(minimum=0.0),
            ),
            ConfigValue(
                "save_sd",
                True,
                lambda: self.strings("cfg_save_sd"),
                validator=Boolean(),
            ),
        )

        self._queue: list = []
        self._cache: dict = {}

        self._sd_seen: dict = {}
        self._sd_seen_ttl: float = 300.0

        self._media_cache: dict = {}

        self._media_cache_limit: int = 200 * 1024 * 1024
        self._media_cache_size: int = 0

        self._media_cache_max_keys: int = 500
        self._precache_tasks: set = set()

        self._precache_by_key: dict = {}
        self._next = 0
        self._threshold = 10
        self._flood_protect_sample = 60
        self._sender_task: asyncio.Task | None = None
        self._raw_handler = None
        self._bot_ready = False

    def get(self, key: str, default: typing.Any = None) -> typing.Any:
        return self.db.get("KNekoSpy", key, default)

    def set(self, key: str, value: typing.Any) -> None:
        self.db.set_sync("KNekoSpy", key, value)

    def get_prefix(self) -> str:
        dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
        return getattr(dispatcher, "_prefix", ".") if dispatcher else "."

    @property
    def _inline(self) -> typing.Any:
        return getattr(self.client, "_kitsune_inline", None)

    @property
    def _bot(self) -> typing.Any:
        inline = self._inline
        return getattr(inline, "_bot", None) if inline else None

    @property
    def _bot_id(self) -> typing.Any:
        inline = self._inline
        return getattr(inline, "_bot_id", None) if inline else None

    @staticmethod
    def _sanitise_text(text: str) -> str:
        import re

        return re.sub(
            r"<emoji document_id=\d+>(.*?)</emoji>",
            r"\1",
            text,
        )

    @staticmethod
    def _entity_url(entity: typing.Any) -> str:
        if entity is None:
            return "tg://user?id=0"
        username = getattr(entity, "username", None)
        if username:
            return f"https://t.me/{username}"
        entity_id = getattr(entity, "id", None)
        if isinstance(entity, User):
            return f"tg://user?id={entity_id}"
        if isinstance(entity, (Channel, Chat)):
            return f"https://t.me/c/{entity_id}/0"
        return f"tg://user?id={entity_id}"

    @staticmethod
    async def _message_link(msg_obj: typing.Any) -> str:
        with contextlib.suppress(Exception):
            chat = getattr(msg_obj, "chat", None)
            username = getattr(chat, "username", None) if chat else None
            if username:
                return f"https://t.me/{username}/{msg_obj.id}"
            chat_id = get_chat_id(msg_obj)
            if chat_id:
                return f"https://t.me/c/{chat_id}/{msg_obj.id}"
        return "https://t.me"

    async def on_load(self) -> None:
        try:
            from ..utils import asset_channel

            desired_kwargs = {
                "title": "kitsune-knekospy",
                "description": "Deleted and edited messages will appear there",
                "archive": True,
                "avatar": (
                    "https://pm1.narvii.com/6733/"
                    "0e0380ca5cd7595de53f48c0ce541d3e2f2effc4v2_hq.jpg"
                ),
                "db": self.db,
            }
            try:
                sig_params = inspect.signature(asset_channel).parameters
            except (TypeError, ValueError):
                sig_params = {}

            has_var_kwargs = any(
                p.kind is inspect.Parameter.VAR_KEYWORD
                for p in sig_params.values()
            )
            kwargs = {
                key: value
                for key, value in desired_kwargs.items()
                if key in sig_params or has_var_kwargs
            }

            result = await asset_channel(self.client, **kwargs)
            channel_id, _ = result if isinstance(result, tuple) else (result, False)

            if not channel_id:
                raise RuntimeError("asset_channel returned no channel id")

            self._tl_channel = channel_id
            self._channel = int(f"-100{channel_id}")
        except Exception:
            self._tl_channel = None
            self._channel = None
            logger.exception("KNekoSpy: failed to create asset channel")

        await self._ensure_bot_in_channel()

        self._raw_handler = self._on_raw_update
        self.client.add_event_handler(self._raw_handler, events.Raw())

        loop = asyncio.get_event_loop()
        self._sender_task = loop.create_task(self._sender_loop())

    async def _ensure_bot_in_channel(self) -> None:
        if self._bot_ready or self._tl_channel is None:
            return

        bot = self._bot
        if bot is None:
            return

        try:
            from telethon.tl.functions.channels import (
                EditAdminRequest,
                InviteToChannelRequest,
            )
            from telethon.tl.types import ChatAdminRights

            bot_me = await bot.get_me()
            bot_username = bot_me.username
            entity = await self.client.get_entity(self._channel)

            with contextlib.suppress(Exception):
                await self.client(
                    InviteToChannelRequest(channel=entity, users=[bot_username])
                )

            with contextlib.suppress(Exception):
                await self.client(
                    EditAdminRequest(
                        channel=entity,
                        user_id=bot_username,
                        admin_rights=ChatAdminRights(
                            post_messages=True,
                            edit_messages=True,
                            delete_messages=True,
                        ),
                        rank="",
                    )
                )

            self._bot_ready = True
            logger.debug("KNekoSpy: bot @%s added to asset channel", bot_username)
        except Exception:
            logger.exception("KNekoSpy: failed to add bot to asset channel")

    async def on_unload(self) -> None:
        for task in list(self._precache_tasks):
            task.cancel()
        self._precache_tasks.clear()

        self._media_cache.clear()
        self._media_cache_size = 0
        if self._sender_task is not None:
            self._sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._sender_task
        if self._raw_handler is not None:
            with contextlib.suppress(Exception):
                self.client.remove_event_handler(self._raw_handler)

    async def _sender_loop(self) -> None:
        while True:
            try:
                if not self._queue or self._next > time.time():
                    await asyncio.sleep(0.1)
                    continue
                if not self._bot_ready:
                    await self._ensure_bot_in_channel()
                factory = self._queue.pop(0)
                try:
                    await factory()
                except Exception as exc:
                    if "chat not found" in str(exc).lower():
                        self._bot_ready = False
                        await self._ensure_bot_in_channel()
                        try:
                            await factory()
                        except Exception as exc2:
                            logger.exception(
                                "KNekoSpy: failed to send queued item after retry"
                            )
                            self._report_internal_error(
                                "_sender_loop (retry)", exc2
                            )
                    else:
                        logger.exception("KNekoSpy: failed to send queued item")
                        self._report_internal_error("_sender_loop", exc)
                self._next = int(time.time()) + self.config["fw_protect"]
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("KNekoSpy: sender loop error")
                await asyncio.sleep(0.1)

    @staticmethod
    def _safe_text(msg_obj: typing.Any) -> str:
        text = getattr(msg_obj, "text", None)
        if text:
            return text
        raw = getattr(msg_obj, "message", None) or getattr(msg_obj, "raw_text", None)
        return raw or ""

    def _bind_client(self, msg_obj: typing.Any) -> typing.Any:
        if msg_obj is None:
            return msg_obj
        with contextlib.suppress(Exception):
            if getattr(msg_obj, "_client", None) is None:
                msg_obj._client = self.client
        return msg_obj

    async def _on_raw_update(self, update: typing.Any) -> None:
        try:
            if isinstance(update, (UpdateNewMessage, UpdateNewChannelMessage)):
                self._bind_client(getattr(update, "message", None))
                await self._cache_new_message(getattr(update, "message", None))
            elif isinstance(update, UpdateEditChannelMessage):
                self._bind_client(getattr(update, "message", None))
                await self._channel_edit_handler(update)
            elif isinstance(update, UpdateEditMessage):
                self._bind_client(getattr(update, "message", None))
                await self._pm_edit_handler(update)
            elif isinstance(update, UpdateDeleteMessages):
                await self._pm_delete_handler(update)
            elif isinstance(update, UpdateDeleteChannelMessages):
                await self._channel_delete_handler(update)
        except Exception as exc:
            logger.exception("KNekoSpy: raw update handler error")
            self._report_internal_error("_on_raw_update", exc)

    def _report_internal_error(self, where: str, exc: Exception) -> None:
        bot = self._bot
        if bot is None or self._channel is None:
            return
        text = (
            "⚠️ <b>KNekoSpy internal error</b>\n"
            f"<b>where:</b> <code>{escape_html(where)}</code>\n"
            f"<b>error:</b> <code>{escape_html(f'{type(exc).__name__}: {exc}')}</code>"
        )
        with contextlib.suppress(Exception):
            self._enqueue(
                lambda: bot.send_message(
                    self._channel,
                    text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            )

    @staticmethod
    def _int(value: typing.Union[str, int], /) -> typing.Union[str, int]:
        return int(value) if str(value).isdigit() else value

    @property
    def blacklist(self):
        return list(
            map(
                self._int,
                self.config["blacklist"]
                + [777000, self.client.tg_id, self._tl_channel, self._bot_id],
            )
        )

    @blacklist.setter
    def blacklist(self, value: list):
        self.config["blacklist"] = list(
            set(value)
            - {777000, self.client.tg_id, self._tl_channel, self._bot_id}
        )

    @property
    def whitelist(self):
        return list(map(self._int, self.config["whitelist"]))

    @whitelist.setter
    def whitelist(self, value: list):
        self.config["whitelist"] = value

    @property
    def always_track(self):
        return list(map(self._int, self.config["always_track"]))

    @command("spymode", required=OWNER)
    async def spymode(self, message: Message) -> None:
        "Включить / выключить режим слежения (сохранение удалённых и изменённых сообщений)"
        await message.edit(
            self.strings("state").format(
                self.strings("off" if self.get("state", False) else "on")
            ),
            parse_mode="html",
        )
        self.set("state", not self.get("state", False))

    @command("spybl", required=OWNER)
    async def spybl(self, message: Message) -> None:
        "Добавить / убрать текущий чат из чёрного списка (игнорируемые чаты)"
        chat = get_chat_id(message)
        if chat in self.blacklist:
            self.blacklist = list(set(self.blacklist) - {chat})
            await message.edit(self.strings("spybl_removed"), parse_mode="html")
        else:
            self.blacklist = list(set(self.blacklist) | {chat})
            await message.edit(self.strings("spybl"), parse_mode="html")

    @command("spyblclear", required=OWNER)
    async def spyblclear(self, message: Message) -> None:
        "Полностью очистить чёрный список слежения"
        self.blacklist = []
        await message.edit(self.strings("spybl_clear"), parse_mode="html")

    @command("spywl", required=OWNER)
    async def spywl(self, message: Message) -> None:
        "Добавить / убрать текущий чат из белого списка (следить только за ними)"
        chat = get_chat_id(message)
        if chat in self.whitelist:
            self.whitelist = list(set(self.whitelist) - {chat})
            await message.edit(self.strings("spywl_removed"), parse_mode="html")
        else:
            self.whitelist = list(set(self.whitelist) | {chat})
            await message.edit(self.strings("spywl"), parse_mode="html")

    @command("spywlclear", required=OWNER)
    async def spywlclear(self, message: Message) -> None:
        "Полностью очистить белый список слежения"
        self.whitelist = []
        await message.edit(self.strings("spywl_clear"), parse_mode="html")

    async def _get_entities_list(self, entities: list) -> str:
        return "\n".join(
            [
                "\u0020\u2800\u0020\u2800<emoji"
                ' document_id=4971987363145188045>▫️</emoji> <b><a href="{}">{}</a></b>'
                .format(
                    self._entity_url(await self.client.get_entity(x)),
                    escape_html(
                        get_display_name(await self.client.get_entity(x))
                    ),
                )
                for x in entities
            ]
        )

    @command("spyinfo", required=OWNER)
    async def spyinfo(self, message: Message) -> None:
        "Показать текущие настройки слежения (списки, режимы, статус)"
        if not self.get("state"):
            await message.edit(
                self.strings("mode_off").format(self.get_prefix()), parse_mode="html"
            )
            return

        info = ""

        if self.config["save_sd"]:
            info += self.strings("save_sd")

        if self.config["enable_groups"]:
            info += self.strings("chat")

        if self.config["enable_pm"]:
            info += self.strings("pm")

        if self.whitelist:
            info += self.strings("whitelist").format(
                await self._get_entities_list(self.whitelist)
            )
        elif not self.always_track:
            info += self.strings("whitelist_empty")

        if self.config["blacklist"]:
            info += self.strings("blacklist").format(
                await self._get_entities_list(self.config["blacklist"])
            )

        if self.always_track:
            info += self.strings("always_track").format(
                await self._get_entities_list(self.always_track)
            )

        await message.edit(info, parse_mode="html")

    def _buffered_file(self, data: bytes, name: str) -> typing.Any:
        try:
            from aiogram.types import BufferedInputFile

            return BufferedInputFile(data, filename=name)
        except Exception:
            buf = io.BytesIO(data)
            buf.name = name
            buf.seek(0)
            return buf

    def _enqueue(self, factory: typing.Callable[[], typing.Awaitable]) -> None:
        self._queue.append(factory)

    @staticmethod
    def _get_document(msg_obj: Message) -> typing.Any:
        media = getattr(msg_obj, "media", None)
        if isinstance(media, MessageMediaDocument):
            return getattr(media, "document", None)

        return getattr(msg_obj, "document", None)

    @staticmethod
    def _get_photo(msg_obj: Message) -> typing.Any:
        media = getattr(msg_obj, "media", None)
        if isinstance(media, MessageMediaPhoto):
            return getattr(media, "photo", None)
        return getattr(msg_obj, "photo", None)

    @classmethod
    def _document_filename(cls, msg_obj: Message) -> str:
        document = cls._get_document(msg_obj)
        if document is not None:
            for attr in getattr(document, "attributes", []) or []:
                if isinstance(attr, DocumentAttributeFilename) and attr.file_name:
                    return attr.file_name
        return "file"

    @classmethod
    def _resolve_media(cls, msg_obj: Message) -> typing.Optional[str]:
        media = getattr(msg_obj, "media", None)

        if cls._get_photo(msg_obj) is not None:
            return "photo"

        document = cls._get_document(msg_obj)
        if document is not None:
            attrs = getattr(document, "attributes", []) or []
            mime = (getattr(document, "mime_type", "") or "").lower()

            has_sticker = any(
                isinstance(a, DocumentAttributeSticker) for a in attrs
            )
            has_animated = any(
                isinstance(a, DocumentAttributeAnimated) for a in attrs
            )
            video_attr = next(
                (a for a in attrs if isinstance(a, DocumentAttributeVideo)),
                None,
            )
            audio_attr = next(
                (a for a in attrs if isinstance(a, DocumentAttributeAudio)),
                None,
            )

            if has_sticker or "sticker" in mime or mime == "application/x-tgsticker":
                return "sticker"

            if audio_attr is not None and getattr(audio_attr, "voice", False):
                return "voice"

            if video_attr is not None and getattr(video_attr, "round_message", False):
                return "video_note"

            if has_animated or mime == "image/gif":
                return "gif"

            if video_attr is not None or mime.startswith("video/"):
                return "video"

            if audio_attr is not None or mime.startswith("audio/"):
                return "audio"

            return "document"

        if media is not None:
            return "document"

        return None

    @staticmethod
    def _is_pm(msg_obj: typing.Any) -> bool:
        peer = getattr(msg_obj, "peer_id", None)
        if isinstance(peer, PeerUser):
            return True
        if isinstance(peer, PeerChat):
            return False

        return bool(getattr(msg_obj, "is_private", False))

    def _self_destruct_id(self, msg_obj: typing.Any) -> typing.Any:
        try:
            return f"{get_chat_id(msg_obj)}/{msg_obj.id}"
        except Exception:
            return getattr(msg_obj, "id", None)

    def _claim_self_destruct(self, msg_obj: typing.Any) -> bool:
        marker = self._self_destruct_id(msg_obj)
        if marker is None:
            return True
        now = time.time()
        expired = [key for key, seen in self._sd_seen.items() if now - seen > self._sd_seen_ttl]
        for key in expired:
            self._sd_seen.pop(key, None)
        if marker in self._sd_seen:
            return False
        self._sd_seen[marker] = now
        return True

    def _make_cache_key(self, msg_obj: Message) -> typing.Any:
        try:
            if self._is_pm(msg_obj) or isinstance(
                getattr(msg_obj, "peer_id", None), PeerChat
            ):
                return msg_obj.id
            return f"{get_chat_id(msg_obj)}/{msg_obj.id}"
        except Exception:
            return getattr(msg_obj, "id", None)

    def _put_media_cache(self, key: typing.Any, data: bytes) -> None:
        if not data or key is None:
            return
        size = len(data)

        while (
            self._media_cache
            and (
                self._media_cache_size + size > self._media_cache_limit
                or len(self._media_cache) >= self._media_cache_max_keys
            )
        ):
            _, evicted = self._media_cache.popitem()

            self._media_cache_size -= len(evicted)

        if key in self._media_cache:
            self._media_cache_size -= len(self._media_cache[key])
        self._media_cache[key] = data
        self._media_cache_size += size

    def _pop_media_cache(self, key: typing.Any) -> typing.Optional[bytes]:
        data = self._media_cache.pop(key, None)
        if data is not None:
            self._media_cache_size -= len(data)
        return data

    async def _download_media_bytes(self, msg_obj: Message) -> typing.Optional[bytes]:
        key = self._make_cache_key(msg_obj)

        pre = self._media_cache.get(key)
        if pre:
            logger.debug(
                "KNekoSpy: using pre-downloaded media from cache (%d bytes, key=%s)",
                len(pre),
                key,
            )
            return pre

        pre = getattr(msg_obj, "_knekospy_media_bytes", None)
        if pre:
            logger.debug(
                "KNekoSpy: using pre-downloaded media from attr (%d bytes)", len(pre)
            )
            return pre

        candidates: list = []
        media = getattr(msg_obj, "media", None)

        candidates.append(msg_obj)

        if media is not None:
            candidates.append(media)

        doc = self._get_document(msg_obj)
        if doc is not None:
            candidates.append(doc)
        photo = self._get_photo(msg_obj)
        if photo is not None:
            candidates.append(photo)

        try:
            is_connected = self.client.is_connected()
        except Exception:
            is_connected = True
        if not is_connected:
            waited = 0.0
            while waited < 15.0:
                await asyncio.sleep(1.0)
                waited += 1.0
                try:
                    if self.client.is_connected():
                        break
                except Exception:
                    break

        last_exc: typing.Optional[Exception] = None
        for idx, candidate in enumerate(candidates):
            try:
                data = await self.client.download_media(candidate, bytes)
                if data:
                    logger.debug(
                        "KNekoSpy: media downloaded (%d bytes) via candidate #%d (%s)",
                        len(data),
                        idx,
                        type(candidate).__name__,
                    )
                    return data
                logger.debug(
                    "KNekoSpy: candidate #%d (%s) returned empty data",
                    idx,
                    type(candidate).__name__,
                )
            except Exception as exc:
                last_exc = exc
                logger.debug(
                    "KNekoSpy: candidate #%d (%s) download failed: %s",
                    idx,
                    type(candidate).__name__,
                    exc,
                )
                continue

        if last_exc is not None:
            logger.warning(
                "KNekoSpy: failed to download media (%s)", last_exc
            )
        else:
            logger.warning("KNekoSpy: media download returned no data")
        return None

    @classmethod
    def _sticker_filename(cls, msg_obj: Message) -> str:
        document = cls._get_document(msg_obj)
        mime = (getattr(document, "mime_type", "") or "").lower() if document else ""
        if mime == "application/x-tgsticker" or "tgs" in mime:
            return "sticker.tgs"
        if "webm" in mime or "video" in mime:
            return "sticker.webm"
        return "sticker.webp"

    async def _enqueue_media(self, msg_obj: Message, caption: str) -> None:
        bot = self._bot
        if bot is None or self._channel is None:
            return

        caption = self._sanitise_text(caption)
        channel = self._channel
        media_type = self._resolve_media(msg_obj)
        logger.debug(
            "KNekoSpy: _enqueue_media resolved media_type=%s (media=%s)",
            media_type,
            type(getattr(msg_obj, "media", None)).__name__,
        )

        if media_type is None:
            self._enqueue(
                lambda: bot.send_message(
                    channel,
                    caption,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            )
            return

        data = await self._download_media_bytes(msg_obj)

        if not data:
            note = "\n\n<i>[media unavailable]</i>"
            self._enqueue(
                lambda: bot.send_message(
                    channel,
                    caption + note,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            )
            return

        if media_type == "photo":
            file = self._buffered_file(data, "photo.jpg")
            self._enqueue(
                lambda: bot.send_photo(
                    channel, photo=file, caption=caption, parse_mode="HTML"
                )
            )
        elif media_type == "sticker":
            fname = self._sticker_filename(msg_obj)
            file = self._buffered_file(data, fname)
            self._enqueue(
                lambda: bot.send_document(
                    channel,
                    document=file,
                    caption=caption + "\n\n&lt;sticker&gt;",
                    parse_mode="HTML",
                )
            )
        elif media_type == "voice":
            file = self._buffered_file(data, "voice.ogg")
            self._enqueue(
                lambda: bot.send_voice(
                    channel, voice=file, caption=caption, parse_mode="HTML"
                )
            )
        elif media_type == "video_note":
            file = self._buffered_file(data, "video_note.mp4")

            self._enqueue(
                lambda: bot.send_message(
                    channel,
                    caption,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            )

            self._enqueue(
                lambda: self._send_video_note_safe(bot, channel, data)
            )
        elif media_type == "gif":
            file = self._buffered_file(data, "animation.mp4")
            self._enqueue(
                lambda: bot.send_animation(
                    channel, animation=file, caption=caption, parse_mode="HTML"
                )
            )
        elif media_type == "video":
            fname = self._document_filename(msg_obj)
            if fname == "file":
                fname = "video.mp4"
            file = self._buffered_file(data, fname)
            self._enqueue(
                lambda: bot.send_video(
                    channel, video=file, caption=caption, parse_mode="HTML"
                )
            )
        elif media_type == "audio":
            fname = self._document_filename(msg_obj)
            if fname == "file":
                fname = "audio.mp3"
            file = self._buffered_file(data, fname)
            self._enqueue(
                lambda: bot.send_audio(
                    channel, audio=file, caption=caption, parse_mode="HTML"
                )
            )
        else:
            file = self._buffered_file(data, self._document_filename(msg_obj))
            self._enqueue(
                lambda: bot.send_document(
                    channel, document=file, caption=caption, parse_mode="HTML"
                )
            )

    async def _send_video_note_safe(
        self, bot: typing.Any, channel: typing.Any, data: bytes
    ) -> None:
        try:
            await bot.send_video_note(
                channel, video_note=self._buffered_file(data, "video_note.mp4")
            )
        except Exception:
            with contextlib.suppress(Exception):
                await bot.send_video(
                    channel,
                    video=self._buffered_file(data, "video_note.mp4"),
                    parse_mode="HTML",
                )

    async def _message_deleted(self, msg_obj: Message, caption: str) -> None:
        await self._enqueue_media(msg_obj, caption)

    async def _message_edited(self, caption: str, msg_obj: Message) -> None:
        bot = self._bot
        if bot is None or self._channel is None:
            return

        if self._resolve_media(msg_obj) is not None:
            await self._enqueue_media(msg_obj, caption)
        else:
            caption = self._sanitise_text(caption)
            channel = self._channel
            self._enqueue(
                lambda: bot.send_message(
                    channel,
                    caption,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            )

    async def _channel_edit_handler(self, update: UpdateEditChannelMessage) -> None:
        if (
            not self.get("state", False)
            or update.message.out
            or (self.config["ignore_inline"] and update.message.via_bot_id)
        ):
            return

        key = f"{get_chat_id(update.message)}/{update.message.id}"
        if (
            key in self._cache
            and self.config["log_edits"]
            and self._should_track(self._cache[key])
        ):
            msg_obj = self._cache[key]
            sender = getattr(msg_obj, "sender", None)
            if sender is None and getattr(msg_obj, "sender_id", None) is not None:
                with contextlib.suppress(Exception):
                    sender = await self.client.get_entity(msg_obj.sender_id)
            if (
                not getattr(sender, "bot", False)
                and update.message.raw_text != msg_obj.raw_text
            ):
                chat = getattr(msg_obj, "chat", None)
                if chat is None:
                    with contextlib.suppress(Exception):
                        chat = await self.client.get_entity(get_chat_id(msg_obj))
                await self._message_edited(
                    self.strings("edited_chat").format(
                        self._entity_url(chat),
                        escape_html(get_display_name(chat)),
                        self._entity_url(sender),
                        escape_html(get_display_name(sender)),
                        self._safe_text(msg_obj),
                        message_url=await self._message_link(msg_obj),
                    ),
                    msg_obj,
                )

        self._cache[key] = update.message
        if getattr(update.message, "media", None) is not None:
            self._spawn_precache(update.message, key)

    def _in_list(self, values: list, target: typing.Any) -> bool:
        if target is None:
            return False
        for item in values:
            if item == target:
                return True
            with contextlib.suppress(Exception):
                if int(item) == int(target):
                    return True
        return False

    def _should_track(self, msg_obj: typing.Any) -> bool:
        if getattr(msg_obj, "out", False):
            return False

        sender_id = getattr(msg_obj, "sender_id", None)
        chat_id = get_chat_id(msg_obj)

        if self._in_list(self.always_track, sender_id) or self._in_list(
            self.always_track, chat_id
        ):
            return True

        if self._in_list(self.blacklist, sender_id) or self._in_list(
            self.blacklist, chat_id
        ):
            return False

        if self.config["ignore_inline"] and getattr(msg_obj, "via_bot_id", None):
            return False

        if not (
            self._in_list(self.whitelist, chat_id)
            or self._in_list(self.whitelist, sender_id)
        ):
            return False

        return True

    async def _pm_edit_handler(self, update: UpdateEditMessage) -> None:
        if (
            not self.get("state", False)
            or update.message.out
            or (self.config["ignore_inline"] and update.message.via_bot_id)
        ):
            return

        key = update.message.id
        msg_obj = self._cache.get(key)
        if (
            key in self._cache
            and msg_obj is not None
            and self.config["log_edits"]
            and self._should_track(msg_obj)
            and update.message.raw_text != msg_obj.raw_text
        ):
            sender = None
            if msg_obj.sender_id is not None:
                with contextlib.suppress(Exception):
                    sender = await self.client.get_entity(msg_obj.sender_id)
            if not getattr(sender, "bot", False):
                chat = None
                if isinstance(msg_obj.peer_id, PeerChat):
                    with contextlib.suppress(Exception):
                        chat = await self.client.get_entity(msg_obj.peer_id.chat_id)
                await self._message_edited(
                    (
                        self.strings("edited_chat").format(
                            self._entity_url(chat),
                            escape_html(get_display_name(chat)),
                            self._entity_url(sender),
                            escape_html(get_display_name(sender)),
                            self._safe_text(msg_obj),
                            message_url=await self._message_link(msg_obj),
                        )
                        if isinstance(msg_obj.peer_id, PeerChat)
                        else self.strings("edited_pm").format(
                            self._entity_url(sender),
                            escape_html(get_display_name(sender)),
                            self._safe_text(msg_obj),
                            message_url=await self._message_link(msg_obj),
                        )
                    ),
                    msg_obj,
                )

        self._cache[update.message.id] = update.message
        if getattr(update.message, "media", None) is not None:
            self._spawn_precache(update.message, update.message.id)

    async def _pm_delete_handler(self, update: UpdateDeleteMessages) -> None:
        if not self.get("state", False):
            return

        for message in update.messages:
            try:
                await self._pm_delete_one(message)
            except Exception as exc:
                logger.exception(
                    "KNekoSpy: failed to process deleted message id=%s", message
                )
                self._report_internal_error("_pm_delete_handler", exc)

    async def _pm_delete_one(self, message: int) -> None:
        if message not in self._cache:
            fallback_key = next(
                (
                    k
                    for k in self._cache
                    if isinstance(k, str) and k.endswith(f"/{message}")
                ),
                None,
            )
            if fallback_key is not None:
                message = fallback_key
            else:
                self._pop_media_cache(message)
                return

        msg_obj = self._cache.pop(message)

        if not self._should_track(msg_obj):
            return

        sender = None
        if msg_obj.sender_id is not None:
            with contextlib.suppress(Exception):
                sender = await self.client.get_entity(msg_obj.sender_id)

        if sender is not None and getattr(sender, "bot", False):
            return

        chat = None
        if isinstance(msg_obj.peer_id, PeerChat):
            with contextlib.suppress(Exception):
                chat = await self.client.get_entity(msg_obj.peer_id.chat_id)

        await self._await_precache(message, timeout=25.0)

        await self._message_deleted(
            msg_obj,
            (
                self.strings("deleted_chat").format(
                    self._entity_url(chat),
                    escape_html(get_display_name(chat)),
                    self._entity_url(sender),
                    escape_html(get_display_name(sender)),
                    self._safe_text(msg_obj),
                    message_url=await self._message_link(msg_obj),
                )
                if isinstance(msg_obj.peer_id, PeerChat)
                else self.strings("deleted_pm").format(
                    self._entity_url(sender),
                    escape_html(get_display_name(sender)),
                    self._safe_text(msg_obj),
                    message_url=await self._message_link(msg_obj),
                )
            ),
        )

    async def _channel_delete_handler(
        self, update: UpdateDeleteChannelMessages
    ) -> None:
        if not self.get("state", False):
            return

        for message in update.messages:
            try:
                await self._channel_delete_one(update.channel_id, message)
            except Exception as exc:
                logger.exception(
                    "KNekoSpy: failed to process deleted channel message "
                    "channel=%s id=%s",
                    update.channel_id,
                    message,
                )
                self._report_internal_error("_channel_delete_handler", exc)

    async def _channel_delete_one(self, channel_id: int, message: int) -> None:
        key = f"{channel_id}/{message}"
        if key not in self._cache:
            fallback_key = next(
                (
                    k
                    for k in self._cache
                    if isinstance(k, str) and k.endswith(f"/{message}")
                ),
                None,
            )
            if fallback_key is not None:
                key = fallback_key
            else:
                self._pop_media_cache(key)
                return

        msg_obj = self._cache.pop(key)

        if not self._should_track(msg_obj):
            return

        sender = getattr(msg_obj, "sender", None)
        if sender is None and getattr(msg_obj, "sender_id", None) is not None:
            with contextlib.suppress(Exception):
                sender = await self.client.get_entity(msg_obj.sender_id)

        if sender is not None and getattr(sender, "bot", False):
            return

        chat = getattr(msg_obj, "chat", None)
        if chat is None:
            with contextlib.suppress(Exception):
                chat = await self.client.get_entity(get_chat_id(msg_obj))

        await self._await_precache(key, timeout=25.0)
        await self._message_deleted(
            msg_obj,
            self.strings("deleted_chat").format(
                self._entity_url(chat),
                escape_html(get_display_name(chat)),
                self._entity_url(sender),
                escape_html(get_display_name(sender)),
                self._safe_text(msg_obj),
                message_url=await self._message_link(msg_obj),
            ),
        )

    @watcher(in_=True)
    async def watcher(self, event: typing.Any) -> None:
        message = event.message
        if message is None or getattr(message, "out", False):
            return

        media = getattr(message, "media", None)
        if media is not None and getattr(media, "ttl_seconds", False):
            await self._handle_self_destruct(message)
            return

        self._cache_message_obj(message)

    async def _cache_new_message(self, message: typing.Any) -> None:
        if message is None:
            return

        if getattr(message, "out", False):
            return

        media = getattr(message, "media", None)
        if media is not None:
            with contextlib.suppress(Exception):
                if getattr(media, "ttl_seconds", False):
                    await self._handle_self_destruct(message)
                    return
        self._cache_message_obj(message)

    async def _handle_self_destruct(self, message: typing.Any) -> None:
        if not self.config["save_sd"]:
            return
        if not self._claim_self_destruct(message):
            return
        bot = self._bot
        if bot is None or self._channel is None:
            return
        data = await self._download_media_bytes(message)
        sender = None
        if getattr(message, "sender_id", None) is not None:
            with contextlib.suppress(Exception):
                sender = await self.client.get_entity(message.sender_id)
        caption = self._sanitise_text(
            self.strings("sd_media").format(
                self._entity_url(sender),
                escape_html(get_display_name(sender)),
            )
        )
        if data:
            media_type = self._resolve_media(message)
            if media_type == "photo":
                file = self._buffered_file(data, "sd.jpg")
                self._enqueue(
                    lambda: bot.send_photo(
                        self._channel, photo=file, caption=caption,
                        parse_mode="HTML",
                    )
                )
            elif media_type == "voice":
                file = self._buffered_file(data, "sd.ogg")
                self._enqueue(
                    lambda: bot.send_voice(
                        self._channel, voice=file, caption=caption,
                        parse_mode="HTML",
                    )
                )
            else:
                file = self._buffered_file(data, "sd.mp4")
                self._enqueue(
                    lambda: bot.send_video(
                        self._channel, video=file, caption=caption,
                        parse_mode="HTML",
                    )
                )
        else:
            self._enqueue(
                lambda: bot.send_message(
                    self._channel,
                    caption + "\n\n<i>[media unavailable]</i>",
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            )

    def _cache_message_obj(self, message: typing.Any) -> None:
        media = getattr(message, "media", None)
        if media is not None and getattr(media, "ttl_seconds", False):
            return

        cache_key = None
        with contextlib.suppress(AttributeError):
            cache_key = (
                message.id
                if self._is_pm(message) or isinstance(message.peer_id, PeerChat)
                else f"{get_chat_id(message)}/{message.id}"
            )
            self._cache[cache_key] = message

        if (
            self.get("state", False)
            and cache_key is not None
            and getattr(message, "media", None) is not None

            and cache_key not in self._precache_by_key
            and cache_key not in self._media_cache
        ):
            self._spawn_precache(message, cache_key)

    def _spawn_precache(self, message: Message, cache_key: typing.Any) -> None:
        try:
            task = asyncio.create_task(
                self._maybe_precache_media(message, cache_key)
            )
        except RuntimeError:
            return
        self._precache_tasks.add(task)
        self._precache_by_key[cache_key] = task

        def _done_callback(t: asyncio.Task) -> None:
            self._precache_tasks.discard(t)
            if self._precache_by_key.get(cache_key) is t:
                self._precache_by_key.pop(cache_key, None)

        task.add_done_callback(_done_callback)

    async def _await_precache(self, cache_key: typing.Any, timeout: float = 25.0) -> None:
        task = self._precache_by_key.get(cache_key)
        if task is None or task.done():
            return
        with contextlib.suppress(asyncio.TimeoutError, Exception):
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)

    async def _maybe_precache_media(
        self, message: Message, cache_key: typing.Any
    ) -> None:
        try:
            media = getattr(message, "media", None)
            if media is None:
                return

            if getattr(media, "ttl_seconds", None):
                return

            media_type = self._resolve_media(message)
            if media_type is None:
                return

            try:
                if not self._should_track(message):
                    return
            except Exception as exc:
                logger.debug("KNekoSpy: precache filter error: %s", exc)

            max_size = 50 * 1024 * 1024
            size = 0
            document = self._get_document(message)
            if document is not None:
                size = getattr(document, "size", 0) or 0
            if size and size > max_size:
                logger.debug(
                    "KNekoSpy: skip precache, media too large (%d bytes)", size
                )
                return

            last_exc: typing.Optional[Exception] = None
            data: typing.Optional[bytes] = None
            for attempt in range(8):
                try:
                    is_connected = self.client.is_connected()
                except Exception:
                    is_connected = True

                if not is_connected:
                    waited = 0.0
                    while waited < 20.0:
                        await asyncio.sleep(1.0)
                        waited += 1.0
                        try:
                            if self.client.is_connected():
                                break
                        except Exception:
                            break

                try:
                    data = await self.client.download_media(message, bytes)
                    if data:
                        break
                except Exception as exc:
                    last_exc = exc
                    logger.debug(
                        "KNekoSpy: precache attempt %d failed: %s",
                        attempt + 1,
                        exc,
                    )

                    await asyncio.sleep(min(1.0 * (attempt + 1), 5.0))

            if data:
                self._put_media_cache(cache_key, data)

                with contextlib.suppress(Exception):
                    message._knekospy_media_bytes = data
                logger.info(
                    "KNekoSpy: pre-cached %s media (%d bytes, key=%s)",
                    media_type,
                    len(data),
                    cache_key,
                )
            else:
                logger.warning(
                    "KNekoSpy: precache FAILED for %s media (key=%s): %s",
                    media_type,
                    cache_key,
                    last_exc
                    if last_exc is not None
                    else "download_media returned empty data after all retries",
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("KNekoSpy: precache task crashed")
