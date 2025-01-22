from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

router = Router(name="/start")

SPECIAL_SEARCH_TEXT = "🔍 Пошук за назвою"
SPECIAL_TRENDING_TEXT = "📈 Популярні фільми"
SPECIAL_HELP_TEXT = " Інформація"

START_MARKUP = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=SPECIAL_SEARCH_TEXT),
            KeyboardButton(text=SPECIAL_TRENDING_TEXT),
            KeyboardButton(text=SPECIAL_HELP_TEXT),
        ]
    ],
    resize_keyboard=True,
)


@router.message(CommandStart(ignore_case=True))
async def start_handler(message: Message):
    await message.reply(
        (
            "👋 Привіт! Я -- бот для пошуку фільмів за назвою!\n"
            "Також вмію показувати популярні фільми за останній час!"
        ),
        reply_markup=START_MARKUP,
    )


@router.message(F.text == SPECIAL_HELP_TEXT)
async def help_handler(message: Message):
    await message.reply("TBA")
