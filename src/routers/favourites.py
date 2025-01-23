from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from routers.start import SPECIAL_FAVOURITES_TEXT

router = Router(name="/favourites")


@router.message(F.text == SPECIAL_FAVOURITES_TEXT)
@router.message(Command("favourites"))
async def favourites_handler(message: Message):
    await message.reply("TBA")
