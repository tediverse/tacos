# Repository Guidelines

## Project Structure & Module Organization

FastAPI boots from `app/main.py`, with runtime settings centralized in `app/config.py` and shared DB helpers in `app/db`. Keep HTTP concerns inside `app/routers/` (currently `posts.py`, `images.py`, `rag.py`) and delegate heavy lifting to the matching module under `app/services/`. SQLAlchemy tables live in `app/models`, while request/response contracts belong in `app/schemas`. Use `alembic/` for migrations, stash reference material in `docs/`, and mirror this layout under `tests/` (e.g., `tests/routers/test_posts.py`).

## Build, Test, and Development Commands

- `python -m venv .venv && source .venv/bin/activate` — create the virtualenv.
- `pip install -r requirements.txt` — install backend dependencies.
- `pip install -r requirements-dev.txt` — install dev/test dependencies.
- `cp .env.example .env` then fill CouchDB, Postgres, and API keys.
- `alembic upgrade head` — apply schema changes; pair with `alembic revision --autogenerate -m "message"` for new work.
- `uvicorn app.main:app --reload` — start the API locally with hot reload.

## Coding Style & Naming Conventions

Use 4-space indentation, Black-compatible wrapping, and type hints across routers, services, and schemas. Router callables should be imperative verbs (`create_post`, `query_rag`) and should only compose services plus response models. Pydantic types follow the `ThingPayload`/`ThingResponse` pattern in `app/schemas`. Keep environment lookups inside `config.py`, inject dependencies with FastAPI's `Depends`, and interact with external systems only inside service classes.

- Prefer dependency injection over module-level clients: avoid initializing CouchDB/Postgres/OpenAI at import time inside services; accept `db`/`parser`/clients as parameters (or via FastAPI `Depends`) so tests can pass fakes and imports stay side-effect free. Use `app.db.couchdb.get_couch()` to fetch `(couch_db, parser)` and `app.db.postgres.base.get_db` for Postgres sessions.
- For HTTP routes, keep the flow router → service → repo (lightweight, Pythonic). Inject services via FastAPI dependencies; tests override the service in one place.

## Security & Configuration Tips

Secrets stay in `.env`, loaded through `python-dotenv`; never hard-code `TACOS_API_KEY`, `OPENAI_API_KEY`, or database credentials. Use distinct CouchDB/Postgres users for local testing, rotate keys after schema deployments, and scrub logs before sharing them. When experimenting with Obsidian LiveSync, point the plugin at a scratch CouchDB database so production notes never leave your lab machine.

## Testing

- Activate the virtualenv before tests: `. .venv/bin/activate && pytest -q` (or keep the shell activated for repeated runs).
- Run tests with `pytest -q`; add `--cov` for coverage when needed.
- Avoid monkeypatching; prefer dependency injection. Refactor services to accept collaborators/config (e.g., base URLs, processors) as parameters so tests can pass fakes directly.
- Keep tests close to the code they cover (e.g., `tests/services`, `tests/routers`).
- Favor small, single-behavior tests; add shared fixtures in `tests/conftest.py` if needed.
- Routers follow a simple, Pythonic flow: router → service → repo. Inject services via FastAPI `Depends`; override the service in tests for easy isolation.
