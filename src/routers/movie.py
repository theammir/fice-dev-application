from enum import IntEnum

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from db.models import Genre, Movie, User
from tmdb import TMDBSession

from .start import SPECIAL_SEARCH_TEXT, SPECIAL_TRENDING_TEXT, START_MARKUP

router = Router(name="/movie")

SPECIAL_CANCEL_TEXT = "✨ Cancel"

MOVIE_FORMAT_STR = """
<b>Назва фільму</b>: {title} ({original_title})

<b>Опис</b>: {overview}
<b>Жанри</b>: {genres}
<b>Дата виходу</b>: <code>{release_date}</code>
<b>Рейтинг</b>: <code>{rating}/10</code> (<i>{vote_count}</i> голосів)
"""


async def format_movie(movie: Movie) -> str:
    genres = [await Genre.by_id(id) for id in movie.genre_ids]  # type: ignore
    genres: list[Genre] = list(filter(lambda g: g is not None, genres))
    return MOVIE_FORMAT_STR.format(
        title=movie.title,
        original_title=movie.original_title,
        overview=movie.overview,
        genres=", ".join([g.name for g in genres]),
        release_date=movie.release_date.strftime("%d/%m/%Y"),
        rating=movie.average_rating,
        vote_count=movie.vote_count,
    )


class SearchState(StatesGroup):
    query = State()


@router.message(F.text == SPECIAL_SEARCH_TEXT)
@router.message(Command("search"))
async def search_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchState.query)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SPECIAL_CANCEL_TEXT)]],
        is_persistent=True,
        resize_keyboard=True,
    )

    await message.reply("🔎 Уведіть назву фільму:", reply_markup=markup)


@router.message(F.text == SPECIAL_CANCEL_TEXT)
async def search_cancel_handler(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return

    await state.clear()
    await message.reply("🔎 Скасовано", reply_markup=START_MARKUP)


@router.message(SearchState.query, F.text)
async def search_process_query(
    message: Message, state: FSMContext, tmdb: TMDBSession
) -> None:
    assert message.text is not None

    await state.clear()

    query = message.text
    movie = await tmdb.search_movie(query)

    if not movie:
        await message.reply("🔎 Результатів за вашим запитом не знайдено")
        return
    await message.reply_photo(
        movie.poster_path,
        await format_movie(movie),
        reply_markup=START_MARKUP,
    )


class PaginatorAction(IntEnum):
    PREV = 0
    NEXT = 1


class PaginatorCallback(CallbackData, prefix="page"):
    action: PaginatorAction
    current_index: int


def paginator_markup(current_index: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← Попередній",
                    callback_data=PaginatorCallback(
                        action=PaginatorAction.PREV, current_index=current_index
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="Наступний →",
                    callback_data=PaginatorCallback(
                        action=PaginatorAction.NEXT, current_index=current_index
                    ).pack(),
                ),
            ]
        ]
    )


@router.message(F.text == SPECIAL_TRENDING_TEXT)
@router.message(Command("trending"), F.from_user)
async def trending_handler(message: Message, tmdb: TMDBSession):
    assert message.from_user is not None

    movies = await tmdb.get_trending_movies(time_window="week")
    if not movies:
        await message.reply(
            (
                "💢 Помилка під час отримання списку фільмів.\n"
                "Спробуйте ще раз через кілька секунд"
            )
        )
        return

    await message.reply_photo(
        movies[0].poster_path,
        await format_movie(movies[0]),
        reply_markup=paginator_markup(0),
    )

    user_id = message.from_user.id
    User.trending_cache[user_id] = movies

    db_user = await User.by_id(user_id)
    await db_user.last_trending.clear()
    await db_user.last_trending.add(*movies)


@router.callback_query(PaginatorCallback.filter())
async def paginator_callback_handler(
    query: CallbackQuery, callback_data: PaginatorCallback
):
    if not query.message or isinstance(query.message, InaccessibleMessage):
        return

    user_id = query.from_user.id

    movies: list[Movie] = []
    if user_id in User.trending_cache:
        movies = User.trending_cache[user_id]
    else:
        db_user = await User.by_id(query.from_user.id)
        await db_user.fetch_related("last_trending")
        movies = await db_user.last_trending.all()
        User.trending_cache[user_id] = movies

    if not movies:
        await query.answer("💢 Список фільмів не знайдено!")
        return

    current_index = callback_data.current_index
    current_index += 1 if callback_data.action == PaginatorAction.NEXT else -1
    current_index %= len(movies)

    movie = movies[current_index]

    await query.answer()
    await query.message.edit_media(
        InputMediaPhoto(media=movie.poster_path),
    )
    await query.message.edit_caption(
        caption=await format_movie(movie),
        reply_markup=paginator_markup(current_index),
    )
