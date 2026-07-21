from __future__ import annotations
import random
import re
from ..core.loader import KitsuneModule, command, watcher, ModuleConfig, ConfigValue
from ..core.security import OWNER

_DB = "kitsune.komezhka"
_MAX_POWER = 10

_KAOMOJI = [
    "(\u2661\u02d8\u25bd\u02d8\u2661)", "(\uff89\u25d5\u30ee\u25d5)\uff89", "(\u0e51\u02d8\u2022\u02d8\u0e51)", "(\u2044\u2044\u2022\u2044\u03c9\u2044\u2022\u2044\u2044)",
    "(\uff61\u2022\u0301\u1d17\u2022\u0300\uff61)", "(\u02d8\u03c9\u02d8)", "(\u30fb\u030a\u03c9\u30fb\u030a)", "(\u25dd\u02d8\u1d55\u02d8)\u2727",
    "(\u256c \u02d8\u25bd\u02d8)\u256c", "(\uff89\uff9f\u2200\uff9f)\uff89", "(\u2044\u2044\u2044\u2044\u2044 \u00b0 \u1d17 \u00b0 \u2044\u2044\u2044\u2044\u2044)",
    "\u0295\u2022\u1d25\u2022\u0294", "(\u3063\u2022\u0301\u25be\u2022\u0300\u3063)", "(\uff20^\u3145\u030a^\uff20)", "(\u2044 \u2044\u2022\u2044\u03c9\u2044\u2022\u2044 \u2044)",
    "(\u2035\u25be \u25be \u2033)", "\uff08\u261e\uff9f\u30ee\uff9f\uff09\u261e", "(\u02c3\u1d25\u02c2)", "\u2727\uff65\uff9f: *(\u2044\u2044>\u2044\u25bd\u2044<\u2044\u2044)*:\uff65\u2727",
    "(\u1d55 \u1d17 \u1d55)", "(\u02d8\u2323\u02d8)", "(\u25d5\u203f\u25d5)", "(\u2665\u02c2\u1d25\u02c3\u2665)",
    "(\u02d9\u03c9\u02d9)", "(*\u00b4\u2200\uff40*)", "(\u30fb\u2200\u30fb)", "(\u261e\uff9f\u30ee\uff9f)\u261e",
    "(\u25cf\u02c6\u1d55\u02c6\u25cf)", "(*\u0e51\u00b4\u1d55`\u0e51)", "(\u3065\uffe3 \u00b3\uffe3)\u3065", "(\u02d8\u1d95\u02d8)",
    "(\u02c3\u0430\u02c2)", "\u0295\u25c9\u1d25\u25c9\u0294", "(\u00b4\u2022 \u03c9 \u2022`)", "\u0294\u1d55\u25e1\u1d55\u0295",
    "(\uff65\u0300\u3078\u00b4\uff65)", "\u2299\uff65\u03c9\uff65\u2299", "(\uff89>\u03c9<)\uff89", "(\u256c\u2022\u1d55\u2022)\u256c",
    "(\u25cf\u00b4\u03c9\uff40\u25cf)", "(\uff65\u2200\uff65)", "(\u30fc\u3141\u30fc)", "(\u2267\u25bd\u2266)",
    "(\uff61>\uff5c<\uff61)", "(\u2022\u02da\u1d55\u02da\u2022)", "(\uff61\u2299\u203f\u2299\uff61)", "(\u25e1\u203f\u25e1)",
    "(\u3063\uff65\u2200\uff65)\u3063", "\u2606\u5f61\u25cf\u203f\u25cf\u5f61\u2606", "(\uff65\u03c9\uff65)\u30ce", "(\uff3e\u25bd\uff3e)",
    "(\u02d8\u25be\u02d8)~\u266a", "\u2570(*\u00b0\u25bd\u00b0*)\u256f", "(\uff61\u30fb\u03c9\u30fb\uff09\u30ce", "(\u2312\u25e1\u2312)",
    "\uff08\u2267\u25bd\u2266\uff09", "(\u00b4\u30fc\uff40)", "(\u02d8\u203f\u02d8\u273f)", "(\u2727\u02f6\u25e1\u02f6\u2727)",
    "(\u256c\u02d8\u25e1\u02d8)\u256c", "(\uff65\u030a\u03c9\uff65\u030a)", "(\u3065\uff61\u25d5\u2038\u25d5\uff61)\u3065", "\uff08*/\u2200\uff3c*\uff09",
    "(\u3063\uff30\u03c9\uff30c)\u3063", "\u2606\uff08\u3063\u25d5\u203f\u25d5\uff09\u3064", "(\uff9f\u30ee\uff9f)", "\u0669(\u02d8\u25bd\u02d8)\u06f6",
    "(\u02d8\u0648\u02d8)", "(\u02d8\u222a\u02d8\u273f)", "\u0295\u25d5\u1d25\u25d5\u0294", "(\uff65\u1d17\uff65)",
    "(\u25b0\u02d8\u25e1\u02d8\u25b0)", "(\uff89\u02d8\u25bd\u02d8)\uff89", "(\u02c3\u25be\u02c2)", "(\u00b4\uff65\u03c9\uff65`)",
    "(\uff61\u2022\u0301\u203f\u2022\u0300\uff61)", "(\u2299\u03c9\u2299)", "(\u02d8\u1d17\u02d8)", "(\uff61\u30fb\u2200\u30fb\uff09",
    "(\u256c\uff9f\u2200\uff9f)\u256c", "(\uff62\u25d5\u203f\u25d5\uff63", "(\uff65\u2323\uff65)", "\u2570(\u02d8\u203f\u02d8)\u256f",
    "(\u3055\u2022\u030a\u03c9\u2022\u030a)\u3055", "(\uff65\u3078\uff65)", "(\u02d8\u0669)", "(\u3063\u02d8\u03c9\u02d8c)",
    "(\uff65\u2261\uff65)", "\uff08*\u00b4\u25bd`*\uff09", "(\u1d17\u1d25\u1d17)", "(\u02da\u1d55\u02da)",
    "\u2570(\u2022\u1d17\u2022)\u256f", "(\u00b4\u203f`\u2661)", "(\uff65\u0301\u30ee\uff65\u0300)", "(\uff9f\u2200\uff9f)",
    "(\u2606\u02c2\u1d25\u02c3\u2606)", "(\u02c3\u02d8\u25bd\u02d8\u02c2)", "(\u3063\u2661\u25e1\u2661\u3063)", "(\uff89\u2661\u2200\u2661)\uff89",
    "(\u02d8\u25bd\u02d8)\u266a", "(\u25d5\u1d17\u25d5)", "(\uff65\u03c9\uff65)", "(\u25b8\u03c9\u25c2)",
    "(\u02d8\uff61\u02d8)", "\u0295\u02d8\u1d25\u02d8\u0294", "(\u3063\u2022\u2038\u2022\u3063)", "(\u25dd\u02d8\u25bd\u02d8)\u2727",
    "(\uff61\u2665\u203f\u2665\uff61)", "(\u2022\u2035\u1d17\u2036\u2022)", "(\uff9f\u2661\uff9f)", "\uff08\u3065\uff61\u25d5\u203f\u25d5\uff09\u3065",
    "(\u02da\u30ee\u02da)", "(\u2606\u3161\u2606)", "(\uff65\u25bd\uff65)", "(\u25d5\u3145\u25d5)",
    "\u0295\u2299\u1d25\u2299\u0294", "(\uff61\u02d8\u2323\u02d8\uff61)", "(\u2727\u203f\u2727)", "(\u3063\u25d5\u203f\u25d5)\u3063",
    "(\uff65\u1d17\uff65)\u2661", "(\u02d8\u25e1\u02d8\u02ce)", "(\uff89\u02d8\u25e1\u02d8)\uff89", "(\u25d5\u2323\u25d5\u273f)",
    "(*^\u30fc^*)", "(\u30fb\u030a\u03c9\u030a\uff65)", "\u2570(\u2665\u203f\u2665)\u256f", "(\u00b4\u2022\u1d17\u2022`)",
    "(\uff9f\u25bd\uff9f)", "(\u02d8\u2323\u02d8*)", "(\u3063\u02d8\u25bd\u02d8)\u3063", "(\uff65\u0301\u1d17\uff65\u0300)",
    "(\u2665\u02d8\u25bd\u02d8)", "(\uff89\u2299\u203f\u2299)\uff89", "(\u02c3\u2022\u1d25\u2022\u02c2)", "(\uff61\u2727\u203f\u2727\uff61)",
    "(\u2312\u1d17\u2312)", "\u0295\u02d8\u25bd\u02d8\u0294", "(\uff65\u2661\uff65)", "(\u25d5\uff65\u25d5)",
    "(\u02d8\u30ee\u02d8\u273f)", "(\uff89\u25d5\u203f\u25d5)\uff89", "(\u3063\uff65\u25bd\uff65)\u3063", "(\uff61\u25d5\u2200\u25d5\uff61)",
    "(\u2665\uff65\u03c9\uff65\u2665)", "(\u02d8\u1d17\u02d8\uff61)", "\u2570(*\u2661\u25bd\u2661*)\u256f", "(\uff65\u00b4\u03c9`\uff65)",
    "(\u25dd\u02d8\u25e1\u02d8)\u2727", "(\u02d9\u1d17\u02d9)", "(\uff89\u2661\u25bd\u2661)\uff89", "(\u02c3\u25e1\u02c2)",
    "(\u3063\u2665\u03c9\u2665)\u3063", "(\uff61\u02d8\u03c9\u02d8\uff61)", "\u0295\u2665\u1d25\u2665\u0294", "(\u2727\u2022\u1d17\u2022\u2727)",
    "(\u02da\u25e1\u02da)", "(\uff89\u02d8\u2200\u02d8)\uff89", "(\u25d5\u2661\u25d5)", "(\uff61\u2299\u03c9\u2299\uff61)",
]

