.PHONY: install demo generate run-all test assets raw pack clean

install:
	uv sync --extra dev

demo: run-all

generate:
	uv run python -m demo generate

run-all:
	uv run python -m demo run-all

test:
	uv run pytest

assets:
	uv run python -m demo assets

raw:
	uv run python scripts/record_raw.py

pack:
	uv run python -m demo pack

all: run-all test assets pack

clean:
	uv run python -m demo clean
