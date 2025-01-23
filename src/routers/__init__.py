from .error import router as error_router
from .favourites import router as favourites_router
from .movie import router as movie_router
from .start import router as start_router

__all__ = ("error_router", "favourites_router", "movie_router", "start_router")