_KAOMOJI_SOFT_LEWD = [
    "(\u2044\u2044\u2044\u2044\u2044 \u00b0 \u1d17 \u00b0 \u2044\u2044\u2044\u2044\u2044)", "(*/\u03c9\uff3c*)", "(\u2044 \u2044\u2022\u2044\u03c9\u2044\u2022\u2044 \u2044)",
    "(\u00b4\u02d8\u0300\u25e1`\u02d8\u2019)", "(\u02d8\u1d17\u02d8)\u2661", "(\u2044\u2044>\u2044\u25bd\u2044<\u2044\u2044)",
    "(\u3063\u2022\u0301\u203f\u2022\u0300\u3063)\u2661", "(\u02d8\u203f\u02d8)\u2661", "(\u2044\u03c9\u2044)",
    "(\u2044\u2044\u2044\u2044\u2044>\u2044\u2044\u2044\u2044\u2044<)", "\uff08\u2044\u2044\u2044 \u00b0\u2200\u00b0 \u2044\u2044\u2044\uff09", "(\u3063\u2022\u0301\u25be\u2022\u0300\u3063)\u2661",
    "(\u02d8\u1d95\u02d8\u2044\u2044\u2044)", "(*\u00b4\u2764`*)", "(\u2044\u2044\u2044\u2044 \u1d17 \u2044\u2044\u2044\u2044)", "\u2764(\u1d55\u02d8\u1d55)\u2661",
    "(\uff65\u2044\u2044\u03c9\u2044\u2044\uff65)", "(\u2044\u2044>\u03c9<\u2044\u2044)", "(\u3063\u2044\u2044\u03c9\u2044\u2044)\u3063", "(\u2044\u2044\u2044\u02d8\u2044\u1d17\u2044\u02d8\u2044\u2044\u2044)",
    "(\u2044\u2044\u2022\u2044\u2200\u2044\u2022\u2044\u2044)", "\uff08\u2044\u2044>\u2044/\u2044<\u2044\u2044\uff09", "(\u02d8\u2044\u03c9\u2044\u02d8)", "(\u2044\u2044\u2661\u2044\u1d17\u2044\u2661\u2044\u2044)",
]

_KAOMOJI_MID_LEWD = [
    "(\u2044\u2044\u2044\u2044\u2044\u2044 >\u1d17< \u2044\u2044\u2044\u2044\u2044\u2044)", "(\u3063\u2044\u2044>\u03c9<\u2044\u2044)\u3063\u2661", "(\u02d8\u2044\u2044\u1d17\u2044\u2044\u02d8)\u2661",
    "(\u2044\u2044\u2044\u2044 \u02f0 \u1d17 \u02f0 \u2044\u2044\u2044\u2044)", "\uff08\u2044\u2044\u2044\u2044 \u00b0 \u2200 \u00b0 \u2044\u2044\u2044\u2044\uff09\u2661", "(\u3063\u02d8\u1d17\u02d8\u2044\u2044\u2044)\u3063",
    "(\u2044\u2044\u2044 \u2565\u03c9\u2565 \u2044\u2044\u2044)", "(\u02d8\u1d17\u02d8\u2044\u2044\u2044)\uff9b", "(\u2044\u2044>\u2200<\u2044\u2044)\u2661\u2661",
    "(\uff89\u2044\u2044\u1d17\u2044\u2044)\uff89\u2661", "(\u2044\u2044\u2044 \u02d8 \u035c\u02d8 \u2044\u2044\u2044)", "(\u3063\u2044\u2044\u2661\u2044\u1d17\u2044\u2661\u2044\u2044)\u3063",
    "\uff08\u2044\u2044\u2044\u2044 \u2299 \u1d17 \u2299 \u2044\u2044\u2044\u2044\uff09", "(\u02d8\u2044\u2044\uff65\u2044\u2044\u03c9\u2044\u2044\uff65\u2044\u2044\u02d8)", "(\u2044\u2044\u2044\u2044 \uff9b\u1d17\uff9b \u2044\u2044\u2044\u2044)",
    "(\u3063\u2044\u2044\uff9b\u2044\u2044)\u3063\u2661\u2661", "(\u2044\u2044\u2044 \u2565 \u035c\u0296 \u2565 \u2044\u2044\u2044)", "(\u02d8\u2044\u2044\u2661\u2044\u2044\u02d8)\uff9b\u2661",
]

