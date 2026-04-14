# MCP Servers — Extending Claude Code Capabilities

## What is MCP

Model Context Protocol (MCP) is how Claude Code connects to external tools and data sources. MCP servers give Claude new abilities without custom code.

## Links

- **Official servers repo**: https://github.com/modelcontextprotocol/servers (83k+ stars)
- **TypeScript SDK**: https://github.com/modelcontextprotocol/typescript-sdk
- **Server directory**: https://www.claudemcp.org
- **Awesome MCP servers**: https://github.com/whitmorelabs/awesome-mcp-servers-1

## Where to configure

### Cursor IDE
File: `.cursor/mcp.json` in project root

### Claude Code CLI
File: `.claude/mcp.json` in project root (or `~/.claude/mcp.json` for global)

### Claude Desktop
File: `claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

## Recommended MCP servers for this workspace

### Tier 1: Install these now

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

### Tier 2: Useful for our AWS/DevOps projects

| Server | Purpose | Package |
|--------|---------|---------|
| GitHub MCP | PR creation, code review, issue management | `@modelcontextprotocol/server-github` |
| PostgreSQL MCP | Database querying and schema inspection | `@modelcontextprotocol/server-postgres` |
| Filesystem MCP | Controlled file access outside workspace | `@modelcontextprotocol/server-filesystem` |

### Tier 3: Consider later

| Server | Purpose |
|--------|---------|
| Playwright | Browser automation for testing |
| Figma MCP | Design-to-code workflows |
| Docker MCP | Container management from Claude |

## Adding a new MCP server

1. Find the server (check https://www.claudemcp.org or the awesome list)
2. Add its config to your MCP JSON file
3. Restart Claude Code / Cursor
4. The tools become available automatically

## Verify MCP servers are working

In Claude Code CLI:
```
/mcp
```

This shows all connected MCP servers and their available tools.
