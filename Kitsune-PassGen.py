# ---------------------------------------------------------------------------------
#  🦊 Kitsune Module — Kitsune-PassGen
# ---------------------------------------------------------------------------------
#  Name:        Kitsune-PassGen
#  Description: Быстрый и безопасный генератор паролей.
#               Адаптировано под Kitsune @Mikasu32
#  Author:      codrago (adapted for Kitsune)
#  Version:     2.0.0
#  Commands:    .pass, .passg
# ---------------------------------------------------------------------------------
#  🔒  Licensed under the GNU AGPLv3
#  🌐  https://www.gnu.org/licenses/agpl-3.0.html
# ---------------------------------------------------------------------------------
from __future__ import annotations

import secrets
import string

from ..core.loader import KitsuneModule, command, ConfigValue, ModuleConfig
from ..core.security import OWNER
from ..utils import escape_html
from ..validators import Integer


# Алфавиты вынесены в константы модуля — собираются один раз при импорте,
# а не на каждый вызов команды (оптимизация по сравнению с оригиналом).
_SAFE_PUNCT: str = "!@#$%^&*()-_=+[]{};:,.?"
_ALNUM: str = string.ascii_letters + string.digits
_FULL: str = _ALNUM + _SAFE_PUNCT

_MIN_LEN: int = 1
_MAX_LEN: int = 1024


class PassGen(KitsuneModule):
    name = "Kitsune-PassGen"
    description = "Быстрый генератор криптостойких паролей. Адаптировано под Kitsune @Mikasu32"
    author = "codrago"
    version = "2.0.0"
    icon = "🔒"
    category = "tools"

    strings_ru = {
        "no_args": (
            "<emoji document_id=5328145443106873128>✖️</emoji> "
            "<b>Укажи длину пароля:</b> <code>.pass 16</code>"
        ),
        "bad_args": (
            "<emoji document_id=5328145443106873128>✖️</emoji> "
            "<b>Длина должна быть числом от {min} до {max}.</b>"
        ),
        "pass": (
            "<emoji document_id=5832546462478635761>🔒</emoji> "
            "<b>Твой пароль ({length} симв.):</b>\n<code>{password}</code>"
        ),
    }

    strings_en = {
        "no_args": (
            "<emoji document_id=5328145443106873128>✖️</emoji> "
            "<b>Specify password length:</b> <code>.pass 16</code>"
        ),
        "bad_args": (
            "<emoji document_id=5328145443106873128>✖️</emoji> "
            "<b>Length must be a number between {min} and {max}.</b>"
        ),
        "pass": (
            "<emoji document_id=5832546462478635761>🔒</emoji> "
            "<b>Your password ({length} chars):</b>\n<code>{password}</code>"
        ),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "default_length",
                16,
                "Длина пароля по умолчанию, если аргумент не указан",
                validator=Integer(minimum=_MIN_LEN, maximum=_MAX_LEN),
            ),
        )

    def _parse_length(self, raw: str) -> int | None:
        """Безопасный разбор длины. Возвращает None при ошибке."""
        raw = (raw or "").strip()
        if not raw:
            default = self.config["default_length"] if self.config else 16
            return int(default)
        if not raw.isdigit():
            return None
        length = int(raw)
        if length < _MIN_LEN or length > _MAX_LEN:
            return None
        return length

    @staticmethod
    def _generate(length: int, alphabet: str) -> str:
        # secrets.choice — криптографически стойкий ГПСЧ (в отличие от random
        # в оригинале), при этом так же быстр для коротких паролей.
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @command("pass", required=OWNER, aliases=["password"])
    async def pass_cmd(self, event) -> None:
        """Сгенерировать буквенно-цифровой пароль заданной длины. Пример: .pass 16. Псевдоним: .password"""
        length = self._parse_length(self.get_args(event))
        if length is None:
            await event.edit(
                self.strings("bad_args", min=_MIN_LEN, max=_MAX_LEN),
                parse_mode="html",
            )
            return
        password = self._generate(length, _ALNUM)
        await event.edit(
            self.strings("pass", length=length, password=escape_html(password)),
            parse_mode="html",
        )

    @command("passg", required=OWNER, aliases=["passgen"])
    async def passg_cmd(self, event) -> None:
        """Сгенерировать пароль со спецсимволами заданной длины. Пример: .passg 32. Псевдоним: .passgen"""
        length = self._parse_length(self.get_args(event))
        if length is None:
            await event.edit(
                self.strings("bad_args", min=_MIN_LEN, max=_MAX_LEN),
                parse_mode="html",
            )
            return
        password = self._generate(length, _FULL)
        await event.edit(
            self.strings("pass", length=length, password=escape_html(password)),
            parse_mode="html",
        )
