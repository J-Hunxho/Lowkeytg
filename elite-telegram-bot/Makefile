.PHONY: install lint format type test run migrate webhook:set webhook:delete

UV ?= uv
PYTHON ?= python3.11

install:
	$(UV) pip install -r requirements.txt

lint:
	ruff check src tests

format:
	ruff format src tests
	ruff check --fix-only src tests
	ruff format --check src tests

type:
	mypy src

test:
	PYTHONPATH=src pytest -q

run:
	PYTHONPATH=src uvicorn app.web.api:app --reload --host 0.0.0.0 --port $${PORT:-8080}

migrate:
	PYTHONPATH=src alembic upgrade head

webhook:set:
	PYTHONPATH=src $(PYTHON) -m app.bootstrap set-webhook

webhook:delete:
	PYTHONPATH=src $(PYTHON) -m app.bootstrap delete-webhook
