import logging
from typing import Any, Literal

import aiohttp
from aiohttp.client import ClientTimeout

from db.models import Movie

SESSION_TIMEOUT = ClientTimeout(total=10)
DEFAULT_LANGUAGE = "uk-UA"

TMDB_SEARCH_ENDPOINT = "https://api.themoviedb.org/3/search/movie"
TMDB_TRENDING_ENDPOINT = "https://api.themoviedb.org/3/trending/movie/{}"
TMDB_DETAILS_ENDPOINT = "https://api.themoviedb.org/3/movie/{}"
TMDB_GENRE_LIST_ENDPOINT = "https://api.themoviedb.org/3/genre/movie/list"
TMDB_IMAGE_ENDPOINT = "https://image.tmdb.org/t/p/original/{}"

POSTER_PLACEHOLDER_PATH = "https://placehold.co/550x825"


class TMDBException(Exception):
    def __init__(self, tmdb_status: int | None, message: str | None) -> None:
        self.tmdb_status = tmdb_status
        self.message = message


class TMDBSession:
    __genres_table: dict[int, str] = {}

    def __init__(self, api_token: str) -> None:
        self.__token = api_token
        self.__session = aiohttp.ClientSession(timeout=SESSION_TIMEOUT)

    @staticmethod
    def genre_name_of(id: int, default: Any) -> str | Any:
        return TMDBSession.__genres_table.get(id, default)

    async def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
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
                if resp.status == 404:
                    return {}
                logging.error("[GET %d] %s %r", code, endpoint, params)
                logging.error("%s", json)
                raise TMDBException(json.get("status"), json.get("message"))

            return json

    async def preload_genres(self, language: str = DEFAULT_LANGUAGE):
        json = await self._get_json(TMDB_GENRE_LIST_ENDPOINT, {"language": language})
        genres = json.get("genres")
        if not genres:
            raise RuntimeError("api didn't return valid genres list")

        TMDBSession.__genres_table = {
            id: name for g in genres if all([id := g.get("id"), name := g.get("name")])
        }

    def _format_movie_poster(self, movie: dict[str, Any]):
        if poster_path := movie.get("poster_path"):
            movie["poster_path"] = TMDB_IMAGE_ENDPOINT.format(poster_path)
        else:
            movie["poster_path"] = POSTER_PLACEHOLDER_PATH
        return movie

    async def get_movie_by_id(
        self, id: int, language: str = DEFAULT_LANGUAGE
    ) -> Movie | None:
        json = await self._get_json(
            TMDB_DETAILS_ENDPOINT.format(id), params={"language": language}
        )

        if not json:
            return None
        if json.get("genres"):
            json["genre_ids"] = list(
                filter(lambda id: id is not None, [g.get("id") for g in json["genres"]])
            )

        return await Movie.from_dict(self._format_movie_poster(json), False)

    async def search_movie(
        self, query: str, *, language: str = DEFAULT_LANGUAGE
    ) -> Movie | None:
        json = await self._get_json(
            TMDB_SEARCH_ENDPOINT, {"query": query, "language": language}
        )

        results = json.get("results")
        if not all(  # using one huge boolean properly asserts types, but i am not doing that
            (
                results,
                isinstance(results, list),
                len(results),  # type: ignore
                json.get("total_results"),
            )
        ):
            return None

        return await Movie.from_dict(self._format_movie_poster(results[0]))  # type: ignore

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
        if not all(
            (
                results,
                isinstance(results, list),
                len(results),  # type: ignore
                json.get("total_results"),
            )
        ):
            return None

        movies: list[Movie] = [
            await Movie.from_dict(self._format_movie_poster(r))
            for r in results  # type: ignore
        ]
        return movies
