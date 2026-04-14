# Claude Code Optimization — Spend Less, Get Better Answers

## Key references

- **Best practices repo**: https://github.com/shanraisshan/claude-code-best-practice (43k+ stars)
- **Claude Code repo**: https://github.com/anthropics/claude-code (113k+ stars)
- **Blueprint**: https://github.com/faizkhairi/claude-code-blueprint
- **Cheatsheet**: https://cc.bruniaux.com/guide/cheatsheet/
- **Cost guide**: https://maxtechera.dev/en/courses/claude-code-mastery/06-production/03-cost-optimization

## Token cost model

| Type | Cost |
|------|------|
| Input tokens | $3 / 1M tokens |
| Output tokens | $15 / 1M tokens |

Output is **5x more expensive**. Strategy: minimize verbose output, maximize precise input.

## Essential commands

| Command | What it does | When to use |
|---------|-------------|-------------|
| `/clear` | Reset conversation context | Every 30-45 min of active work |
| `/compact` | Summarize history, free tokens | When context grows but you need some continuity |
| `/cost` | Show session token usage + cost | Check periodically |
| `/context` | Detailed token breakdown | Diagnose why messages are expensive |
| `/plan` | Enter Plan Mode (read-only) | Before any feature > 1 hour of work |
| `/simplify` | Detect over-engineering + auto-fix | After implementing a feature |
| `/batch` | Parallel worktree agents for refactors | Large-scale changes across many files |
| `/insights` | Usage analytics + optimization report | Weekly review |

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Shift+Tab` | Cycle permission modes |
| `Esc` x2 | Rewind (undo last action) |
| `Ctrl+R` | Search command history |

## CLAUDE.md optimization rules

1. **Keep under 60 lines** (2,000 tokens max). It loads on EVERY request.
2. **No dynamic content** (timestamps, session notes) — breaks prompt caching.
3. **Add conciseness rule**: `"Be concise. Code and essential comments only."`
4. **Reference files, don't embed**: say "see src/utils/api.ts" instead of pasting content.
5. **Every prohibition needs an alternative**: "Never use console.log → use src/utils/logger.ts"

## .claudeignore (create at project root)

```
node_modules/
dist/
build/
.git/
*.log
*.lock
package-lock.json
yarn.lock
.terraform/
*.tfstate
*.tfstate.backup
.next/
coverage/
__pycache__/
*.pyc
```

## Workflow: Explore → Plan → Implement → Commit

1. **Explore**: let Claude read the codebase, ask questions
2. **Plan** (`/plan`): validate approach before writing code
3. **Implement**: switch to Agent mode, execute the plan
4. **Commit**: review changes, commit with clear message

## Common mistakes that waste tokens

| Mistake | Cost impact | Fix |
|---------|-----------|-----|
| Not using `/clear` | Context grows → 3x cost | Clear every 30-45 min |
| Letting Claude be verbose | 2x output tokens | Add "be concise" to CLAUDE.md |
| Large files in context | Inflated input per message | Split code, use .claudeignore |
| Repeating instructions | 50+ tokens per message | Put instructions in CLAUDE.md once |
| No Plan Mode | Misfocused code → redo | Always plan features > 1h |
