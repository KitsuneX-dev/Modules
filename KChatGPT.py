__version__ = (1, 0, 0)

# ──────────────────────────────────────────────────────────────────────────
#    █▄▀ █ ▀█▀ █▀ █ █ █▄ █ █▀▀
#    █ █ █  █  ▄█ █▄█ █ ▀█ ██▄
#    Адаптация под Kitsune UserBot
#    Original: Copyright 2022 t.me/morisummermods
#    Licensed under CC BY-NC-SA 4.0 International
# ──────────────────────────────────────────────────────────────────────────
# meta developer: @morisummermods (adapted for Kitsune)
# meta banner: https://i.imgur.com/H1vPM6U.jpg

import contextlib
import logging
import re
import typing

import requests

from ..core.loader import KitsuneModule, command, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..utils import answer, escape_html, run_sync
from ..validators import Hidden, String

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class KChatGPT(KitsuneModule):
    """ChatGPT AI API interaction (adapted for Kitsune)"""

    name = "ChatGPT"
    description = "ChatGPT AI API interaction"
    author = "morisummermods"
    version = "1.0.0"
    icon = "🤖"
    category = "ai"

    pip_requires: typing.ClassVar[list[str]] = ["requests"]

    strings_en = {
        "name": "ChatGPT",
        "no_args": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>No arguments"
            " provided</b>"
        ),
        "question": (
            "<emoji document_id=5974038293120027938>👤</emoji> <b>Question:</b>"
            " {question}\n"
        ),
        "answer": (
            "<emoji document_id=5199682846729449178>🤖</emoji> <b>Answer:</b> {answer}"
        ),
        "loading": "<code>Loading...</code>",
        "no_api_key": (
            "<b>🚫 No API key provided</b>\n<i><emoji"
            " document_id=5199682846729449178>ℹ️</emoji> Get it from official OpenAI"
            " website and add it to config</i>"
        ),
        "request_error": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Request failed:</b>"
            " <code>{err}</code>"
        ),
    }

    strings_ru = {
        "no_args": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Не указаны"
            " аргументы</b>"
        ),
        "question": (
            "<emoji document_id=5974038293120027938>👤</emoji> <b>Вопрос:</b>"
            " {question}\n"
        ),
        "answer": (
            "<emoji document_id=5199682846729449178>🤖</emoji> <b>Ответ:</b> {answer}"
        ),
        "loading": "<code>Загрузка...</code>",
        "no_api_key": (
            "<b>🚫 Не указан API ключ</b>\n<i><emoji"
            " document_id=5199682846729449178>ℹ️</emoji> Получите его на официальном"
            " сайте OpenAI и добавьте в конфиг</i>"
        ),
        "request_error": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Ошибка запроса:</b>"
            " <code>{err}</code>"
        ),
    }

    strings_es = {
        "no_args": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>No se han"
            " proporcionado argumentos</b>"
        ),
        "question": (
            "<emoji document_id=5974038293120027938>👤</emoji> <b>Pregunta:</b>"
            " {question}\n"
        ),
        "answer": (
            "<emoji document_id=5199682846729449178>🤖</emoji> <b>Respuesta:</b>"
            " {answer}"
        ),
        "loading": "<code>Cargando...</code>",
        "no_api_key": (
            "<b>🚫 No se ha proporcionado una clave API</b>\n<i><emoji"
            " document_id=5199682846729449178>ℹ️</emoji> Obtenga una en el sitio web"
            " oficial de OpenAI y agréguela a la configuración</i>"
        ),
        "request_error": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Solicitud fallida:</b>"
            " <code>{err}</code>"
        ),
    }

    strings_fr = {
        "no_args": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Aucun argument"
            " fourni</b>"
        ),
        "question": (
            "<emoji document_id=5974038293120027938>👤</emoji> <b>Question:</b>"
            " {question}\n"
        ),
        "answer": (
            "<emoji document_id=5199682846729449178>🤖</emoji> <b>Réponse:</b> {answer}"
        ),
        "loading": "<code>Chargement...</code>",
        "no_api_key": (
            "<b>🚫 Aucune clé API fournie</b>\n<i><emoji"
            " document_id=5199682846729449178>ℹ️</emoji> Obtenez-en un sur le site"
            " officiel d'OpenAI et ajoutez-le à la configuration</i>"
        ),
        "request_error": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Échec de la"
            " requête:</b> <code>{err}</code>"
        ),
    }

    strings_de = {
        "no_args": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Keine Argumente"
            " angegeben</b>"
        ),
        "question": (
            "<emoji document_id=5974038293120027938>👤</emoji> <b>Frage:</b>"
            " {question}\n"
        ),
        "answer": (
            "<emoji document_id=5199682846729449178>🤖</emoji> <b>Antwort:</b> {answer}"
        ),
        "loading": "<code>Laden...</code>",
        "no_api_key": (
            "<b>🚫 Kein API-Schlüssel angegeben</b>\n<i><emoji"
            " document_id=5199682846729449178>ℹ️</emoji> Holen Sie sich einen auf der"
            " offiziellen OpenAI-Website und fügen Sie ihn der Konfiguration hinzu</i>"
        ),
        "request_error": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Anfrage"
            " fehlgeschlagen:</b> <code>{err}</code>"
        ),
    }

    strings_tr = {
        "no_args": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Argümanlar"
            " verilmedi</b>"
        ),
        "question": (
            "<emoji document_id=5974038293120027938>👤</emoji> <b>Soru:</b> {question}\n"
        ),
        "answer": (
            "<emoji document_id=5199682846729449178>🤖</emoji> <b>Cevap:</b> {answer}"
        ),
        "loading": "<code>Yükleniyor...</code>",
        "no_api_key": (
            "<b>🚫 API anahtarı verilmedi</b>\n<i><emoji"
            " document_id=5199682846729449178>ℹ️</emoji> OpenAI'nın resmi websitesinden"
            " alın ve yapılandırmaya ekleyin</i>"
        ),
        "request_error": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>İstek başarısız:</b>"
            " <code>{err}</code>"
        ),
    }

    strings_uz = {
        "no_args": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Argumentlar"
            " ko'rsatilmadi</b>"
        ),
        "question": (
            "<emoji document_id=5974038293120027938>👤</emoji> <b>Savol:</b>"
            " {question}\n"
        ),
        "answer": (
            "<emoji document_id=5199682846729449178>🤖</emoji> <b>Javob:</b> {answer}"
        ),
        "loading": "<code>Yuklanmoqda...</code>",
        "no_api_key": (
            "<b>🚫 API kalit ko'rsatilmadi</b>\n<i><emoji"
            " document_id=5199682846729449178>ℹ️</emoji> Ofitsial OpenAI veb-saytidan"
            " oling</i>"
        ),
        "request_error": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>So'rov xatosi:</b>"
            " <code>{err}</code>"
        ),
    }

    strings_it = {
        "no_args": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Nessun argomento"
            " fornito</b>"
        ),
        "question": (
            "<emoji document_id=5974038293120027938>👤</emoji> <b>Domanda:</b>"
            " {question}\n"
        ),
        "answer": (
            "<emoji document_id=5199682846729449178>🤖</emoji> <b>Risposta:</b> {answer}"
        ),
        "loading": "<code>Caricamento...</code>",
        "no_api_key": (
            "<b>🚫 Nessuna chiave API fornita</b>\n<i><emoji"
            " document_id=5199682846729449178>ℹ️</emoji> Ottienila dal sito ufficiale"
            " di OpenAI e aggiungila al tuo file di configurazione</i>"
        ),
        "request_error": (
            "<emoji document_id=5312526098750252863>🚫</emoji> <b>Richiesta fallita:</b>"
            " <code>{err}</code>"
        ),
    }

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "api_key",
                "",
                "API key from OpenAI",
                validator=Hidden(String()),
            ),
            ConfigValue(
                "model",
                "gpt-3.5-turbo",
                "OpenAI chat completion model name",
                validator=String(max_len=100),
            ),
        )

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: dict,
        data: dict,
    ) -> dict:
        resp = await run_sync(
            requests.request,
            method,
            url,
            headers=headers,
            json=data,
            timeout=60,
        )
        return resp.json()

    def _process_code_tags(self, text: str) -> str:
        return re.sub(
            r"`(.*?)`",
            r"<code>\1</code>",
            re.sub(r"```(.*?)```", r"<code>\1</code>", text, flags=re.DOTALL),
            flags=re.DOTALL,
        )

    async def _get_chat_completion(self, prompt: str) -> str:
        try:
            resp = await self._make_request(
                method="POST",
                url=_OPENAI_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f'Bearer {self.config["api_key"]}',
                },
                data={
                    "model": self.config["model"],
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        except Exception as exc:
            logger.exception("ChatGPT: request failed")
            return f"🚫 {exc}"

        if resp.get("error", None):
            with contextlib.suppress(Exception):
                return f"🚫 {resp['error']['message']}"
            return "🚫 Unknown API error"

        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("ChatGPT: unexpected response: %s", resp)
            return f"🚫 Unexpected response: {exc}"

    @command(
        "gpt",
        required=OWNER,
        aliases=["chatgpt", "gpt3"],
    )
    async def gpt_cmd(self, event) -> None:
        """<question> - Ask a question"""
        if not self.config["api_key"]:
            await answer(event, self.strings("no_api_key"))
            return

        args = self.get_args(event)
        if not args:
            await answer(event, self.strings("no_args"))
            return

        await answer(
            event,
            "\n".join(
                [
                    self.strings("question").format(question=escape_html(args)),
                    self.strings("answer").format(answer=self.strings("loading")),
                ]
            ),
        )

        result = await self._get_chat_completion(args)

        await answer(
            event,
            "\n".join(
                [
                    self.strings("question").format(question=escape_html(args)),
                    self.strings("answer").format(
                        answer=self._process_code_tags(result)
                    ),
                ]
            ),
        )
