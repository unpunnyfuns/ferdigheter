# Contributing

## Add a skill

1. Copy the template: `cp -R skills/_template skills/<name>`.
2. Edit `skills/<name>/SKILL.md`. `name` must equal the folder name and be lowercase kebab-case. `description` is required, max 1024 chars.
3. For third-party skills, set `license` and `source`.
4. Regenerate the index:

   ```sh
   pip install -r requirements.txt
   python3 scripts/registry.py build
   ```

5. Commit the skill folder together with the regenerated `index.json` and `README.md`.

## Validate without writing

```sh
python3 scripts/registry.py validate
python3 scripts/registry.py build --check
```

## Tests

```sh
pytest
```
