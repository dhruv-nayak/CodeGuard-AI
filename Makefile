.PHONY: install test lint check run smoke migrate
install:
	python -m pip install -r requirements.txt

test:
	pytest -q

lint:
	ruff check app tests alembic scripts

check:
	python -m compileall -q app scripts
	node --check app/static/app.js
	pytest -q

run:
	uvicorn app.main:app --reload

smoke:
	python scripts/smoke_test.py http://127.0.0.1:8000

migrate:
	alembic upgrade head
