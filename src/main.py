import contextlib
import logging
import os

import aiogram
import dotenv
from aiogram.client.default import DefaultBotProperties
from aiogram.dispatcher.dispatcher import Dispatcher, loggers
from aiogram.enums import ParseMode
from rich.logging import RichHandler
from tortoise import Tortoise, run_async

import routers
from tmdb import TMDBSession

dotenv.load_dotenv()


def expect_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"expected {key} in env")
    return value


async def main() -> None:
    bot_token = expect_env("BOT_TOKEN")
    bot = aiogram.Bot(
        bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    tmdb_token = expect_env("TMDB_AUTH_TOKEN")
    tmdb = TMDBSession(tmdb_token)
    await tmdb.preload_genres()

    db_url = expect_env("DB_URL")
    await Tortoise.init(db_url=db_url, modules={"models": ["db.models"]})
    await Tortoise.generate_schemas()

    dp = Dispatcher(tmdb=tmdb)
    dp.include_routers(*[getattr(routers, r) for r in routers.__all__])

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging._nameToLevel[(os.getenv("LOG") or "INFO").upper()],
        format="%(message)s",
        handlers=[
            RichHandler(rich_tracebacks=True, log_time_format="[%d/%m/%y %H:%M:%S]")
        ],
    )
    loggers.event.setLevel(logging.WARNING)

    with contextlib.suppress(KeyboardInterrupt):
        run_async(main())