_KAOMOJI_HARD_LEWD = [
    "(\u2044\u2044\u2044\u2044\u2044 \u0296\u203f\u0296 \u2044\u2044\u2044\u2044\u2044)", "(\u3063\u2044\u2044\u2044 \u035c\u0296\u035c\u0296 \u2044\u2044\u2044)\u3063\u2661", "(\u02d8\u2044\u2044\u035c\u0296\u2044\u2044\u02d8)\uff9b\u2661\u2661",
    "\uff08\u2044\u2044\u2044\u2044 \u3016 \uff9b \u3017 \u2044\u2044\u2044\u2044\uff09", "(\u2044\u2044\u2044 \u2565 \u035c\u0296 \u2565 \u2044\u2044\u2044)\u2661\u2764", "(\u3063\u2044\u2044\u2044 \uff9b\u035c\u0296 \u2044\u2044\u2044)\u3063\u2764",
    "(\u2044\u2044\u2044\u2044 >\u035c\u0296< \u2044\u2044\u2044\u2044)", "(\u02d8\u2044\u2044\u035c\u0296\u2044\u2044\u02d8\u2044\u2044\u2044)\u2661", "\uff08\u2044\u2044\u2044\u2044 \uff9b \u035c\u0296 \uff9b \u2044\u2044\u2044\u2044\uff09\u2764",
    "(\u3063\u2044\u2044\u2761\u2044\uff9b\u2044\u2761\u2044\u2044)\u3063\u2764", "(\u2044\u2044\u2044 \u2299 \uff9b \u2299 \u2044\u2044\u2044)\u2661\u2761", "(\u02d8\u2044\u2044\u3016\uff9b\u3017\u2044\u2044\u02d8)\u2764\u2764",
    "(\u2044\u2044\u2044\u2044 \u2565 \u035c\u0296 \u2565 \u2044\u2044\u2044\u2044)\uff9b\uff9b", "(\u3063\u2044\u2044\u2044 \u035c\u0296 \u2044\u2044\u2044)\u3063\uff9b\u2764\u2764", "\uff08\u2044\u2044\u2044\u2044 \u3016 \u035c\u0296 \u3017 \u2044\u2044\u2044\u2044\uff09\u2761",
    "(\u2044\u2044\u2044 \u2565\uff9b\u2565 \u2044\u2044\u2044)\u2764\u2761", "(\u02d8\u2044\u2044\u035c\u0296\uff9b\u035c\u0296\u2044\u2044\u02d8)\u2764", "(\u3063\u2044\u2044\u2044 >\u035c\u0296< \u2044\u2044\u2044)\u3063\u2761\u2764",
]

_ACTIONS = [
    "ломается на секунду", "улыбается", "тихо мур", "перезагружается",
    "поджимает ушки", "краснеет", "прячется за лапки", "нервно теребит рукав",
    "тихо пищит", "машет хвостиком", "отводит взгляд", "смущённо хихикает",
    "дрожит от стеснения", "закрывает лицо лапками", "топчет ножкой", "сворачивается клубочком",
    "шепчет еле слышно", "стеснительно улыбается", "прижимает ушки", "мяукает",
    "теребит край кофты", "смотрит исподлобья", "ковыряет носком пол", "теребит пальчики",
    "прячет лицо в ладошках", "смущённо отворачивается", "тихо сопёт", "кутается в пледик",
    "теребит воротник", "робко машет лапкой", "виляет хвостом", "шмыгает носиком",
    "путается в словах", "нервно сглатывает", "теребит прядку волос", "покачивается с ноги на ногу",
    "тихо вздыхает", "застенчиво улыбается", "прячется за подушку", "робко выглядывает",
    "нервно хихикает", "теплеет ушками", "прикусывает губку", "робко тянется к тебе",
    "опускает глазки", "теребит капюшон", "обнимает подушку", "нервно покашливает",
    "пушит хвостик", "прижимается к стенке", "тихо ахает", "робко кивает",
    "смотрит большими глазками", "вскидывает лапки", "буркает под нос", "теребит бантик",
    "смущённо топчется", "проводит лапкой по волосам", "робко тянет ручку", "потирает лапки",
    "прячется в капюшон", "тихо мяукает в сторонку", "перебирает лапками", "заливается румянцем",
    "нервно облизывает губки", "притопывает лапками", "смотрит через чёлку", "робко улыбается уголком рта",
    "подрагивает ушками", "тихо поскуливает", "обнимает себя за плечи", "закрывает глазки лапками",
    "вертит пуговицу", "нервно теребит цепочку", "мнёт краешек футболки", "тихо посапывает",
    "прячет лапки в рукава", "робко моргает", "тихо пыхтит", "прижимает ладошки к щёкам",
    "нервно крутит локон", "отворачивается и краснеет", "покачивает головкой", "теребит реснички",
    "робко выглядывает из-за угла", "смущённо кусает ноготок", "поджимает лапки к груди", "тихо посмеивается",
    "мотает головой от смущения", "потирает глазки", "теребит шнурок", "робко тянется к телефону",
    "прижимается лбом к экрану", "тихо мячит", "нервно моргает", "смущённо отводит глазки",
    "покраснев до ушей", "теребит край юбки", "робко поглаживает ушки", "тихо шепчет в сторонку",
    "прячется под одеяло", "нервно стучит пальчиками", "опускает взгляд в пол", "робко машет хвостиком",
    "теплеет щёчками", "смущённо потягивается", "тихо помурлыкивает", "прикрывает лицо воротником",
    "робко жмётся к тебе", "надувает щёчки", "хлопает глазками", "смущённо ковыряет пол носочком",
    "тихо чихает и краснеет", "робко перебирает пальчики", "прячет нос в шарфик", "смущённо теребит уголок пледа",
    "поднимает глазки и тут же опускает", "робко улыбается краешком губ", "нервно приглаживает чёлку", "тихо мурчит себе под нос",
    "прижимает лапки к мордочке", "смущённо покачивает хвостиком", "робко жмурится", "теребит краешек рукава зубками",
    "тихо посвистывает от смущения", "робко закрывает ротик лапкой", "смущённо вертит прядку", "прячет глазки за чёлкой",
    "тихо булькает от стеснения", "робко трогает свои ушки", "смущённо разглядывает пол", "нервно перебирает бусинки",
    "прижимает мягкие лапки к щекам", "робко высовывается из пледа", "тихо попискивает от радости", "смущённо машет ручкой",
    "заворачивается в одеялко", "робко подглядывает одним глазком", "тихо урчит от уюта", "смущённо прячет мордочку",
    "нежно тянется обняться", "робко прижимает хвостик", "тихо жмётся поближе", "смущённо прячет личико",
]

