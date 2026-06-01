from __future__ import annotations
import asyncio
import io
import logging
import warnings
from collections import defaultdict

from telethon.tl.functions.messages import SearchRequest, GetHistoryRequest
from telethon.tl.types import (
    InputMessagesFilterEmpty,
    PeerUser,
    PeerChat,
    PeerChannel,
)
from telethon.utils import get_peer_id

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER

logger = logging.getLogger(__name__)


class TopKitsuneModule(KitsuneModule):
    name = "TopKitsune"
    description = "Топ пользователей по сообщениям в чате. Адаптировал @Mikasu32"
    author = "nercymods | Kitsune by @Mikasu32"
    version = "1.1.0"
    icon = "🏆"
    category = "tools"

    strings_ru = {
        "loading": (
            "<emoji document_id=5780543148782522693>🕒</emoji> "
            "<b>Подсчёт сообщений начался, подождите. "
            "Если в чате много сообщений — это может занять время.</b>"
        ),
        "topchat": (
            "<emoji document_id=5323538339062628165>💬</emoji> "
            "<b>Топ пользователей в</b>"
        ),
        "msgcount": "Количество сообщений",
        "private_chat": (
            "<emoji document_id=5323538339062628165>💬</emoji> "
            "<b>Количество сообщений в личном чате с</b>"
        ),
        "title": "Топ пользователей по количеству сообщений",
        "unsupported": "❌ Неподдерживаемый тип чата.",
        "no_data": "❌ Не удалось получить данные.",
        "deps_missing": (
            "❌ <b>Не установлены зависимости:</b> <code>{deps}</code>\n"
            "Установите их через <code>{prefix}sh pip install matplotlib numpy</code> "
            "или дождитесь автоматической установки."
        ),
    }

    @command("top", required=OWNER, aliases=["топ"])
    async def top_cmd(self, event) -> None:
        """Показать топ пользователей по числу сообщений в чате. В личке — статистика двух собеседников. Псевдоним: .топ"""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np
            from matplotlib.colors import LinearSegmentedColormap
        except ImportError as exc:
            dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
            prefix = dispatcher._prefix if dispatcher else "."
            await event.reply(
                self.strings("deps_missing").format(
                    deps=str(exc.name or "matplotlib/numpy"),
                    prefix=prefix,
                ),
                parse_mode="html",
            )
            return

        msg = await event.reply(self.strings("loading"), parse_mode="html")

        peer = event.message.peer_id
        if isinstance(peer, PeerUser):
            chat_type = "private"
            chat_id = peer.user_id
        elif isinstance(peer, (PeerChat, PeerChannel)):
            chat_type = "chat"
            chat_id = event.chat_id
        else:
            await msg.edit(self.strings("unsupported"), parse_mode="html")
            return

        try:
            if chat_type == "chat":
                await self._render_chat_top(event, msg, chat_id, plt, np, LinearSegmentedColormap)
            else:
                await self._render_private_top(event, msg, chat_id, plt, np, LinearSegmentedColormap)
        except Exception as exc:
            logger.exception("TopKitsune: failed to build top")
            try:
                await msg.edit(
                    f"❌ Ошибка: <code>{type(exc).__name__}: {exc}</code>",
                    parse_mode="html",
                )
            except Exception:
                pass

    async def _render_chat_top(self, event, msg, chat_id, plt, np, LinearSegmentedColormap) -> None:
        client = self.client
        chat = await event.get_chat()
        users = await client.get_participants(chat_id, aggressive=False, limit=200)
        if not users:
            await msg.edit(self.strings("no_data"), parse_mode="html")
            return
        users_dict = {
            user.id: (user.username or user.first_name or f"id{user.id}")
            for user in users
        }
        message_count: dict[int, int] = defaultdict(int)

        async def _count_for(uid: int) -> tuple[int, int]:
            try:
                result = await client(SearchRequest(
                    peer=chat_id,
                    q="",
                    filter=InputMessagesFilterEmpty(),
                    from_id=await client.get_input_entity(uid),
                    min_date=None,
                    max_date=None,
                    offset_id=0,
                    add_offset=0,
                    limit=0,
                    max_id=0,
                    min_id=0,
                    hash=0,
                ))
                return uid, getattr(result, "count", 0)
            except Exception:
                return uid, 0

        sem = asyncio.Semaphore(8)

        async def _bounded(uid: int):
            async with sem:
                return await _count_for(uid)

        results = await asyncio.gather(*[_bounded(uid) for uid in users_dict])
        for uid, cnt in results:
            message_count[uid] = cnt

        sorted_counts = sorted(message_count.items(), key=lambda kv: kv[1], reverse=True)
        top_users = [item for item in sorted_counts if item[1] > 0][:20]
        if not top_users:
            await msg.edit(self.strings("no_data"), parse_mode="html")
            return

        usernames = [users_dict.get(uid, f"id{uid}") for uid, _ in top_users]
        counts = [cnt for _, cnt in top_users]

        buf = await asyncio.to_thread(
            self._render_bar_chart, plt, np, LinearSegmentedColormap, usernames, counts,
        )

        title = getattr(chat, "title", None) or "чате"
        caption_lines = [f"{self.strings('topchat')} <b>{self._escape(title)}:</b>"]
        for i, (user, count) in enumerate(zip(usernames, counts), start=1):
            caption_lines.append(f"{i}. {self._escape(str(user))} — {count}")
        caption = "\n".join(caption_lines)
        if len(caption) > 1024:
            caption = caption[:1020] + "..."

        await self.client.send_file(
            event.chat_id,
            buf,
            caption=caption,
            parse_mode="html",
            force_document=False,
            reply_to=getattr(event.message, "reply_to_msg_id", None) or event.message.id,
        )
        try:
            await msg.delete()
        except Exception:
            pass

    async def _render_private_top(self, event, msg, chat_id, plt, np, LinearSegmentedColormap) -> None:
        client = self.client
        me = await client.get_me()
        target = await client.get_entity(chat_id)

        my_count, their_count = await asyncio.gather(
            self._count_messages_fast(client, chat_id, me.id),
            self._count_messages_fast(client, chat_id, target.id),
        )

        pairs = [
            (me.first_name or "Me", my_count),
            (getattr(target, "first_name", None) or "Peer", their_count),
        ]
        pairs.sort(key=lambda kv: kv[1], reverse=True)
        usernames = [n for n, _ in pairs]
        counts = [c for _, c in pairs]

        buf = await asyncio.to_thread(
            self._render_bar_chart, plt, np, LinearSegmentedColormap, usernames, counts,
        )

        target_name = getattr(target, "first_name", None) or "Peer"
        caption_lines = [f"{self.strings('private_chat')} <b>{self._escape(target_name)}:</b>"]
        for user, count in zip(usernames, counts):
            caption_lines.append(f'"{self._escape(str(user))}" — {count}')
        caption = "\n".join(caption_lines)

        await self.client.send_file(
            event.chat_id,
            buf,
            caption=caption,
            parse_mode="html",
            force_document=False,
            reply_to=getattr(event.message, "reply_to_msg_id", None) or event.message.id,
        )
        try:
            await msg.delete()
        except Exception:
            pass

    @staticmethod
    def _escape(text: str) -> str:
        return (
            (text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @staticmethod
    async def _count_messages_fast(client, chat_id, user_id) -> int:
        total = 0
        offset_id = 0
        limit = 100
        for _ in range(50):
            history = await client(GetHistoryRequest(
                peer=chat_id,
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=limit,
                max_id=0,
                min_id=0,
                hash=0,
            ))
            messages = getattr(history, "messages", []) or []
            if not messages:
                break
            for m in messages:
                if getattr(m, "sender_id", None) == user_id:
                    total += 1
            if len(messages) < limit:
                break
            offset_id = messages[-1].id
        return total

    def _render_bar_chart(self, plt, np, LinearSegmentedColormap, usernames, counts) -> io.BytesIO:
        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(10, max(5, len(usernames) * 0.35)))
        try:
            cmap = LinearSegmentedColormap.from_list(
                "kitsune_top", ["#8A2BE2", "#4B0082"], N=max(len(usernames), 2)
            )
            colors = [cmap(i) for i in np.linspace(0, 1, len(usernames))]
            bars = ax.barh(usernames, counts, color=colors, edgecolor="black", linewidth=0.5)
            for bar in bars:
                bar.set_alpha(0.85)
                bar.set_hatch("///")
            ax.set_xlabel(self.strings("msgcount"), fontsize=12, color="white")
            ax.set_title(self.strings("title"), fontsize=14, color="white", pad=20)
            ax.invert_yaxis()
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#8A2BE2")
            ax.spines["bottom"].set_color("#8A2BE2")
            ax.grid(True, linestyle="--", alpha=0.5, color="gray")
            for i, bar in enumerate(bars):
                if i < 3:
                    bar.set_color("#FFD700")
                    ax.text(
                        bar.get_width() + max(counts) * 0.01,
                        bar.get_y() + bar.get_height() / 2,
                        f"#{i+1}",
                        va="center",
                        ha="left",
                        color="#FFD700",
                        fontsize=12,
                    )
            buf = io.BytesIO()
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
            buf.seek(0)
            buf.name = "top.png"
            return buf
        finally:
            plt.close(fig)
