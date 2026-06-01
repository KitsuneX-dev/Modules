# *      _                             __  __           _       _
# *     / \  _   _ _ __ ___  _ __ __ _|  \/  | ___   __| |_   _| | ___  ___ 
# *    / _ \| | | | '__/ _ \| '__/ _` | |\/| |/ _ \ / _` | | | | |/ _ \/ __|
# *   / ___ \ |_| | | | (_) | | | (_| | |  | | (_) | (_| | |_| | |  __/\__ \
# *  /_/   \_\__,_|_|  \___/|_|  \__,_|_|  |_|\___/ \__,_|\__,_|_|\___||___/
# *
# *                          © Copyright 2024
# *
# *                      https://t.me/AuroraModules
# *
# * 🔒 Code is licensed under GNU AGPLv3
# * 🌐 https://www.gnu.org/licenses/agpl-3.0.html
# * ⛔️ You CANNOT edit this file without direct permission from the author.
# * ⛔️ You CANNOT distribute this file if you have modified it without the direct permission of the author.
#
# ============================================================================
#  Адаптация под UserBot Kitsune — оригинальная логика игры сохранена 1-в-1.
#  Original author: Felix (@AuroraModules)
#  Kitsune-port:    native Kitsune API (KitsuneModule / @command / inline)
# ============================================================================

# Name: KitsuneRPSgame
# Author: Felix (Kitsune-port)
# Commands:
# .sgamerps (.rps) | .cleargames (.clg)
# scope: kitsune_only
# meta developer: @AuroraModules

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
import typing

from telethon.utils import get_display_name  # type: ignore

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER
from ..utils import escape_html

logger = logging.getLogger(__name__)

# Таблица победителей считается один раз на уровне модуля (быстрее, чем
# пересоздавать словарь в каждом раунде).
_WIN_TABLE: dict[str, str] = {
    "rock": "scissors",
    "scissors": "paper",
    "paper": "rock",
}
_CHOICES: tuple[str, ...] = ("rock", "scissors", "paper")

# Время жизни одной игры (защита от «вечных» зависших партий в памяти).
_GAME_TTL: float = 60 * 30  # 30 минут