_ACTIONS_SOFT_LEWD = [
    "робко прикусывает нижнюю губку", "смущённо облизывается", "прижимается всем телом",
    "тихо стонет от смущения", "тает в твоих руках", "шепчет на ушко", "смотрит томным взглядом",
    "медленно облизывает губки", "горячо выдыхает", "дрожит от возбуждения",
    "прикусывает пальчик", "смущённо разводит лапки", "тихо тянет тебя ближе",
    "прижимается грудкой", "соблазнительно улыбается", "покачивает бёдрами",
    "томно вздыхает", "смотрит из-под ресничек", "тихо мурлычет тебе на ушко",
    "робко прижимается бедром", "нежно кусает мочку ушка", "тихо постанывает от прикосновений",
    "смущённо ёрзает на месте", "проводит язычком по губкам", "жарко дышит тебе в шею",
    "трётся щёчкой о тебя", "робко тянет за край одежды", "смущённо приоткрывает губки",
]

_ACTIONS_MID_LEWD = [
    "томно постанывает и выгибается", "прижимается бёдрами и тихо мурлычет", "медленно ведёт лапкой по своему бедру",
    "смущённо закусывает губку и жарко дышит", "прогибается в спинке от прикосновений", "тихо скулит от нетерпения",
    "приоткрывает губки и тяжело дышит", "прижимается всем телом и трётся", "томно облизывает губки, глядя в глаза",
    "дрожит и прижимается ближе", "тихо стонет тебе на ушко", "соблазнительно выгибает спинку",
    "медленно расстёгивает верхнюю пуговку", "жарко шепчет 'хочу тебя'", "прикусывает губу и постанывает",
    "нежно ведёт язычком по губам", "прижимается грудкой и тает", "томно ёрзает, ища прикосновений",
    "горячо выдыхает и прижимается ниже", "смущённо стягивает край футболки", "тихо мурлычет и трётся бедром",
]

_ACTIONS_HARD_LEWD = [
    "громко постанывает, выгибаясь всем телом", "течёт от одного твоего голоса", "жарко дышит и умоляет прикоснуться",
    "прижимается мокрыми бёдрами", "стонет и просит ещё", "дрожит всем телом от возбуждения",
    "томно раздвигает лапки, глядя в глаза", "прикусывает губу и громко стонет", "трётся всем телом, изнывая от желания",
    "шепчет 'возьми меня' на ушко", "тает и стекает по тебе", "прогибается и громко мурлычет от каждого касания",
    "не выдерживает и стонет твоё имя", "жарко умоляет не останавливаться", "дрожит на грани, кусая губы",
    "прижимается и трётся, изнывая от течки", "громко дышит и просит сильнее", "изгибается и постанывает без остановки",
    "льнёт всем телом, задыхаясь от желания", "стонет и цепляется за тебя лапками", "течёт и дрожит, умоляя взглядом",
]

_EMOJI = [
    "\U0001F495", "\U0001F496", "\U0001F497", "\U0001F361", "\U0001F43E", "\U0001F431", "\U0001F97A", "\U0001F380",
    "\U0001F9ED", "\U0001F4A4", "\U0001F36D", "\u2728", "\U0001F338", "\U0001F36C", "\U0001F9A2", "\U0001F49E",
    "\U0001F90D", "\U0001F98A", "\U0001F365", "\U0001F4A2", "\U0001F49D", "\U0001F49B", "\U0001F49C", "\U0001F499",
    "\U0001F49A", "\U0001F493", "\U0001F49F", "\U0001F60A", "\U0001F633", "\U0001F60D", "\U0001F970", "\U0001F925",
    "\U0001F63B", "\U0001F638", "\U0001F63C", "\U0001F345", "\U0001F353", "\U0001F352", "\U0001F351", "\U0001F91E",
    "\U0001F44F", "\U0001F44B", "\U0001F91A", "\U0001F44C", "\U0001F450", "\U0001F646", "\U0001F31F", "\U0001F4AB",
    "\U0001F30C", "\U0001F308", "\U0001F340", "\U0001F33C", "\U0001F337", "\U0001F33F", "\U0001F344", "\U0001F423",
    "\U0001F425", "\U0001F430", "\U0001F98B", "\U0001F42D", "\U0001F439", "\U0001F43C", "\U0001F411", "\U0001F98C",
    "\U0001F339", "\U0001F33A", "\U0001F33B", "\U0001F341", "\U0001F342", "\U0001F343", "\U0001F35E", "\U0001F369",
    "\U0001F36A", "\U0001F370", "\U0001F382", "\U0001F9C1", "\U0001F368", "\U0001F366", "\U0001F367", "\U0001F36F",
    "\U0001F41B", "\U0001F41D", "\U0001F998", "\U0001F407", "\U0001F43F", "\U0001F994", "\U0001F9A5", "\U0001F54A",
    "\u2b50", "\U0001F320", "\u2600", "\U0001F319", "\u2601", "\U0001F327", "\u2744", "\u26c4",
    "\U0001F386", "\U0001F388", "\U0001F390", "\U0001F9F5", "\U0001F60C", "\U0001F929", "\U0001F642", "\u263a",
    "\U0001F917", "\U0001F91F", "\U0001F44D", "\U0001F91D", "\U0001F64F", "\U0001F4AE", "\U0001F32B", "\U0001F52E",
    "\U0001F9F8", "\U0001F9F6", "\U0001F9E6", "\U0001F460", "\U0001F457", "\U0001F452", "\U0001F455", "\U0001F9E3",
]

_EMOJI_SOFT_LEWD = [
    "\U0001F63B", "\U0001F60F", "\U0001F49E", "\U0001F445", "\U0001F31A", "\U0001F604", "\U0001F607", "\U0001F60D",
    "\U0001F970", "\U0001F618", "\U0001F633", "\U0001F97A", "\U0001F44F", "\U0001F49F",
]

_EMOJI_MID_LEWD = [
    "\U0001F609", "\U0001F60F", "\U0001F975", "\U0001F624", "\U0001F92A", "\U0001F4A6", "\U0001F346", "\U0001F351",
    "\U0001F608", "\U0001F31A", "\u2764\uFE0F", "\U0001F445", "\U0001F444", "\U0001F4A2",
]

