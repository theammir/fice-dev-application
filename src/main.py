import asyncio
import contextlib
import logging
import os

import aiogram
import dotenv
from aiogram.client.default import DefaultBotProperties
from aiogram.dispatcher.dispatcher import Dispatcher, loggers
from aiogram.enums import ParseMode
from rich.logging import RichHandler

import routers
from tmdb import TMDBSession

dotenv.load_dotenv()


async def main() -> None:
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("expected BOT_TOKEN in env")

    bot = aiogram.Bot(
        bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    tmdb_token = os.getenv("TMDB_AUTH_TOKEN")
    if not tmdb_token:
        raise ValueError("expected TMDB_AUTH_TOKEN in env")

    tmdb = TMDBSession(tmdb_token)

    dp = Dispatcher(tmdb=tmdb)
    dp.include_routers(routers.movie_router, routers.error_router)

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            RichHandler(rich_tracebacks=True, log_time_format="[%d/%m/%y %H:%M:%S]")
        ],
    )
    loggers.event.setLevel(logging.WARNING)

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
