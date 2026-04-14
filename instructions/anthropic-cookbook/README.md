# Anthropic Cookbook — Official Claude Examples

## What it does

Official Anthropic repository with notebooks and recipes showing effective ways to use Claude. The go-to reference for prompt engineering, tool use, and API patterns.

## Links

- **Repo**: https://github.com/anthropics/anthropic-cookbook (40k+ stars)
- **Anthropic docs**: https://docs.anthropic.com

## Key sections relevant to optimization

### Prompt engineering
- Prompt caching techniques (pay 10% for cached portions)
- System prompt design
- Structured output patterns
- Tool use / function calling

### Cost reduction patterns
- Batch API usage (50% cheaper for non-real-time tasks)
- Prompt caching (static content first, dynamic last)
- Efficient context window management
- Token counting and budgeting

## How to use

```bash
git clone https://github.com/anthropics/anthropic-cookbook.git
cd anthropic-cookbook
```

Browse the notebooks directly on GitHub or run them locally with Jupyter.

## Most useful notebooks for our projects

| Notebook | Relevance |
|----------|-----------|
| Prompt caching | Reduce API costs for repeated system prompts |
| Tool use | Build Claude-powered tools (relevant for Project-A RAG) |
| Retrieval augmented generation | Direct input for GenAI Security Gateway |
| Embeddings | Useful for Project-A document search |
| Citations | Source attribution for RAG responses |

## Quick reference: prompt caching

Structure prompts with static content first for maximum cache hits:
1. System prompt (static — cached)
2. Tool definitions (static — cached)
3. Conversation history (semi-static)
4. Current user message (dynamic — never cached)
