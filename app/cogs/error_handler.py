import discord
from discord.ext import commands

from app.core.bot import DisBot


class ErrorHandler(commands.Cog):
    """Обработчик ошибок команд."""

    def __init__(self, bot: DisBot) -> None:
        """Инициализация Cog."""
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Обработка ошибок команд."""
        original_error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            pass
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ У вас недостаточно прав для выполнения этой команды.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"❌ Неправильное использование команды. "
                f"Используйте: `{self.bot.command_prefix}{ctx.command.name} "
                f"{ctx.command.signature}`"
            )
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ Эта команда недоступна в личных сообщениях.")
        elif isinstance(original_error, (ConnectionError, TimeoutError)):
            await ctx.send("❌ Проблема с сетью. Попробуйте позже.")
        else:
            await ctx.send("❌ Произошла ошибка при выполнении команды.")
            print(f"Command error: {error}")


async def setup(bot: DisBot) -> None:
    """Загрузка Cog в бота."""
    await bot.add_cog(ErrorHandler(bot))
