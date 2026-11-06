import os
import sys
from collections.abc import Callable, Iterator
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/nexus_test"
MODELS_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "models.py"


@pytest.fixture
def load_models(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[], ModuleType]]:
    """Загружает модели с тестовым окружением без чтения .env и подключения к БД."""
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)

    def load() -> ModuleType:
        spec = spec_from_file_location("app.data.models", MODELS_PATH)
        assert spec is not None and spec.loader is not None
        module = module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        return module

    with patch.dict(os.environ, {"DATABASE_URL": TEST_DATABASE_URL}, clear=True):
        yield load


@pytest.mark.asyncio
async def test_database_uses_one_engine_and_standard_session(
    load_models: Callable[[], ModuleType],
) -> None:
    """DATABASE_URL достаточно для одной обычной сессии с корректным закрытием."""
    with patch(
        "sqlalchemy.ext.asyncio.create_async_engine", wraps=create_async_engine
    ) as create_engine:
        models = load_models()

    create_engine.assert_called_once()
    assert models.engine.url == make_url(TEST_DATABASE_URL)
    assert isinstance(models.async_session, async_sessionmaker)
    assert models.async_session.kw["expire_on_commit"] is False

    async with models.async_session() as session:
        assert isinstance(session, AsyncSession)
        assert session.bind is models.engine
        nickname = models.Nickname(nickname="test_player")
        session.add(nickname)
        assert nickname in session

    assert nickname not in session
    await models.engine.dispose()


@pytest.mark.parametrize("schema", [None, "", "nexus_custom"])
def test_database_schema_sets_connection_search_path(
    load_models: Callable[[], ModuleType], monkeypatch: pytest.MonkeyPatch, schema: str | None
) -> None:
    """Схема берётся из окружения; отсутствующее или пустое значение даёт public."""
    if schema is not None:
        monkeypatch.setenv("DATABASE_SCHEMA", schema)

    with patch(
        "sqlalchemy.ext.asyncio.create_async_engine", wraps=create_async_engine
    ) as create_engine:
        models = load_models()

    expected_schema = schema or "public"
    assert create_engine.call_args.kwargs["connect_args"] == {
        "server_settings": {"search_path": expected_schema}
    }
    assert models.DATABASE_SCHEMA == expected_schema


@pytest.mark.parametrize("database_url", [None, ""])
def test_database_url_is_required(
    load_models: Callable[[], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    database_url: str | None,
) -> None:
    """Отсутствующий или пустой URL вызывает понятную ошибку до подключения."""
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL")
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        load_models()


@pytest.mark.asyncio
async def test_init_models_creates_tables_with_single_engine(
    load_models: Callable[[], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Инициализация создаёт таблицы только в одном подключении."""
    models = load_models()
    connection = AsyncMock()
    engine = MagicMock()
    engine.begin.return_value.__aenter__.return_value = connection
    monkeypatch.setattr(models, "engine", engine)

    await models.init_models()

    engine.begin.assert_called_once_with()
    connection.run_sync.assert_awaited_once_with(models.Base.metadata.create_all)


@pytest.mark.asyncio
async def test_add_nicknames_uses_standard_session(
    load_models: Callable[[], ModuleType],
) -> None:
    """DB-декоратор передаёт обычную сессию и сохраняет только новые ники."""
    models = load_models()
    spec = spec_from_file_location("app.data.request", MODELS_PATH.with_name("request.py"))
    assert spec is not None and spec.loader is not None
    requests = module_from_spec(spec)
    spec.loader.exec_module(requests)

    result = MagicMock()
    result.scalars.return_value.all.return_value = ["existing_player"]
    saved_nicknames = []

    async def capture_commit(session: AsyncSession) -> None:
        assert session.bind is models.engine
        saved_nicknames.extend(nickname.nickname for nickname in session.new)

    with (
        patch.object(AsyncSession, "execute", autospec=True, return_value=result) as execute,
        patch.object(AsyncSession, "commit", autospec=True, side_effect=capture_commit) as commit,
    ):
        added = await requests.add_nicknames({"existing_player", "new_player"})

    assert added == ["new_player"]
    assert saved_nicknames == ["new_player"]
    execute.assert_awaited_once()
    commit.assert_awaited_once_with(execute.call_args.args[0])
