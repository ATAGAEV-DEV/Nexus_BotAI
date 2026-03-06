from discord.ext import commands

from app.core.embeds import Embeds
from app.data.request import (
    add_nicknames,
    count_nicknames,
    delete_nickname,
    find_nickname,
    upsert_nickname,
)


class Nicknames(commands.Cog):
    """Управление игровыми никами."""

    def __init__(self, bot: commands.Bot) -> None:
        """Инициализация кога."""
        self.bot = bot

    @commands.command(name="nick")
    @commands.guild_only()
    async def add_nick(self, ctx: commands.Context, *nicks: str) -> None:
        """Добавляет один или несколько игровых ников (через пробел)."""
        if not nicks:
            embed = Embeds.error(
                "Ошибка", "Укажите хотя бы один ник.\nПример: `?nick Nick1 Nick2 Nick3`"
            )
            await ctx.send(embed=embed)
            return

        async with ctx.typing():
            try:
                added = await add_nicknames(nicknames=set(nicks))
                if added:
                    nick_list = "\n".join(f"• {n}" for n in added)
                    embed = Embeds.success(
                        "Ники добавлены",
                        f"Добавлено: {len(added)} из {len(nicks)}\n{nick_list}",
                    )
                else:
                    embed = Embeds.info("Ники", "Все указанные ники уже есть в базе.")
                await ctx.send(embed=embed)
            except Exception as e:
                embed = Embeds.error("Ошибка", f"Произошла ошибка: {e}")
                await ctx.send(embed=embed)

    @commands.command(name="lol")
    @commands.guild_only()
    async def check_nick(self, ctx: commands.Context, nick: str | None = None) -> None:
        """Проверяет наличие ника в базе данных."""
        if not nick:
            embed = Embeds.error("Ошибка", "Укажите ник.\nПример: `?lol Nick1`")
            await ctx.send(embed=embed)
            return

        async with ctx.typing():
            try:
                result = await find_nickname(nickname=nick)
                if result:
                    db_nick, description = result
                    if description:
                        embed = Embeds.success("Найден", f"**{db_nick}** — {description}")
                    else:
                        embed = Embeds.success("Найден", f"**{db_nick}**")
                else:
                    embed = Embeds.info("Не найден", f"Ник **{nick}** отсутствует в базе.")
                await ctx.send(embed=embed)
            except Exception as e:
                embed = Embeds.error("Ошибка", f"Произошла ошибка: {e}")
                await ctx.send(embed=embed)

    @commands.command(name="nicklist")
    @commands.guild_only()
    async def nick_list(self, ctx: commands.Context) -> None:
        """Показывает количество ников в базе данных."""
        async with ctx.typing():
            try:
                total = await count_nicknames()
                embed = Embeds.info("База ников", f"Всего ников в базе: **{total}**")
                await ctx.send(embed=embed)
            except Exception as e:
                embed = Embeds.error("Ошибка", f"Произошла ошибка: {e}")
                await ctx.send(embed=embed)

    @commands.command(name="nickdesc")
    @commands.guild_only()
    async def nick_desc(
        self, ctx: commands.Context, nick: str | None = None, *, description: str | None = None
    ) -> None:
        """Добавляет ник с описанием или обновляет описание существующего."""
        if not nick or not description:
            embed = Embeds.error(
                "Ошибка", "Укажите ник и описание.\nПример: `?nickdesc Nick1 читер`"
            )
            await ctx.send(embed=embed)
            return

        async with ctx.typing():
            try:
                is_new = await upsert_nickname(nickname=nick, description=description)
                if is_new:
                    embed = Embeds.success(
                        "Ник добавлен", f"**{nick}** — {description}"
                    )
                else:
                    embed = Embeds.success(
                        "Описание обновлено", f"**{nick}** — {description}"
                    )
                await ctx.send(embed=embed)
            except Exception as e:
                embed = Embeds.error("Ошибка", f"Произошла ошибка: {e}")
                await ctx.send(embed=embed)

    @commands.command(name="nickdel")
    @commands.guild_only()
    async def nick_del(self, ctx: commands.Context, nick: str | None = None) -> None:
        """Удаляет ник из базы данных."""
        if not nick:
            embed = Embeds.error("Ошибка", "Укажите ник.\nПример: `?nickdel Nick1`")
            await ctx.send(embed=embed)
            return

        async with ctx.typing():
            try:
                deleted = await delete_nickname(nickname=nick)
                if deleted:
                    embed = Embeds.success("Удалён", f"Ник **{nick}** удалён из базы.")
                else:
                    embed = Embeds.info("Не найден", f"Ник **{nick}** не найден в базе.")
                await ctx.send(embed=embed)
            except Exception as e:
                embed = Embeds.error("Ошибка", f"Произошла ошибка: {e}")
                await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Загрузка кога в бота."""
    await bot.add_cog(Nicknames(bot))
