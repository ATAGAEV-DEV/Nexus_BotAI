import os
import tempfile

import discord
from discord.ext import commands

from app.core.config import settings
from app.data.request import add_nicknames, find_nicknames
from app.services.image_to_text import ai_generate, generate_prompt


class Screenshots(commands.Cog):
    """Обработка скриншотов из игры."""

    def __init__(self, bot: commands.Bot) -> None:
        """Инициализация кога."""
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Обработка сообщений с картинками из указанного канала."""
        if message.author.bot:
            return

        if message.channel.id != settings.SCREENSHOT_CHANNEL_ID:
            return

        if message.content and message.content.strip() != "?":
            return

        is_add_mode = message.content.strip() == "?"

        image_attachments = [
            att
            for att in message.attachments
            if att.content_type and att.content_type.startswith("image/")
        ]

        if not image_attachments:
            return

        async with message.channel.typing():
            for attachment in image_attachments:
                image_bytes = await attachment.read()

                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp.write(image_bytes)
                    tmp_path = tmp.name

                try:
                    prompt_message = generate_prompt(tmp_path)
                    result = await ai_generate(prompt_message)
                finally:
                    os.unlink(tmp_path)

                if not result:
                    await message.reply(
                        "⏰ Не удалось распознать ники на скриншоте."
                    )
                    continue

                nicknames = {line.strip() for line in result.strip().splitlines() if line.strip()}

                if not nicknames:
                    continue

                if is_add_mode:
                    added = await add_nicknames(nicknames=nicknames)
                    already_existed = sorted(nicknames - set(added))

                    parts = []
                    if added:
                        parts.append("Добавлены в БД:\n" + " ".join(added))
                    if already_existed:
                        parts.append("Уже были в БД:\n" + " ".join(already_existed))
                    await message.reply("\n\n".join(parts))
                else:
                    found_in_db = await find_nicknames(nicknames=nicknames)

                    known = []
                    unknown = []
                    for nick in sorted(nicknames):
                        db_entry = found_in_db.get(nick.lower())
                        if db_entry:
                            db_nick, description = db_entry
                            if description:
                                known.append(f"**{db_nick}** — {description}")
                            else:
                                known.append(f"**{db_nick}**")
                        else:
                            unknown.append(nick)

                    parts = []
                    if known:
                        parts.append("Игроки которые есть в списке:\n" + "\n".join(known))
                    if unknown:
                        parts.append("Остальные ники:\n" + " ".join(unknown))

                    await message.channel.send("\n\n".join(parts))


async def setup(bot: commands.Bot) -> None:
    """Загрузка кога в бота."""
    await bot.add_cog(Screenshots(bot))
