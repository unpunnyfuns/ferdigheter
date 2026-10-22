# Contributing

## Add a skill

1. Copy the template: `cp -R skills/_template skills/<category>/<name>`.
2. Edit `skills/<category>/<name>/SKILL.md`. `name` must equal the folder name and be lowercase kebab-case. `description` is required, max 1024 chars.
3. Categories are folders under `skills/`. Reuse an existing one when it fits; create a new kebab-case folder otherwise. Skill names must be unique across categories.
4. For third-party skills, set `license` and `source`.
5. Regenerate the index:

   ```sh
   pip install -r requirements.txt
   python3 scripts/registry.py build
   ```

6. Commit the skill folder together with the regenerated `index.json` and `README.md`.

## Validate without writing

```sh
python3 scripts/registry.py validate
python3 scripts/registry.py build --check
```

## Tests

```sh
pytest
```
