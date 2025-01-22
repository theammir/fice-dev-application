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
    genre_ids: list[int]  # TODO: Genre list
    release_date: str
    average_rating: float  # vote_average
    vote_count: int

    @staticmethod
    def from_json(json: dict[str, Any]):
        # WARN: Throws KeyError, caller's job to handle
        return Movie(
            json["title"],
            json["original_title"],
            TMDB_IMAGE_ENDPOINT.format(
                json["poster_path"].strip("/")
            ),  # TODO: Handle missing poster
            json.get("overview") or "Опис не знайдено.",
            json.get("genre_ids") or [],
            json.get("release_date") or "відсутня",
            json.get("vote_average") or 0.0,
            json.get("vote_count") or 0,
        )


class TMDBException(Exception):
    def __init__(self, tmdb_status: int | None, message: str | None) -> None:
        self.tmdb_status = tmdb_status
        self.message = message


class TMDBSession:
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
                logging.info(f"[GET {code}] {endpoint} {params}")
            else:
                logging.error(f"[GET {code}] {endpoint} {params}")
                logging.error(json)
                raise TMDBException(json.get("status"), json.get("message"))

            return json

    async def search_movie(
        self, query: str, *, language: str = DEFAULT_LANGUAGE
    ) -> Movie | None:
        json = await self._get_json(
            TMDB_SEARCH_ENDPOINT, {"query": query, "language": language}
        )

        results = json.get("results")
        if not all((results, len(results), json.get("total_results"))):
            return None

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

        movies: list[Movie] = [Movie.from_json(r) for r in results]
        return movies