class KitsuneRPSgameMod(KitsuneModule):
    """Kitsune-port: игра «Камень, ножницы, бумага» (Rock, Paper, Scissors)."""

    name = "KitsuneRPSgame"
    description = "Play «Rock, Paper, Scissors» right inside Telegram (Kitsune-port)."
    author = "Felix"
    version = "1.0.0-kitsune"
    icon = "✌️"
    category = "fun"

    strings_en = {
        "searching": "<b>✌️ The game «Rock, Paper, Scissors» begins!\n👀 Waiting for a second player to join...</b>",
        "join_game": "👾 Join the game",
        "rules": "📄 Game rules",
        "game_started": "⚠ The game has already started",
        "game_already_running": "<emoji document_id=5255772095958229697>🤚</emoji> <b>Oops, a game is already running, use </b><code>{}cleargames</code><b> to end all active games.</b>",
        "games_cleared": "<emoji document_id=6007942490076745785>🧹</emoji> <b>All active games have been ended and cleared.</b>",
        "turn": "<b>🕹 The game has started!\n👀 The first turn goes to {}</b>!",
        "next_player": "<b>😱 It's {}'s turn next</b>",
        "not_your_turn": "⚠ It's not your turn!",
        "not_player": "❌ You're not participating in the game",
        "cooldown": "⚠ Not so fast!",
        "winner": "<b>🎉 Winner: {}</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> chose: {}</b> \n<b>👤<a href='tg://openmessage?user_id={}'>{}</a> chose: {}</b>",
        "draw": "<b>🤝 It's a draw!</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> chose: {}</b>\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> chose: {}</b>",
        "error_play_yourself": "⚠ You can't play against yourself",
        "rock": "🪨 Rock",
        "scissors": "✂️ Scissors",
        "paper": "📄 Paper",
        "random": "🎲 Random choice",
        "close_button": "🔻 Close",
        "no_inline": "❌ Inline-bot is not configured, the game requires it.",
        "game_expired": "⌛ This game has expired.",
    }

    strings_ru = {
        "searching": "<b>✌️ Игра «Камень, ножницы, бумага» начинается!\n👀 Ожидание, присоединение 2 игрока...</b>",
        "join_game": "👾 Присоединиться к игре",
        "rules": "📄 Правила игры",
        "game_started": "⚠ Игра уже началась",
        "game_already_running": "<emoji document_id=5255772095958229697>🤚</emoji> <b>Упс, игра уже запущена, используйте </b><code>{}cleargames</code><b>, чтобы завершить все начатые игры.</b>",
        "games_cleared": "<emoji document_id=6007942490076745785>🧹</emoji> <b>Все активные игры были завершены и очищены.</b>",
        "turn": "<b>🕹 Игра началась!\n👀 Первый ход за {}</b>!",
        "next_player": "<b>😱 Следующий ходит {}</b>",
        "not_your_turn": "⚠ Это не ваш ход!",
        "not_player": "❌ Вы не участвуете в игре",
        "cooldown": "⚠ Не так быстро!",
        "winner": "<b>🎉 Победитель: {}</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> выбрал: {}</b> \n<b>👤<a href='tg://openmessage?user_id={}'>{}</a> выбрал: {}</b>",
        "draw": "<b>🤝 Ничья!</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> выбрал: {}</b>\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> выбрал: {}</b>",
        "error_play_yourself": "⚠ Вы не можете играть с самим сабой",
        "rock": "🪨 Камень",
        "scissors": "✂️ Ножницы",
        "paper": "📄 Бумага",
        "random": "🎲 Случайный выбор",
        "close_button": "🔻 Закрыть",
        "no_inline": "❌ Inline-бот не настроен, без него игра не работает.",
        "game_expired": "⌛ Эта игра уже истекла.",
    }

    strings_uz = {
        "searching": "<b>✌️ «Qog'oz, Qaychi, Tosh» o'yini boshlanmoqda!\n👀 Ikkinchi o'yinchi kutilmoqda...</b>",
        "join_game": "👾 O'yinga qo'shilish",
        "rules": "📄 O'yin qoidalari",
        "game_started": "⚠ O'yin allaqachon boshlangan",
        "game_already_running": "<emoji document_id=5255772095958229697>🤚</emoji> <b>Oops, o'yin allaqachon boshlangan, </b><code>{}cleargames</code><b> buyruqni ishlating, barcha o'yinlarni tugatish uchun.</b>",
        "games_cleared": "<emoji document_id=6007942490076745785>🧹</emoji> <b>Barcha faol o'yinlar tugatildi va tozalandi.</b>",
        "turn": "<b>🕹 O'yin boshlandi!\n👀 Birinchi yurish {}</b>!",
        "next_player": "<b>😱 Keyingi yurish {} da</b>",
        "not_your_turn": "⚠ Bu sizning navbatingiz emas!",
        "not_player": "❌ Siz o'yinda emassiz",
        "cooldown": "⚠ Shoshilmang!",
        "winner": "<b>🎉 G'olib: {}</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> tanladi: {}</b> \n<b>👤<a href='tg://openmessage?user_id={}'>{}</a> tanladi: {}</b>",
        "draw": "<b>🤝 Durrang!</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> tanladi: {}</b>\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> tanladi: {}</b>",
        "error_play_yourself": "⚠ O'zingiz bilan o'ynay olmaysiz",
        "rock": "🪨 Tosh",
        "scissors": "✂️ Qaychi",
        "paper": "📄 Qog'oz",
        "random": "🎲 Tasodifiy tanlash",
        "close_button": "🔻 Yopish",
        "no_inline": "❌ Inline-bot sozlanmagan, o'yin usiz ishlamaydi.",
        "game_expired": "⌛ Bu o'yin muddati tugagan.",
    }

    strings_de = {
        "searching": "<b>✌️ Das Spiel «Schere, Stein, Papier» beginnt!\n👀 Warte auf den zweiten Spieler...</b>",
        "join_game": "👾 Dem Spiel beitreten",
        "rules": "📄 Spielregeln",
        "game_started": "⚠ Das Spiel hat bereits begonnen",
        "game_already_running": "<emoji document_id=5255772095958229697>🤚</emoji> <b>Ups, ein Spiel läuft bereits, benutze </b><code>{}cleargames</code><b>, um alle aktiven Spiele zu beenden.</b>",
        "games_cleared": "<emoji document_id=6007942490076745785>🧹</emoji> <b>Alle aktiven Spiele wurden beendet und gelöscht.</b>",
        "turn": "<b>🕹 Das Spiel hat begonnen!\n👀 Der erste Zug geht an {}</b>!",
        "next_player": "<b>😱 Der nächste Zug geht an {}</b>",
        "not_your_turn": "⚠ Es ist nicht dein Zug!",
        "not_player": "❌ Du nimmst nicht am Spiel teil",
        "cooldown": "⚠ Nicht so schnell!",
        "winner": "<b>🎉 Gewinner: {}</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> wählte: {}</b> \n<b>👤<a href='tg://openmessage?user_id={}'>{}</a> wählte: {}</b>",
        "draw": "<b>🤝 Unentschieden!</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> wählte: {}</b>\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> wählte: {}</b>",
        "error_play_yourself": "⚠ Du kannst nicht gegen dich selbst spielen",
        "rock": "🪨 Stein",
        "scissors": "✂️ Schere",
        "paper": "📄 Papier",
        "random": "🎲 Zufällige Wahl",
        "close_button": "🔻 Schließen",
        "no_inline": "❌ Der Inline-Bot ist nicht konfiguriert, das Spiel benötigt ihn.",
        "game_expired": "⌛ Dieses Spiel ist abgelaufen.",
    }

    strings_es = {
        "searching": "<b>✌️ El juego «Piedra, Papel, Tijeras» comienza!\n👀 Esperando que se una un segundo jugador...</b>",
        "join_game": "👾 Unirse al juego",
        "rules": "📄 Reglas del juego",
        "game_started": "⚠ El juego ya ha comenzado",
        "game_already_running": "<emoji document_id=5255772095958229697>🤚</emoji> <b>Ups, un juego ya está en marcha, usa </b><code>{}cleargames</code><b> para terminar todos los juegos activos.</b>",
        "games_cleared": "<emoji document_id=6007942490076745785>🧹</emoji> <b>Todos los juegos activos han sido terminados y eliminados.</b>",
        "turn": "<b>🕹 ¡El juego ha comenzado!\n👀 El primer turno es para {}</b>!",
        "next_player": "<b>😱 El siguiente turno es para {}</b>",
        "not_your_turn": "⚠ ¡No es tu turno!",
        "not_player": "❌ No estás participando en el juego",
        "cooldown": "⚠ ¡No tan rápido!",
        "winner": "<b>🎉 Ganador: {}</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> eligió: {}</b> \n<b>👤<a href='tg://openmessage?user_id={}'>{}</a> eligió: {}</b>",
        "draw": "<b>🤝 ¡Empate!</b>\n\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> eligió: {}</b>\n<b>👤 <a href='tg://openmessage?user_id={}'>{}</a> eligió: {}</b>",
        "error_play_yourself": "⚠ No puedes jugar contra ti mismo",
        "rock": "🪨 Piedra",
        "scissors": "✂️ Tijeras",
        "paper": "📄 Papel",
        "random": "🎲 Elección aleatoria",
        "close_button": "🔻 Cerrar",
        "no_inline": "❌ El bot inline no está configurado, el juego lo necesita.",
        "game_expired": "⌛ Este juego ha caducado.",
    }

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        # game_id -> состояние партии
        self.games: dict[str, dict[str, typing.Any]] = {}
        # user_id -> время последнего клика (анти-спам, как в оригинале)
        self.last_click_time: dict[int, float] = {}
        # Кэш отображаемых имён, чтобы не дёргать get_entity на каждый ход.
        self._name_cache: dict[int, str] = {}

    # ------------------------------------------------------------------ #
    #  Вспомогательные методы                                            #
    # ------------------------------------------------------------------ #
    def _inline(self) -> typing.Any:
        """Возвращает inline-менеджер Kitsune (или None)."""
        return getattr(self.client, "_kitsune_inline", None) or getattr(
            self.client, "inline", None
        )

    def _prefix(self) -> str:
        """Текущий префикс юзербота (для подсказок в строках)."""
        dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
        prefix = getattr(dispatcher, "_prefix", ".") if dispatcher else "."
        return escape_html(prefix)

    async def _display_name(self, user_id: int) -> str:
        """Безопасно получить отображаемое имя пользователя с кэшированием."""
        if user_id in self._name_cache:
            return self._name_cache[user_id]
        name = str(user_id)
        try:
            entity = await self.client.get_entity(user_id)
            name = get_display_name(entity) or str(user_id)
        except Exception:
            logger.debug("RPS: get_entity failed for %s", user_id, exc_info=True)
        self._name_cache[user_id] = name
        return name

    def _make_choice_markup(self, game_id: str) -> list:
        """Клавиатура выбора хода (disable_security=True — нужна 2-му игроку)."""
        return [
            [
                {"text": self.strings("rock"), "callback": self.make_choice,
                 "args": (game_id, "rock"), "disable_security": True},
                {"text": self.strings("scissors"), "callback": self.make_choice,
                 "args": (game_id, "scissors"), "disable_security": True},
                {"text": self.strings("paper"), "callback": self.make_choice,
                 "args": (game_id, "paper"), "disable_security": True},
            ],
            [
                {"text": self.strings("random"), "callback": self.make_choice,
                 "args": (game_id, "random"), "disable_security": True},
            ],
        ]

    def _purge_expired(self) -> None:
        """Удаляет «протухшие» партии, чтобы не копить мусор в памяти."""
        now = time.time()
        expired = [
            gid for gid, g in self.games.items()
            if now - g.get("created_at", now) > _GAME_TTL
        ]
        for gid in expired:
            self.games.pop(gid, None)

    @staticmethod
    def _is_on_cooldown(store: dict[int, float], user_id: int, seconds: float) -> bool:
        """Анти-спам: True, если пользователь кликает слишком часто."""
        now = time.time()
        last = store.get(user_id)
        if last is not None and now - last < seconds:
            return True
        store[user_id] = now
        return False

    # ------------------------------------------------------------------ #
    #  Команды                                                           #
    # ------------------------------------------------------------------ #
    @command(
        "sgamerps",
        required=OWNER,
        aliases=["rps"],
    )
    async def sgamerps_cmd(self, event) -> None:
        """- Start the game «Rock, Paper, Scissors» | - Начать игру «Камень, ножницы, бумага»"""
        try:
            self._purge_expired()

            inline = self._inline()
            if inline is None:
                await event.edit(self.strings("no_inline"), parse_mode="html")
                return

            chat_id = event.chat_id
            player1_id = event.sender_id
            game_id = f"{chat_id}_{player1_id}"

            if game_id in self.games:
                await event.edit(
                    self.strings("game_already_running").format(self._prefix()),
                    parse_mode="html",
                )
                return

            self.games[game_id] = {
                "player1": player1_id,
                "player2": None,
                "choices": {},
                "current_turn": None,
                "created_at": time.time(),
            }

            await inline.form(
                self.strings("searching"),
                event.message,
                [
                    [
                        {
                            "text": self.strings("rules"),
                            "url": "https://ru.wikipedia.org/wiki/Камень,_ножницы,_бумага",
                        }
                    ],
                    [
                        {
                            "text": self.strings("join_game"),
                            "callback": self.join_game,
                            "args": (game_id,),
                            "disable_security": True,
                        }
                    ],
                ],
            )
        except Exception:
            logger.exception("RPS: failed to start a game")
            with contextlib.suppress(Exception):
                await event.edit(
                    "❌ <b>RPS:</b> internal error, see logs.", parse_mode="html"
                )

    @command(
        "cleargames",
        required=OWNER,
        aliases=["clg"],
    )
    async def cleargames_cmd(self, event) -> None:
        """- Clear all active games | - Очистить все активные игры"""
        try:
            self.games.clear()
            self.last_click_time.clear()
            self._name_cache.clear()
            await event.edit(self.strings("games_cleared"), parse_mode="html")
        except Exception:
            logger.exception("RPS: failed to clear games")
            with contextlib.suppress(Exception):
                await event.edit(
                    "❌ <b>RPS:</b> internal error, see logs.", parse_mode="html"
                )

    # ------------------------------------------------------------------ #
    #  Inline-колбэки                                                    #
    # ------------------------------------------------------------------ #
    async def join_game(self, call, game_id: str) -> None:
        try:
            game = self.games.get(game_id)
            if game is None:
                with contextlib.suppress(Exception):
                    await call.answer(self.strings("game_expired"), show_alert=True)
                return

            player2_id = call.from_user_id

            if self._is_on_cooldown(self.last_click_time, player2_id, 3):
                await call.answer(self.strings("cooldown"))
                return

            if game["player1"] == player2_id:
                await call.answer(self.strings("error_play_yourself"))
                return

            if game["player2"] is not None:
                await call.answer(self.strings("game_started"))
                return

            game["player2"] = player2_id
            game["current_turn"] = random.choice([game["player1"], game["player2"]])

            first_name = await self._display_name(game["current_turn"])
            inline = self._inline()
            if inline is None:
                await call.answer("❌ Inline unavailable", show_alert=True)
                return
            await inline.edit(
                call,
                self.strings("turn").format(first_name),
                reply_markup=self._make_choice_markup(game_id),
            )
        except Exception:
            logger.exception("RPS: join_game failed")
            with contextlib.suppress(Exception):
                await call.answer("❌ Error", show_alert=True)

    async def make_choice(self, call, game_id: str, choice: str) -> None:
        try:
            game = self.games.get(game_id)
            if game is None:
                with contextlib.suppress(Exception):
                    await call.answer(self.strings("game_expired"), show_alert=True)
                return

            user_id = call.from_user_id

            if self._is_on_cooldown(self.last_click_time, user_id, 2):
                await call.answer(self.strings("cooldown"))
                return

            if user_id not in (game["player1"], game["player2"]):
                await call.answer(self.strings("not_player"))
                return

            # Каждый игрок ходит только один раз.
            if user_id in game["choices"]:
                await call.answer(self.strings("not_your_turn"))
                return

            is_random = choice == "random"
            if is_random:
                choice = random.choice(_CHOICES)

            game["choices"][user_id] = (choice, "random" if is_random else None)

            if len(game["choices"]) == 2:
                await self.resolve_game(call, game_id)
            else:
                game["current_turn"] = (
                    game["player1"] if user_id == game["player2"] else game["player2"]
                )
                next_player = await self._display_name(game["current_turn"])
                inline = self._inline()
                if inline is None:
                    await call.answer("❌ Inline unavailable", show_alert=True)
                    return
                await inline.edit(
                    call,
                    self.strings("next_player").format(next_player),
                    reply_markup=self._make_choice_markup(game_id),
                )
        except Exception:
            logger.exception("RPS: make_choice failed")
            with contextlib.suppress(Exception):
                await call.answer("❌ Error", show_alert=True)

    async def resolve_game(self, call, game_id: str) -> None:
        game = self.games.get(game_id)
        if not game:
            return

        player1_id = game["player1"]
        player2_id = game["player2"]

        player1_choice, player1_random = game["choices"].get(player1_id, (None, None))
        player2_choice, player2_random = game["choices"].get(player2_id, (None, None))

        if player1_choice is None or player2_choice is None:
            return

        player1_choice_text = self.strings(player1_choice)
        player2_choice_text = self.strings(player2_choice)

        if player1_random:
            player1_choice_text += " [🎲RANDOM]"
        if player2_random:
            player2_choice_text += " [🎲RANDOM]"

        # Имена игроков получаем параллельно для скорости.
        name1, name2 = await asyncio.gather(
            self._display_name(player1_id),
            self._display_name(player2_id),
        )

        if player1_choice == player2_choice:
            result_message = self.strings("draw").format(
                player1_id, escape_html(name1), player1_choice_text,
                player2_id, escape_html(name2), player2_choice_text,
            )
        else:
            winner_id = (
                player1_id if _WIN_TABLE[player1_choice] == player2_choice else player2_id
            )
            winner_name = name1 if winner_id == player1_id else name2
            result_message = self.strings("winner").format(
                escape_html(winner_name),
                player1_id, escape_html(name1), player1_choice_text,
                player2_id, escape_html(name2), player2_choice_text,
            )

        inline_mgr = self._inline()
        if inline_mgr is not None:
            await inline_mgr.edit(
                call,
                result_message,
                reply_markup=[
                    [
                        {
                            "text": self.strings("close_button"),
                            "callback": self.call_del,
                            "args": (game_id,),
                            "disable_security": True,
                        }
                    ]
                ],
            )

    async def call_del(self, call, game_id: str | None = None) -> None:
        """Закрытие сообщения и очистка завершённой партии."""
        try:
            if game_id is not None:
                self.games.pop(game_id, None)
            inline = self._inline()
            if inline is not None:
                with contextlib.suppress(Exception):
                    await inline.edit(call, "🔻")
            with contextlib.suppress(Exception):
                await call.answer()
        except Exception:
            logger.exception("RPS: call_del failed")
