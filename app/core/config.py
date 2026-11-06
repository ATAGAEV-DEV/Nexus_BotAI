import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    """Класс для управления конфигурацией бота."""

    def __init__(self) -> None:
        """Инициализация конфигурации и загрузка переменных окружения."""
        self.DC_TOKEN = os.getenv("DC_TOKEN")
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        self.SCREENSHOT_CHANNEL_ID = int(os.getenv("SCREENSHOT_CHANNEL_ID", "0"))

        self._validate()

    @property
    def database_url(self) -> str:
        """Возвращает URL базы данных."""
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set")
        return self.DATABASE_URL

    def _validate(self):
        if not self.DC_TOKEN:
            print("DC_TOKEN не найден в переменных окружения!")
            raise ValueError("DC_TOKEN is required")
        if not self.DATABASE_URL:
            print("DATABASE_URL не найден в переменных окружения!")
            raise ValueError("DATABASE_URL is required")


settings = Config()
