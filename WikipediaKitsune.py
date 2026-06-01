from __future__ import annotations
import asyncio
import logging
import typing
from urllib.parse import quote

import aiohttp

from ..core.loader import KitsuneModule, command, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..utils import escape_html
from ..validators import Integer

logger = logging.getLogger(__name__)

_USER_AGENT = "KitsuneUserBot-Wikipedia/1.0 (https://t.me/KitsuneUB)"
_API_BASE   = "https://{lang}.wikipedia.org/w/api.php"
_PAGE_URL   = "https://{lang}.wikipedia.org/wiki/{title}"
_TIMEOUT    = aiohttp.ClientTimeout(total=15, connect=8)


async def _wiki_search(session: aiohttp.ClientSession, lang: str, query: str, limit: int) -> list[str]:
    params = {
        "action":    "opensearch",
        "search":    query,
        "limit":     str(limit),
        "namespace": "0",
        "format":    "json",
    }
    async with session.get(_API_BASE.format(lang=lang), params=params) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
        return [t for t in data[1] if isinstance(t, str) and t]
    return []


async def _wiki_summary(session: aiohttp.ClientSession, lang: str, title: str, sentences: int) -> tuple[str, str] | None:
    params = {
        "action":        "query",
        "prop":          "extracts",
        "exintro":       "1",
        "explaintext":   "1",
        "exsentences":   str(sentences),
        "redirects":     "1",
        "titles":        title,
        "format":        "json",
        "formatversion": "2",
    }
    async with session.get(_API_BASE.format(lang=lang), params=params) as resp:
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    pages = (data.get("query") or {}).get("pages") or []
    if not pages:
        return None
    page = pages[0]
    if page.get("missing"):
        return None
    extract = page.get("extract") or ""
    real_title = page.get("title") or title
    if not extract.strip():
        return None
    return real_title, extract.strip()


