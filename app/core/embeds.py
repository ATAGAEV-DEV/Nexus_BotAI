import discord


class Embeds:
    """Фабрика для создания стандартных Discord Embed-ов."""

    @staticmethod
    def success(title: str, description: str) -> discord.Embed:
        """Создает Embed для успешного выполнения операции."""
        return discord.Embed(
            title=f"✅ {title}", description=description, color=discord.Color.green()
        )

    @staticmethod
    def error(title: str, description: str) -> discord.Embed:
        """Создает Embed для сообщения об ошибке."""
        return discord.Embed(title=f"❌ {title}", description=description, color=discord.Color.red())

    @staticmethod
    def info(title: str, description: str) -> discord.Embed:
        """Создает информационный Embed."""
        return discord.Embed(title=f"ℹ️ {title}", description=description, color=discord.Color.blue())
