import logging
from typing import Any, Literal

import aiohttp
from aiohttp.client import ClientTimeout
from attr import dataclass

SESSION_TIMEOUT = ClientTimeout(total=10)
DEFAULT_LANGUAGE = "uk-UA"

TMDB_SEARCH_ENDPOINT = "https://api.themoviedb.org/3/search/movie"
TMDB_TRENDING_ENDPOINT = "https://api.themoviedb.org/3/trending/movie/{}"
TMDB_GENRE_LIST_ENDPOINT = "https://api.themoviedb.org/3/genre/movie/list"
TMDB_IMAGE_ENDPOINT = "https://image.tmdb.org/t/p/original/{}"


@dataclass
class Movie:
    title: str
    original_title: str
    poster_path: str
    overview: str
    genres: list[str]
    release_date: str
    average_rating: float  # vote_average
    vote_count: int

    @staticmethod
    def from_json(json: dict[str, Any]):
        # WARN: Throws KeyError, caller's job to handle
        genre_ids = json.get("genre_ids") or []
        genres = list(
            filter(
                lambda g: g,
                [TMDBSession.genre_table.get(g, "") for g in genre_ids],
            )
        )
        return Movie(
            json["title"],
            json["original_title"],
            TMDB_IMAGE_ENDPOINT.format(
                json["poster_path"].strip("/")
            ),  # TODO: Handle missing poster
            json.get("overview") or "Опис не знайдено.",
            genres,
            json.get("release_date") or "відсутня",
            json.get("vote_average") or 0.0,
            json.get("vote_count") or 0,
        )


class TMDBException(Exception):
    def __init__(self, tmdb_status: int | None, message: str | None) -> None:
        self.tmdb_status = tmdb_status
        self.message = message


class TMDBSession:
    genre_table: dict[int, str] = {}

    def __init__(self, api_token: str) -> None:
        self.__token = api_token
        self.__session = aiohttp.ClientSession(timeout=SESSION_TIMEOUT)

    async def _get_json(self, endpoint: str, params: dict[str, Any]):
        # WARN: Throws TMDBException, caller's job to handle
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.__token}",
        }
        async with self.__session.get(endpoint, headers=headers, params=params) as resp:
            code = resp.status
            json = await resp.json()

            if resp.ok:
                logging.info("[GET %d] %s %r", code, endpoint, params)
            else:
                logging.error("[GET %d] %s %r", code, endpoint, params)
                logging.error("%s", json)
                raise TMDBException(json.get("status"), json.get("message"))

            return json

    async def _init_genres(self, language: str = DEFAULT_LANGUAGE):
        if TMDBSession.genre_table:
            return

        json = await self._get_json(TMDB_GENRE_LIST_ENDPOINT, {"language": language})
        genres = json.get("genres")
        if not genres:
            return

        TMDBSession.genre_table = {g.get("id"): g.get("name") for g in genres}

    async def search_movie(
        self, query: str, *, language: str = DEFAULT_LANGUAGE
    ) -> Movie | None:
        json = await self._get_json(
            TMDB_SEARCH_ENDPOINT, {"query": query, "language": language}
        )

        results = json.get("results")
        if not all((results, len(results), json.get("total_results"))):
            return None

        await self._init_genres(language)
        return Movie.from_json(results[0])

    async def get_trending_movies(
        self,
        *,
        time_window: Literal["day", "week"],
        language: str = DEFAULT_LANGUAGE,
    ) -> list[Movie] | None:
        json = await self._get_json(
            TMDB_TRENDING_ENDPOINT.format(time_window), {"language": language}
        )
        results = json.get("results")
        if not all((results, len(results), json.get("total_results"))):
            return None

        await self._init_genres(language)
        movies: list[Movie] = [Movie.from_json(r) for r in results]
        return movies
