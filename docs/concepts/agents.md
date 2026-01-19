# Agents

Ralph works with multiple AI coding agents. This page explains how agents are discovered, managed, and rotated.

## Supported Agents

Ralph currently supports these AI agent CLIs:

| Agent | CLI Command | Provider |
|-------|-------------|----------|
| Claude | `claude` | Anthropic |
| Codex | `codex` | OpenAI |

You need at least one installed. If you have multiple, Ralph uses them all.

## How Agent Discovery Works

When you run `ralph run`, Ralph checks which agent CLIs are available:

```
$ ralph run
# Ralph checks:
# - Is 'claude' in PATH? Yes → add to pool
# - Is 'codex' in PATH? Yes → add to pool
# Result: pool has [Claude, Codex]
```

If no agents are found, Ralph tells you how to install one.

### Filtering Agents

You can restrict which agents to use with the `--agents` option:

```bash
ralph run --agents claude        # Only use Claude
ralph run --agents codex         # Only use Codex
ralph run -a claude,codex        # Use both (explicit)
```

Agent names are case-insensitive ("Claude", "claude", and "CLAUDE" all work).

## The Agent Pool

Ralph manages available agents in a pool:

```
┌─────────────────────────────────────────┐
│              Agent Pool                  │
├──────────────┬──────────────────────────┤
│    Claude    │         Codex            │
│  (available) │      (available)         │
└──────────────┴──────────────────────────┘
         │
         ▼
    Random selection
         │
         ▼
    ┌──────────┐
    │ Rotation │  ← Agent works on task
    └──────────┘
```

For each rotation, Ralph randomly selects an available agent from the pool.

## Agent Exhaustion

Agents can become "exhausted" when they hit rate limits:

- **Rate limits** - Too many requests in a time period
- **Quota exceeded** - Daily or monthly usage limits reached
- **Token limits** - Context or output limits exceeded

When Ralph detects exhaustion:

1. The exhausted agent is removed from the pool
2. Ralph continues with remaining agents
3. If all agents are exhausted, Ralph stops with exit code 4

```
┌─────────────────────────────────────────┐
│              Agent Pool                  │
├──────────────┬──────────────────────────┤
│    Claude    │         Codex            │
│ (exhausted)  │      (available)         │
│     ✗        │          ✓               │
└──────────────┴──────────────────────────┘
         │
         ▼
    Codex continues alone
```

## Detecting Exhaustion

Ralph detects exhaustion by looking for patterns in agent responses:

**Claude:**
- "rate limit"
- "quota exceeded"
- "token limit"
- "usage limit"

**Codex:**
- "rate_limit_exceeded"
- "daily_limit"
- "usage_limit"

These patterns are only checked in stderr (error output), not stdout. This prevents false positives when prompts or agent output mention these terms.

## Benefits of Multiple Agents

Having multiple agents installed gives you:

- **More uptime** - If one agent is rate limited, others continue
- **Higher throughput** - Distribute load across providers
- **Resilience** - No single point of failure

## Installing Agents

### Claude CLI

1. Download from [claude.ai/download](https://claude.ai/download)
2. Run the installer
3. Log in: `claude login`
4. Verify: `claude --version`

### Codex CLI

1. Install from [github.com/openai/codex](https://github.com/openai/codex)
2. Set your API key: `export OPENAI_API_KEY=your-key`
3. Verify: `codex --version`

## Seeing Which Agent is Working

The Ralph output shows which agent is running each rotation:

```
  ╭── Claude working... ──────────────────────────────────╮
  │  Iteration:    1/20                                   │
  ...

  ╭── Codex working... ───────────────────────────────────╮
  │  Iteration:    2/20                                   │
  ...
```

## When All Agents Are Exhausted

If all agents hit their limits:

```
  ╭───────────────────────────────────────────────────────╮
  │  ⚠ AGENTS EXHAUSTED                                   │
  │  All agents rate limited                              │
  ╰───────────────────────────────────────────────────────╯

  Next steps:
    1. Wait for rate limits to reset
    2. Run: ralph run
```

State is preserved. When you run `ralph run` again, it picks up where it left off with a fresh agent pool.

## Related

- [Getting started](../getting-started.md) - Installing agent CLIs
- [How it works](../how-it-works.md) - Where agents fit in the loop
- [Rotations](./rotations.md) - What happens during each agent session
- [Troubleshooting](../troubleshooting/agent-errors.md) - Agent-related errors
