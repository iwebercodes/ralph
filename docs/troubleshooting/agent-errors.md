# Agent CLI Errors

Problems with the AI agent command-line tools (not Ralph itself).

## "No AI agents available"

None of the supported agent CLIs are installed.

### Install at least one agent

**Claude CLI** (from Anthropic):
- Download from [claude.ai/download](https://claude.ai/download)

**Codex CLI** (from OpenAI):
- Install from [github.com/openai/codex](https://github.com/openai/codex)

### Verify installation

```bash
# Check Claude
claude --version

# Check Codex
codex --version
```

If either works, Ralph can use it.

### Check PATH

If installed but not found, the CLI may not be in your PATH:

```bash
# Find the CLI
which claude
which codex
# or on Windows
where claude
where codex
```

## "All agents exhausted"

All available agents hit their rate limits.

### What to do

1. **Wait:** Rate limits reset over time (usually within an hour)
2. **Add more agents:** Install additional agent CLIs for more capacity
3. **Resume later:** State is saved, just run `ralph run` when ready

### Preventing exhaustion

- Install multiple agent CLIs (Claude and Codex)
- Break large tasks into smaller pieces
- Use `--max` with reasonable values

## Agent-specific errors

### Claude CLI

**"claude CLI not found"**
- Install from [claude.ai/download](https://claude.ai/download)
- Verify: `claude --version`

**Authentication errors:**
```bash
claude login
```

**Rate limits:**
- Look for "rate limit" or "quota exceeded" in errors
- Wait for limits to reset or use another agent

### Codex CLI

**"codex CLI not found"**
- Install from [github.com/openai/codex](https://github.com/openai/codex)
- Verify: `codex --version`

**Authentication errors:**
- Ensure `OPENAI_API_KEY` is set in your environment
- Check your API key is valid

**Rate limits:**
- Look for "rate_limit_exceeded" or "daily_limit" in errors
- Wait for limits to reset or use another agent

## Connection errors

Network issues between you and the agent's servers.

### Check your connection

```bash
# For Claude
curl https://api.anthropic.com

# For OpenAI/Codex
curl https://api.openai.com
```

### Common fixes

- Check internet connection
- Check if behind a proxy
- Try again later (server issues)

## Timeout errors

An agent took too long to respond.

### What happens

Ralph waits up to 30 minutes for an agent response. If exceeded:
- The rotation fails with a timeout error
- State is preserved
- Run `ralph run` to retry

### Causes

- Very complex prompts
- Network slowdowns
- API service degradation

## Still not working?

If agent CLIs work on their own but not with Ralph:

1. Make sure you're in a Ralph-initialized directory
2. Check that PROMPT.md exists and isn't empty
3. Run `ralph status` to see current state
4. Try `ralph reset` and start fresh

## Related

- [Getting started](../getting-started.md) - Initial setup including agent CLIs
- [Agents](../concepts/agents.md) - How Ralph works with multiple agents
- [ralph run](../commands/run.md) - Running Ralph
