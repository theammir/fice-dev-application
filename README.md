<div align="center"><h1>FICE Dev Test Bot</h1></div>

This Telegram bot is a tesk task application, powered by [`aiogram`](https://github.com/aiogram/aiogram) v3, [`tortoise-orm`](https://github.com/tortoise/tortoise-orm) and a simple async TMDB wrapper.

## Features ✨

### _/start_: the menu

* Takes you straight into action, no typing needed.
![image](https://github.com/user-attachments/assets/cab4f56e-b5d0-4066-bd24-28df55e047ec)

### _/search_

* Find movies by name, any language. Get a short summary, along with the trailer link, if available.
![image](https://github.com/user-attachments/assets/a6ce54df-aafd-4956-b1bd-1d79c44d1a6a)

### _/trending_

* Get a paginated preview of current trending movies.
![image](https://github.com/user-attachments/assets/5818c3fe-8bbc-4376-97bd-99b64b4cca24)

### _/favourites_ and ⭐️

* Add any movie you see to your personal favourites. View them in a concise list.
![image](https://github.com/user-attachments/assets/1ae0a3d5-d772-48cf-973d-7c91b44461a6)

## Thought out stuff 🟢

* 🟢 API responses are saved to both the database and in-memory LRU/TTL cache to avoid frequent refetching.
* 🟢 The user flow is designed to be as minimally annoying as possible, both in DMs and public chats.
* 🟢 Proper error and timeout handling. It gets the job done, at least.
* 🟢 [Rich](https://github.com/Textualize/rich) logging
* 🟢 No third-party synchronous TMDB API wrappers used.
* 🟢 API responses. I don't trust them, _at all!_ <sub>[(c)](https://youtube.com/clip/UgkxkqxKvQZOgCwbY_9ea8SJEuz2kQwHLH6t?si=DTQAujlA3W0FsxJT)</sub>
A lot of stuff is `None`-checked and otherwise validated.

## Not that thought out 🔴

* 🔴 The output of _/favourites_ can exceed the character limit at some point, so I probably should've introduced a paginator.
* 🔴 `DB_URL` variable should be split into multiple components, the password being one of them.
I don't feel like installing postgres, though, so I won't bother.

## Setup

Rename `.env.example` to `.env` and set the following variables:
* `BOT_TOKEN` (ask [@BotFather](https://t.me/BotFather))
* `TMDB_AUTH_TOKEN` (you can get one [here](https://www.themoviedb.org/settings/api), you need the long one)
* `DB_URL` (the default is fine)

The project uses the [uv](https://github.com/astral-sh/uv) manager.
If you have it installed, just `run` the main file.
```bash
$ uv run src/main.py
```
It will automatically create a virtual environment and install the dependencies.

Otherwise, you can do it manually
```bash
$ python -m venv .venv
$ . .venv/bin/activate
(.venv) $ pip install .
(.venv) $ python src/main.py
```

To run with a custom log level once, use `LOG`:
```bash
$ LOG=debug uv run src/main.py
(.venv) $ LOG=debug python src/main.py
```
For persistence, change the default inside `.env`.
