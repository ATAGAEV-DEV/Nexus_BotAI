import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.data.request as request_module

MODELS_PATH = Path(__file__).resolve().parents[2] / "app" / "data" / "models.py"
pytestmark = pytest.mark.integration


def load_models(database_url: str, schema: str):
    """Загружает модели с изолированной схемой тестовой базы."""
    spec = spec_from_file_location("integration_models", MODELS_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    os.environ["DATABASE_URL"] = database_url
    os.environ["DATABASE_SCHEMA"] = schema
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_database_operations_round_trip(integration_schema: tuple[str, str]) -> None:
    """Все операции реально создают, читают, обновляют и удаляют записи."""
    database_url, schema = integration_schema
    models = load_models(database_url, schema)
    request_module.async_session = models.async_session
    await models.init_models()
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            tables = await connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = :schema"),
                {"schema": schema},
            )
        assert set(tables.scalars()) == {"steam_subscriptions", "steam_games", "nicknames"}

        created = await request_module.add_steam_subscription(server_id=1, channel_id=10)
        updated = await request_module.add_steam_subscription(server_id=1, channel_id=10)
        await request_module.add_steam_subscription(server_id=1, channel_id=11)
        async with models.async_session() as session:
            updated.is_active = False
            await session.merge(updated)
            await session.commit()
        assert created.channel_id == 10
        assert await request_module.get_active_steam_subscriptions() == [11]

        assert await request_module.is_game_new_and_save("Игра") is True
        assert await request_module.is_game_new_and_save("Игра") is False
        assert await request_module.add_nicknames({"Альфа", "Бета"}) == ["Альфа", "Бета"]
        assert await request_module.add_nicknames({"альфа", "Гамма"}) == ["Гамма", "альфа"]
        assert await request_module.find_nicknames({"АЛЬФА", "Нет"}) == {"альфа": ("альфа", None)}
        assert await request_module.find_nickname("бета") == ("Бета", None)
        assert await request_module.find_nickname("нет") is None
        assert await request_module.count_nicknames() == 4
        assert await request_module.upsert_nickname("Бета", "описание") is False
        assert await request_module.upsert_nickname("Дельта", "новый") is True
        assert await request_module.find_nickname("БЕТА") == ("Бета", "описание")
        assert await request_module.delete_nickname("дельта") is True
        assert await request_module.delete_nickname("дельта") is False
        assert await request_module.count_nicknames() == 4
    finally:
        await models.engine.dispose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_database_operation_reports_timeout_and_errors(
    integration_schema: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Декоратор повторяет таймаут и оборачивает обычную ошибку базы."""
    database_url, schema = integration_schema
    models = load_models(database_url, schema)
    request_module.async_session = models.async_session
    monkeypatch.setattr(request_module.asyncio, "sleep", request_module.asyncio.sleep)
    calls = 0

    @request_module.db_operation("проверке таймаута")
    async def timed_out(session) -> None:
        nonlocal calls
        calls += 1
        raise TimeoutError

    with pytest.raises(Exception, match="Таймаут при проверке таймаута"):
        await timed_out()
    assert calls == 3

    @request_module.db_operation("проверке ошибки")
    async def failed(session) -> None:
        raise RuntimeError("connection")

    with pytest.raises(Exception, match="Ошибка при проверке ошибки: connection"):
        await failed()
    await models.engine.dispose()
