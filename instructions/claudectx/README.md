# claudectx — Token Audit & Optimization CLI

## What it does

CLI tool that audits what Claude Code loads per session and automatically optimizes it. Reported 80% token reduction on large projects.

## Links

- **Repo**: https://github.com/Horilla/claudectx (MIT license)
- **Website**: https://claudectx.horilla.com
- **NPM**: `claudectx`

## Install

```bash
# Try immediately (no install)
npx claudectx analyze

# Install globally
npm install -g claudectx

# Homebrew (macOS/Linux)
brew tap Horilla/claudectx && brew install claudectx
```

## Key commands

### Analyze (run this first)

```bash
npx claudectx analyze
```

Shows token breakdown per source (CLAUDE.md, open files, history, MCP results) and detects waste patterns.

### Optimize

```bash
claudectx optimize --apply
```

Automatically:
1. Splits CLAUDE.md into lean core + demand-loaded `@file` sections (under 2K tokens)
2. Generates `.claudeignore` for common patterns
3. Strips cache-busting content (timestamps, session notes)

### Other useful commands

| Command | Purpose |
|---------|---------|
| `claudectx watch` | Live terminal dashboard — token burn, cache hits, most-read files |
| `claudectx compress` | Distill session into MEMORY.md (8K → 150-200 tokens) |
| `claudectx report` | 7/30-day analytics (cost, cache hits, waste) |
| `claudectx budget "**/*.py"` | Estimate token cost before running a task |
| `claudectx drift` | Find stale/dead references in CLAUDE.md |
| `claudectx warmup` | Pre-warm Anthropic prompt cache |
| `claudectx convert --to cursor` | Export CLAUDE.md to Cursor rules format |
| `claudectx mcp` | Local MCP proxy — symbol-level file reads instead of full files |

### Safety

Every file touched is backed up to `~/.claudectx/backups/`. Revert with:

```bash
claudectx revert --list
claudectx revert --id <backup-id>
```

## Expected results

| Metric | Before | After |
|--------|--------|-------|
| Tokens per request | ~18K | ~3.7K |
| Cache hit rate | 12% | 74% |
| Monthly cost (team of 9) | $87 | $17 |

Results vary by project size. Run `analyze` first to see your baseline.
