.PHONY: install run-bot run-api format lint test

install:
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

run-bot:
python -m bot.main

run-api:
uvicorn api.app:app --reload --port 8000

format:
ruff format .

lint:
ruff check .

test:
pytest