_EMOJI_HARD_LEWD = [
    "\U0001F608", "\U0001F4A6", "\U0001F346", "\U0001F351", "\U0001F445", "\U0001F444", "\U0001F975", "\U0001F624",
    "\u2764\uFE0F\u200D\U0001F525", "\U0001F32B", "\U0001F62B", "\U0001F92A", "\U0001F60F", "\U0001F4A2", "\U0001F31A",
]

_SUFFIX = [
    "~", "~\U0001F495", " uwu", " owo", " hihi~", " kyaa~", " mrr~", " nya~", " >w<", " :3", " \u02d8\u02d8", " \u2661",
    "~nya", " uwu~", " x3", " \uff9e\uff9e", " hehe~", " mya~", " nyaa~", " owo~", " \u0669(\u02d8\u25bd\u02d8)\u06f6",
    " nnn~", " ehe~", " mm~", " \u2661\u2661", " purr~", " o///o", " uwu\U0001F43E", " nya\u2661", " >////<",
    " \u2661w\u2661", " :3c", " \uff5e\uff9e", " \u2665", " (\u02d8\u03c9\u02d8)", " ehehe~",
    " mew~", " nyan~", " uwu\u2661", " \u2727", " prr~", " hnng~", " nnya~", " owo\U0001F43E", " :33", " ny~",
    " ehe\u2661", " mrrp~", " \u2661\u02d8\u02d8", " hehe\u2661", " uu~", " ^^", " ^w^", " >\u03c9<", " \uff5e",
]

_SUFFIX_SOFT_LEWD = [
    "~\u2764", " nyaa~\u2764", " mmh~", " ah~", " \U0001F63B", " uwu\u2764", " \u2661\u2661\u2661",
    " ~senpai\u2661", " (\u02d8\u1d17\u02d8)", " mrrp~\u2764", " \U0001F60F", " haa~", " o///o\u2764",
    " nnh~", " aah~", " \u2661\u02d8\u1d17\u02d8", " hnn~", " mm\u2764", " prr~\u2764", " \u2764\u2764",
]

_SUFFIX_MID_LEWD = [
    " aah~\u2764", " mmh\u2764", " haa~\u2764", " nnh~\u2764", " hnng~\u2764", " \u2764\u2764\u2764",
    " ~senpai\u2764", " mrr\u2764", " o///o\u2764\u2764", " haaa~", " nyaa\u2764\u2764", " (\u02d8\u1d17\u02d8)\u2764",
    " hah~\u2764", " mmm\u2764", " nn~\u2764",
]

_SUFFIX_HARD_LEWD = [
    " aaah~\u2764\u2764", " mmmh\u2764\u2764", " haaa~\u2764\u2764", " nnngh~\u2764", " a-ah~\u2764\u2764",
    " \u2764\u2764\u2764\u2764", " haa\u2764\u2764\u2764", " mnn~\u2764\u2764", " ~\u2764master\u2764",
    " o//////o\u2764\u2764", " nyaaa\u2764\u2764\u2764", " ah-ah~\u2764\u2764", " hnnng\u2764\u2764",
]

_PREFIX_INTERJ = [
    "\u043c-\u043c", "\u044d-\u044d\u0442\u043e", "\u043d-\u043d\u0443", "\u0432-\u0432\u043e\u0442", "\u043e\u0439", "\u0430-\u0430", "\u0445\u043c\u043c", "\u044d\u044d",
    "\u0443-\u0443", "\u0430\u0445", "\u043e-\u043e", "\u043c\u043c", "\u0430\u0439", "\u043d\u0443-\u0443", "\u044d\u043c-\u043c", "\u043e\u0439-\u043e\u0439",
    "\u043d-\u043d\u0435", "\u043a-\u043a", "\u0433-\u0433", "\u0442-\u0442\u0430\u043a", "\u0432\u0430\u0430", "\u044f-\u044f", "\u043c\u044f", "\u043d\u044f",
    "\u0443\u043c-\u043c", "\u0430\u0445-\u0430\u0445", "\u043e\u0445", "\u0443\u0445", "\u044d\u0445", "\u043d-\u043d\u0430\u0432\u0435\u0440\u043d\u043e", "\u043f-\u043f\u0440\u043e\u0441\u0442\u043e",
    "\u043d\u0443 \u0432\u043e\u0442", "\u044d-\u043c-\u043c", "\u0430-\u0430\u0445", "\u043e-\u043e\u0439", "\u043c-\u043c\u043c", "\u0432-\u0432\u0435\u0434\u044c", "\u043d-\u043d\u0430\u0434\u043e",
    "\u0442-\u0442\u044b", "\u044f-\u044f \u043d\u0435 \u0437\u043d\u0430\u044e", "\u0443\u0430\u0445", "\u0445\u0435\u0445", "\u043d\u043d\u0443", "\u0430\u0439-\u044f\u0439", "\u044d\u0445-\u043c",
]

_TAIL_INTERJ = [
    "\u043d\u044f~", "\u0443\u0432\u0443", "\u0445\u0435-\u0445\u0435", "\u043c\u044f~", "\u0430\u0445\u0430", "\u044d\u0445\u0435\u0445\u0435", "\u043c\u043c~", "\u0430\u0433\u0430",
    "\u043d\u0443 \u0442\u0438\u043f\u0430", "\u043d\u0430\u0432\u0435\u0440\u043d\u043e~", "\u0435\u0441\u043b\u0438 \u0447\u0451~", "\u0432\u043e\u0442 \u0442\u0430\u043a~", "\u0445\u0438-\u0445\u0438", "\u0443\u0433\u0443~",
    "\u043d\u044f\u0430~", "\u0445\u0435\u0445\u0435~", "\u043c\u0443\u0440~", "\u0443\u0432\u0443~", "\u0435\u0445\u0435~", "\u043d\u0443-\u043d\u0443", "\u043e\u043a\u0435\u0439~",
    "\u043f\u0440\u0430\u0432\u0434\u0430~", "\u0432\u0440\u043e\u0434\u0435 \u0431\u044b", "\u043d\u0430\u0432\u0435\u0440\u043d\u043e\u0435", "\u0445\u043c~", "\u0442\u0430\u043a-\u0442\u043e~", "\u043c\u044f\u0443~",
]

_TAIL_INTERJ_LEWD = [
    "\u0445\u0430\u0430~", "\u043d\u044f\u0430\u0430~", "\u043c\u043c\u043c~", "\u043e\u0439 \u0447\u0442\u043e \u044f \u0433\u043e\u0432\u043e\u0440\u044e~", "\u0430\u0445~", "\u043d\u0435 \u0441\u043c\u043e\u0442\u0440\u0438 \u0442\u0430\u043a~",
    "\u044f \u0432\u0441\u044f \u0433\u043e\u0440\u044e~", "\u0442\u0435\u0431\u0435 \u043d\u0440\u0430\u0432\u0438\u0442\u0441\u044f~", "\u043c\u043c\u0445~", "\u0430\u0445\u0445~", "\u044f \u043d\u0435 \u0432\u044b\u0434\u0435\u0440\u0436\u0443~",
]

