"""
KiSearch — поиск и установка модулей из @KitsuneModules
Автор: @Mikasu32
"""
# meta developer: @Mikasu32

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from kitsune.core.loader import KitsuneModule, command
from kitsune.core.security import OWNER

logger = logging.getLogger(__name__)

# ─── Настройки канала (не менять) ────────────────────────────────────────────

_CHANNEL    = "KitsuneModules"
_CHANNEL_ID = -1003823823667
_DB_NS      = "kitsune.kisearch"
_DB_KEY     = "index"
_PAGE_SIZE  = 8

# Ищем прямые ссылки на .py (GitHub raw, CDN и т.п.)
_URL_RE = re.compile(r'https?://\S+\.py(?:\b[^\s]*)?', re.IGNORECASE)


# ─── Индекс ───────────────────────────────────────────────────────────────────

class _Index:
    """Локальный индекс модулей, хранится в БД как JSON."""

    def __init__(self, db: Any) -> None:
        self._db: Any = db
        self._data: list[dict] = []

    def load(self) -> None:
        raw = self._db.get(_DB_NS, _DB_KEY, "[]")
        try:
            self._data = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except Exception:
            self._data = []

    async def persist(self) -> None:
        await self._db.set(_DB_NS, _DB_KEY,
                           json.dumps(self._data, ensure_ascii=False))

    def replace(self, entries: list[dict]) -> None:
        self._data = list(entries)

    def all(self) -> list[dict]:
        return list(self._data)

    def search(self, query: str) -> list[dict]:
        q = query.lower().strip()
        if not q:
            return self.all()
        result = []
        for e in self._data:
            hay = (
                e.get("name", "").lower()
                + " " + e.get("filename", "").lower()
                + " " + e.get("caption", "").lower()
            )
            if q in hay:
                result.append(e)
        return result

    def __len__(self) -> int:
        return len(self._data)


# ─── Сканер канала ────────────────────────────────────────────────────────────

async def _scan_channel(client: Any, progress_cb=None) -> list[dict]:
    """
    Перебирает сообщения @KitsuneModules.
    Поддерживает два формата поста:
      • вложенный .py файл (старый формат)
      • ссылка на raw .py в тексте сообщения (новый формат)
    Возвращает список записей для индекса.
    """
    entries: list[dict] = []

    try:
        async for msg in client.iter_messages(_CHANNEL, limit=None):
            caption: str = (msg.message or "").strip()
            fname: str | None = None
            url: str | None = None

            # ── Вариант 1: вложенный .py файл ──────────────────────────────
            if msg.file:
                f = getattr(msg.file, "name", None) or ""
                if f.lower().endswith(".py"):
                    fname = f

            # ── Вариант 2: ссылка на .py в тексте ──────────────────────────
            if not fname:
                m = _URL_RE.search(caption)
                if m:
                    raw_url = m.group(0).rstrip(".,)")
                    if raw_url.lower().endswith(".py"):
                        url   = raw_url
                        fname = raw_url.split("/")[-1].split("?")[0]

            if not fname:
                continue

            # Читаемое имя: title-case из имени файла
            stem = re.sub(r"\.py$", "", fname, flags=re.IGNORECASE)
            display = stem.replace("_", " ").replace("-", " ").strip().title()

            # Если первая строка caption короткая и не похожа на код — берём её
            if caption:
                first = caption.split("\n")[0].strip()
                first = re.sub(r"^[#📦🦊⚙️🔧💾\-*\s]+", "", first).strip()
                if first and len(first) <= 60 and not first.startswith(
                    ("import", "from", "class", "def", "http")
                ):
                    display = first

            date_str = msg.date.strftime("%d.%m.%Y") if msg.date else "—"

            entries.append({
                "name":     display,
                "filename": fname,
                "caption":  caption,
                "msg_id":   msg.id,
                "url":      url,       # str — ссылка; None — вложенный файл
                "date":     date_str,
            })

            if progress_cb and len(entries) % 10 == 0:
                try:
                    await progress_cb(len(entries))
                except Exception:
                    pass

    except Exception as exc:
        logger.exception("KiSearch._scan_channel: ошибка")
        raise RuntimeError(str(exc)) from exc

    return entries


# ─── Главный модуль ───────────────────────────────────────────────────────────

