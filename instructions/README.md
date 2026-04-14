# Claude Code Optimization — Resource Hub

Quick-access instructions for configuring Claude Code to spend fewer tokens and get better answers.

## Folders

| Folder | Purpose | Priority |
|--------|---------|----------|
| [`context7/`](context7/) | MCP server — live library docs injection | **Install now** |
| [`sequential-thinking/`](sequential-thinking/) | MCP server — structured step-by-step reasoning | **Install now** |
| [`claude-code-optimization/`](claude-code-optimization/) | Token saving techniques, commands, workflow | **Read first** |
| [`claudectx/`](claudectx/) | CLI tool — audit and optimize token usage | **Run `npx claudectx analyze`** |
| [`mcp-servers/`](mcp-servers/) | MCP ecosystem overview + full config | Reference |
| [`anthropic-cookbook/`](anthropic-cookbook/) | Official Anthropic examples + prompt engineering | Reference |
| [`claude-sdks/`](claude-sdks/) | Python + TypeScript SDKs (API + Agent) | For development |

## Quick start (3 steps)

### 1. Add MCP servers to your config

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

### 2. Audit your current token usage

```bash
npx claudectx analyze
```

### 3. Apply optimizations

```bash
npx claudectx optimize --apply
```

## Daily habits that save tokens

1. `/clear` every 30-45 minutes of active work
2. `/compact` when context grows but you need continuity
3. `/plan` before any feature that takes > 1 hour
4. Write concise prompts (bullet points > paragraphs)
5. Add "use context7" when asking about specific libraries
6. Use sequential thinking for architecture decisions

## All verified URLs

| Resource | URL | Stars |
|----------|-----|-------|
| Claude Code | https://github.com/anthropics/claude-code | 113k |
| MCP Servers | https://github.com/modelcontextprotocol/servers | 83k |
| Context7 | https://github.com/upstash/context7 | 52k |
| Best Practices | https://github.com/shanraisshan/claude-code-best-practice | 43k |
| Anthropic Cookbook | https://github.com/anthropics/anthropic-cookbook | 40k |
| Anthropic Python SDK | https://github.com/anthropics/anthropic-sdk-python | 3.2k |
| Anthropic TS SDK | https://github.com/anthropics/anthropic-sdk-typescript | 1.8k |
| Claude Agent SDK (Python) | https://github.com/anthropics/claude-agent-sdk-python | 6.3k |
| Claude Agent SDK (TS) | https://github.com/anthropics/claude-agent-sdk-typescript | 1.3k |
| claudectx | https://github.com/Horilla/claudectx | New |
| Claude Code Blueprint | https://github.com/faizkhairi/claude-code-blueprint | 18 |
| Cheatsheet | https://cc.bruniaux.com/guide/cheatsheet/ | — |
