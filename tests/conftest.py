import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ENV_TEST_PATH = Path(__file__).resolve().parents[1] / ".env.test"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Добавляет явный переключатель для тестов с базой данных."""
    parser.addoption("--run-integration", action="store_true", help="run database integration tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Пропускает интеграционные тесты без явного флага запуска."""
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="нужен флаг --run-integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


def load_test_database_url() -> str:
    """Читает URL только из .env.test, не используя рабочее окружение."""
    values = dotenv_values(ENV_TEST_PATH, interpolate=False)
    database_url = values.get("TEST_DATABASE_URL")
    if not database_url or not database_url.strip():
        raise pytest.UsageError("В .env.test отсутствует непустой TEST_DATABASE_URL")
    return database_url


@pytest_asyncio.fixture
async def integration_schema() -> AsyncIterator[tuple[str, str]]:
    """Создаёт и удаляет отдельную схему для одного интеграционного теста."""
    database_url = load_test_database_url()
    schema = f"nexus_test_{uuid.uuid4().hex}"
    engine = create_async_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        yield database_url, schema
    finally:
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
