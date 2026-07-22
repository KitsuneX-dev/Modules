from ..core.loader import KitsuneModule, command
from ..core.security import OWNER


class VoiceGirls2Module(KitsuneModule):
    name = "voiceGirls2"
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

    @command("нупупсик", required=OWNER)
    async def nupupsik_cmd(self, event):
        """| Ну пупсик"""
        await self._send_voice(event, "https://t.me/radiofmonline/239")

    @command("нуикактебе", required=OWNER)
    async def nuikaktebe_cmd(self, event):
        """| Ну и как тебе"""
        await self._send_voice(event, "https://t.me/radiofmonline/240")

    @command("тебе", required=OWNER)
    async def tebe_cmd(self, event):
        """| Ну тебе"""
        await self._send_voice(event, "https://t.me/radiofmonline/241")

    @command("ичто", required=OWNER)
    async def ichto_cmd(self, event):
        """| Ну и что"""
        await self._send_voice(event, "https://t.me/radiofmonline/242")

    @command("ч969", required=OWNER)
    async def ch969_cmd(self, event):
        """| 969"""
        await self._send_voice(event, "https://t.me/radiofmonline/243")

    @command("нискажу", required=OWNER)
    async def niskazhu_cmd(self, event):
        """| Ни скажу"""
        await self._send_voice(event, "https://t.me/radiofmonline/244")

    @command("норм", required=OWNER)
    async def norm_cmd(self, event):
        """| Нормально дела"""
        await self._send_voice(event, "https://t.me/radiofmonline/245")

    @command("хз", required=OWNER)
    async def hz_cmd(self, event):
        """| Не знаю"""
        await self._send_voice(event, "https://t.me/radiofmonline/246")

    @command("куда", required=OWNER)
    async def kuda_cmd(self, event):
        """| Куда?"""
        await self._send_voice(event, "https://t.me/radiofmonline/247")

    @command("кто", required=OWNER)
    async def kto_cmd(self, event):
        """| Кто?"""
        await self._send_voice(event, "https://t.me/radiofmonline/248")

    @command("чотам", required=OWNER)
    async def chotam_cmd(self, event):
        """| Ну чо там"""
        await self._send_voice(event, "https://t.me/radiofmonline/249")

    @command("дада", required=OWNER)
    async def dada_cmd(self, event):
        """| Ну да да"""
        await self._send_voice(event, "https://t.me/radiofmonline/250")

    @command("молодец", required=OWNER)
    async def molodets_cmd(self, event):
        """| Какой молодец"""
        await self._send_voice(event, "https://t.me/radiofmonline/251")

    @command("машина", required=OWNER)
    async def mashina_cmd(self, event):
        """| А какая у тебя машина"""
        await self._send_voice(event, "https://t.me/radiofmonline/252")

    @command("ятебяхочу", required=OWNER)
    async def yatebyahochu_cmd(self, event):
        """| Я тебя хочу"""
        await self._send_voice(event, "https://t.me/radiofmonline/253")

    @command("наебала", required=OWNER)
    async def naebala_cmd(self, event):
        """| Я тебя обвела вокруг носа"""
        await self._send_voice(event, "https://t.me/radiofmonline/254")

    @command("тебепизда", required=OWNER)
    async def tebepizda_cmd(self, event):
        """| Я рассулу скажу он тебе жопу порвет"""
        await self._send_voice(event, "https://t.me/radiofmonline/255")

    @command("какая", required=OWNER)
    async def kakaya_cmd(self, event):
        """| Какая?"""
        await self._send_voice(event, "https://t.me/radiofmonline/256")

    @command("какдела", required=OWNER)
    async def kakdela_cmd(self, event):
        """| Как дела?"""
        await self._send_voice(event, "https://t.me/radiofmonline/257")

    @command("какое", required=OWNER)
    async def kakoe_cmd(self, event):
        """| Какое ?"""
        await self._send_voice(event, "https://t.me/radiofmonline/258")

    @command("янипон", required=OWNER)
    async def yanipon_cmd(self, event):
        """| Я не понимаю тебя"""
        await self._send_voice(event, "https://t.me/radiofmonline/259")

    @command("адрес", required=OWNER)
    async def adres_cmd(self, event):
        """| Квартира 70, 4 этаж"""
        await self._send_voice(event, "https://t.me/radiofmonline/260")

    @command("серьёзно", required=OWNER)
    async def seryozno_cmd(self, event):
        """| Я не шучу, Я серьёзно говорю"""
        await self._send_voice(event, "https://t.me/radiofmonline/261")

    @command("согл", required=OWNER)
    async def sogl_cmd(self, event):
        """| Я согласна"""
        await self._send_voice(event, "https://t.me/radiofmonline/262")

    @command("ядома", required=OWNER)
    async def yadoma_cmd(self, event):
        """| Я дома"""
        await self._send_voice(event, "https://t.me/radiofmonline/263")

    @command("ясн", required=OWNER)
    async def yasn_cmd(self, event):
        """| Ясно"""
        await self._send_voice(event, "https://t.me/radiofmonline/264")

    @command("япон", required=OWNER)
    async def yapon_cmd(self, event):
        """| Я поняла"""
        await self._send_voice(event, "https://t.me/radiofmonline/265")

    @command("котенок", required=OWNER)
    async def kotenok_cmd(self, event):
        """| Котенок"""
        await self._send_voice(event, "https://t.me/radiofmonline/266")

    @command("привет", required=OWNER)
    async def privet_cmd(self, event):
        """| Привет"""
        await self._send_voice(event, "https://t.me/radiofmonline/267")

    @command("зачем", required=OWNER)
    async def zachem_cmd(self, event):
        """| Зачем"""
        await self._send_voice(event, "https://t.me/radiofmonline/268")

    @command("ачо", required=OWNER)
    async def acho_cmd(self, event):
        """| А чо"""
        await self._send_voice(event, "https://t.me/radiofmonline/269")

    @command("пруфы", required=OWNER)
    async def prufy_cmd(self, event):
        """| А чем ты докажешь?"""
        await self._send_voice(event, "https://t.me/radiofmonline/270")

    @command("ачто", required=OWNER)
    async def achto_cmd(self, event):
        """| А что?"""
        await self._send_voice(event, "https://t.me/radiofmonline/271")

    @command("марина", required=OWNER)
    async def marina_cmd(self, event):
        """| А меня зовут Марина"""
        await self._send_voice(event, "https://t.me/radiofmonline/272")

    @command("гдеживешь", required=OWNER)
    async def gdezhivesh_cmd(self, event):
        """| А где ты живёшь?"""
        await self._send_voice(event, "https://t.me/radiofmonline/273")

    @command("гдеэто", required=OWNER)
    async def gdeeto_cmd(self, event):
        """| А где это?"""
        await self._send_voice(event, "https://t.me/radiofmonline/274")

    @command("болт", required=OWNER)
    async def bolt_cmd(self, event):
        """| Ну болт"""
        await self._send_voice(event, "https://t.me/radiofmonline/275")

    @command("нусегодня", required=OWNER)
    async def nusegodnya_cmd(self, event):
        """| Ну сегодня я встала почистила зубки"""
        await self._send_voice(event, "https://t.me/radiofmonline/276")

    @command("какзовут", required=OWNER)
    async def kakzovut_cmd(self, event):
        """| Как вас зовут"""
        await self._send_voice(event, "https://t.me/radiofmonline/277")

    @command("ябпосмотрела", required=OWNER)
    async def yabposmotrela_cmd(self, event):
        """| Я бы посмотрела на это"""
        await self._send_voice(event, "https://t.me/radiofmonline/278")

    @command("тычего", required=OWNER)
    async def tychego_cmd(self, event):
        """| Зай ну ты чего?"""
        await self._send_voice(event, "https://t.me/radiofmonline/279")
