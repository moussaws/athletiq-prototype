.PHONY: help install install-cv install-dev lint format typecheck test test-cov run api web demo seed docker-up docker-down clean

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
UVICORN ?= $(PYTHON) -m uvicorn

help:
	@echo "AthletIQ prototype targets:"
	@echo "  make install        install core python deps"
	@echo "  make install-dev    + dev deps (ruff, mypy, pytest)"
	@echo "  make install-cv     + CV deps (torch, ultralytics, supervision)"
	@echo "  make lint           ruff check"
	@echo "  make format         ruff format"
	@echo "  make typecheck      mypy"
	@echo "  make test           pytest (skips CV/slow)"
	@echo "  make test-cov       pytest with coverage"
	@echo "  make api            run FastAPI locally"
	@echo "  make web            run Next.js dashboard locally"
	@echo "  make seed           seed synthetic players + sample match"
	@echo "  make demo           full end-to-end demo pipeline"
	@echo "  make docker-up      docker-compose up --build"
	@echo "  make docker-down    docker-compose down"

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

install-cv:
	$(PIP) install -e ".[dev,cv,statsbomb]"

lint:
	$(PYTHON) -m ruff check src tests

format:
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check --fix src tests

typecheck:
	$(PYTHON) -m mypy src/athletiq

test:
	$(PYTHON) -m pytest -q

test-cov:
	$(PYTHON) -m pytest --cov=src/athletiq --cov-report=term-missing --cov-report=xml

api:
	$(UVICORN) athletiq.api.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd web && pnpm dev

seed:
	$(PYTHON) -m athletiq.cli seed

demo:
	$(PYTHON) -m athletiq.cli demo

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