_VOWELS = "\u0430\u0435\u0451\u0438\u043e\u0443\u044b\u044d\u044e\u044f"

_WORD_RE = re.compile(r"[\u0410-\u042f\u0430-\u044f\u0451\u0401A-Za-z]+")

# \u0421\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f, \u043a\u043e\u0442\u043e\u0440\u044b\u0435 \u0432\u043e\u0442\u0447\u0435\u0440 \u041d\u0415 \u0434\u043e\u043b\u0436\u0435\u043d \u043f\u0435\u0440\u0435\u0434\u0435\u043b\u044b\u0432\u0430\u0442\u044c (\u0447\u0442\u043e\u0431\u044b \u043d\u0435 \u043b\u043e\u043c\u0430\u0442\u044c \u0432\u044b\u0432\u043e\u0434 \u0434\u0440\u0443\u0433\u0438\u0445 \u043c\u043e\u0434\u0443\u043b\u0435\u0439):
# HTML-\u0442\u0435\u0433\u0438, \u0441\u0441\u044b\u043b\u043a\u0438, \u0431\u043b\u043e\u043a\u0438 \u043a\u043e\u0434\u0430, \u0443\u043f\u043e\u043c\u0438\u043d\u0430\u043d\u0438\u044f \u043a\u0430\u0441\u0442\u043e\u043c-\u044d\u043c\u043e\u0434\u0437\u0438.
_SKIP_RE = re.compile(r"</?[a-zA-Z][^>]*>|https?://|```|<emoji|<tg-emoji")


def _lewd_level(power: int) -> int:
    if power <= 6:
        return 0
    if power <= 8:
        return 1
    if power == 9:
        return 2
    return 3


def _kao_pool(level: int) -> list:
    if level == 0:
        return list(_KAOMOJI)
    if level == 1:
        return list(_KAOMOJI) + _KAOMOJI_SOFT_LEWD
    if level == 2:
        return _KAOMOJI[:60] + _KAOMOJI_SOFT_LEWD * 2 + _KAOMOJI_MID_LEWD * 2
    return _KAOMOJI[:20] + _KAOMOJI_MID_LEWD * 2 + _KAOMOJI_HARD_LEWD * 3


def _act_pool(level: int) -> list:
    if level == 0:
        return list(_ACTIONS)
    if level == 1:
        return list(_ACTIONS) + _ACTIONS_SOFT_LEWD
    if level == 2:
        return _ACTIONS_MID_LEWD + _ACTIONS_SOFT_LEWD + _ACTIONS[:30]
    return _ACTIONS_HARD_LEWD + _ACTIONS_HARD_LEWD + _ACTIONS_MID_LEWD


def _emo_pool(level: int) -> list:
    if level == 0:
        return list(_EMOJI)
    if level == 1:
        return list(_EMOJI) + _EMOJI_SOFT_LEWD
    if level == 2:
        return _EMOJI[:50] + _EMOJI_SOFT_LEWD * 2 + _EMOJI_MID_LEWD * 2
    return _EMOJI[:20] + _EMOJI_MID_LEWD * 2 + _EMOJI_HARD_LEWD * 3


def _suf_pool(level: int) -> list:
    if level == 0:
        return list(_SUFFIX)
    if level == 1:
        return list(_SUFFIX) + _SUFFIX_SOFT_LEWD
    if level == 2:
        return _SUFFIX[:25] + _SUFFIX_SOFT_LEWD * 2 + _SUFFIX_MID_LEWD * 2
    return _SUFFIX[:10] + _SUFFIX_MID_LEWD * 2 + _SUFFIX_HARD_LEWD * 3


def _pick(seq, k):
    if k <= 0:
        return []
    if k >= len(seq):
        pool = list(seq)
        random.shuffle(pool)
        return pool
    return random.sample(list(seq), k)


def _stutter_word(word: str, chance: float) -> str:
    if len(word) < 2 or random.random() > chance:
        return word
    first = word[0]
    if not first.isalpha():
        return word
    reps = random.choice([1, 1, 2, 2, 3])
    return (first.lower() + "-") * reps + word


def _stretch_vowels(word: str, chance: float) -> str:
    if random.random() > chance:
        return word
    out = []
    for ch in word:
        out.append(ch)
        if ch.lower() in _VOWELS and random.random() < 0.5:
            out.append(ch * random.choice([1, 2, 2, 3, 4]))
    return "".join(out)


def _softish(word: str, power: int) -> str:
    chance = min(0.10 + power * 0.03, 0.45)
    if random.random() < chance and "\u0440" in word:
        return word.replace("\u0440", "\u0440~", 1)
    return word


def _process_text(text: str, power: int) -> str:
    if not text.strip():
        return text
    power = max(1, min(_MAX_POWER, power))
    level = _lewd_level(power)

    stutter_chance = min(0.08 + power * 0.09, 0.9)
    stretch_chance = min(0.06 + power * 0.08, 0.78)

    def repl(m: re.Match) -> str:
        w = m.group(0)
        w = _stutter_word(w, stutter_chance)
        w = _stretch_vowels(w, stretch_chance)
        w = _softish(w, power)
        return w

    result = _WORD_RE.sub(repl, text)

    parts: list[str] = []
    if random.random() < min(0.15 + power * 0.09, 0.8):
        parts.append(random.choice(_PREFIX_INTERJ) + " ")
    parts.append(result)
    tail_pool = _TAIL_INTERJ + (_TAIL_INTERJ_LEWD if level >= 1 else [])
    if random.random() < min(0.05 + power * 0.06, 0.55):
        parts.append(" " + random.choice(tail_pool))

    kao_pool = _kao_pool(level)
    act_pool = _act_pool(level)
    emo_pool = _emo_pool(level)
    suf_pool = _suf_pool(level)

    if power < 4:
        n_kao, n_act, n_emo = 1, 1, 1
    elif power < 7:
        n_kao, n_act, n_emo = 2, random.choice([1, 2]), 2
    elif power < 9:
        n_kao, n_act, n_emo = random.choice([2, 3]), random.choice([1, 2]), random.choice([2, 3])
    else:
        n_kao, n_act, n_emo = random.choice([3, 4]), random.choice([2, 3]), random.choice([3, 4])

    tail: list[str] = []
    if random.random() < min(0.45 + power * 0.08, 0.98):
        for kao in _pick(kao_pool, random.randint(1, n_kao)):
            tail.append(" " + kao)
    if random.random() < min(0.40 + power * 0.08, 0.96):
        for act in _pick(act_pool, random.randint(1, n_act)):
            tail.append(" *" + act + "*")
    if random.random() < min(0.35 + power * 0.08, 0.94):
        for emo in _pick(emo_pool, random.randint(1, n_emo)):
            tail.append(" " + emo)
    random.shuffle(tail)
    body = "".join(parts) + "".join(tail)

    if power < 6:
        n_suf = 1
    elif power < 9:
        n_suf = random.choice([1, 1, 2])
    else:
        n_suf = random.choice([1, 2, 2, 3])
    if random.random() < min(0.25 + power * 0.09, 0.9):
        body += "".join(_pick(suf_pool, n_suf))
    return body


