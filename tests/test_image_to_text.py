import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

import pytest

SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "image_to_text.py"


@pytest.mark.asyncio
async def test_ai_client_uses_token_and_provider_url_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Клиент получает ключ и адрес AI из новых переменных без запросов к API."""
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    environment = {
        "AI_TOKEN": "test-ai-token",
        "AI_PROVIDER_URL": "https://ai.example.test/v1",
    }
    with patch.dict(os.environ, environment, clear=True):
        spec = spec_from_file_location("app.services.image_to_text", SERVICE_PATH)
        assert spec is not None and spec.loader is not None
        service = module_from_spec(spec)
        spec.loader.exec_module(service)

        try:
            assert service.client.api_key == environment["AI_TOKEN"]
            assert str(service.client.base_url) == environment["AI_PROVIDER_URL"] + "/"
        finally:
            await service.client.close()
