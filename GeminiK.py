"""
GeminiK — модуль Google Gemini AI для Kitsune UserBot.

Команды:
    .g <текст>           — спросить Gemini (ответь на медиа для анализа)
    .gclear              — очистить память диалога в текущем чате
    .gsafety [уровень]   — посмотреть/сменить уровень safety-фильтров
    .gmodel  [модель]    — посмотреть/сменить модель Gemini
    .gkeys               — показать статус API-ключей

Адаптирован из SenkoGuardianModules/Gemini для Kitsune.
"""

from __future__ import annotations

import asyncio
import logging
import typing

try:
    from google import genai
    from google.genai import types
    from google.genai.types import (
        SafetySetting,
        HarmCategory,
        HarmBlockThreshold,
    )
    GOOGLE_AVAILABLE = True
except Exception:  # ImportError или ошибки внутри пакета
    genai = None  # type: ignore
    types = None  # type: ignore
    GOOGLE_AVAILABLE = False

from ..core.loader import KitsuneModule, command, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..validators import String, Choice, Integer, Float, Hidden
from ..utils import escape_html

logger = logging.getLogger(__name__)

DB_OWNER = "kitsune.modules.gemini"
DB_HISTORY_KEY = "conversations_v1"
DB_SAFETY_KEY = "safety_level"

GEMINI_TIMEOUT = 120        # секунд на запрос
MAX_MSG_LEN = 4096          # лимит Telegram на длину сообщения

# Поддерживаемые MIME-типы вложений для мультимодального анализа.
SUPPORTED_MIME = frozenset({
    "image/png", "image/jpeg", "image/webp", "image/heic", "image/heif",
    "video/mp4", "video/mpeg", "video/mov", "video/avi", "video/webm",
    "audio/mp3", "audio/mpeg", "audio/wav", "audio/ogg", "audio/flac",
    "audio/aac", "audio/aiff",
    "application/pdf", "text/plain",
})

# Соответствие уровня фильтров -> порог блокировки.
_SAFETY_MAP = {
    "none": "BLOCK_NONE",
    "low": "BLOCK_ONLY_HIGH",
    "medium": "BLOCK_MEDIUM_AND_ABOVE",
    "high": "BLOCK_LOW_AND_ABOVE",
}

_SAFETY_ICONS = {"none": "🔓", "low": "🟡", "medium": "🟠", "high": "🔒"}

# Категории фильтров (CIVIC_INTEGRITY есть не во всех версиях SDK).
_BASE_CATEGORIES = [
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
    "HARM_CATEGORY_CIVIC_INTEGRITY",
]


