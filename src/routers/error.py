import logging
from typing import NoReturn

import aiohttp
from aiogram import Router
from aiogram.types import ErrorEvent

from tmdb import TMDBException

router = Router(name="/error")


@router.error()
async def error_handler(event: ErrorEvent) -> NoReturn:
    if event.update.message is not None:
        if isinstance(event.exception, TMDBException):
            await event.update.message.reply(
                f"💢 Помилка сервісу!\nПовідомлення: <i>{event.exception.message}</i>"
            )
        elif isinstance(event.exception, KeyError):
            await event.update.message.reply("💢 Помилка обробки даних із сервера!")
        elif isinstance(event.exception, aiohttp.ClientError):
            logging.error("Network error! Message: %s", event.update.message.text)
            await event.update.message.reply(
                "💢 Помилка мережі! Спробуйте ще раз невдовзі"
            )
        else:
            logging.error("Unknown error! Message: %s", event.update.message.text)
            await event.update.message.reply("💢 Невідома помилка!")
    raise event.exception
