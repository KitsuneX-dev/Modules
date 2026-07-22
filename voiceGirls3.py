from ..core.loader import KitsuneModule, command
from ..core.security import OWNER


class VoiceGirls3Module(KitsuneModule):
    name = "voiceGirls3"
    description = "Голосовые сообщения девушек by @modwini | Адаптация под Kitsune @Mikasu32"
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

    @command("пр", required=OWNER)
    async def pr_cmd(self, event):
        """| Привет"""
        await self._send_voice(event, "https://t.me/radiofmonline/335")

    @command("кд", required=OWNER)
    async def kd_cmd(self, event):
        """| Как дела?"""
        await self._send_voice(event, "https://t.me/radiofmonline/336")

    @command("прив", required=OWNER)
    async def priv_cmd(self, event):
        """| Приветик"""
        await self._send_voice(event, "https://t.me/radiofmonline/337")

    @command("норм", required=OWNER)
    async def norm_cmd(self, event):
        """| Все нормально"""
        await self._send_voice(event, "https://t.me/radiofmonline/338")

    @command("нуи", required=OWNER)
    async def nui_cmd(self, event):
        """| Ну и что"""
        await self._send_voice(event, "https://t.me/radiofmonline/339")

    @command("хорошо", required=OWNER)
    async def horosho_cmd(self, event):
        """| Хорошо"""
        await self._send_voice(event, "https://t.me/radiofmonline/340")

    @command("аня", required=OWNER)
    async def anya_cmd(self, event):
        """| Я Аня"""
        await self._send_voice(event, "https://t.me/radiofmonline/341")

    @command("мне19", required=OWNER)
    async def mne19_cmd(self, event):
        """| Мне 19 лет"""
        await self._send_voice(event, "https://t.me/radiofmonline/342")

    @command("хз", required=OWNER)
    async def hz_cmd(self, event):
        """| не знаю"""
        await self._send_voice(event, "https://t.me/radiofmonline/343")

    @command("непон", required=OWNER)
    async def nepon_cmd(self, event):
        """| Не поняла"""
        await self._send_voice(event, "https://t.me/radiofmonline/344")

    @command("го", required=OWNER)
    async def go_cmd(self, event):
        """| Ну давай"""
        await self._send_voice(event, "https://t.me/radiofmonline/345")

    @command("да", required=OWNER)
    async def da_cmd(self, event):
        """| Да"""
        await self._send_voice(event, "https://t.me/radiofmonline/346")

    @command("нуда", required=OWNER)
    async def nuda_cmd(self, event):
        """| Ну да"""
        await self._send_voice(event, "https://t.me/radiofmonline/347")

    @command("что", required=OWNER)
    async def chto_cmd(self, event):
        """| Что?"""
        await self._send_voice(event, "https://t.me/radiofmonline/348")

    @command("куда", required=OWNER)
    async def kuda_cmd(self, event):
        """| Куда?"""
        await self._send_voice(event, "https://t.me/radiofmonline/349")

    @command("спок", required=OWNER)
    async def spok_cmd(self, event):
        """| Спокойной ночи"""
        await self._send_voice(event, "https://t.me/radiofmonline/350")

    @command("кн", required=OWNER)
    async def kn_cmd(self, event):
        """| Как настроение?"""
        await self._send_voice(event, "https://t.me/radiofmonline/351")

    @command("добр", required=OWNER)
    async def dobr_cmd(self, event):
        """| Доброе утро"""
        await self._send_voice(event, "https://t.me/radiofmonline/352")

    @command("пока", required=OWNER)
    async def poka_cmd(self, event):
        """| Пока"""
        await self._send_voice(event, "https://t.me/radiofmonline/353")

    @command("прощай", required=OWNER)
    async def proschay_cmd(self, event):
        """| Прощай"""
        await self._send_voice(event, "https://t.me/radiofmonline/354")

    @command("сладких", required=OWNER)
    async def sladkih_cmd(self, event):
        """| Сладких снов"""
        await self._send_voice(event, "https://t.me/radiofmonline/355")

    @command("лан", required=OWNER)
    async def lan_cmd(self, event):
        """| Ну ладно"""
        await self._send_voice(event, "https://t.me/radiofmonline/356")

    @command("пж", required=OWNER)
    async def pzh_cmd(self, event):
        """| Ну пожалуйста"""
        await self._send_voice(event, "https://t.me/radiofmonline/357")

    @command("дядя", required=OWNER)
    async def dyadya_cmd(self, event):
        """| Дядя не надо"""
        await self._send_voice(event, "https://t.me/radiofmonline/358")

    @command("хм", required=OWNER)
    async def hm_cmd(self, event):
        """| хмммм"""
        await self._send_voice(event, "https://t.me/radiofmonline/359")
