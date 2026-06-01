from __future__ import annotations
import random

from ..core.loader import KitsuneModule, command
from ..core.security import OWNER

_FACES = (
    "( ͡° ͜ʖ ͡°)",
    "( ͡~ ͜ʖ ͡°)",
    "( ͡° ͜ʖ ͡ °)",
    "( ͠° ͟ʖ ͡°)",
    "(つ ͡° ͜ʖ ͡°)つ",
    "(╯°□°）╯︵ ┻━┻",
    "┬─┬ノ( º _ ºノ)",
    "(ノಠ益ಠ)ノ彡┻━┻",
    "¯\\_(ツ)_/¯",
    "¯\\_(ツ)_/¯",
    "(づ｡◕‿‿◕｡)づ",
    "(◕‿◕)",
    "(✿◠‿◠)",
    "(╥﹏╥)",
    "(づ￣ ³￣)づ",
    "(｡♥‿♥｡)",
    "ʕ•ᴥ•ʔ",
    "ʕ ᴖᴥᴖʔ",
    "(•‿•)",
    "(•_•)",
    "( •_•)>⌐■-■",
    "(⌐■_■)",
    "(°ロ°)",
    "(o^^)o",
    "(°〇°)",
    "(✧ω✧)",
    "(ㆆ_ㆆ)",
    "(ಠ_ಠ)",
    "(ಥ﹏ಥ)",
    "(ʘ‿ʘ)",
    "(◣_◢)",
    "(¬‿¬)",
    "ヽ(´▽`)/",
    "ヽ(°〇°)ﾉ",
    "(╬ Ò﹏Ó)",
    "(づ▰╹◡╹▰)づ",
    "(ʘᗩʘ')",
    "(•ω•)",
    "(◔◡◔)",
    "(*≧ω≦*)",
    "(=^･ω･^=)",
    "(=ↀωↀ=)",
    "(=^･ｪ･^=)",
    "(=｀ω´=)",
    "(=^‥^=)",
    "(✪‿✪)",
    "(╯︵╰,)",
    "(*￣3￣)╭",
    "(─‿‿─)",
    "(¬､¬)",
    "(˘ω˘)",
    "(´• ω •`)",
    "(/◔ ◡ ◔)/",
    "(งツ)ว",
    "(҂◡_◡) ᕤ",
    "(งಠ_ಠ)ง",
    "(ノ°益°)ノ",
    "(҂⌣̀_⌣́)",
    "(ʘ_ʘ)",
    "ƪ(ړײ)‎ƪ​​",
)


class AsciiFaceKitsuneModule(KitsuneModule):
    name = "AsciiFaceKitsune"
    description = "Случайный AsciiFace. Адаптировал @Mikasu32"
    author = "@codrago_m | Kitsune by @Mikasu32"
    version = "1.0.0"
    icon = "😛"
    category = "fun"

    strings_ru = {
        "ascii_face": "😛 <b>Ваш рандомный AsciiFace:</b> <code>{face}</code>",
    }

    @command("ascii", required=OWNER, aliases=["asciiface"])
    async def ascii_cmd(self, event) -> None:
        """Отправить случайный ASCII-смайлик. Псевдоним: .asciiface"""
        face = random.choice(_FACES)
        await event.reply(
            self.strings("ascii_face").format(face=face),
            parse_mode="html",
        )
