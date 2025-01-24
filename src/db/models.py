from datetime import datetime
from typing import Any

from cachetools import LRUCache
from tortoise import fields
from tortoise.models import Model


class Genre(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=256)

    cache = LRUCache(maxsize=1024)

    @staticmethod
    async def by_id(genre_id: int) -> "Genre | None":
        return Genre.cache.get(genre_id) or (await Genre.get_or_none(id=genre_id))


class Movie(Model):
    id = fields.IntField(primary_key=True)
    title = fields.CharField(max_length=256)
    original_title = fields.CharField(max_length=256)
    overview = fields.TextField()
    poster_path = fields.CharField(max_length=256)
    genre_ids = fields.JSONField(field_type=list[int])
    release_date = fields.DateField()
    average_rating = fields.FloatField()
    vote_count = fields.IntField()

    @staticmethod
    async def from_dict(data: dict[str, Any]) -> "Movie":
        return (
            await Movie.update_or_create(
                id=data["id"],
                title=data.get("title") or data["original_title"],
                original_title=data.get("original_title") or data["title"],
                overview=data.get("overview") or "Опис не знайдено.",
                poster_path=data["poster_path"],
                genre_ids=data.get("genre_ids") or [],
                release_date=datetime.strptime(
                    data.get("release_date") or "1970-01-01", "%Y-%m-%d"
                ),
                average_rating=data.get("vote_average") or 0.0,
                vote_count=data.get("vote_count") or 0,
            )
        )[0]


class User(Model):
    id = fields.IntField(primary_key=True)
    favourites = fields.ManyToManyField("models.Movie", related_name="favourite_of")
    last_trending = fields.ManyToManyField(
        "models.Movie", related_name="last_trending_of"
    )

    trending_cache = LRUCache(maxsize=1024)
    favourites_cache = LRUCache(maxsize=1024)

    @staticmethod
    async def by_id(user_id: int) -> "User":
        return (await User.get_or_create(id=user_id))[0]