class KomezhkaModule(KitsuneModule):
    name = "Komezhka"
    description = "\U0001F98A \u041f\u0440\u0435\u0432\u0440\u0430\u0449\u0430\u0435\u0442 \u0442\u0432\u043e\u0438 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u0432 \u043e\u043c\u0435\u0436\u043a\u0443~ (uwu, \u0437\u0430\u0438\u043a\u0430\u043d\u0438\u0435, \u043a\u0430\u043e\u043c\u043e\u0434\u0437\u0438, *\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f*, \u044d\u043c\u043e\u0434\u0437\u0438). \u0421\u0438\u043b\u0430 1-10: 1-6 \u043c\u0438\u043b\u043e, 7-8 \u043b\u0451\u0433\u043a\u0438\u0439 \u0444\u043b\u0438\u0440\u0442, 9-10 18+"
    author = "@Mikasu32"
    version = "3.0.0"
    icon = "\U0001F98A"
    category = "fun"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.config = ModuleConfig(
            ConfigValue(
                "power",
                default=3,
                doc="\u0421\u0438\u043b\u0430 \u044d\u0444\u0444\u0435\u043a\u0442\u0430 \u043e\u043c\u0435\u0436\u043a\u0438 1-10. 1-6 \u2014 \u043c\u0438\u043b\u0430\u044f, 7-8 \u2014 \u043b\u0451\u0433\u043a\u0438\u0439 \u0444\u043b\u0438\u0440\u0442, 9 \u2014 \u0441\u0440\u0435\u0434\u043d\u044f\u044f \u043f\u043e\u0448\u043b\u043e\u0441\u0442\u044c, 10 \u2014 \u043c\u043e\u0449\u043d\u0430\u044f (18+).",
            ),
            ConfigValue(
                "min_len",
                default=1,
                doc="\u041c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u0430\u044f \u0434\u043b\u0438\u043d\u0430 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u0434\u043b\u044f \u0430\u0432\u0442\u043e\u0440\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f.",
            ),
        )

    strings_ru = {
        "on": "\U0001F98A <b>Komezhka v3.0</b> \u0432\u043a\u043b\u044e\u0447\u0435\u043d\u0430~ \u0442\u0435\u043f\u0435\u0440\u044c \u0432\u0441\u0435 \u0442\u0432\u043e\u0438 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u0431\u0443\u0434\u0443\u0442 \u043e\u043c\u0435\u0436\u043d\u044b\u043c\u0438 (\u02d8\u03c9\u02d8)",
        "off": "\U0001F98A <b>Komezhka</b> \u0432\u044b\u043a\u043b\u044e\u0447\u0435\u043d\u0430. \u0421\u043d\u043e\u0432\u0430 \u0433\u043e\u0432\u043e\u0440\u0438\u0448\u044c \u043a\u0430\u043a \u043d\u043e\u0440\u043c\u0430\u043b\u044c\u043d\u044b\u0439 \u0447\u0435\u043b\u043e\u0432\u0435\u043a.",
        "status_on": "\U0001F98A <b>Komezhka v3.0</b>\n<blockquote>\u0421\u0442\u0430\u0442\u0443\u0441: <b>\u0432\u043a\u043b\u044e\u0447\u0435\u043d\u0430</b> \u2705\n\u0421\u0438\u043b\u0430 \u044d\u0444\u0444\u0435\u043a\u0442\u0430: <code>{power}/10</code> \u2014 {mood}</blockquote>\n<i>Dev: \u2728 @Mikasu32 \u2728 \u0441 \u043b\u044e\u0431\u043e\u0432\u044c\u044e \u0438 \u043e\u043c\u0435\u0436\u043d\u043e\u0441\u0442\u044c\u044e~ \U0001F98A</i>",
        "status_off": "\U0001F98A <b>Komezhka v3.0</b>\n<blockquote>\u0421\u0442\u0430\u0442\u0443\u0441: <b>\u0432\u044b\u043a\u043b\u044e\u0447\u0435\u043d\u0430</b> \u274c\n\u0421\u0438\u043b\u0430 \u044d\u0444\u0444\u0435\u043a\u0442\u0430: <code>{power}/10</code> \u2014 {mood}</blockquote>\n<i>Dev: \u2728 @Mikasu32 \u2728 \u0441 \u043b\u044e\u0431\u043e\u0432\u044c\u044e \u0438 \u043e\u043c\u0435\u0436\u043d\u043e\u0441\u0442\u044c\u044e~ \U0001F98A</i>",
        "power_set": "\U0001F98A \u0421\u0438\u043b\u0430 \u044d\u0444\u0444\u0435\u043a\u0442\u0430 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0430: <code>{power}/10</code>\n<blockquote>{mood}</blockquote>",
        "power_err": "\u274c \u0423\u043a\u0430\u0436\u0438 \u0447\u0438\u0441\u043b\u043e \u043e\u0442 1 \u0434\u043e 10: <code>.kpower 5</code>\n<blockquote>1-6 \u2014 \u043c\u0438\u043b\u043e~ \u2661\n7-8 \u2014 \u043b\u0451\u0433\u043a\u0438\u0439 \u0444\u043b\u0438\u0440\u0442 \U0001F60f\n9 \u2014 \u0441\u0440\u0435\u0434\u043d\u044f\u044f \u043f\u043e\u0448\u043b\u043e\u0441\u0442\u044c (18+)\n10 \u2014 \u043c\u043e\u0449\u043d\u0430\u044f \u043f\u043e\u0448\u043b\u043e\u0441\u0442\u044c (18+) \U0001F525</blockquote>",
        "uwu_err": "\u274c \u0423\u043a\u0430\u0436\u0438 \u0442\u0435\u043a\u0441\u0442 \u0438\u043b\u0438 \u043e\u0442\u0432\u0435\u0442\u044c \u043d\u0430 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435: <code>.kuwu \u043f\u0440\u0438\u0432\u0435\u0442</code>",
    }

    def _mood(self, power: int) -> str:
        if power <= 3:
            return "\u043b\u0451\u0433\u043a\u0430\u044f \u043e\u043c\u0435\u0436\u043a\u0430~ \u2661"
        if power <= 6:
            return "\u043d\u0430\u0441\u044b\u0449\u0435\u043d\u043d\u0430\u044f \u043e\u043c\u0435\u0436\u043a\u0430~ (\u02d8\u03c9\u02d8)"
        if power <= 8:
            return "\u043b\u0451\u0433\u043a\u0438\u0439 \u0444\u043b\u0438\u0440\u0442 \U0001F60f"
        if power == 9:
            return "\u0441\u0440\u0435\u0434\u043d\u044f\u044f \u043f\u043e\u0448\u043b\u043e\u0441\u0442\u044c (18+)"
        return "\u043c\u043e\u0449\u043d\u0430\u044f \u043f\u043e\u0448\u043b\u043e\u0441\u0442\u044c (18+) \U0001F525"

    async def on_load(self) -> None:
        if self.db.get(_DB, "enabled", None) is None:
            await self.db.set(_DB, "enabled", False)

    def _is_enabled(self) -> bool:
        return bool(self.db.get(_DB, "enabled", False))

    def _power(self) -> int:
        try:
            p = int(self.config["power"]) if self.config else 3
        except Exception:
            p = 3
        return max(1, min(_MAX_POWER, p))

    @command("komezhka", aliases=["omega", "kome"], required=OWNER)
    async def komezhka_cmd(self, event) -> None:
        "\u2014 \u0441\u0442\u0430\u0442\u0443\u0441 \u043c\u043e\u0434\u0443\u043b\u044f, \u0430 \u0442\u0430\u043a\u0436\u0435 .komezhka on/off \u0434\u043b\u044f \u0432\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f/\u0432\u044b\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u043e\u043c\u0435\u0436\u043a\u0438"
        args = self.get_args(event).strip().lower()
        if args in ("on", "\u0432\u043a\u043b", "1", "true"):
            await self.db.set(_DB, "enabled", True)
            await event.edit(self.strings("on"), parse_mode="html")
            return
        if args in ("off", "\u0432\u044b\u043a\u043b", "0", "false"):
            await self.db.set(_DB, "enabled", False)
            await event.edit(self.strings("off"), parse_mode="html")
            return
        key = "status_on" if self._is_enabled() else "status_off"
        p = self._power()
        await event.edit(self.strings(key).format(power=p, mood=self._mood(p)), parse_mode="html")

    @command("kon", required=OWNER)
    async def kon_cmd(self, event) -> None:
        "\u2014 \u0431\u044b\u0441\u0442\u0440\u043e \u0432\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u043e\u043c\u0435\u0436\u043a\u0443 (\u0430\u0432\u0442\u043e\u0440\u0435\u0434\u0430\u043a\u0442 \u0432\u0441\u0435\u0445 \u0442\u0432\u043e\u0438\u0445 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0439)"
        await self.db.set(_DB, "enabled", True)
        await event.edit(self.strings("on"), parse_mode="html")

    @command("koff", required=OWNER)
    async def koff_cmd(self, event) -> None:
        "\u2014 \u0431\u044b\u0441\u0442\u0440\u043e \u0432\u044b\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u043e\u043c\u0435\u0436\u043a\u0443"
        await self.db.set(_DB, "enabled", False)
        await event.edit(self.strings("off"), parse_mode="html")

    @command("kpower", required=OWNER)
    async def kpower_cmd(self, event) -> None:
        "\u2014 \u0441\u0438\u043b\u0430 \u044d\u0444\u0444\u0435\u043a\u0442\u0430 <1-10>: 1-6 \u043c\u0438\u043b\u043e, 7-8 \u0444\u043b\u0438\u0440\u0442, 9 \u0441\u0440\u0435\u0434\u043d\u044f\u044f, 10 \u043c\u043e\u0449\u043d\u0430\u044f \u043f\u043e\u0448\u043b\u043e\u0441\u0442\u044c (18+)"
        args = self.get_args(event).strip()
        try:
            value = int(args)
            if value < 1 or value > _MAX_POWER:
                raise ValueError
        except (ValueError, TypeError):
            await event.edit(self.strings("power_err"), parse_mode="html")
            return
        self.config["power"] = value
        await self.db.set(f"kitsune.config.{self.name.lower()}", "power", value)
        await event.edit(self.strings("power_set").format(power=value, mood=self._mood(value)), parse_mode="html")

    @command("kuwu", aliases=["komeone"], required=OWNER)
    async def kuwu_cmd(self, event) -> None:
        "\u2014 \u0440\u0430\u0437\u043e\u0432\u043e \u043f\u0435\u0440\u0435\u0434\u0435\u043b\u0430\u0442\u044c \u0442\u0435\u043a\u0441\u0442 \u0438\u043b\u0438 reply \u0432 \u043e\u043c\u0435\u0436\u043a\u0443 \u0431\u0435\u0437 \u0432\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u0430\u0432\u0442\u043e\u0440\u0435\u0436\u0438\u043c\u0430"
        args = self.get_args(event).strip()
        if not args:
            reply = await event.message.get_reply_message()
            if reply and (reply.raw_text or reply.text):
                args = reply.raw_text or reply.text
        if not args:
            await event.edit(self.strings("uwu_err"), parse_mode="html")
            return
        await event.edit(_process_text(args, self._power()))

    @watcher(out=True)
    async def omezhka_watcher(self, event) -> None:
        if not self._is_enabled():
            return
        message = event.message
        if message is None:
            return
        text = message.raw_text or message.text or ""
        if not text.strip():
            return
        dispatcher = getattr(self.client, "_kitsune_dispatcher", None)
        prefix = dispatcher._prefix if dispatcher else "."
        if text.startswith(prefix):
            return
        # \u041d\u0435 \u0442\u0440\u043e\u0433\u0430\u0435\u043c \u0444\u043e\u0440\u043c\u0430\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0439/\u0441\u043b\u0443\u0436\u0435\u0431\u043d\u044b\u0439 \u0432\u044b\u0432\u043e\u0434 \u0434\u0440\u0443\u0433\u0438\u0445 \u043c\u043e\u0434\u0443\u043b\u0435\u0439 (HTML-\u0442\u0435\u0433\u0438 / \u0441\u0441\u044b\u043b\u043a\u0438 / \u043a\u043e\u0434)
        if _SKIP_RE.search(text):
            return
        # \u0421\u043b\u0438\u0448\u043a\u043e\u043c \u0434\u043b\u0438\u043d\u043d\u044b\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u044f \u043d\u0435 \u0440\u0430\u0437\u0434\u0443\u0432\u0430\u0435\u043c \u0437\u0430 \u043b\u0438\u043c\u0438\u0442 Telegram (4096)
        if len(text) > 3500:
            return
        try:
            min_len = int(self.config["min_len"]) if self.config else 1
        except Exception:
            min_len = 1
        if len(text.strip()) < max(1, min_len):
            return
        new_text = _process_text(text, self._power())
        if new_text == text:
            return
        if len(new_text) > 4096:
            return
        try:
            await message.edit(new_text)
        except Exception:
            pass


