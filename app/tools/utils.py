import base64
import re
from datetime import datetime


def clean_content(content: str) -> str:
    """Очищает строку от нежелательных символов."""
    return content.strip()


def is_valid_url(url: str) -> bool:
    """Проверяет, является ли строка валидным URL."""
    regex = re.compile(
        r"^(?:http|ftp)s?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
        r"(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return re.match(regex, url) is not None


def format_dt(dt: datetime, style: str = "f") -> str:
    """Форматирует дату для Discord (<t:timestamp:style>)."""
    return f"<t:{int(dt.timestamp())}:{style}>"


def encode_image_to_base64(image_path: str) -> str:
    """Кодирует изображение в строку base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
