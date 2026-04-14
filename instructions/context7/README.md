# Context7 — Live Documentation MCP Server

## What it does

Context7 fetches **up-to-date, version-specific documentation** for any library and injects it directly into your AI context window. No more hallucinated APIs or deprecated methods.

## Links

- **Repo**: https://github.com/upstash/context7 (52k+ stars)
- **Website**: https://context7.com
- **NPM**: `@upstash/context7-mcp`

## Install (one command)

```bash
npx ctx7 setup
```

This auto-detects your environment (Cursor, Claude Desktop, Claude Code) and configures everything.

## Manual MCP config

Add to your MCP configuration file (`.cursor/mcp.json`, `claude_desktop_config.json`, or `.claude/mcp.json`):

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

## How to use

Add **"use context7"** to any prompt:

```
How do I set up authentication in Supabase? use context7
```

```
Show me Terraform aws_iam_role resource usage. use context7
```

Context7 will:
1. Resolve the library (`resolve-library-id` tool)
2. Fetch current docs + code examples (`query-docs` tool)
3. Inject them into your context

## Why this saves tokens

- Prevents follow-up corrections when Claude hallucinates an API
- Gives precise, version-specific code — no guessing
- Reduces back-and-forth "that method doesn't exist" cycles
