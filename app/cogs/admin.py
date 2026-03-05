from discord.ext import commands

from app.core.checks import admin_or_owner
from app.core.embeds import Embeds


class Admin(commands.Cog):
    """Административные команды."""

    def __init__(self, bot: commands.Bot) -> None:
        """Инициализация Cog."""
        self.bot = bot

    @commands.command(name="steam")
    @commands.guild_only()
    @admin_or_owner()
    async def steam(self, ctx: commands.Context) -> None:
        """Показывает текущие бесплатные раздачи в Steam."""
        from app.services.steam import get_free_steam_games

        games = await get_free_steam_games()
        if not games:
            embed = Embeds.info("Steam Раздачи", "Раздач на сегодня от Steam нету.")
        else:
            description = "\n".join(f"• {game}" for game in games)
            embed = Embeds.info("Бесплатные раздачи Steam", description)

        await ctx.send(embed=embed)

    @commands.command(name="set_steam")
    @commands.guild_only()
    @admin_or_owner()
    async def set_steam_channel(self, ctx: commands.Context) -> None:
        """Устанавливает текущий канал для уведомлений о раздачах Steam."""
        from app.data.request import add_steam_subscription

        if not ctx.guild:
            embed = Embeds.error("Ошибка", "Эта команда доступна только на серверах.")
            await ctx.send(embed=embed)
            return

        server_id = ctx.guild.id
        channel_id = ctx.channel.id

        try:
            await add_steam_subscription(server_id=server_id, channel_id=channel_id)  # type: ignore
            embed = Embeds.success(
                "Успех", "Этот канал успешно установлен для получения бесплатных раздач Steam!"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = Embeds.error("Ошибка", f"Произошла ошибка при сохранении: {e}")
            await ctx.send(embed=embed)

    @commands.command(name="nick")
    @commands.guild_only()
    @admin_or_owner()
    async def add_nick(self, ctx: commands.Context, *nicks: str) -> None:
        """Добавляет один или несколько игровых ников (через пробел)."""
        if not nicks:
            embed = Embeds.error(
                "Ошибка", "Укажите хотя бы один ник.\nПример: `?addnick Nick1 Nick2 Nick3`"
            )
            await ctx.send(embed=embed)
            return

        from app.data.request import add_nicknames

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
    @admin_or_owner()
    async def check_nick(self, ctx: commands.Context, nick: str | None = None) -> None:
        """Проверяет наличие ника в базе данных."""
        if not nick:
            embed = Embeds.error("Ошибка", "Укажите ник.\nПример: `?checknick Nick1`")
            await ctx.send(embed=embed)
            return

        from app.data.request import find_nickname

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


async def setup(bot: commands.Bot) -> None:
    """Загрузка Cog в бота."""
    await bot.add_cog(Admin(bot))
