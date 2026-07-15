# Repository Guidelines

## Project Structure & Module Organization

This repository is an AstrBot plugin. `main.py` is the plugin entry point and wires AstrBot handlers to application services. Core code lives under `src/` using a layered layout: `domain/` for entities and business data builders, `application/` for commands, services, and presenters, `infrastructure/` for persistence, rendering, config, cache, and HTTP utilities, and `shared/` for constants and paths. HTML/CSS render templates are in `templates/`; bundled images are in `resources/images/`; README preview assets are in `assets/`. Tests and mocks live in `tests/`.

## Build, Test, and Development Commands

- `python -m pip install -r requirements.txt`: install runtime dependencies such as `aiosqlite` and `jinja2`; image rendering uses AstrBot's built-in network t2i service and does not require local Playwright.
- `python tests/run_tests.py --quick --no-install`: run the curated standalone test suite without installing missing tools.
- `python -m pytest tests/test_plain_message_patterns.py -q`: run a focused regression test file.
- `python -m ruff check .` and `python -m ruff format .`: lint and format Python code.
- `pre-commit run --all-files`: run whitespace, YAML, Ruff, and Ruff format hooks before submitting changes.

## Coding Style & Naming Conventions

Use Python 3.10+ syntax and type hints for public functions. Follow Ruff formatting, four-space indentation, and existing async handler style. Keep `main.py` focused on registration and orchestration; move business logic into `src/application` or `src/domain`. Use `snake_case` for modules, functions, variables, and test files; use `PascalCase` for classes. Keep plugin constants in `src/shared/constants.py`.

## Testing Guidelines

Tests use `pytest`. Prefer small regression tests for command parsing, data validation, and service behavior. Name test files `test_*.py` and test functions `test_*`. Add mocks under `tests/mocks/` rather than depending on a live AstrBot instance when possible. When changing command matching, include explicit positive and negative trigger cases.

## Commit & Pull Request Guidelines

Git history follows conventional prefixes such as `feat(...)`, `fix:`, `chore:`, `style(...)`, and `docs:`. Keep commits scoped and describe the user-visible behavior change. PRs should include a concise summary, linked issues when applicable, test commands run, and screenshots or generated preview images for rendering/template changes.

## Security & Configuration Tips

Do not hardcode secrets, provider IDs, or user-specific paths. Add configurable plugin options to `_conf_schema.json`, keep `metadata.yaml` and README behavior in sync, and avoid committing runtime data from `data/` or cache output.
