.PHONY: check test

check:
	python -m ruff format --check .
	python -m ruff check .
	pyright

test:
	python -m pytest -q
