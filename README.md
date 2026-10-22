# ferdigheter

Registry of agent skills in the [Agent Skills](https://agentskills.io) format. Agent-agnostic: anything that reads `SKILL.md` can use them.

## Structure

| Path | Purpose |
|---|---|
| `skills/<category>/<name>/` | One skill per folder, `SKILL.md` plus supporting files. Category is the parent folder |
| `skills/_template/` | Starting point for a new skill |
| `CATALOG.md` | Generated list of every skill by category |
| `index.json` | Generated machine-readable index |
| `vendor.json` | Upstream repo, path, ref and last-synced commit for every vendored skill |
| `scripts/registry.py` | Validates skills, generates `index.json` and `CATALOG.md`, vendors and updates third-party skills |
| `scripts/licenses/` | License templates used by `add` |

## Using a skill

Every skill is a folder with a `SKILL.md`, grouped by category.

1. Clone the repo:

   ```bash
   # clone the registry
   git clone https://github.com/<owner>/ferdigheter
   ```

2. Copy or symlink the skill folder into wherever your agent looks for skills.

### Hermes Agent

Hermes can add this repo as a tap:

```bash
# add this repo as a Hermes tap
hermes skills tap add <owner>/ferdigheter
```

Manual install:

1. Copy `skills/<category>/<name>` into `~/.hermes/skills/<category>/<name>` (global) or `.hermes/skills/<category>/<name>` (project). The layout maps one-to-one.
2. Project skills need `hermes skills trust` before they load.

### OpenCode

OpenCode scans these directories automatically, no config needed:

| Scope | Path |
|---|---|
| Global | `~/.config/opencode/skills/<name>` |
| Project | `.opencode/skills/<name>` |

OpenCode also recurses, so copying a whole category folder works too.

Or point `opencode.json` at a clone of this repo:

```jsonc
{ "skills": ["~/src/ferdigheter/skills"] }
```

### Claude Code and others

Copy `skills/<category>/<name>` into `~/.claude/skills/<name>` or `.claude/skills/<name>`. OpenCode and Hermes also scan `.agents/skills/`; Claude Code does not.

### Machine-readable index

```bash
# list every indexed skill
curl -s https://raw.githubusercontent.com/<owner>/ferdigheter/main/index.json | jq '.skills[] | {name, category, description, path}'
```

Each entry has `name`, `category`, `description`, `path`, and optionally `license`, `source`, `tags`, `metadata`.

## Skills

See [CATALOG.md](CATALOG.md) for the full list by category, or [index.json](index.json) for tooling.

## Adding a skill

1. `cp -R skills/_template skills/<category>/<name>`. Reuse an existing category folder or create a new kebab-case one.
2. Edit `skills/<category>/<name>/SKILL.md`. `name` must equal the folder name, lowercase kebab-case. `description` is required. For third-party skills use the `add` command instead, see [CONTRIBUTING.md](CONTRIBUTING.md).
3. Build the index:

   ```bash
   # install the runtime deps
   pip install -r requirements.txt
   # regenerate index.json and CATALOG.md
   python3 scripts/registry.py build
   ```

4. Commit the folder plus the regenerated `index.json` and `CATALOG.md`.

Details in [CONTRIBUTING.md](CONTRIBUTING.md).

## Updating vendored skills

New third-party skills are added with `add`; see CONTRIBUTING.

Needs network access; run it where you have it, then commit and push to the mirror.

```bash
# report entries with newer upstream commits
python3 scripts/registry.py sync --check
# sync every vendored skill
python3 scripts/registry.py sync
# sync one vendored skill
python3 scripts/registry.py sync web/vercel-react-best-practices
```

`sync` replaces the skill folder with upstream, records the commit in `vendor.json`, and rebuilds the index. It refuses to touch a folder with uncommitted changes.

The registry owns four frontmatter fields: `name`, `license`, `source` and `tags`. Sync keeps those values, plus a `LICENSE` file the registry added for an upstream that ships none. Everything else, `description`, `metadata` and any other key, comes from upstream and is overwritten on every sync.

`sync --check` only compares commits; it exits 1 when any entry has a newer upstream commit and 0 when all are current.

If a sync aborts partway, restore the affected skill with:

```bash
# restore the skill folder and the manifest
git checkout -- skills/<category>/<name> vendor.json
```

If an `add` stops partway, undo it by hand:

```bash
# remove the half-vendored folder
rm -rf skills/<category>/<name>
# then delete its entry from vendor.json
```