class KiSearchModule(KitsuneModule):
    """Поиск и установка модулей из @KitsuneModules."""

    name        = "KiSearch"
    description = "Поиск и установка модулей из @KitsuneModules"
    author      = "@Mikasu32"
    version     = "1.0.0"
    icon        = "🦊"
    category    = "loader"

    # ─── Строки ────────────────────────────────────────────────────────────────

    strings_ru = {
        # Поиск
        "no_args":      "❌ Укажи название модуля:\n<code>.ks ping</code>",
        "searching":    "🔍 Ищу <b>{query}</b>...",
        "not_found":    "🔍 Ничего не найдено по запросу <b>{query}</b>.",
        # Пустой индекс
        "no_index":     (
            "📭 Каталог ещё не загружен.\n"
            "Запускаю фоновое сканирование <b>@KitsuneModules</b>...\n"
            "Когда закончу — напишу в <b>Избранное</b>."
        ),
        # Синхронизация
        "syncing":      "🔄 Сканирую <b>@KitsuneModules</b>...\nНайдено: <b>{count}</b>",
        "synced":       "✅ Каталог обновлён — <b>{count}</b> модулей.",
        "sync_err":     "❌ Ошибка сканирования:\n<code>{err}</code>",
        "already_sync": "⏳ Сканирование уже выполняется, подожди...",
        "bg_done":      "🦊 Каталог <b>@KitsuneModules</b> готов: <b>{count}</b> модулей.",
        # Установка
        "installing":   "⏳ Устанавливаю <b>{name}</b>...",
        "installed":    "✅ <b>{name}</b> успешно установлен.",
        "inst_err":     "❌ Ошибка установки:\n<code>{err}</code>",
        "no_file":      "❌ Файл недоступен.",
        # Карточка
        "card":         "📦 <b>{name}</b>  ·  <i>{filename}</i>\n📅 {date}\n\n{caption}",
        "card_nodesc":  "📦 <b>{name}</b>  ·  <i>{filename}</i>\n📅 {date}\n\n<i>Описание отсутствует</i>",
        "counter":      "{idx} / {total}",
        # Кнопки
        "btn_install":  "⬇️ Установить",
        "btn_source":   "📨 Источник",
        "btn_prev":     "←",
        "btn_next":     "→",
        # Список
        "list_title":   "📋 Каталог <b>@KitsuneModules</b> — <b>{total}</b> модулей:",
        "list_empty":   "📭 Каталог пуст. Запусти <code>.kssync</code> для сканирования.",
    }

    strings_en = {
        "no_args":      "❌ Specify a module name:\n<code>.ks ping</code>",
        "searching":    "🔍 Searching <b>{query}</b>...",
        "not_found":    "🔍 Nothing found for <b>{query}</b>.",
        "no_index":     (
            "📭 Catalog is not loaded yet.\n"
            "Starting background scan of <b>@KitsuneModules</b>...\n"
            "I'll notify you in <b>Saved Messages</b> when done."
        ),
        "syncing":      "🔄 Scanning <b>@KitsuneModules</b>...\nFound: <b>{count}</b>",
        "synced":       "✅ Catalog updated — <b>{count}</b> modules.",
        "sync_err":     "❌ Scan error:\n<code>{err}</code>",
        "already_sync": "⏳ Scan already in progress, please wait...",
        "bg_done":      "🦊 <b>@KitsuneModules</b> catalog ready: <b>{count}</b> modules.",
        "installing":   "⏳ Installing <b>{name}</b>...",
        "installed":    "✅ <b>{name}</b> successfully installed.",
        "inst_err":     "❌ Installation error:\n<code>{err}</code>",
        "no_file":      "❌ File is unavailable.",
        "card":         "📦 <b>{name}</b>  ·  <i>{filename}</i>\n📅 {date}\n\n{caption}",
        "card_nodesc":  "📦 <b>{name}</b>  ·  <i>{filename}</i>\n📅 {date}\n\n<i>No description</i>",
        "counter":      "{idx} / {total}",
        "btn_install":  "⬇️ Install",
        "btn_source":   "📨 Source",
        "btn_prev":     "←",
        "btn_next":     "→",
        "list_title":   "📋 <b>@KitsuneModules</b> catalog — <b>{total}</b> modules:",
        "list_empty":   "📭 Catalog is empty. Run <code>.kssync</code> to scan.",
    }

    # ─── Инициализация ─────────────────────────────────────────────────────────

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._idx: _Index | None = None
        self._syncing: bool = False

    async def on_load(self) -> None:
        self._idx = _Index(self.db)
        self._idx.load()
        if not len(self._idx):
            asyncio.create_task(self._bg_sync())

    async def on_unload(self) -> None:
        pass

    # ─── Фоновая синхронизация ────────────────────────────────────────────────

    async def _bg_sync(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            entries = await _scan_channel(self.client)
            self._idx.replace(entries)
            await self._idx.persist()
            logger.info("KiSearch: фоновая синхронизация завершена — %d модулей", len(entries))
            try:
                await self.client.send_message(
                    "me",
                    self.strings("bg_done", count=len(entries)),
                    parse_mode="html",
                )
            except Exception:
                pass
        except Exception:
            logger.exception("KiSearch: фоновая синхронизация упала")
        finally:
            self._syncing = False

    # ─── Вспомогательный метод ────────────────────────────────────────────────

    def _inline(self):
        return (
            getattr(self.client, "_kitsune_inline", None)
            or getattr(self.client, "inline", None)
        )

    # ─── Команды ──────────────────────────────────────────────────────────────

    @command("ks", required=OWNER, aliases=["kisearch"])
    async def ks_cmd(self, event) -> None:
        """ks <название> — найти модуль в каталоге @KitsuneModules"""
        query = self.get_args(event).strip()

        if not query:
            await event.message.edit(self.strings("no_args"), parse_mode="html")
            return

        await event.message.edit(self.strings("searching", query=query), parse_mode="html")

        if not len(self._idx):
            await event.message.edit(self.strings("no_index"), parse_mode="html")
            if not self._syncing:
                asyncio.create_task(self._bg_sync())
            return

        results = self._idx.search(query)

        if not results:
            await event.message.edit(
                self.strings("not_found", query=query), parse_mode="html"
            )
            return

        inline = self._inline()

        if not inline:
            await event.message.edit(
                self._card_text(results[0], 1, len(results)), parse_mode="html"
            )
            return

        await inline.form(
            text=self._card_text(results[0], 1, len(results)),
            message=event.message,
            reply_markup=self._card_buttons(results[0], results, 0),
        )

    @command("kssync", required=OWNER)
    async def kssync_cmd(self, event) -> None:
        """kssync — переиндексировать канал @KitsuneModules"""
        if self._syncing:
            await event.message.edit(self.strings("already_sync"), parse_mode="html")
            return

        self._syncing = True

        async def _progress(n: int) -> None:
            try:
                await event.message.edit(
                    self.strings("syncing", count=n), parse_mode="html"
                )
            except Exception:
                pass

        try:
            entries = await _scan_channel(self.client, progress_cb=_progress)
            self._idx.replace(entries)
            await self._idx.persist()
            await event.message.edit(
                self.strings("synced", count=len(entries)), parse_mode="html"
            )
        except Exception as exc:
            logger.exception("KiSearch.kssync: ошибка")
            await event.message.edit(
                self.strings("sync_err", err=str(exc)[:200]), parse_mode="html"
            )
        finally:
            self._syncing = False

    @command("kslist", required=OWNER)
    async def kslist_cmd(self, event) -> None:
        """kslist — список всех модулей в каталоге"""
        entries = self._idx.all()

        if not entries:
            await event.message.edit(self.strings("list_empty"), parse_mode="html")
            return

        inline = self._inline()

        if not inline:
            lines = "\n".join(f"📦 <b>{e['name']}</b>" for e in entries[:30])
            tail = f"\n<i>…ещё {len(entries) - 30}</i>" if len(entries) > 30 else ""
            await event.message.edit(
                self.strings("list_title", total=len(entries))
                + "\n\n" + lines + tail,
                parse_mode="html",
            )
            return

        await inline.form(
            text=self.strings("list_title", total=len(entries)),
            message=event.message,
            reply_markup=self._list_buttons(entries, 0),
        )

    # ─── Callbacks ────────────────────────────────────────────────────────────

    async def _cb_nav(self, call, results: list, idx: int) -> None:
        """Листание карточек поиска ← →."""
        idx = max(0, min(idx, len(results) - 1))
        inline = self._inline()
        if inline:
            await inline.edit(
                call,
                self._card_text(results[idx], idx + 1, len(results)),
                reply_markup=self._card_buttons(results[idx], results, idx),
            )
        await call.answer()

    async def _cb_install(self, call, msg_id: int, filename: str, name: str, url: str | None = None) -> None:
        """Установить модуль: по URL (новый формат) или из вложения канала (старый формат)."""
        loader = getattr(self.client, "_kitsune_loader", None)
        inline = self._inline()

        if not loader:
            await call.answer("❌ Loader недоступен", show_alert=True)
            return

        await call.answer()

        async def _edit(text: str) -> None:
            if inline:
                try:
                    await inline.edit(call, text, reply_markup=[])
                except Exception:
                    pass

        await _edit(self.strings("installing", name=name))

        try:
            # ── Вариант 1: ссылка — пробуем load_from_url, иначе скачиваем сами ──
            if url:
                if hasattr(loader, "load_from_url"):
                    mod = await loader.load_from_url(url, progress_cb=_edit)
                else:
                    import urllib.request
                    data: bytes = await asyncio.to_thread(
                        lambda: urllib.request.urlopen(url, timeout=30).read()
                    )
                    mod_dir = Path.home() / ".kitsune" / "modules"
                    mod_dir.mkdir(parents=True, exist_ok=True)
                    dest = mod_dir / filename
                    dest.write_bytes(data)
                    mod = await loader.load_from_file(dest, progress_cb=_edit)

            # ── Вариант 2: вложенный файл в сообщении канала ──────────────────
            else:
                msg = await self.client.get_messages(_CHANNEL_ID, ids=msg_id)
                if not msg or not msg.file:
                    await call.answer(self.strings("no_file"), show_alert=True)
                    return
                data = await self.client.download_media(msg, bytes)
                mod_dir = Path.home() / ".kitsune" / "modules"
                mod_dir.mkdir(parents=True, exist_ok=True)
                dest = mod_dir / filename
                dest.write_bytes(data)
                mod = await loader.load_from_file(dest, progress_cb=_edit)

            await _edit(self.strings("installed", name=mod.name))
            await call.answer(f"✅ {mod.name} установлен!", show_alert=True)

        except Exception as exc:
            logger.exception("KiSearch._cb_install: ошибка для %s", filename)
            err = str(exc)[:250]
            await _edit(self.strings("inst_err", err=err))
            await call.answer(f"❌ {err[:80]}", show_alert=True)

    async def _cb_open_card(self, call, entries: list, idx: int) -> None:
        """Открыть карточку из списка .kslist."""
        inline = self._inline()
        if inline:
            e = entries[idx]
            await inline.edit(
                call,
                self._card_text(e, idx + 1, len(entries)),
                reply_markup=self._card_buttons(e, entries, idx),
            )
        await call.answer()

    async def _cb_list_page(self, call, entries: list, page: int) -> None:
        """Листание страниц в .kslist."""
        inline = self._inline()
        if inline:
            await inline.edit(
                call,
                self.strings("list_title", total=len(entries)),
                reply_markup=self._list_buttons(entries, page),
            )
        await call.answer()

    # ─── Сборщики UI ──────────────────────────────────────────────────────────

    def _card_text(self, entry: dict, idx: int, total: int) -> str:
        name     = entry.get("name", entry.get("filename", "?"))
        filename = entry.get("filename", "")
        date     = entry.get("date", "—")
        caption  = entry.get("caption", "").strip()

        if len(caption) > 450:
            caption = caption[:447] + "…"

        if caption:
            return self.strings(
                "card", name=name, filename=filename, date=date, caption=caption
            )
        return self.strings("card_nodesc", name=name, filename=filename, date=date)

    def _card_buttons(self, entry: dict, results: list, idx: int) -> list[list[dict]]:
        msg_id   = entry.get("msg_id")
        filename = entry.get("filename", "")
        name     = entry.get("name", filename)
        url      = entry.get("url")          # None для вложений, str для ссылок

        top: list[dict] = [
            {
                "text":     self.strings("btn_install"),
                "callback": self._cb_install,
                "args":     (msg_id, filename, name, url),
            },
        ]
        if msg_id:
            top.append({
                "text": self.strings("btn_source"),
                "url":  f"https://t.me/{_CHANNEL}/{msg_id}",
            })

        rows: list[list[dict]] = [top]

        if len(results) > 1:
            nav: list[dict] = []
            if idx > 0:
                nav.append({
                    "text":     self.strings("btn_prev"),
                    "callback": self._cb_nav,
                    "args":     (results, idx - 1),
                })
            nav.append({
                "text":     self.strings("counter", idx=idx + 1, total=len(results)),
                "callback": self._cb_nav,
                "args":     (results, idx),
            })
            if idx < len(results) - 1:
                nav.append({
                    "text":     self.strings("btn_next"),
                    "callback": self._cb_nav,
                    "args":     (results, idx + 1),
                })
            rows.append(nav)

        return rows

    def _list_buttons(self, entries: list, page: int) -> list[list[dict]]:
        start = page * _PAGE_SIZE
        end   = min(start + _PAGE_SIZE, len(entries))
        rows: list[list[dict]] = []

        for i in range(start, end):
            e = entries[i]
            rows.append([{
                "text":     f"📦  {e['name']}",
                "callback": self._cb_open_card,
                "args":     (entries, i),
            }])

        total_pages = (len(entries) + _PAGE_SIZE - 1) // _PAGE_SIZE
        if total_pages > 1:
            pager: list[dict] = []
            if page > 0:
                pager.append({
                    "text":     "←",
                    "callback": self._cb_list_page,
                    "args":     (entries, page - 1),
                })
            pager.append({
                "text":     f"{page + 1} / {total_pages}",
                "callback": self._cb_list_page,
                "args":     (entries, page),
            })
            if page < total_pages - 1:
                pager.append({
                    "text":     "→",
                    "callback": self._cb_list_page,
                    "args":     (entries, page + 1),
                })
            rows.append(pager)

        return rows