class WikipediaKitsuneModule(KitsuneModule):
    name        = "WikipediaKitsune"
    description = "Поиск статей в Wikipedia на нескольких языках через REST API. Адаптировал @Mikasu32"
    author      = "dend1yya | adapted by @Mikasu32"
    version     = "2.0.0"
    icon        = "📚"
    category    = "info"

    strings_ru = {
        "no_query":   "❌ <b>Введите свой поисковый запрос на Википедии.</b>\nПример: <code>.wikiru Telegram</code>",
        "loading":    "🔍 <b>Ищу в Википедии...</b>",
        "result":     "📚 <b>{title}</b>\n\n<blockquote expandable>{text}</blockquote>\n\n🔗 <a href=\"{url}\">{lang_label}</a>",
        "disambig":   "🦋 <b>Найдено несколько вариантов. Уточните запрос:</b>\n\n{options}",
        "not_found":  "❌ <b>По запросу <i>{query}</i> ничего не найдено.</b>",
        "error":      "❌ <b>Ошибка при выполнении запроса:</b>\n<code>{err}</code>",
        "timeout":    "❌ <b>Превышено время ожидания ответа от Wikipedia.</b>",
        "lang_ru":    "Открыть в Википедии",
        "lang_en":    "Open in Wikipedia",
        "lang_uz":    "Vikipediyada ochish",
        "lang_de":    "In Wikipedia öffnen",
        "lang_es":    "Abrir en Wikipedia",
    }

    strings_en = {
        "no_query":   "❌ <b>Enter your search term on Wikipedia.</b>\nExample: <code>.wikien Telegram</code>",
        "loading":    "🔍 <b>Searching Wikipedia...</b>",
        "result":     "📚 <b>{title}</b>\n\n<blockquote expandable>{text}</blockquote>\n\n🔗 <a href=\"{url}\">{lang_label}</a>",
        "disambig":   "🦋 <b>Several possible options found. Specify your request:</b>\n\n{options}",
        "not_found":  "❌ <b>Nothing found for query <i>{query}</i>.</b>",
        "error":      "❌ <b>An error occurred while executing the request:</b>\n<code>{err}</code>",
        "timeout":    "❌ <b>Wikipedia request timed out.</b>",
        "lang_ru":    "Open in Wikipedia",
        "lang_en":    "Open in Wikipedia",
        "lang_uz":    "Open in Wikipedia",
        "lang_de":    "Open in Wikipedia",
        "lang_es":    "Open in Wikipedia",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "sentences",
                5,
                "Количество предложений в выдержке (1-15)",
                validator=Integer(minimum=1, maximum=15),
            ),
            ConfigValue(
                "disambig_limit",
                8,
                "Максимум вариантов при неоднозначности (3-15)",
                validator=Integer(minimum=3, maximum=15),
            ),
            ConfigValue(
                "max_length",
                3500,
                "Максимальная длина текста выдержки (500-4000)",
                validator=Integer(minimum=500, maximum=4000),
            ),
        )

    async def _do_search(self, event, lang: str) -> None:
        query = self.get_args(event).strip()
        if not query:
            await event.edit(self.strings("no_query"), parse_mode="html")
            return

        await event.edit(self.strings("loading"), parse_mode="html")

        cfg = self.config
        sentences      = cfg["sentences"]      if cfg else 5
        disambig_limit = cfg["disambig_limit"] if cfg else 8
        max_length     = cfg["max_length"]     if cfg else 3500

        headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT, headers=headers) as session:
                summary = await _wiki_summary(session, lang, query, sentences)
                if summary is not None:
                    title, extract = summary
                    if len(extract) > max_length:
                        extract = extract[:max_length].rsplit(" ", 1)[0] + "…"
                    page_url = _PAGE_URL.format(lang=lang, title=quote(title.replace(" ", "_")))
                    label_key = f"lang_{lang}"
                    lang_label = self.strings(label_key) if label_key in (self.strings_ru if lang == "ru" else self.strings_en) else self.strings("lang_en")
                    await event.edit(
                        self.strings("result").format(
                            title=escape_html(title),
                            text=escape_html(extract),
                            url=page_url,
                            lang_label=lang_label,
                        ),
                        parse_mode="html",
                        link_preview=False,
                    )
                    return

                options = await _wiki_search(session, lang, query, disambig_limit)
        except asyncio.TimeoutError:
            await event.edit(self.strings("timeout"), parse_mode="html")
            return
        except aiohttp.ClientResponseError as exc:
            await event.edit(
                self.strings("error").format(err=f"HTTP {exc.status}: {escape_html(exc.message or '')}"),
                parse_mode="html",
            )
            return
        except Exception as exc:
            logger.exception("WikipediaKitsune: unexpected error")
            await event.edit(
                self.strings("error").format(err=escape_html(str(exc))[:200]),
                parse_mode="html",
            )
            return

        if not options:
            await event.edit(
                self.strings("not_found").format(query=escape_html(query)),
                parse_mode="html",
            )
            return

        formatted = "\n".join(
            f"• <code>{escape_html(opt)}</code>" for opt in options
        )
        await event.edit(
            self.strings("disambig").format(options=formatted),
            parse_mode="html",
            link_preview=False,
        )

    @command("wikiru", required=OWNER, aliases=["вики", "википедия"])
    async def wikiru_cmd(self, event) -> None:
        await self._do_search(event, "ru")

    @command("wikien", required=OWNER, aliases=["wiki"])
    async def wikien_cmd(self, event) -> None:
        await self._do_search(event, "en")

    @command("wikiuz")
    async def wikiuz_cmd(self, event) -> None:
        await self._do_search(event, "uz")

    @command("wikide")
    async def wikide_cmd(self, event) -> None:
        await self._do_search(event, "de")

    @command("wikies")
    async def wikies_cmd(self, event) -> None:
        await self._do_search(event, "es")
