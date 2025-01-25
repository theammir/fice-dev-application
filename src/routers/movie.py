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
    Message,
)

from db.models import Movie, User
from routers.favourites import favourite_button
from tmdb import TMDBSession

from .start import SPECIAL_SEARCH_TEXT, SPECIAL_TRENDING_TEXT, START_MARKUP

router = Router(name="MOVIE")


def format_movie(movie: Movie) -> str:
    MOVIE_FORMAT_STR = """
<b>Назва фільму</b>: {title}
{trailer}
<b>Опис</b>: {overview}
<b>Жанри</b>: {genres}
<b>Дата виходу</b>: <code>{release_date}</code>
<b>Рейтинг</b>: <code>{rating}/10</code> (<i>{vote_count}</i> голосів)
    """
    title = (
        movie.title
        if movie.title == movie.original_title
        else f"{movie.title} ({movie.original_title})"
    )
    trailer = (
        f"<a href='{movie.trailer}'>(дивитись трейлер)</a>\n" if movie.trailer else ""
    )
    genres = list(
        filter(
            lambda g: g, [TMDBSession.genre_name_of(id, "") for id in movie.genre_ids]
        )
    )
    return MOVIE_FORMAT_STR.format(
        title=title,
        trailer=trailer,
        overview=movie.overview,
        genres=", ".join(genres),
        release_date=movie.release_date.strftime("%d/%m/%Y"),
        rating=movie.average_rating,
        vote_count=movie.vote_count,
    )


class SearchState(StatesGroup):
    query = State()


# TODO: Only use reply markups in DMs


@router.message(F.text == SPECIAL_SEARCH_TEXT)
@router.message(Command("search", "find"), F.from_user)
async def search_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchState.query)
    await message.reply("🔎 Уведіть назву фільму:", reply_markup=START_MARKUP)


@router.message(SearchState.query, F.text)
async def search_process_query(
    message: Message, state: FSMContext, tmdb: TMDBSession
) -> None:
    assert message.text is not None

    await state.clear()

    query = message.text.lower()
    if not (movie := Movie.query_lookup_cache.get(query)):
        movie = await tmdb.search_movie(query)
        Movie.query_lookup_cache[query] = movie

    if not movie:
        await message.reply(
            "🔎 Результатів за вашим запитом не знайдено", reply_markup=START_MARKUP
        )
        return
    await message.reply_photo(
        movie.poster_path,
        format_movie(movie),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[favourite_button(movie.id)]]
        ),
    )


@router.message(F.text.casefold().startswith("/view_") & F.text.len() > len("/view_"))
async def view_handler(message: Message, tmdb: TMDBSession):
    assert message.text is not None

    command_split = message.text.split("_")
    assert len(command_split) > 1

    id_str = command_split[1]
    movie_id: int
    try:
        movie_id = int(id_str)
    except ValueError:
        await message.reply(
            "💢 Неправильний параметр!\nЦя команда не створена для виклику вручну"
        )
        return

    if not (cached_movie := Movie.id_lookup_cache.get(movie_id)):
        cached_movie = await tmdb.get_movie_by_id(movie_id)
        Movie.id_lookup_cache[movie_id] = cached_movie

    if not cached_movie:
        await message.reply("🔎 Фільму за цим параметром не знайдено")
        return

    await message.reply_photo(
        cached_movie.poster_path,
        format_movie(cached_movie),
        reply_markup=START_MARKUP,
    )


class PaginatorAction(IntEnum):
    PREV = 0
    NEXT = 1


class PaginatorCallback(CallbackData, prefix="page"):
    action: PaginatorAction
    current_index: int


def paginator_markup(current_index: int, movie_id: int):
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
            ],
            [favourite_button(movie_id)],
        ]
    )


@router.message(F.text == SPECIAL_TRENDING_TEXT)
@router.message(Command("trending", "popular"), F.from_user)
async def trending_handler(message: Message, tmdb: TMDBSession):
    assert message.from_user is not None

    if not (movies := Movie.currently_trending_cache.get(0)):
        movies = await tmdb.get_trending_movies(time_window="week")
        Movie.currently_trending_cache[0] = movies

    if not movies:
        await message.reply(
            (
                "💢 Помилка під час отримання списку фільмів.\n"
                "Спробуйте ще раз через кілька секунд"
            )
        )
        return

    movie = movies[0]
    if not movie.trailer:
        trailer = await tmdb.get_movie_trailer(movie.id)
        if trailer:
            movie.trailer = trailer
            await movie.save(update_fields=("trailer",), force_update=True)
            Movie.currently_trending_cache[0][0].trailer = trailer

    await message.reply_photo(
        movie.poster_path,
        format_movie(movie),
        reply_markup=paginator_markup(0, movie.id),
    )

    user_id = message.from_user.id
    User.last_trending_cache[user_id] = movies

    db_user = await User.by_id(user_id)
    await db_user.last_trending.clear()
    await db_user.last_trending.add(*movies)


@router.callback_query(PaginatorCallback.filter())
async def paginator_callback_handler(
    query: CallbackQuery, callback_data: PaginatorCallback, tmdb: TMDBSession
):
    if not query.message or isinstance(query.message, InaccessibleMessage):
        return

    user_id = query.from_user.id

    if not (cached_movies := User.last_trending_cache.get(user_id)):
        db_user = await User.by_id(user_id)
        await db_user.fetch_related("last_trending")
        User.last_trending_cache[user_id] = (
            cached_movies
        ) = await db_user.last_trending.all()

    if not cached_movies:
        await query.answer("💢 Список фільмів не знайдено!")
        return

    current_index = callback_data.current_index
    current_index += 1 if callback_data.action == PaginatorAction.NEXT else -1
    current_index %= len(cached_movies)

    movie = cached_movies[current_index]
    # PERF: when has no available trailer, makes requests repeatedly
    if not movie.trailer:
        trailer = await tmdb.get_movie_trailer(movie.id)
        if trailer:
            movie.trailer = trailer
            await movie.save(update_fields=("trailer",), force_update=True)
            if Movie.currently_trending_cache:
                Movie.currently_trending_cache[0][current_index].trailer = trailer
            User.last_trending_cache[user_id][current_index].trailer = trailer

    await query.message.edit_media(
        InputMediaPhoto(media=movie.poster_path),
    )
    await query.message.edit_caption(
        caption=format_movie(movie),
        reply_markup=paginator_markup(current_index, movie.id),
    )
    await query.answer()
