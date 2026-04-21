import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, AsyncOpenAI, BadRequestError

from app.tools.utils import encode_image_to_base64

load_dotenv()

AI_TOKEN_POLZA = os.getenv("AI_TOKEN_POLZA")
polza = "https://api.polza.ai/api/v1"

client = AsyncOpenAI(
    api_key=AI_TOKEN_POLZA,
    base_url=polza,
    timeout=60.0,
)


async def ai_generate(message: list) -> Any | None:
    """Отправляет сообщение в AI и возвращает ответ."""
    try:
        completion = await client.chat.completions.create(
            # model="google/gemini-2.0-flash-001",
            model="google/gemini-3.1-flash-lite-preview",
            messages=message,
            temperature=0.1,
        )

        response_text = completion.choices[0].message.content
        return response_text

    except BadRequestError as e:
        print(f"Ошибка запроса к API: {e}")

    except APIConnectionError as e:
        print(f"Ошибка подключения к API: {e}")

    except APIError as e:
        print(f"Ошибка API: {e}")

    except Exception as e:
        print(f"Неожиданная ошибка: {e}")


def generate_prompt(image_path: str) -> list[dict]:
    """Генерирует промт для извлечения игровых ников из скриншота."""
    prompt = (
        "Ты получаешь скриншот из видеоигры. "
        "На нём отображены игровые ники (никнеймы) игроков.\n\n"
        "Твоя задача — извлечь ВСЕ игровые ники, "
        "которые ты видишь на скриншоте.\n\n"
        "Правила для ников:\n"
        "- Ник может содержать ТОЛЬКО: латинские буквы (A-Z, a-z), "
        "цифры (0-9), дефис (-), нижнее подчёркивание (_) и точку (.)\n"
        "- Любые другие символы НЕ являются частью ника\n"
        "- Будь максимально точен в распознавании каждого символа\n\n"
        "Формат ответа:\n"
        "- Верни ТОЛЬКО список ников, каждый на новой строке\n"
        "- Никаких пояснений, заголовков или нумерации\n"
        "- Только сами ники, по одному на строку"
    )

    base64_image = encode_image_to_base64(image_path)

    message = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ],
        }
    ]

    return message
