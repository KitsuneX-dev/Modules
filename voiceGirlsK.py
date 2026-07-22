from ..core.loader import KitsuneModule, command
from ..core.security import OWNER


class VoiceGirlsKModule(KitsuneModule):
    name = "voiceGirlsK"
    description = "K Голосовые сообщения девушек by @modwini | Адаптация под Kitsune @Mikasu32"
    author = "@modwini | Адаптация под Kitsune @Mikasu32"
    version = "1.0.0"
    icon = "🎤"
    category = "fun"

    async def _send_voice(self, event, url):
        message = event.message
        reply = await message.get_reply_message()
        await message.delete()
        await self.client.send_file(
            message.peer_id,
            url,
            voice_note=True,
            reply_to=reply.id if reply else None,
        )

    @command("приветик", required=OWNER)
    async def privetik_cmd(self, event):
        """| Приветик"""
        await self._send_voice(event, "https://t.me/radiofmonline/195")

    @command("кд", required=OWNER)
    async def kd_cmd(self, event):
        """| Как дела?"""
        await self._send_voice(event, "https://t.me/radiofmonline/198")

    @command("да", required=OWNER)
    async def da_cmd(self, event):
        """| Да"""
        await self._send_voice(event, "https://t.me/radiofmonline/197")

    @command("нет", required=OWNER)
    async def net_cmd(self, event):
        """| Нет"""
        await self._send_voice(event, "https://t.me/radiofmonline/196")

    @command("жаль", required=OWNER)
    async def zhal_cmd(self, event):
        """| очень жаль"""
        await self._send_voice(event, "https://t.me/radiofmonline/199")

    @command("недоверяю", required=OWNER)
    async def nedoveryayu_cmd(self, event):
        """| я тебе не доверяю"""
        await self._send_voice(event, "https://t.me/radiofmonline/200")

    @command("подожди", required=OWNER)
    async def podozhdi_cmd(self, event):
        """| подожди"""
        await self._send_voice(event, "https://t.me/radiofmonline/201")

    @command("спок", required=OWNER)
    async def spok_cmd(self, event):
        """| спокойной ночи"""
        await self._send_voice(event, "https://t.me/radiofmonline/202")

    @command("ясно", required=OWNER)
    async def yasno_cmd(self, event):
        """| ясно"""
        await self._send_voice(event, "https://t.me/radiofmonline/203")

    @command("обид", required=OWNER)
    async def obid_cmd(self, event):
        """| я обиделась"""
        await self._send_voice(event, "https://t.me/radiofmonline/204")

    @command("тмн", required=OWNER)
    async def tmn_cmd(self, event):
        """| ты мне нравишся"""
        await self._send_voice(event, "https://t.me/radiofmonline/205")

    @command("мур", required=OWNER)
    async def mur_cmd(self, event):
        """| мур"""
        await self._send_voice(event, "https://t.me/radiofmonline/206")

    @command("пж", required=OWNER)
    async def pzh_cmd(self, event):
        """| ну пожалуйста"""
        await self._send_voice(event, "https://t.me/radiofmonline/207")

    @command("спс", required=OWNER)
    async def sps_cmd(self, event):
        """| спасибо"""
        await self._send_voice(event, "https://t.me/radiofmonline/208")

    @command("тыгде", required=OWNER)
    async def tygde_cmd(self, event):
        """| Ну ты где?"""
        await self._send_voice(event, "https://t.me/radiofmonline/209")

    @command("дог", required=OWNER)
    async def dog_cmd(self, event):
        """| Договорились"""
        await self._send_voice(event, "https://t.me/radiofmonline/210")

    @command("дутро", required=OWNER)
    async def dutro_cmd(self, event):
        """| Доброе утро"""
        await self._send_voice(event, "https://t.me/radiofmonline/211")

    @command("кснемогу", required=OWNER)
    async def ksnemogu_cmd(self, event):
        """| К сожалению не могу"""
        await self._send_voice(event, "https://t.me/radiofmonline/212")

    @command("нипон", required=OWNER)
    async def nipon_cmd(self, event):
        """| Нипоняла"""
        await self._send_voice(event, "https://t.me/radiofmonline/213")

    @command("интересно", required=OWNER)
    async def interesno_cmd(self, event):
        """| Расскажи мне интересно"""
        await self._send_voice(event, "https://t.me/radiofmonline/214")

    @command("чмоки", required=OWNER)
    async def chmoki_cmd(self, event):
        """| Чмоки чмоки"""
        await self._send_voice(event, "https://t.me/radiofmonline/215")

    @command("спок2", required=OWNER)
    async def spok2_cmd(self, event):
        """| Спокойной ночи тебе"""
        await self._send_voice(event, "https://t.me/radiofmonline/216")

    @command("тыменялюбишь", required=OWNER)
    async def tymenyalyubish_cmd(self, event):
        """| А ты меня любишь?"""
        await self._send_voice(event, "https://t.me/radiofmonline/217")

    @command("нукотик", required=OWNER)
    async def nukotik_cmd(self, event):
        """| Ну котик"""
        await self._send_voice(event, "https://t.me/radiofmonline/218")

    @command("котик", required=OWNER)
    async def kotik_cmd(self, event):
        """| Котик"""
        await self._send_voice(event, "https://t.me/radiofmonline/219")

    @command("блин", required=OWNER)
    async def blin_cmd(self, event):
        """| Ну блин"""
        await self._send_voice(event, "https://t.me/radiofmonline/220")

    @command("скоробуду", required=OWNER)
    async def skorobudu_cmd(self, event):
        """| Скоро буду"""
        await self._send_voice(event, "https://t.me/radiofmonline/221")
