# Contributing

## Add a skill

1. Copy the template: `cp -R skills/_template skills/<category>/<name>`.
2. Edit `skills/<category>/<name>/SKILL.md`. `name` must equal the folder name and be lowercase kebab-case. `description` is required, max 1024 chars.
3. Categories are folders under `skills/`. Reuse an existing one when it fits; create a new kebab-case folder otherwise. Skill names must be unique across categories.
4. Add `tags` if useful. Use `needs-network` for skills that fetch from the web at runtime; this registry is mirrored to offline environments.
5. Regenerate the index:

   ```sh
   pip install -r requirements.txt
   python3 scripts/registry.py build
   ```

6. Commit the skill folder together with the regenerated `index.json` and `README.md`.

## Vendor a third-party skill

```sh
python3 scripts/registry.py add django/django-expert \
  --repo https://github.com/vintasoftware/django-ai-plugins \
  --path skills/django-expert --license MIT --tags django,python \
  --copyright "2025 Vinta Software"
```

This writes the `vendor.json` entry, pulls the folder, sets `license`, `source` and `tags` in the frontmatter, writes a `LICENSE` file if upstream has none (templates in `scripts/licenses/`), and rebuilds. Add `needs-network` to `--tags` if the skill fetches from the web at runtime. Then commit the folder, `vendor.json`, `index.json` and `README.md`.

Later updates: `python3 scripts/registry.py sync <category>/<name>`.

## Validate without writing

```sh
python3 scripts/registry.py validate
python3 scripts/registry.py build --check
```

## Tests

```sh
pytest
```

## Lint

```sh
pip install -r requirements-dev.txt
ruff check scripts tests
ruff format scripts tests
```
