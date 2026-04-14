# Claude SDKs — Official Anthropic Libraries

## Overview

Anthropic maintains **4 official SDKs**. Two are API clients, two are for building autonomous agents.

## API SDKs (for calling Claude models)

### Python SDK

- **Repo**: https://github.com/anthropics/anthropic-sdk-python (3.2k stars)
- **PyPI**: `anthropic`

```bash
pip install anthropic
```

```python
from anthropic import Anthropic

client = Anthropic()
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)
```

### TypeScript SDK

- **Repo**: https://github.com/anthropics/anthropic-sdk-typescript (1.8k stars)
- **NPM**: `@anthropic-ai/sdk`

```bash
npm install @anthropic-ai/sdk
```

```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic();
const message = await client.messages.create({
  model: "claude-sonnet-4-20250514",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello" }],
});
```

## Agent SDKs (for building autonomous agents)

### Python Agent SDK

- **Repo**: https://github.com/anthropics/claude-agent-sdk-python (6.3k stars)
- **PyPI**: `claude-agent-sdk`

```bash
pip install claude-agent-sdk
```

Enables building agents that autonomously read files, run commands, search the web, and edit code using built-in tools (Read, Edit, Bash, Glob).

### TypeScript Agent SDK

- **Repo**: https://github.com/anthropics/claude-agent-sdk-typescript (1.3k stars)
- **NPM**: `claude-agent-sdk`

```bash
npm install claude-agent-sdk
```

Same capabilities as Python SDK, includes hook system, MCP server integration, tasks, and subagents.

## Which SDK to use

| Use case | SDK |
|----------|-----|
| Call Claude API from your app | `anthropic` (Python) or `@anthropic-ai/sdk` (TS) |
| Build autonomous coding agents | `claude-agent-sdk` (Python or TS) |
| Our Project-A (GenAI Gateway) | API SDK for the gateway, Agent SDK for RAG automation |

## WRONG URLs (from original list)

These do NOT exist:
- ~~github.com/anthropics/claude-sdk-python~~ → use `anthropic-sdk-python`
- ~~github.com/anthropics/claude-sdk-typescript~~ → use `anthropic-sdk-typescript`
