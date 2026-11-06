import discord
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.embeds import Embeds
from app.data.request import get_active_steam_subscriptions, is_game_new_and_save
from app.services.steam import get_free_steam_games


async def check_steam_games(bot: discord.Client) -> None:
    """Проверяет новые бесплатные раздачи Steam и рассылает их по подпискам."""
    games = await get_free_steam_games()
    if not games:
        return

    new_games = []
    for game in games:
        if await is_game_new_and_save(game_name=game):  # type: ignore
            new_games.append(game)
    if not new_games:
        return

    subs = await get_active_steam_subscriptions()  # type: ignore
    if not subs:
        return

    description = "\n".join(f"• {game}" for game in new_games)
    embed = Embeds.info("Бесплатные раздачи Steam", description)

    for channel_id in subs:
        channel = bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Ошибка при отправке в канал {channel_id}: {e}")


def start_scheduler(bot: discord.Client) -> None:
    """Инициализирует и запускает асинхронный планировщик задач."""
    scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Moscow"))
    scheduler.add_job(check_steam_games, "cron", hour=12, minute=0, args=[bot])
    scheduler.start()
