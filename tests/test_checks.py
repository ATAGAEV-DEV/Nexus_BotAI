import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from discord.ext import commands

CHECKS_PATH = Path(__file__).resolve().parents[1] / "app" / "core" / "checks.py"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("allowed_users", "username", "administrator", "allowed"),
    [
        ("alice, bob, ,", "alice", False, True),
        ("alice, bob, ,", "bob", False, True),
        ("alice", "other", True, True),
        ("alice", "other", False, False),
        (None, "atagaev", False, False),
        ("", "atagaev", False, False),
        ("", "other", True, True),
        (" , , ", "", False, False),
    ],
)
async def test_admin_access_uses_server_permissions_or_environment_list(
    monkeypatch: pytest.MonkeyPatch,
    allowed_users: str | None,
    username: str,
    administrator: bool,
    allowed: bool,
) -> None:
    """Доступ дают права сервера или имя из .env, без встроенных исключений."""
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    environment = {} if allowed_users is None else {"ALLOWED_USERS": allowed_users}
    with patch.dict(os.environ, environment, clear=True):
        spec = spec_from_file_location("checks_under_test", CHECKS_PATH)
        assert spec is not None and spec.loader is not None
        checks = module_from_spec(spec)
        spec.loader.exec_module(checks)

    ctx = SimpleNamespace(
        author=SimpleNamespace(
            name=username,
            guild_permissions=SimpleNamespace(administrator=administrator),
        )
    )
    predicate = checks.admin_or_owner().predicate
    if allowed:
        assert await predicate(ctx) is True
    else:
        with pytest.raises(commands.MissingPermissions) as exc:
            await predicate(ctx)
        assert exc.value.missing_permissions == ["administrator"]
