# Sequential Thinking — Structured Reasoning MCP Server

## What it does

Official Anthropic MCP server that forces **step-by-step structured reasoning**. Breaks complex problems into manageable steps with support for revision, branching, and hypothesis verification.

## Links

- **Source**: https://github.com/modelcontextprotocol/servers (83k+ stars)
- **Package**: `@modelcontextprotocol/server-sequential-thinking`
- **Docs**: https://mcpservers.org/servers/modelcontextprotocol/sequentialthinking

## Install

```bash
npx -y @modelcontextprotocol/server-sequential-thinking
```

## MCP config

Add to your MCP configuration file:

```json
{
  "mcpServers": {
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

## How to use

Ask Claude to use sequential thinking for complex problems:

```
Use sequential thinking to design the authentication flow for our EKS-based microservices.
```

```
Think through this step by step using sequential thinking: how should we structure the Terraform modules for multi-account AWS?
```

The tool provides:
- **Thought steps**: numbered, trackable reasoning
- **Revision**: can go back and correct earlier steps
- **Branching**: explore alternative approaches
- **Dynamic depth**: adjusts number of steps as needed

## Why this saves tokens

- Gets the architecture right on the first attempt
- Avoids wasted code generation from a wrong plan
- Pairs perfectly with Plan Mode (`/plan`) for complex features
- Reduces "redo this differently" cycles
