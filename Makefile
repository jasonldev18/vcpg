# Recipes avoid shell syntax so they run the same under sh and Windows cmd.
ifeq ($(OS),Windows_NT)
  PY := .venv/Scripts/python.exe
  BOOTSTRAP := py -3.12
else
  PY := .venv/bin/python
  BOOTSTRAP := python3.12
endif

.PHONY: setup dev test lint live

setup:
	$(BOOTSTRAP) -m venv .venv
	$(PY) -m pip install -e .[dev]
	npm --prefix frontend ci

dev:
	$(PY) scripts/dev.py

test:
	$(PY) -m pytest
	npm --prefix frontend test

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(PY) -m mypy
	npm --prefix frontend run lint

live:
	$(PY) -m pytest -m live
