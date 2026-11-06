import os
import runpy
from collections.abc import Callable
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord.ext import commands

import app.cogs.admin as admin_cog
import app.cogs.general as general_cog
import app.cogs.nicknames as nicknames_cog
import app.cogs.screenshots as screenshots_cog
import app.core.bot as bot_module
import app.core.config as config_module
import app.core.embeds as embeds_module
import app.services.image_to_text as image_service
import app.services.scheduler as scheduler_service
import app.services.steam as steam_service
import app.tools.utils as utils_module
import main
from app.core.embeds import Embeds

CONFIG_PATH = Path(__file__).resolve().parents[1] / "app" / "core" / "config.py"


def load_config(monkeypatch: pytest.MonkeyPatch, environment: dict[str, str]) -> ModuleType:
    """Загружает конфигурацию из заданного окружения без чтения .env."""
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    spec = spec_from_file_location("config_under_test", CONFIG_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    with patch.dict(os.environ, environment, clear=True):
        spec.loader.exec_module(module)
    return module


def test_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Конфигурация читает токен, базу и канал из окружения."""
    module = load_config(
        monkeypatch,
        {
            "DC_TOKEN": "token",
            "DATABASE_URL": "postgresql+asyncpg://example",
            "SCREENSHOT_CHANNEL_ID": "42",
        },
    )
    assert module.settings.DC_TOKEN == "token"
    assert module.settings.database_url == "postgresql+asyncpg://example"
    assert module.settings.SCREENSHOT_CHANNEL_ID == 42


@pytest.mark.parametrize("missing", ["DC_TOKEN", "DATABASE_URL"])
def test_config_requires_token_and_database(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    """Отсутствие обязательной переменной останавливает создание конфигурации."""
    environment = {"DC_TOKEN": "token", "DATABASE_URL": "postgresql+asyncpg://example"}
    del environment[missing]
    with pytest.raises(ValueError, match=missing):
        load_config(monkeypatch, environment)


def test_database_url_property_rejects_empty_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Свойство URL повторно проверяет значение перед возвратом."""
    settings = config_module.Config.__new__(config_module.Config)
    settings.DATABASE_URL = ""
    with pytest.raises(ValueError, match="DATABASE_URL"):
        _ = settings.database_url


def test_embeds_use_expected_colors() -> None:
    """Каждый тип embed получает свой заголовок и цвет."""
    assert Embeds.success("Готово", "описание").colour.value == 0x2ECC71
    assert Embeds.error("Ошибка", "описание").title == "❌ Ошибка"
    assert Embeds.info("Инфо", "описание").colour.value == 0x3498DB


@pytest.mark.asyncio
async def test_ping_and_help_cover_visible_and_hidden_commands() -> None:
    """Ping считает задержку, а help пропускает скрытые команды и пустые коги."""
    hidden = SimpleNamespace(hidden=True, name="secret", help="скрыто")
    visible = SimpleNamespace(hidden=False, name="ping", help="проверка")
    empty_cog = SimpleNamespace(get_commands=lambda: [])
    populated_cog = SimpleNamespace(get_commands=lambda: [hidden, visible])
    bot = SimpleNamespace(latency=0.1234, cogs={"Empty": empty_cog, "General": populated_cog})
    cog = general_cog.General(bot)
    ctx = AsyncMock()
    ctx.typing = MagicMock(return_value=AsyncMock())

    await cog.ping.callback(cog, ctx)
    await cog.help_command.callback(cog, ctx)

    assert "123мс" in ctx.send.await_args_list[0].kwargs["embed"].description
    fields = ctx.send.await_args_list[1].kwargs["embed"].fields
    assert [field.name for field in fields] == ["General"]
    assert "`?ping`" in fields[0].value and "secret" not in fields[0].value


@pytest.mark.asyncio
async def test_cog_setup_functions_register_cogs() -> None:
    """Каждый setup добавляет в бота экземпляр своего кога."""
    bot = AsyncMock()
    await general_cog.setup(bot)
    await admin_cog.setup(bot)
    await nicknames_cog.setup(bot)
    await screenshots_cog.setup(bot)
    assert [call.args[0].__class__.__name__ for call in bot.add_cog.await_args_list] == [
        "General",
        "Admin",
        "Nicknames",
        "Screenshots",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(("games", "title"), [([], "Раздач на сегодня"), (["Игра"], "• Игра")])
async def test_steam_command(games: list[str], title: str) -> None:
    """Команда steam показывает пустой и непустой списки раздач."""
    ctx = AsyncMock()
    ctx.typing = MagicMock(return_value=AsyncMock())
    with patch("app.services.steam.get_free_steam_games", AsyncMock(return_value=games)):
        await admin_cog.Admin.steam.callback(admin_cog.Admin(SimpleNamespace()), ctx)
    assert title in ctx.send.await_args.kwargs["embed"].description


@pytest.mark.asyncio
async def test_set_steam_handles_dm_success_and_error() -> None:
    """Команда set_steam покрывает личные сообщения, успех и ошибку сохранения."""
    cog = admin_cog.Admin(SimpleNamespace())
    command = admin_cog.Admin.set_steam_channel.callback
    dm = AsyncMock(guild=None)
    dm.typing = MagicMock(return_value=AsyncMock())
    await command(cog, dm)
    assert "только на серверах" in dm.send.await_args.kwargs["embed"].description

    ok = AsyncMock()
    ok.typing = MagicMock(return_value=AsyncMock())
    ok.guild.id, ok.channel.id = 1, 2
    with patch("app.data.request.add_steam_subscription", AsyncMock()) as save:
        await command(cog, ok)
    save.assert_awaited_once_with(server_id=1, channel_id=2)

    failed = AsyncMock()
    failed.typing = MagicMock(return_value=AsyncMock())
    failed.guild.id, failed.channel.id = 1, 2
    with patch("app.data.request.add_steam_subscription", AsyncMock(side_effect=RuntimeError("db"))):
        await command(cog, failed)
    assert "db" in failed.send.await_args.kwargs["embed"].description


@pytest.mark.asyncio
async def test_error_handler_reports_each_error_type(capsys: pytest.CaptureFixture[str]) -> None:
    """Обработчик выбирает сообщение по типу ошибки и печатает неизвестную ошибку."""
    error_module = load_module("app.cogs.error_handler")
    bot = SimpleNamespace(command_prefix="?")
    handler = error_module.ErrorHandler(bot)
    await error_module.setup(AsyncMock(add_cog=AsyncMock()))
    ctx = AsyncMock()
    ctx.command.name, ctx.command.signature = "nick", "<nick>"

    cases = [
        (commands.CommandNotFound(), None),
        (commands.MissingPermissions(["administrator"]), "недостаточно прав"),
        (commands.MissingRequiredArgument(SimpleNamespace(name="nick", displayed_name="nick")), "?nick <nick>"),
        (commands.NoPrivateMessage(), "личных сообщениях"),
        (SimpleNamespace(original=ConnectionError(), __class__=commands.CommandInvokeError), "сетью"),
        (commands.CommandError("boom"), "Произошла ошибка"),
    ]
    for error, expected in cases:
        ctx.send.reset_mock()
        await handler.on_command_error(ctx, error)
        if expected is None:
            ctx.send.assert_not_awaited()
        else:
            assert expected in ctx.send.await_args.args[0]
    assert "boom" in capsys.readouterr().out


def load_module(name: str) -> ModuleType:
    """Повторно загружает модуль для проверки его setup без изменения глобального состояния."""
    path = Path(__file__).resolve().parents[1] / Path(*name.split(".")).with_suffix(".py")
    spec = spec_from_file_location(f"{name}_under_test", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_nickname_commands_cover_validation_results_and_errors() -> None:
    """Команды ников покрывают отсутствие аргументов, результаты и исключения."""
    cog = nicknames_cog.Nicknames(SimpleNamespace())
    ctx = AsyncMock()
    ctx.typing = MagicMock(return_value=AsyncMock())
    targets = {cog.add_nick: {"add_nicknames": AsyncMock()}, cog.check_nick: {"find_nickname": AsyncMock()}, cog.nick_list: {"count_nicknames": AsyncMock()}, cog.nick_desc: {"upsert_nickname": AsyncMock()}, cog.nick_del: {"delete_nickname": AsyncMock()}}
    for command, names in targets.items():
        command.callback.__globals__.update(names)

    async def call(command, *args, **kwargs):
        return await command.callback(cog, ctx, *args, **kwargs)

    await call(cog.add_nick)
    targets[cog.add_nick]["add_nicknames"].return_value = ["A"]
    await call(cog.add_nick, "A", "B")
    targets[cog.add_nick]["add_nicknames"].return_value = []
    await call(cog.add_nick, "A")
    targets[cog.add_nick]["add_nicknames"].side_effect = RuntimeError("db")
    await call(cog.add_nick, "A")

    await call(cog.check_nick, None)
    targets[cog.check_nick]["find_nickname"].return_value = ("A", "описание")
    await call(cog.check_nick, "A")
    targets[cog.check_nick]["find_nickname"].return_value = ("A", None)
    await call(cog.check_nick, "A")
    targets[cog.check_nick]["find_nickname"].return_value = None
    await call(cog.check_nick, "A")
    targets[cog.check_nick]["find_nickname"].side_effect = RuntimeError("db")
    await call(cog.check_nick, "A")

    targets[cog.nick_list]["count_nicknames"].return_value = 3
    await call(cog.nick_list)
    targets[cog.nick_list]["count_nicknames"].side_effect = RuntimeError("db")
    await call(cog.nick_list)

    await call(cog.nick_desc, None, description=None)
    await call(cog.nick_desc, "A", description=None)
    targets[cog.nick_desc]["upsert_nickname"].return_value = True
    await call(cog.nick_desc, "A", description="новый")
    targets[cog.nick_desc]["upsert_nickname"].return_value = False
    await call(cog.nick_desc, "A", description="старый")
    targets[cog.nick_desc]["upsert_nickname"].side_effect = RuntimeError("db")
    await call(cog.nick_desc, "A", description="ошибка")

    await call(cog.nick_del, None)
    targets[cog.nick_del]["delete_nickname"].return_value = True
    await call(cog.nick_del, "A")
    targets[cog.nick_del]["delete_nickname"].return_value = False
    await call(cog.nick_del, "A")
    targets[cog.nick_del]["delete_nickname"].side_effect = RuntimeError("db")
    await call(cog.nick_del, "A")

    messages = [item.kwargs["embed"].description for item in ctx.send.await_args_list]
    assert any("Добавлено: 1" in message for message in messages)
    assert any("уже есть" in message for message in messages)
    assert any("описание" in message for message in messages)
    assert any("отсутствует" in message for message in messages)
    assert any("Всего ников" in message for message in messages)
    assert any("Ник добавлен" in call.kwargs["embed"].title for call in ctx.send.await_args_list)
    assert messages.count("Произошла ошибка: db") == 5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "result", "added", "found", "expected"),
    [
        (" ?", None, [], {}, "Не удалось распознать"),
        (" ?", " \n ", [], {}, None),
        (" ?", "Player\nNew", ["New"], {}, "Уже были"),
        ("EMPTY", "known\nplain\nunknown", [], {"known": ("Known", "описание"), "plain": ("Plain", None)}, "unknown"),
    ],
)
async def test_screenshots_cover_filters_and_database_results(tmp_path: Path, content, result, added, found, expected) -> None:
    """Каждый сценарий скриншота проверяет один результат распознавания."""
    cog = screenshots_cog.Screenshots(SimpleNamespace())
    namespace = cog.on_message.__func__.__globals__
    image = SimpleNamespace(content_type="image/jpeg", read=AsyncMock(return_value=b"jpeg"))
    current = message(content="" if content == "EMPTY" else content, attachments=[image])
    ignored = [SimpleNamespace(author=SimpleNamespace(bot=True)), message(channel_id=1), message(content="?nick"), message(attachments=[SimpleNamespace(content_type="text/plain")])]
    add, find, unlink = AsyncMock(return_value=added), AsyncMock(return_value=found), MagicMock()
    temporary = MagicMock(); temporary.return_value.__enter__.return_value.name = str(tmp_path / "shot.jpg")
    with patch.dict(namespace, {"settings": SimpleNamespace(SCREENSHOT_CHANNEL_ID=7), "generate_prompt": lambda path: [], "ai_generate": AsyncMock(return_value=result), "add_nicknames": add, "find_nicknames": find, "os": SimpleNamespace(unlink=unlink), "tempfile": SimpleNamespace(NamedTemporaryFile=temporary)}):
        for item in ignored:
            await cog.on_message(item)
        await cog.on_message(current)
    if content == " ?":
        add.assert_awaited_once() if result and result.strip() else add.assert_not_awaited()
    else:
        find.assert_awaited_once()
    assert unlink.call_count == 1
    if not expected:
        return
    sent = current.reply.await_args.args[0] if content == " ?" else current.channel.send.await_args.args[0]
    assert expected in sent


def message(**overrides: object) -> SimpleNamespace:
    """Создаёт минимальное сообщение Discord для обработчика скриншотов."""
    values = {
        "author": SimpleNamespace(bot=False),
        "channel": SimpleNamespace(id=7, typing=MagicMock(return_value=AsyncMock()), send=AsyncMock()),
        "content": "",
        "attachments": [],
        "reply": AsyncMock(),
    }
    values.update({key: value for key, value in overrides.items() if key in values or key == "channel_id"})
    if "channel_id" in overrides:
        values["channel"] = SimpleNamespace(id=overrides["channel_id"], typing=MagicMock(return_value=AsyncMock()), send=AsyncMock())
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_bot_startup_loads_extensions_and_scheduler() -> None:
    """Старт бота загружает расширения, создаёт таблицы и запускает планировщик."""
    bot = bot_module.DisBot.__new__(bot_module.DisBot)
    bot.load_extension = AsyncMock()
    with (
        patch.object(bot_module, "init_models", AsyncMock()) as init_models,
        patch.object(bot_module, "start_scheduler") as start,
    ):
        await bot.setup_hook()
        await bot.on_ready()
    assert bot.load_extension.await_count == 5
    init_models.assert_awaited_once()
    start.assert_called_once_with(bot)


def test_encode_image(tmp_path: Path) -> None:
    """Кодирование изображения возвращает декодируемую строку base64."""
    path = tmp_path / "image.bin"
    path.write_bytes(b"abc")
    assert utils_module.encode_image_to_base64(str(path)) == "YWJj"


def test_generate_prompt_uses_encoded_image(tmp_path: Path) -> None:
    """Промпт содержит инструкцию и data URL изображения."""
    path = tmp_path / "image.jpg"
    path.write_bytes(b"abc")
    prompt = image_service.generate_prompt(str(path))
    assert prompt[0]["content"][1]["image_url"]["url"].endswith("YWJj")


@pytest.mark.asyncio
async def test_ai_generate_handles_success_and_errors(capsys: pytest.CaptureFixture[str]) -> None:
    """AI-клиент возвращает текст либо печатает все виды ошибок."""
    success = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ник"))])
    errors = [
        image_service.BadRequestError("bad", response=MagicMock(), body=None),
        image_service.APIConnectionError(request=MagicMock()),
        image_service.APIError("api", request=MagicMock(), body=None),
        RuntimeError("unexpected"),
    ]
    create = AsyncMock(side_effect=[success, *errors])
    with patch.object(image_service.client.chat.completions, "create", create):
        assert await image_service.ai_generate([]) == "ник"
        for _ in errors:
            assert await image_service.ai_generate([]) is None
    output = capsys.readouterr().out
    assert all(word in output for word in ("запроса", "подключения", "API", "Неожиданная"))


def rss(title: str, description: str = "Game", date: str = "Fri, 06 Nov 2026 00:00:00 GMT") -> str:
    """Собирает минимальный RSS-элемент для парсера Steam."""
    return f"<item><title>{title}</title><description>{description}</description><pubDate>{date}</pubDate></item>"


def test_parse_rss_filters_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Парсер оставляет только свежие игры и отбрасывает неполные элементы."""
    class FixedDate(steam_service.date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 6)

    monkeypatch.setattr(steam_service, "date", FixedDate)
    xml = "<rss><channel>" + "".join(
        [
            rss("Game (Steam)"),
            rss("Old", date="Wed, 04 Nov 2026 00:00:00 GMT"),
            rss("Giveaway"),
            rss("Addon", "Это DLC"),
            rss("", date="bad-date"),
            "<item></item>",
            "<item><title>No date</title></item>",
        ]
    ) + "</channel></rss>"
    assert steam_service.parse_rss(xml) == ["Game"]
    assert steam_service.parse_rss("<rss><item><title>Game</title><pubDate>Fri, 06 Nov 2026 00:00:00 GMT</pubDate></item></rss>") == ["Game"]


@pytest.mark.asyncio
async def test_steam_fetch_and_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Загрузка RSS возвращает текст, а ошибка превращается в пустой список."""
    response = AsyncMock()
    response.text.return_value = "<rss/>"
    session = MagicMock()
    session.get.return_value = AsyncMock(__aenter__=AsyncMock(return_value=response))
    session.__aenter__.return_value = session
    with patch.object(steam_service.aiohttp, "ClientSession", return_value=session):
        assert await steam_service.fetch_rss("https://example.test") == "<rss/>"
    with patch.object(steam_service, "fetch_rss", AsyncMock(side_effect=RuntimeError("down"))):
        assert await steam_service.get_free_steam_games() == []
    assert "down" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_scheduler_sends_only_new_games() -> None:
    """Планировщик останавливается на пустых этапах и отправляет только в текстовые каналы."""
    bot = SimpleNamespace(get_channel=lambda channel_id: {1: AsyncMock(spec=[]), 2: failing_channel()}.get(channel_id))
    with patch.object(scheduler_service, "get_free_steam_games", AsyncMock(return_value=[])):
        await scheduler_service.check_steam_games(bot)
    with (
        patch.object(scheduler_service, "get_free_steam_games", AsyncMock(return_value=["Old"])),
        patch.object(scheduler_service, "is_game_new_and_save", AsyncMock(return_value=False)),
    ):
        await scheduler_service.check_steam_games(bot)
    with (
        patch.object(scheduler_service, "get_free_steam_games", AsyncMock(return_value=["New"])),
        patch.object(scheduler_service, "is_game_new_and_save", AsyncMock(return_value=True)),
        patch.object(scheduler_service, "get_active_steam_subscriptions", AsyncMock(return_value=[])),
    ):
        await scheduler_service.check_steam_games(bot)
    with (
        patch.object(scheduler_service, "get_free_steam_games", AsyncMock(return_value=["New"])),
        patch.object(scheduler_service, "is_game_new_and_save", AsyncMock(return_value=True)),
        patch.object(scheduler_service, "get_active_steam_subscriptions", AsyncMock(return_value=[1, 2, 3])),
    ):
        await scheduler_service.check_steam_games(bot)
    scheduler = MagicMock()
    with patch.object(scheduler_service, "AsyncIOScheduler", return_value=scheduler):
        scheduler_service.start_scheduler(SimpleNamespace())
    scheduler.start.assert_called_once()


def failing_channel() -> AsyncMock:
    """Создаёт текстовый канал, отправка в который завершается ошибкой."""
    channel = AsyncMock(spec=scheduler_service.discord.TextChannel)
    channel.send.side_effect = RuntimeError("forbidden")
    return channel


def test_main_starts_and_stops_without_token(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Точка входа запускает бота либо завершается при пустом токене."""
    bot = MagicMock()
    monkeypatch.setattr(main, "DisBot", MagicMock(return_value=bot))
    monkeypatch.setattr(main.settings, "DC_TOKEN", "token")
    main.main()
    bot.run.assert_called_once_with("token")
    monkeypatch.setattr(main.settings, "DC_TOKEN", "")
    main.main()
    assert "DC_TOKEN" in capsys.readouterr().out


def test_main_module_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Запуск файла как программы создаёт бота и вызывает run ровно один раз."""
    bot = MagicMock()
    create_bot = MagicMock(return_value=bot)
    monkeypatch.setattr(bot_module, "DisBot", create_bot)
    monkeypatch.setattr(config_module.settings, "DC_TOKEN", "test-token")

    namespace = runpy.run_path(str(Path(main.__file__)), run_name="__main__")

    create_bot.assert_called_once_with(
        command_prefix="?",
        intents=namespace["intents"],
        help_command=None,
    )
    bot.run.assert_called_once_with("test-token")
