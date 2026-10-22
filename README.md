# ferdigheter

Registry of agent skills in the [Agent Skills](https://agentskills.io) format. Agent-agnostic: anything that reads `SKILL.md` can use them.

## Structure

| Path | Purpose |
|---|---|
| `skills/<category>/<name>/` | One skill per folder, `SKILL.md` plus supporting files. Category is the parent folder |
| `skills/_template/` | Starting point for a new skill |
| `index.json` | Generated machine-readable index |
| `vendor.json` | Upstream repo, path, ref and last-synced commit for every vendored skill |
| `scripts/registry.py` | Validates skills, generates `index.json` and the table below, vendors and updates third-party skills |
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

<!-- index:start -->
### django

| Skill | Description | Tags |
|---|---|---|
| [cdrf-expert](skills/django/cdrf-expert/) | Expert guidance for Django REST Framework class-based views using Classy DRF (https://www.cdrf.co). Use when selecting or debugging APIView, GenericAPIView, concrete generic views, mixin combinations, or ViewSet/GenericViewSet/ModelViewSet behavior; tracing method resolution order (MRO); understanding which method to override (`create` vs `perform_create`, `update` vs `perform_update`, `destroy` vs `perform_destroy`, `get_queryset`, `get_serializer_class`); and comparing behavior across DRF versions. Do not use for function-based views, GraphQL, FastAPI/Flask, frontend work, or non-DRF backend frameworks. | django, drf, python, needs-network |
| [django-celery-expert](skills/django/django-celery-expert/) | Expert Django Celery guidance for asynchronous task processing. Use when designing background tasks, configuring Celery workers, handling task retries and errors, optimizing Celery performance, implementing periodic tasks with Celery Beat, or setting up production monitoring for Celery. Do not use for general Django questions unrelated to Celery, non-Celery task systems (Django Q, Huey, RQ), ML/data pipeline orchestration (Airflow, Prefect), or frontend and API-only concerns. Follows Vinta's Django Celery best practices. | django, celery, python |
| [django-expert](skills/django/django-expert/) | Expert Django backend development guidance. Use when creating Django models, views, serializers, or APIs; debugging ORM queries or migrations; optimizing database performance; implementing authentication; writing tests; or working with Django REST Framework. Follows Django best practices and modern patterns. | django, python |
| [django-reviewer](skills/django/django-reviewer/) | Review Django and Python changes for clarity, consistency, maintainability, ORM or DRF anti-patterns, and project conventions while preserving behavior. Use after Django code changes or when the user explicitly requests review. Report findings by default; apply refinements only when the user expresses explicit edit intent or the host has already authorized edits. | django, python, review |
| [django-safe-migration](skills/django/django-safe-migration/) | Write, review, and rewrite Django migrations for PostgreSQL with zero-downtime guarantees. Use this skill whenever the user mentions migrations, Django schema changes, or deployment safety — even if they don't say "zero downtime" explicitly. Trigger on: "review this migration", "is this migration safe?", "write a migration for...", "rewrite this migration", "how do I add a NOT NULL column / drop a column / add an index / rename a column / add a FK without downtime", "will this migration cause locks?", "this migration is blocking production". Covers: SeparateDatabaseAndState two-file splits, AddIndexConcurrently, FK NOT VALID + VALIDATE, db_default for NOT NULL columns, lock_timeout, and RunPython safety rules. | django, postgres, migrations, python |

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
2. Edit `skills/<category>/<name>/SKILL.md`. `name` must equal the folder name, lowercase kebab-case. `description` is required. For third-party skills use the `add` command instead, see [CONTRIBUTING.md](CONTRIBUTING.md).
3. Build the index:

   ```bash
   # install the runtime deps
   pip install -r requirements.txt
   # regenerate index.json and the README table
   python3 scripts/registry.py build
   ```

4. Commit the folder plus the regenerated `index.json` and `README.md`.

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
