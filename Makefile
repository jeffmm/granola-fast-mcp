build:
	uv sync --all-extras
test:
	uv run pytest tests/ -v
format:
	uv run ruff format src/ tests/
lint:
	uv run ruff check src/ tests/
