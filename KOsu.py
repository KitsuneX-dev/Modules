__version__ = (1, 3, 0)

# ──────────────────────────────────────────────────────────────────────────
#    █▄▀ █ ▀█▀ █▀ █ █ █▄ █ █▀▀
#    █ █ █  █  ▄█ █▄█ █ ▀█ ██▄
#    Адаптация под Kitsune UserBot
#    Original: Copyright 2022 t.me/morisummermods
#    Licensed under CC BY-NC-SA 4.0 International
# ──────────────────────────────────────────────────────────────────────────
# requires: requests emoji-country-flag
# meta developer: @morisummermods (adapted for Kitsune)
# meta banner: https://i.imgur.com/fPWWFrL.jpg
# meta pic: https://i.imgur.com/fcHCrS2.png

import contextlib
import datetime
import json
import logging
import typing

import requests

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER
from ..utils import answer, escape_html, run_sync

logger = logging.getLogger(__name__)

_OSU_URL = "https://osu.ppy.sh/users/"


class KOsu(KitsuneModule):
    """I'm an osu!bot that can do some things written by @morisummerzxc (adapted for Kitsune)"""

    name = "Osu"
    description = "osu! profile / top scores viewer"
    author = "morisummerzxc"
    version = "1.3.0"
    icon = "🟠"
    category = "tools"

    pip_requires: typing.ClassVar[list[str]] = ["requests"]

    strings_en = {
        "name": "Osu",
        "you_are": (
            "<emoji document_id=5398001711786762757>✅</emoji> <b>You are"
            " </b><code>{}</code><b> now</b>"
        ),
        "no_nick": (
            "Remember your nickname with <code>.osume &lt;your nickname&gt;</code>"
            " or use <code>.osutop &lt;nickname&gt;</code>"
        ),
        "loading": "<code>Loading...</code>",
        "error": "🚫 <b>Failed:</b> <code>{err}</code>",
        "not_found": "🚫 <b>User</b> <code>{nick}</code> <b>not found</b>",
    }

    strings_ru = {
        "you_are": (
            "<emoji document_id=5398001711786762757>✅</emoji> <b>Теперь ты"
            " </b><code>{}</code><b></b>"
        ),
        "no_nick": (
            "Запомни свой ник через <code>.osume &lt;твой ник&gt;</code>"
            " или используй <code>.osutop &lt;ник&gt;</code>"
        ),
        "loading": "<code>Загрузка...</code>",
        "error": "🚫 <b>Ошибка:</b> <code>{err}</code>",
        "not_found": "🚫 <b>Игрок</b> <code>{nick}</code> <b>не найден</b>",
    }

    async def on_load(self) -> None:
        self.url = _OSU_URL
        self.nickname = self.db.get(self.name, "nickname", "")

    async def _fetch_profile(self, nickname: str) -> dict:
        """Загружает данные профиля osu! — поддерживает старый и новый формат страницы."""
        req = await run_sync(
            requests.get,
            f"{_OSU_URL}{nickname}",
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        text = req.text
        info: dict = {}

        # Вариант 1: старый data-initial-data
        start = text.find('data-initial-data="')
        if start != -1:
            start += 19
            raw = text[start : text.find('"', start + 1)].replace("&quot;", '"'
            )
            with contextlib.suppress(Exception):
                info = json.loads(raw)

        # Вариант 2: новый формат — <script id="json-user">
        if not info.get("user"):
            for tag_id in ('id="json-user"', "id='json-user'"):
                idx = text.find(tag_id)
                if idx != -1:
                    s = text.find(">", idx) + 1
                    e = text.find("</script>", s)
                    if e > s:
                        with contextlib.suppress(Exception):
                            info["user"] = json.loads(text[s:e])
                            break

        if not info.get("user"):
            raise ValueError("not_found")

        # Ищем extras (scoresBest и др.) — могут быть в отдельном блоке
        if "extras" not in info:
            for tag_id in ('id="json-extras"', "id='json-extras'",
                           'id="json-user-extras"'):
                idx = text.find(tag_id)
                if idx != -1:
                    s = text.find(">", idx) + 1
                    e = text.find("</script>", s)
                    if e > s:
                        with contextlib.suppress(Exception):
                            info["extras"] = json.loads(text[s:e])
                            break

        # Если extras нет — пробуем вытащить scoresBest из user напрямую
        if "extras" not in info:
            scores = info["user"].get("scoresBest") or info["user"].get("scores_best")
            info["extras"] = {"scoresBest": scores or []}

        return info

    @staticmethod
    def _country_flag(code: str) -> str:
        """Конвертирует 2-буквенный код страны в эмодзи флага без сторонних зависимостей."""
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())

    @staticmethod
    def _grade(top: dict) -> str:
        if top["rank"] == "X":
            return "SS+"
        if top["rank"][-1] == "H":
            return top["rank"][:-1] + "+"
        return top["rank"]

    @classmethod
    def _format_score(cls, top: dict, *, with_hits: bool = False) -> str:
        out = (
            '<a href="'
            + top["beatmap"]["url"]
            + '">'
            + top["beatmapset"]["title"]
            + "</b> by <b>"
            + top["beatmapset"]["artist_unicode"]
            + "["
            + top["beatmap"]["version"].replace("&#039;", "'")
            + "]</a>\n"
        )
        out += f"{cls._grade(top)} " + str(round(float(top["accuracy"]) * 100, 2)) + "% "
        for mod in top["mods"]:
            out += f"{mod} "
        out += str(top["beatmap"]["difficulty_rating"]) + "★"
        if top["perfect"]:
            out += "FC"
        out += "\n" + str(top["pp"]) + "pp\n</b>"
        if with_hits:
            out += (
                "{"
                + str(top["statistics"]["count_300"])
                + "/"
                + str(top["statistics"]["count_100"])
                + "/"
                + str(top["statistics"]["count_50"])
                + "/"
                + str(top["statistics"]["count_miss"])
                + "}\n"
            )
        out += (
            datetime.datetime.strptime(
                top["created_at"], "%Y-%m-%dT%H:%M:%S+00:00"
            ).strftime("%d.%m.%Y %H:%M:%S")
            + ("\n" if with_hits else "\n\n")
        )
        return out

    @command("osume", required=OWNER)
    async def osume_cmd(self, event) -> None:
        """Remember user's nickname for commands | Запомнить ник для команд"""
        nickname = self.get_args(event)
        await self.db.set(self.name, "nickname", nickname)
        self.nickname = nickname
        await answer(
            event,
            self.strings("you_are").format(escape_html(self.nickname)),
        )

    @command("osutop", required=OWNER)
    async def osutop_cmd(self, event) -> None:
        """[nickname] - Get user's 5 best plays | [ник] - Топ-5 лучших скоров игрока"""
        nickname = self.nickname
        url = self.url
        args = self.get_args(event)
        if not nickname and not args:
            await answer(event, self.strings("no_nick"))
            return
        if args:
            nickname = args

        await answer(event, self.strings("loading"))

        try:
            info = await self._fetch_profile(nickname)
        except ValueError:
            await answer(
                event, self.strings("not_found").format(nick=escape_html(nickname))
            )
            return
        except Exception as exc:
            logger.exception("Osu: osutop failed")
            await answer(event, self.strings("error").format(err=escape_html(str(exc))))
            return

        try:
            top_scores = (info.get("extras") or {}).get("scoresBest") or []
            rank = info["user"]["statistics"]["global_rank"]
            out = (
                "5 best scores for: "
                + '<a href="' + url + nickname + '">' + nickname + "</a> #"
                + str(rank) + "\n\n<b>"
            )
            if not top_scores:
                out += "No scores available."
            else:
                for top in top_scores[:5]:
                    out += self._format_score(top, with_hits=False)
        except Exception as exc:
            logger.exception("Osu: failed to format top scores")
            await answer(event, self.strings("error").format(err=escape_html(str(exc))))
            return

        await answer(event, out)

    @command("osuprofile", required=OWNER, aliases=["osup"])
    async def osuprofile_cmd(self, event) -> None:
        """[nickname] - Get user's profile | [ник] - Профиль игрока"""
        nickname = self.nickname
        url = self.url
        args = self.get_args(event)
        if not nickname and not args:
            await answer(event, self.strings("no_nick"))
            return
        if args:
            nickname = args

        await answer(event, self.strings("loading"))

        try:
            info = await self._fetch_profile(nickname)
        except ValueError:
            await answer(
                event, self.strings("not_found").format(nick=escape_html(nickname))
            )
            return
        except Exception as exc:
            logger.exception("Osu: osuprofile failed")
            await answer(event, self.strings("error").format(err=escape_html(str(exc))))
            return

        try:
            profile = info["user"]
            photo = profile["avatar_url"]
            out = (
                '<a href="'
                + url
                + profile["username"]
                + '">'
                + self._country_flag(profile["country_code"])
                + profile["username"]
                + " profile</a>:\n\n"
            )
            out += (
                "<b>PP: "
                + str(profile["statistics"]["pp"])
                + "| #"
                + str(profile["statistics"]["global_rank"])
                + "(#"
                + str(profile["statistics"]["country_rank"])
                + ")</b>"
                + "\n\n"
            )
            scores_best = (info.get("extras") or {}).get("scoresBest") or []
            if scores_best:
                top_score = self._format_score(scores_best[0], with_hits=True)
                out += "Highest pp play:\n" + top_score + "\n"
            out += (
                "Play count: "
                + str(profile["statistics"]["play_count"])
                + "\nPlay time: "
                + str(round(profile["statistics"]["play_time"] / 3600, 2))
                + "h\nAccuracy: "
                + str(round(profile["statistics"]["hit_accuracy"], 2))
                + "%\nLVL: "
                + str(profile["statistics"]["level"]["current"])
                + "\n\nJoined "
                + str(
                    datetime.datetime.strptime(
                        profile["join_date"], "%Y-%m-%dT%H:%M:%S+00:00"
                    ).strftime("%d.%m.%Y")
                )
            )
        except Exception as exc:
            logger.exception("Osu: failed to format profile")
            await answer(event, self.strings("error").format(err=escape_html(str(exc))))
            return

        # Удаляем сообщение-загрузку и отправляем фото с подписью
        peer = getattr(event, "peer_id", None) or getattr(event, "chat_id", None)
        try:
            await self.client.send_file(peer, photo, caption=out, parse_mode="html")
            with contextlib.suppress(Exception):
                await event.delete()
        except Exception as exc:
            logger.exception("Osu: send_file failed")
            await answer(event, self.strings("error").format(err=escape_html(str(exc))))
