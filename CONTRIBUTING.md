# Contributing

## Add a skill

1. Copy the template: `cp -R skills/_template skills/<category>/<name>`.
2. Edit `skills/<category>/<name>/SKILL.md`. `name` must equal the folder name and be lowercase kebab-case. `description` is required, max 1024 chars.
3. Categories are folders under `skills/`. Reuse an existing one when it fits; create a new kebab-case folder otherwise. Skill names must be unique across categories.
4. Add `tags` if useful. Use `needs-network` for skills that fetch from the web at runtime; this registry is mirrored to offline environments.
5. Regenerate the index:

   ```bash
   # install the runtime deps
   pip install -r requirements.txt
   # regenerate index.json and CATALOG.md
   python3 scripts/registry.py build
   ```

6. Commit the skill folder together with the regenerated `index.json` and `CATALOG.md`.

## Vendor a third-party skill

1. Vendor the upstream skill:

   ```bash
   # pull the skill, set its frontmatter, write a LICENSE and rebuild
   python3 scripts/registry.py add django/django-expert \
     --repo https://github.com/vintasoftware/django-ai-plugins \
     --path skills/django-expert --license MIT --tags django,python \
     --copyright "2025 Vinta Software"
   ```

   This writes the `vendor.json` entry, pulls the folder, sets `name`, `license`, `source` and `tags` in the frontmatter, writes a `LICENSE` file if upstream has none (templates in `scripts/licenses/`), and rebuilds. `name` comes from the key, so the skill can be renamed on the way in. Add `needs-network` to `--tags` if the skill fetches from the web at runtime.

2. Commit the folder, `vendor.json`, `index.json` and `CATALOG.md`.
3. Later updates: `python3 scripts/registry.py sync <category>/<name>`.

If `add` fails the closing build, it prints a cleanup hint; follow it, fix the cause, then run `add` again.

## Validate without writing

```bash
# check every skill and the manifest
python3 scripts/registry.py validate
# fail if index.json or CATALOG.md are out of date
python3 scripts/registry.py build --check
```

## Tests

```bash
# run the test suite
pytest
```

## Lint

```bash
# install the dev deps
pip install -r requirements-dev.txt
# lint
ruff check scripts tests
# format
ruff format scripts tests
```
