import os
from collections.abc import Callable

from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

ALLOWED_USERS = {
    username.strip() for username in os.getenv("ALLOWED_USERS", "").split(",") if username.strip()
}


def admin_or_owner() -> Callable:
    """Проверка: администратор или разрешённый пользователь."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.name in ALLOWED_USERS:
            return True
        if ctx.author.guild_permissions.administrator:
            return True
        raise commands.MissingPermissions(["administrator"])

    return commands.check(predicate)
