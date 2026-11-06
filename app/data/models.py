import os

from dotenv import load_dotenv
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL не задан в переменных окружения. "
        "Установите переменную для подключения к PostgreSQL."
    )

DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA") or "public"

engine = create_async_engine(
    DATABASE_URL,
    connect_args={"server_settings": {"search_path": DATABASE_SCHEMA}},
    pool_pre_ping=True,
    pool_recycle=1800,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс для всех моделей, поддерживающий асинхронные атрибуты."""

    pass


class SteamSubscription(Base):
    """Модель подписки на раздачи Steam."""

    __tablename__ = "steam_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)


class SteamGame(Base):
    """Модель разосланных игр Steam."""

    __tablename__ = "steam_games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, default=func.now())


class Nickname(Base):
    """Модель игрового ника."""

    __tablename__ = "nicknames"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nickname = Column(String(50), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


async def init_models() -> None:
    """Создает таблицы в базе данных, если они не существуют."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
