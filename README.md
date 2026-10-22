# ferdigheter

Registry of agent skills in the [Agent Skills](https://agentskills.io) format. Agent-agnostic: anything that reads `SKILL.md` can use them.

## Structure

| Path | Purpose |
|---|---|
| `skills/<category>/<name>/` | One skill per folder, `SKILL.md` plus supporting files. Category is the parent folder |
| `skills/_template/` | Starting point for a new skill |
| `index.json` | Generated machine-readable index |
| `vendor.json` | Upstream repo, path, ref and last-synced commit for every vendored skill |
| `scripts/registry.py` | Validates skills, generates `index.json` and the table below |

## Using a skill

Every skill is a folder with a `SKILL.md`, grouped by category. Copy or symlink the skill folder into wherever your agent looks for skills.

```sh
git clone https://github.com/<owner>/ferdigheter
```

### Hermes Agent

Hermes can add this repo as a tap:

```sh
hermes skills tap add <owner>/ferdigheter
```

Manual: copy `skills/<category>/<name>` into `~/.hermes/skills/<category>/<name>` (global) or `.hermes/skills/<category>/<name>` (project). The layout maps one-to-one. Project skills need `hermes skills trust` before they load.

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

```sh
curl -s https://raw.githubusercontent.com/<owner>/ferdigheter/main/index.json | jq '.skills[] | {name, category, description, path}'
```

Each entry has `name`, `category`, `description`, `path`, and optionally `license`, `source`, `tags`, `metadata`.

## Skills

<!-- index:start -->
### mcp

| Skill | Description | Tags |
|---|---|---|
| [mcp-builder](skills/mcp/mcp-builder/) | Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript (MCP SDK). | mcp, python, typescript, needs-network |

### web

| Skill | Description | Tags |
|---|---|---|
| [vercel-composition-patterns](skills/web/vercel-composition-patterns/) | React composition patterns that scale. Use when refactoring components with boolean prop proliferation, building flexible component libraries, or designing reusable APIs. Triggers on tasks involving compound components, render props, context providers, or component architecture. Includes React 19 API changes. | react, architecture, components |
| [vercel-react-best-practices](skills/web/vercel-react-best-practices/) | React and Next.js performance optimization guidelines from Vercel Engineering. This skill should be used when writing, reviewing, or refactoring React/Next.js code to ensure optimal performance patterns. Triggers on tasks involving React components, Next.js pages, data fetching, bundle optimization, or performance improvements. | react, nextjs, performance |
| [web-design-guidelines](skills/web/web-design-guidelines/) | Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices". | ui, accessibility, review, needs-network |
<!-- index:end -->

## Adding a skill

1. `cp -R skills/_template skills/<category>/<name>`. Reuse an existing category folder or create a new kebab-case one.
2. Edit `skills/<category>/<name>/SKILL.md`. `name` must equal the folder name, lowercase kebab-case. `description` is required. Third-party skills get `license` and `source`.
3. `pip install -r requirements.txt && python3 scripts/registry.py build`
4. Commit the folder plus the regenerated `index.json` and `README.md`.

Details in [CONTRIBUTING.md](CONTRIBUTING.md).

## Updating vendored skills

Needs network access; run it where you have it, then commit and push to the mirror.

```sh
python3 scripts/registry.py sync --check
python3 scripts/registry.py sync
python3 scripts/registry.py sync web/vercel-react-best-practices
```

`sync` replaces the skill folder with upstream, keeps the registry's `license`, `source` and `tags` frontmatter and any `LICENSE` file upstream lacks, records the commit in `vendor.json`, and rebuilds the index. It refuses to touch a folder with uncommitted changes.
