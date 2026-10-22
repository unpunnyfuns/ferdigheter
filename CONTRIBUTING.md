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

1. Add an entry to `vendor.json` keyed `<category>/<name>` with `repo`, `path` (folder inside the upstream repo) and `ref` (branch or tag).
2. Run `python3 scripts/registry.py sync <category>/<name>`. This creates the folder and records the upstream commit. Do not run `validate` or `build` between steps 1 and 2; they will complain about the missing folder.
3. In `skills/<category>/<name>/SKILL.md` frontmatter, set `license` to an SPDX id, `source` to the upstream repo URL, and `tags`. Sync preserves these on later updates. Change nothing else in the folder.
4. If upstream ships no license file, add one named `LICENSE` with the license text and copyright holder. Sync keeps it.
5. Run `python3 scripts/registry.py build` and commit the folder, `vendor.json`, `index.json` and `README.md`.

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
