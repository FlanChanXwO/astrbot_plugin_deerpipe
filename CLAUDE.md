# CLAUDE.md — astrbot_plugin_deerpipe

AstrBot plugin for daily check-ins, monthly calendars, yearly deer maps, and a static help image.

## Project overview

- **Language**: Python 3.10+
- **Framework**: AstrBot plugin system
- **Architecture**: layered `src/` layout with `domain/`, `application/`, `infrastructure/`, and `shared/`
- **Current focus**: stable check-in flows, calendar rendering, data import/export, and narrow plain-text triggers

## Communication language

Use Chinese for user-facing replies and project notes unless the user asks otherwise.

## Skills

Prefer the `astrbot-dev-skill` when modifying plugin hooks, config, commands, or rendering flow. It helps keep AstrBot API usage aligned with the current framework.

## Directory structure

```
main.py                  # Plugin entry point and AstrBot hooks/commands
metadata.yaml             # Plugin metadata and version
_conf_schema.json        # AstrBot config schema
CHANGELOG.md             # Release notes
src/
  domain/                # Entities, value objects, domain services
  application/           # Command handlers, services, presenters
  infrastructure/        # DB, config, cache, rendering, utilities
  shared/                # Constants, paths, shared helpers
templates/               # HTML/CSS templates for rendered images
resources/images/        # Bundled runtime image assets (characters, pipes, etc.)
assets/                  # README previews + runtime static help.png
scripts/                 # Dev-only helpers (e.g. gen_help_image.py)
tests/                   # pytest suites and mocks
```

## Key conventions

- Keep `main.py` thin; put business logic in `src/application` or `src/domain`.
- Store shared trigger patterns and constants in `src/shared/constants.py`.
- Plain-text command triggers must stay narrow and anchored. Add regression tests whenever matching rules change.
- Help image is a fixed file at `assets/help.png` (no t2i). After command surface changes, regenerate with `python scripts/gen_help_image.py`.
- Use `async def` for AstrBot handlers and public service methods that touch I/O.
- Keep `metadata.yaml`, `CHANGELOG.md`, and release-visible behavior in sync.

## Testing

- Preferred quick check: `python tests/run_tests.py --quick --no-install`
- Focused regression: `python -m pytest tests/test_plain_message_patterns.py -q`
- Lint/format: `python -m ruff check .` and `python -m ruff format .`

## Versioning and releases

- Use semantic versioning.
- Patch bumps are for bug fixes and trigger/validation corrections.
- Update `metadata.yaml` and add a new `## [X.Y.Z]` section in `CHANGELOG.md` for every release.
- Keep release notes concise and user-facing.