class GeminiKModule(KitsuneModule):
    name        = "GeminiK"
    description = "Google Gemini AI — чат с памятью, анализ фото/аудио/видео/PDF"
    author      = "SenkoGuardianModules (адапт. для Kitsune)"
    version     = "2.0"
    icon        = "✨"
    category    = "ai"

    # Loader сам поставит зависимость перед загрузкой модуля.
    pip_requires: typing.ClassVar[list[str]] = ["google-genai"]

    strings_ru = {
        "no_api_key":      '❗️ <b>API ключ не настроен.</b>\nПолучить: <a href="https://aistudio.google.com/app/apikey">здесь</a>.\nНастроить: <code>.cfg GeminiK api_key</code>',
        "invalid_api_key": "❗️ <b>Неверный или отозванный API ключ.</b>",
        "no_prompt":       "⚠️ <i>Нужен текст запроса или ответ на медиа.</i>",
        "processing":      "✨ <b>Gemini думает...</b>",
        "api_error":       "❗️ <b>Ошибка Gemini API:</b>\n<code>{}</code>",
        "timeout":         f"❗️ <b>Таймаут ({GEMINI_TIMEOUT} сек).</b> Попробуй ещё раз.",
        "blocked":         "🚫 <b>Ответ заблокирован фильтрами.</b>\n<code>{}</code>\n<i>Снизь уровень: </i><code>.gsafety none</code>",
        "empty":           "🤔 <b>Пустой ответ от модели.</b>",
        "mem_cleared":     "🧹 <b>Память диалога очищена.</b>",
        "no_mem":          "ℹ️ <b>История в этом чате уже пуста.</b>",
        "response_prefix": "✨ <b>Gemini</b>",
        "safety_set":      "{} <b>Safety-фильтры:</b> <code>{}</code>",
        "safety_show": (
            "🛡 <b>Текущий уровень фильтров:</b> <code>{}</code>\n\n"
            "<b>Доступные значения:</b>\n"
            "• <code>none</code> — отключены\n"
            "• <code>low</code> — блок только явного\n"
            "• <code>medium</code> — стандарт (по умолч.)\n"
            "• <code>high</code> — максимум\n\n"
            "<i>Сменить: </i><code>.gsafety none</code>"
        ),
        "safety_bad":      "❗️ Используй: <code>none</code> / <code>low</code> / <code>medium</code> / <code>high</code>",
        "sdk_missing":     "⚠️ <b>Нужна библиотека:</b> <code>pip install google-genai</code>\n<i>Загрузи модуль заново — Kitsune поставит её автоматически.</i>",
        "quota_error": (
            "❗️ <b>Превышен лимит API (quota / 429).</b>\n"
            "Подожди немного или проверь <a href='https://aistudio.google.com/app/billing'>тарифный план</a>.\n"
            "<i>Можно добавить несколько ключей через запятую.</i>"
        ),
        "region_error": (
            "❗️ <b>Gemini недоступен в вашем регионе.</b>\n"
            "Настрой прокси: <code>.cfg GeminiK proxy http://user:pass@host:port</code>"
        ),
        "model_show":      "🤖 <b>Текущая модель:</b> <code>{}</code>",
        "model_set":       "✅ <b>Модель установлена:</b> <code>{}</code>",
        "keys_none":       "🔑 <b>Ключи не настроены.</b>\n<code>.cfg GeminiK api_key</code>",
        "keys_status":     "🔑 <b>Активных API-ключей:</b> <code>{}</code>",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "api_key",
                default="",
                doc="API ключи Google Gemini (через запятую — ротация при ошибках).",
                validator=Hidden(),
            ),
            ConfigValue(
                "model_name",
                default="gemini-2.0-flash",
                doc="Модель Gemini (напр. gemini-2.0-flash, gemini-2.5-flash).",
                validator=String(min_len=1, max_len=128),
            ),
            ConfigValue(
                "system_instruction",
                default="",
                doc="Системная инструкция (характер/роль ассистента).",
                validator=String(max_len=4000),
            ),
            ConfigValue(
                "max_history",
                default=10,
                doc="Макс. пар «вопрос-ответ» в памяти на чат (0 = без лимита).",
                validator=Integer(minimum=0, maximum=200),
            ),
            ConfigValue(
                "temperature",
                default=1.0,
                doc="Температура генерации (0.0–2.0).",
                validator=Float(minimum=0.0, maximum=2.0),
            ),
            ConfigValue(
                "safety_settings",
                default="medium",
                doc="Уровень safety-фильтров по умолчанию: none / low / medium / high",
                validator=Choice(["none", "low", "medium", "high"]),
            ),
            ConfigValue(
                "proxy",
                default="",
                doc="Прокси для запросов. Формат: http://user:pass@host:port",
                validator=String(max_len=256),
            ),
        )

    # ──────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────

    def _cfg(self, key: str, default: typing.Any = None) -> typing.Any:
        """Безопасное чтение конфига."""
        try:
            if self.config is not None and key in self.config:
                return self.config[key]
        except Exception:
            pass
        return default

    async def _save_cfg(self, key: str, value: typing.Any) -> None:
        """Сохранить значение конфига и в память, и в БД (как делает loader)."""
        try:
            self.config[key] = value
        except Exception:
            logger.exception("GeminiK: config[%s] validation failed", key)
            raise
        db_key = f"kitsune.config.{self.name.lower()}"
        await self.db.set(db_key, key, self.config[key])

    def _get_api_keys(self) -> list[str]:
        raw = str(self._cfg("api_key", "") or "").strip()
        if not raw:
            return []
        return [k.strip() for k in raw.split(",") if k.strip()]

    def _build_client(self, api_key: str):
        """Создать genai.Client с учётом прокси и таймаута."""
        kwargs: dict = {"api_key": api_key.strip()}
        proxy = str(self._cfg("proxy", "") or "").strip()
        http_kwargs: dict = {"timeout": GEMINI_TIMEOUT * 1000}  # мс
        if proxy:
            # httpx (sync) и aiohttp (async) принимают proxy через *_client_args.
            http_kwargs["client_args"] = {"proxy": proxy}
            http_kwargs["async_client_args"] = {"proxy": proxy}
        try:
            kwargs["http_options"] = types.HttpOptions(**http_kwargs)
        except Exception:
            # Старые версии SDK без некоторых полей — пробуем без client_args.
            try:
                kwargs["http_options"] = types.HttpOptions(timeout=GEMINI_TIMEOUT * 1000)
            except Exception:
                kwargs.pop("http_options", None)
        return genai.Client(**kwargs)

    def _get_safety_level(self) -> str:
        return str(
            self.db.get(DB_OWNER, DB_SAFETY_KEY, self._cfg("safety_settings", "medium"))
        ).lower()

    def _build_safety(self) -> list:
        """Список SafetySetting для текущего уровня; недоступные категории пропускаются."""
        level = self._get_safety_level()
        threshold_name = _SAFETY_MAP.get(level, "BLOCK_MEDIUM_AND_ABOVE")
        try:
            threshold = getattr(HarmBlockThreshold, threshold_name)
        except Exception:
            threshold = HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        settings: list = []
        for cat_name in _BASE_CATEGORIES:
            category = getattr(HarmCategory, cat_name, None)
            if category is None:
                continue
            try:
                settings.append(SafetySetting(category=category, threshold=threshold))
            except Exception:
                continue
        return settings

    # ── История диалога (хранится в БД) ──

    def _get_history(self, chat_id: int) -> list:
        all_hist = self.db.get(DB_OWNER, DB_HISTORY_KEY, {}) or {}
        return list(all_hist.get(str(chat_id), []))

    def _set_history(self, chat_id: int, history: list) -> None:
        all_hist = self.db.get(DB_OWNER, DB_HISTORY_KEY, {}) or {}
        all_hist[str(chat_id)] = history
        self.db.set_sync(DB_OWNER, DB_HISTORY_KEY, all_hist)

    def _clear_history(self, chat_id: int) -> None:
        all_hist = self.db.get(DB_OWNER, DB_HISTORY_KEY, {}) or {}
        if str(chat_id) in all_hist:
            all_hist.pop(str(chat_id), None)
            self.db.set_sync(DB_OWNER, DB_HISTORY_KEY, all_hist)

    def _append_history(self, chat_id: int, user_text: str, model_text: str) -> None:
        """В историю кладём только текст (медиа в БД не храним)."""
        history = self._get_history(chat_id)
        history.append({"role": "user", "text": user_text})
        history.append({"role": "model", "text": model_text})
        max_len = int(self._cfg("max_history", 10) or 0)
        if max_len > 0:
            history = history[-max_len * 2:]
        self._set_history(chat_id, history)

    def _mem_display(self, chat_id: int) -> str:
        pairs = len(self._get_history(chat_id)) // 2
        max_len = int(self._cfg("max_history", 10) or 0)
        return f"🧠 [{pairs}/∞]" if max_len == 0 else f"🧠 [{pairs}/{max_len}]"

    # ── Медиа из ответа ──

    async def _get_media_part(self, message) -> typing.Optional[dict]:
        """Скачать медиа из сообщения и вернуть {'data','mime_type'} либо None."""
        if not message:
            return None
        mime: typing.Optional[str] = None
        try:
            if getattr(message, "photo", None):
                mime = "image/jpeg"
            elif getattr(message, "document", None):
                doc_mime = (getattr(message.document, "mime_type", "") or "").lower()
                if doc_mime not in SUPPORTED_MIME:
                    return None
                mime = doc_mime
            else:
                return None
            data = await message.download_media(bytes)
            if not data:
                return None
            return {"data": data, "mime_type": mime}
        except Exception:
            logger.exception("GeminiK: download_media failed")
            return None

    # ── Сборка contents для запроса ──

    def _build_contents(self, history: list, parts: list) -> list:
        contents: list = []
        for h in history:
            text = h.get("text", "")
            if not text:
                continue
            contents.append(
                types.Content(
                    role=h.get("role", "user"),
                    parts=[types.Part.from_text(text=str(text))],
                )
            )
        cur_parts: list = []
        for p in parts:
            if isinstance(p, str) and p:
                cur_parts.append(types.Part.from_text(text=p))
            elif isinstance(p, dict) and p.get("data"):
                cur_parts.append(
                    types.Part.from_bytes(data=p["data"], mime_type=p["mime_type"])
                )
        if not cur_parts:
            cur_parts.append(types.Part.from_text(text=" "))
        contents.append(types.Content(role="user", parts=cur_parts))
        return contents

    # ── Вызов Gemini (async, с ротацией ключей) ──

    async def _call_gemini(self, parts: list, history: list) -> tuple[str, bool]:
        """Возвращает (текст_ответа_или_ошибки, is_success)."""
        keys = self._get_api_keys()
        if not keys:
            return self.strings("no_api_key"), False

        model_name = self._cfg("model_name", "gemini-2.0-flash")
        temperature = float(self._cfg("temperature", 1.0) or 1.0)
        system = (self._cfg("system_instruction", "") or "").strip() or None
        safety = self._build_safety()

        try:
            cfg = types.GenerateContentConfig(
                temperature=temperature,
                safety_settings=safety,
                system_instruction=system,
            )
        except Exception:
            cfg = types.GenerateContentConfig(temperature=temperature)

        contents = self._build_contents(history, parts)
        last_err: typing.Optional[str] = None

        for key in keys:
            client = None
            try:
                client = self._build_client(key)
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=cfg,
                    ),
                    timeout=GEMINI_TIMEOUT,
                )

                text = getattr(response, "text", None)
                if text:
                    return text, True

                # Пустой ответ — разбираем причину.
                candidates = getattr(response, "candidates", None) or []
                if candidates:
                    finish = getattr(candidates[0], "finish_reason", None)
                    finish_str = getattr(finish, "name", str(finish)) if finish else "UNKNOWN"
                    return self.strings("blocked").format(f"finish_reason={finish_str}"), False
                fb = getattr(response, "prompt_feedback", None)
                if fb is not None:
                    reason = getattr(fb, "block_reason", None)
                    reason_str = getattr(reason, "name", str(reason)) if reason else "UNKNOWN"
                    return self.strings("blocked").format(f"block_reason={reason_str}"), False
                return self.strings("empty"), False

            except asyncio.TimeoutError:
                return self.strings("timeout"), False

            except Exception as e:
                msg = str(e)
                low = msg.lower()
                if "quota" in low or "429" in low or "resource_exhausted" in low:
                    last_err = self.strings("quota_error")
                    continue  # пробуем следующий ключ
                if ("location" in low or "user location" in low
                        or "not supported" in low or "failed_precondition" in low):
                    return self.strings("region_error"), False
                if ("api key" in low or "api_key" in low
                        or "invalid" in low or "unauthenticated" in low
                        or "permission" in low or "401" in low or "403" in low):
                    last_err = self.strings("invalid_api_key")
                    continue  # пробуем следующий ключ
                last_err = self.strings("api_error").format(escape_html(msg[:500]))
                logger.exception("GeminiK: API call failed")
            finally:
                if client is not None:
                    try:
                        await client.aio.close()
                    except Exception:
                        pass

        return last_err or self.strings("api_error").format("Unknown error"), False

    # ── Вывод длинного ответа ──

    async def _send_answer(self, status_msg, header: str, answer: str) -> None:
        full = f"{header}\n\n{answer}"
        if len(full) <= MAX_MSG_LEN:
            await status_msg.edit(full, parse_mode="html", link_preview=False)
            return
        # Первая часть редактирует статус, остальные — отдельные сообщения.
        first = True
        chat_id = getattr(status_msg, "chat_id", None)
        for i in range(0, len(full), MAX_MSG_LEN):
            chunk = full[i:i + MAX_MSG_LEN]
            if first:
                await status_msg.edit(chunk, parse_mode="html", link_preview=False)
                first = False
            else:
                try:
                    await self.client.send_message(
                        chat_id, chunk, parse_mode="html", link_preview=False
                    )
                except Exception:
                    await self.client.send_message(chat_id, chunk)

    # ──────────────────────────────────────────────────
    # Commands
    # ──────────────────────────────────────────────────

    @command("g", required=OWNER, aliases=["gemini", "ai"])
    async def g_cmd(self, event) -> None:
        """<текст> — спросить Gemini. Ответь на медиа для анализа."""
        if not GOOGLE_AVAILABLE:
            await event.edit(self.strings("sdk_missing"), parse_mode="html")
            return
        if not self._get_api_keys():
            await event.edit(self.strings("no_api_key"), parse_mode="html")
            return

        text = (self.get_args(event) or "").strip()
        try:
            reply = await event.message.get_reply_message()
        except Exception:
            reply = None

        parts: list = []
        display_text = text

        if reply:
            media = await self._get_media_part(reply)
            if media:
                parts.append(media)
                if text:
                    parts.append(text)
                display_text = text or "[медиа]"
            else:
                reply_text = (getattr(reply, "text", "") or "").strip()
                if reply_text:
                    combined = f"{reply_text}\n\n{text}".strip() if text else reply_text
                    parts.append(combined)
                    display_text = combined
                elif text:
                    parts.append(text)
        elif text:
            parts.append(text)

        if not parts:
            await event.edit(self.strings("no_prompt"), parse_mode="html")
            return

        await event.edit(self.strings("processing"), parse_mode="html")

        chat_id = event.chat_id
        history = self._get_history(chat_id)
        answer, ok = await self._call_gemini(parts, history)

        if ok:
            self._append_history(chat_id, display_text or "[медиа]", answer)
            header = f"{self.strings('response_prefix')} {self._mem_display(chat_id)}"
            await self._send_answer(event, header, answer)
        else:
            await event.edit(answer, parse_mode="html", link_preview=False)

    @command("gclear", required=OWNER, aliases=["gc"])
    async def gclear_cmd(self, event) -> None:
        """Очистить память Gemini в этом чате."""
        chat_id = event.chat_id
        if not self._get_history(chat_id):
            await event.edit(self.strings("no_mem"), parse_mode="html")
            return
        self._clear_history(chat_id)
        await event.edit(self.strings("mem_cleared"), parse_mode="html")

    @command("gsafety", required=OWNER)
    async def gsafety_cmd(self, event) -> None:
        """[none/low/medium/high] — уровень safety-фильтров Gemini."""
        arg = (self.get_args(event) or "").strip().lower()
        current = self._get_safety_level()

        if not arg:
            await event.edit(self.strings("safety_show").format(current), parse_mode="html")
            return
        if arg not in _SAFETY_MAP:
            await event.edit(self.strings("safety_bad"), parse_mode="html")
            return

        await self.db.set(DB_OWNER, DB_SAFETY_KEY, arg)
        await event.edit(
            self.strings("safety_set").format(_SAFETY_ICONS[arg], arg),
            parse_mode="html",
        )

    @command("gmodel", required=OWNER)
    async def gmodel_cmd(self, event) -> None:
        """[модель] — показать или сменить модель Gemini."""
        arg = (self.get_args(event) or "").strip()
        if not arg:
            await event.edit(
                self.strings("model_show").format(escape_html(self._cfg("model_name", ""))),
                parse_mode="html",
            )
            return
        try:
            await self._save_cfg("model_name", arg)
        except Exception as e:
            await event.edit(
                self.strings("api_error").format(escape_html(str(e))),
                parse_mode="html",
            )
            return
        await event.edit(
            self.strings("model_set").format(escape_html(arg)),
            parse_mode="html",
        )

    @command("gkeys", required=OWNER)
    async def gkeys_cmd(self, event) -> None:
        """Показать количество настроенных API-ключей."""
        keys = self._get_api_keys()
        if not keys:
            await event.edit(self.strings("keys_none"), parse_mode="html")
            return
        await event.edit(self.strings("keys_status").format(len(keys)), parse_mode="html")
