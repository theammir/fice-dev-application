from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardButton,
    Message,
)

from db.models import Movie, User
from routers.start import SPECIAL_FAVOURITES_TEXT

router = Router(name="/favourites")


def favourite_button(movie_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text="⭐", callback_data=FavouriteCallback(movie_id=movie_id).pack()
    )


@router.message(F.text == SPECIAL_FAVOURITES_TEXT)
@router.message(Command("favourites"), F.from_user)
async def favourites_handler(message: Message):
    assert message.from_user is not None

    user_id = message.from_user.id
    movies: list[Movie] | None = []
    if not (movies := User.favourites_cache.get(user_id)):
        db_user = await User.by_id(user_id)
        await db_user.fetch_related("favourites")
        movies = await db_user.favourites.all()
        User.favourites_cache[user_id] = movies

    if not movies:
        await message.reply("⭐ Обраних фільмів не знайдено! Спробуйте додати нові.")
        return

    reply_text = "Натисніть на команду біля назви фільму, щоб подивитись деталі:\n\n"
    reply_text += "\n".join(
        "⭐ <b>{index}. {title} ({original_title})</b> {command}".format(
            index=i + 1,
            title=movie.title,
            original_title=movie.original_title,
            command=f"/view_{movie.id}",
        )
        for i, movie in enumerate(movies)
    )

    await message.reply(reply_text)


class FavouriteCallback(CallbackData, prefix="favourite"):
    movie_id: int


@router.callback_query(FavouriteCallback.filter())
async def favourite_callback_handler(
    query: CallbackQuery, callback_data: FavouriteCallback
):
    if not query.message or isinstance(query.message, InaccessibleMessage):
        return

    user_id = query.from_user.id
    movie_id = callback_data.movie_id

    db_user = await User.by_id(user_id)

    if not (cached_movies := User.favourites_cache.get(user_id)):
        await db_user.fetch_related("favourites")
        User.favourites_cache[user_id] = cached_movies = await db_user.favourites.all()

    already_favourite = movie_id in [m.id for m in cached_movies]
    movie = await Movie.get(id=movie_id)

    if already_favourite:
        await db_user.favourites.remove(movie)
        User.favourites_cache[user_id].remove(movie)
        await query.answer("❌ Фільм успішно видалено з обраних!")
        return

    await db_user.favourites.add(movie)
    User.favourites_cache[user_id].append(movie)
    await query.answer("⭐ Фільм успішно додано до обраних!")
