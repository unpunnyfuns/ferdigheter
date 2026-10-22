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

1. Copy the upstream skill folder as-is into `skills/<category>/<name>`. Keep its supporting files.
2. In its `SKILL.md` frontmatter, set `license` to an SPDX id (`MIT`, `Apache-2.0`), `source` to the upstream repo URL, and `tags`. Change nothing else in the folder.
3. If the upstream folder has no license file, add one named `LICENSE` with the upstream license text and copyright holder.
4. Continue from step 5 above.

## Validate without writing

```sh
python3 scripts/registry.py validate
python3 scripts/registry.py build --check
```

## Tests

```sh
pytest
```
