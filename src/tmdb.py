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
TMDB_VIDEOS_ENDPOINT = "https://api.themoviedb.org/3/movie/{}/videos"
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

    def _is_results_valid(self, results: list[dict[str, Any]] | Any) -> bool:
        return bool(results) and isinstance(results, list) and bool(len(results))

    def _filter_trailers(
        self, results: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]]:
        if not self._is_results_valid(results):
            return []
        return sorted(
            [
                video
                for video in results  # type: ignore
                if (type := video.get("type")) and type.lower() == "trailer"
                if (site := video.get("site")) and site.lower() == "youtube"
                if video.get("official")
            ],
            key=lambda video: video.get("size") or 0,
            reverse=True,
        )

    def _trailer_from_results(self, results: list[dict[str, Any]] | None) -> str | None:
        trailer_list = self._filter_trailers(results)
        if not trailer_list:
            return None

        key = trailer_list[0].get("key")
        return f"https://youtube.com/watch?v={key}" if key else None

    async def get_movie_trailer(
        self, id: int, language: str = DEFAULT_LANGUAGE
    ) -> str | None:
        json = await self._get_json(
            TMDB_VIDEOS_ENDPOINT.format(id), params={"language": language}
        )
        if (
            not (trailer := self._trailer_from_results(json.get("results")))  # type: ignore
            and language != "en-US"
        ):
            return await self.get_movie_trailer(id, language="en-US")

        return trailer

    async def get_movie_by_id(
        self, id: int, language: str = DEFAULT_LANGUAGE
    ) -> Movie | None:
        json = await self._get_json(
            TMDB_DETAILS_ENDPOINT.format(id),
            params={"append_to_response": "videos", "language": language},
        )

        if not json:
            return None

        if json.get("genres"):
            json["genre_ids"] = list(
                filter(lambda id: id is not None, [g.get("id") for g in json["genres"]])
            )

        if (videos := json.get("videos")) and (results := videos.get("results")):
            json["trailer"] = self._trailer_from_results(
                results
            ) or await self.get_movie_trailer(json["id"], language="en-US")

        return await Movie.from_dict(self._format_movie_poster(json), False)

    async def search_movie(
        self, query: str, *, language: str = DEFAULT_LANGUAGE
    ) -> Movie | None:
        movie_json = await self._get_json(
            TMDB_SEARCH_ENDPOINT, {"query": query, "language": language}
        )
        movie_results = movie_json.get("results")
        if not all(
            (self._is_results_valid(movie_results), movie_json.get("total_results"))
        ):
            return None
        movie = movie_results[0]  # type: ignore
        movie["trailer"] = await self.get_movie_trailer(movie["id"])

        return await Movie.from_dict(self._format_movie_poster(movie))

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
        if not all((self._is_results_valid(results), json.get("total_results"))):
            return None

        movies: list[Movie] = [
            await Movie.from_dict(self._format_movie_poster(r))
            for r in results  # type: ignore
        ]
        return movies
