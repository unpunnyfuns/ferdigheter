# ferdigheter

Registry of agent skills in the [Agent Skills](https://agentskills.io) format. Agent-agnostic: anything that reads `SKILL.md` can use them.

## Structure

| Path | Purpose |
|---|---|
| `skills/<name>/` | One skill per folder, `SKILL.md` plus supporting files |
| `skills/_template/` | Starting point for a new skill |
| `index.json` | Generated machine-readable index |
| `scripts/registry.py` | Validates skills, generates `index.json` and the table below |

## Using a skill

Every skill is a folder with a `SKILL.md`. Copy or symlink the folder into wherever your agent looks for skills.

```sh
git clone https://github.com/<owner>/ferdigheter
```

### Hermes Agent

Hermes installs straight from a GitHub path, or you can add this repo as a tap:

```sh
hermes skills install <owner>/ferdigheter/skills/<name>
hermes skills tap add <owner>/ferdigheter
```

Manual: copy into `~/.hermes/skills/<name>` (global) or `.hermes/skills/<name>` (project). Project skills need `hermes skills trust` before they load.

### OpenCode

OpenCode scans these directories automatically, no config needed:

| Scope | Path |
|---|---|
| Global | `~/.config/opencode/skills/<name>` |
| Project | `.opencode/skills/<name>` |

Or point `opencode.json` at a clone of this repo:

```jsonc
{ "skills": ["~/src/ferdigheter/skills"] }
```

### Claude Code and others

Copy into `~/.claude/skills/<name>` or `.claude/skills/<name>`. OpenCode and Hermes also read `.agents/skills/<name>`, so that path works for all three.

### Machine-readable index

```sh
curl -s https://raw.githubusercontent.com/<owner>/ferdigheter/main/index.json | jq '.skills[] | {name, description, path}'
```

Each entry has `name`, `description`, `path`, and optionally `license`, `source`, `tags`, `metadata`.

## Skills

<!-- index:start -->
| Skill | Description | Tags |
|---|---|---|
| [vercel-composition-patterns](skills/vercel-composition-patterns/) | React composition patterns that scale. Use when refactoring components with boolean prop proliferation, building flexible component libraries, or designing reusable APIs. Triggers on tasks involving compound components, render props, context providers, or component architecture. Includes React 19 API changes. | react, architecture, components |
| [vercel-react-best-practices](skills/vercel-react-best-practices/) | React and Next.js performance optimization guidelines from Vercel Engineering. This skill should be used when writing, reviewing, or refactoring React/Next.js code to ensure optimal performance patterns. Triggers on tasks involving React components, Next.js pages, data fetching, bundle optimization, or performance improvements. | react, nextjs, performance |
| [web-design-guidelines](skills/web-design-guidelines/) | Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices". | ui, accessibility, review |
<!-- index:end -->

## Adding a skill

1. `cp -R skills/_template skills/<name>`
2. Edit `skills/<name>/SKILL.md`. `name` must equal the folder name, lowercase kebab-case. `description` is required. Third-party skills get `license` and `source`.
3. `pip install -r requirements.txt && python3 scripts/registry.py build`
4. Commit the folder plus the regenerated `index.json` and `README.md`.

Details in [CONTRIBUTING.md](CONTRIBUTING.md).
