import discord
from discord.ext import commands

from app.data.models import init_models
from app.services.scheduler import start_scheduler


class DisBot(commands.Bot):
    """Основной класс бота Nexus Bot AI."""

    def __init__(
        self,
        command_prefix: str,
        intents: discord.Intents,
        help_command: commands.HelpCommand | None = None,
    ):
        """Инициализация бота."""
        super().__init__(command_prefix=command_prefix, intents=intents, help_command=help_command)

    async def setup_hook(self) -> None:
        """Загрузка расширений (Cogs) при старте бота."""
        await self.load_extension("app.cogs.admin")
        await self.load_extension("app.cogs.general")
        await self.load_extension("app.cogs.nicknames")
        await self.load_extension("app.cogs.error_handler")
        await self.load_extension("app.cogs.screenshots")

    async def on_ready(self) -> None:
        """Инициализация при подключении бота к Discord."""
        await init_models()
        start_scheduler(self)
