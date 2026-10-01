# Publish by updating the version and pushing a v<version> tag.
# .github/workflows/publish.yml checks, builds, and uploads to PyPI.
# GitHub Actions authenticates through PyPI Trusted Publishing; no local publish target is needed.

.PHONY: dev-install check clean build

dev-install:
	uv sync --extra dev

check:
	uv run --extra dev --locked python -m unittest discover -s tests
	uv run --extra dev --locked ruff check .
	uv run --extra dev --locked ruff format --check .

clean:
	rm -rf -- dist/ build/ src/calendargen.egg-info/

build:
	uv build --clear --no-sources
