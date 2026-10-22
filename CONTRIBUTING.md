# Contributing

## Add a skill

1. Copy the template: `cp -R skills/_template skills/<category>/<name>`.
2. Edit `skills/<category>/<name>/SKILL.md`. `name` must equal the folder name and be lowercase kebab-case. `description` is required, max 1024 chars.
3. Categories are folders under `skills/`. Reuse an existing one when it fits; create a new kebab-case folder otherwise. Skill names must be unique across categories.
4. Add `tags` if useful. Use `needs-network` for skills that fetch from the web at runtime; this registry is mirrored to offline environments.
5. Regenerate the index:

   ```bash
   # install deps into .venv (needs Poetry, installed with pipx)
   poetry install
   # regenerate index.json and CATALOG.md
   poetry run python scripts/registry.py build
   ```

6. Commit the skill folder together with the regenerated `index.json` and `CATALOG.md`.

## Vendor a third-party skill

1. Vendor the upstream skill:

   ```bash
   # pull the skill, set its frontmatter, write a LICENSE and rebuild
   poetry run python scripts/registry.py add django/django-expert \
     --repo https://github.com/vintasoftware/django-ai-plugins \
     --path skills/django-expert --license MIT --tags django,python \
     --copyright "2025 Vinta Software"
   ```

   This writes the `vendor.json` entry, pulls the folder, sets `name`, `license`, `source` and `tags` in the frontmatter, writes a `LICENSE` file if upstream has none (templates in `scripts/licenses/`), and rebuilds. `name` comes from the key, so the skill can be renamed on the way in. Add `needs-network` to `--tags` if the skill fetches from the web at runtime.

2. Commit the folder, `vendor.json`, `index.json` and `CATALOG.md`.
3. Later updates: `poetry run python scripts/registry.py sync <category>/<name>`.

If `add` fails the closing build, it prints a cleanup hint; follow it, fix the cause, then run `add` again.

## Validate without writing

```bash
# check every skill and the manifest
poetry run python scripts/registry.py validate
# fail if index.json or CATALOG.md are out of date
poetry run python scripts/registry.py build --check
```

## Tests

```bash
# run the test suite
poetry run pytest
```

## Lint

```bash
# lint
poetry run ruff check scripts tests
# format
poetry run ruff format scripts tests
```
