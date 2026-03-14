# prcat

**AI-powered PR reviewer — understand any pull request in seconds.**

```
$ prcat https://github.com/django/django/pull/17842

PR #17842: Fix queryset annotation with complex expressions
django/django  feature/fix-annotation → main  +85/-12  6 file(s)

Verdict: Needs minor changes ⚠️

## Summary
This PR fixes a bug where annotating a queryset with complex F() expressions
containing subqueries would fail under certain database backends...

## Concerns
- [WARNING] src/db/models/sql/compiler.py L342
  The fallback path for non-standard backends isn't covered by tests.

## Questions for author
- Does this fix apply to GROUP BY queries with aggregates?

## Suggested review comment
The fix looks correct. I'd like to see a test for the SQLite fallback path
before merging. Otherwise LGTM.
```

## Install

```bash
pip install prcat
```

Set an API key (or use Ollama for local, free review):

```bash
export ANTHROPIC_API_KEY=your-key     # Claude (default)
export OPENAI_API_KEY=your-key        # or OpenAI
# or use --provider ollama             # local, no API key needed
```

Authenticate with GitHub (required to fetch private PRs):

```bash
gh auth login   # uses gh CLI — recommended
# or: export GITHUB_TOKEN=your-token
```

## Usage

```bash
# Review by PR number (auto-detects repo from git remote)
prcat 42

# Explicit repo
prcat owner/repo#42

# Full URL
prcat https://github.com/owner/repo/pull/42

# Review styles
prcat 42 --style summary    # just summarize the PR
prcat 42 --style risks      # focus on risks only
prcat 42 --style review     # full review (default)

# Use different AI providers
prcat 42 --provider openai
prcat 42 --provider ollama --model qwen2.5:7b

# Copy review to clipboard
prcat 42 --copy

# Save to file
prcat 42 --output review.md

# Compact mode (for CI / scripts)
prcat 42 --compact          # exits 1 if CRITICAL issues found
```

## Options

| Flag | Description |
|------|-------------|
| `--style` | `review` (default), `summary`, or `risks` |
| `--provider` | `claude` (default), `openai`, `ollama` |
| `--model` | Override default model |
| `--no-comments` | Skip fetching existing PR comments |
| `--compact` | One-line output, exit 1 on CRITICAL |
| `--copy` | Copy review to clipboard |
| `--output FILE` | Save review to file |

## Use in CI

Exit code `1` when the AI finds CRITICAL issues — perfect for CI gates:

```yaml
# .github/workflows/pr-review.yml
- name: AI PR review
  run: prcat ${{ github.event.pull_request.number }} --compact
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Developer workflow

prcat fills the missing piece in the git-workflow toolkit:

```bash
# Start the day
standup-ai                          # generate standup from git commits

# Before you push
critiq                              # review YOUR own changes before pushing
testfix pytest                      # 3. Auto-fix failing tests

# When you submit a PR
gpr                                 # generate PR description + commit message

# When you review a teammate's PR  ← prcat fits here
prcat 42                            # AI-assisted review of their changes

# After merging
gitbrief --changed-only             # pack context for LLM
changelog-ai v1.0.0 v1.1.0         # generate CHANGELOG
chronicle repo                      # understand the story behind changes
```

| Tool | When | What it does |
|------|------|-------------|
| [standup-ai](https://github.com/faw21/standup-ai) | Morning | Generate daily standup from commits |
| [critiq](https://github.com/faw21/critiq) | Before push | Review YOUR own code |
| [gpr](https://github.com/faw21/gpr) | Commit/PR | Generate PR descriptions + commit messages |
| **prcat** | PR review | Review TEAMMATES' pull requests |
| [gitbrief](https://github.com/faw21/gitbrief) | PR prep | Pack codebase context for LLMs |
| [changelog-ai](https://github.com/faw21/changelog-ai) | Release | Generate CHANGELOG from git history |
| [chronicle](https://github.com/faw21/chronicle) | Explore | Understand stories behind git history |

## Default models

| Provider | Default model |
|----------|--------------|
| Claude | `claude-haiku-4-5` |
| OpenAI | `gpt-4o-mini` |
| Ollama | `qwen2.5:1.5b` |

Override with `--model`:
```bash
prcat 42 --provider claude --model claude-sonnet-4-5   # deeper review
prcat 42 --provider openai --model gpt-4o               # OpenAI GPT-4o
prcat 42 --provider ollama --model qwen2.5:7b           # larger local model
```

- [difftests](https://github.com/faw21/difftests) — AI test generator from git diffs

- [critiq-action](https://github.com/faw21/critiq-action) — critiq as a GitHub Action for CI

- [testfix](https://github.com/faw21/testfix) — AI failing test auto-fixer

- [mergefix](https://github.com/faw21/mergefix) — AI merge conflict resolver: fix all conflicts with one command

## License

MIT — free for personal and commercial use.
