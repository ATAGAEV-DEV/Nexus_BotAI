import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import Nickname, SteamGame, SteamSubscription, async_session

DB_TIMEOUT = 10


def db_operation(operation_name: str) -> Callable:
    """Декоратор для устранения бойлерплейта БД-операций.

    Оборачивает функцию в async with session + try/except с таймаутом.
    Делает до 3-х попыток в случае таймаута.
    Декорируемая функция должна принимать session: AsyncSession первым аргументом.
    """

    def decorator(func_inner: Callable) -> Callable:
        @wraps(func_inner)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                async with async_session() as session:
                    try:
                        return await asyncio.wait_for(
                            func_inner(session, *args, **kwargs), timeout=DB_TIMEOUT
                        )
                    except TimeoutError:
                        if attempt == max_retries:
                            raise Exception(f"Таймаут при {operation_name}.")
                        await asyncio.sleep(1)
                    except Exception as e:
                        if isinstance(e, (ValueError, Exception)) and "Таймаут" in str(e):
                            if attempt == max_retries:
                                raise
                            await asyncio.sleep(1)
                            continue
                        raise Exception(f"Ошибка при {operation_name}: {e}")

        return wrapper

    return decorator


@db_operation("добавлении подписки на Steam")
async def add_steam_subscription(
    session: AsyncSession, server_id: int, channel_id: int
) -> SteamSubscription:
    """Добавляет или обновляет подписку на рассылку Steam раздач."""
    stmt = select(SteamSubscription).where(
        SteamSubscription.server_id == server_id, SteamSubscription.channel_id == channel_id
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.is_active = True  # type: ignore
    else:
        subscription = SteamSubscription(server_id=server_id, channel_id=channel_id)
        session.add(subscription)

    await session.commit()
    return subscription


@db_operation("проверке игры Steam")
async def is_game_new_and_save(session: AsyncSession, game_name: str) -> bool:
    """Если игры (по имени) нет в БД — сохраняет и возвращает True. Иначе False."""
    stmt = select(SteamGame.name).where(SteamGame.name == game_name)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return False
    session.add(SteamGame(name=game_name))
    await session.commit()
    return True


@db_operation("получении списка каналов для рассылки")
async def get_active_steam_subscriptions(session: AsyncSession) -> list[int]:
    """Возвращает список ID каналов, подписанных на раздачи."""
    stmt = select(SteamSubscription.channel_id).where(SteamSubscription.is_active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


@db_operation("добавлении ников")
async def add_nicknames(session: AsyncSession, nicknames: set[str]) -> list[str]:
    """Добавляет ники в БД, пропуская уже существующие. Возвращает список добавленных."""
    stmt = select(Nickname.nickname).where(Nickname.nickname.in_(nicknames))
    result = await session.execute(stmt)
    existing = set(result.scalars().all())

    new_nicknames = nicknames - existing
    for nick in new_nicknames:
        session.add(Nickname(nickname=nick))

    if new_nicknames:
        await session.commit()

    return sorted(new_nicknames)


@db_operation("поиске ников в БД")
async def find_nicknames(
    session: AsyncSession, nicknames: set[str]
) -> dict[str, tuple[str, str | None]]:
    """Ищет ники в БД (case-insensitive). Возвращает {nick_lower: (db_nickname, description)}."""
    lower_nicks = [n.lower() for n in nicknames]
    stmt = select(Nickname.nickname, Nickname.description).where(
        func.lower(Nickname.nickname).in_(lower_nicks)
    )
    result = await session.execute(stmt)
    return {row[0].lower(): (row[0], row[1]) for row in result.all()}


@db_operation("поиске ника в БД")
async def find_nickname(session: AsyncSession, nickname: str) -> tuple[str, str | None] | None:
    """Ищет один ник в БД (case-insensitive). Возвращает (nickname, description) или None."""
    stmt = select(Nickname.nickname, Nickname.description).where(
        func.lower(Nickname.nickname) == nickname.lower()
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    return (row[0], row[1]) if row else None


@db_operation("подсчёте ников")
async def count_nicknames(session: AsyncSession) -> int:
    """Возвращает общее количество ников в БД."""
    stmt = select(func.count()).select_from(Nickname)
    result = await session.execute(stmt)
    return result.scalar_one()


@db_operation("добавлении/обновлении ника с описанием")
async def upsert_nickname(session: AsyncSession, nickname: str, description: str) -> bool:
    """Добавляет ник с описанием или обновляет описание если ник уже есть.

    Возвращает True если ник был создан, False если обновлён.
    """
    stmt = select(Nickname).where(func.lower(Nickname.nickname) == nickname.lower())
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.description = description  # type: ignore
        await session.commit()
        return False

    session.add(Nickname(nickname=nickname, description=description))
    await session.commit()
    return True


@db_operation("удалении ника")
async def delete_nickname(session: AsyncSession, nickname: str) -> bool:
    """Удаляет ник из БД (case-insensitive). Возвращает True если ник был найден и удалён."""
    stmt = select(Nickname).where(func.lower(Nickname.nickname) == nickname.lower())
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if not existing:
        return False

    await session.delete(existing)
    await session.commit()
    return True
