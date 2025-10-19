.PHONY: install lint format type test run migrate webhook:set webhook:delete

UV?=uv
PYTHON?=python3.11

install:
$(UV) pip install -r requirements.txt

lint:
ruff check src tests

format:
ruff format src tests
ruff check --fix-only src tests
ruff format --check src tests
ruff format src tests

type:
mypy src

test:
pytest -q

run:
UVICORN_PORT=$${PORT:-8000} uvicorn src.app.web.api:app --reload --host 0.0.0.0 --port $${PORT:-8000}

migrate:
alembic upgrade head

webhook:set:
$(PYTHON) -m src.app.bootstrap set-webhook

webhook:delete:
$(PYTHON) -m src.app.bootstrap delete-webhook
