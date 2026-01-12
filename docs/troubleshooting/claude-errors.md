# Claude CLI Errors

Problems with the Claude command-line tool (not Ralph itself).

## "claude CLI not found"

The Claude CLI isn't installed or not in your PATH.

### Install Claude CLI

Download from [claude.ai/download](https://claude.ai/download).

### Verify installation

```bash
claude --version
```

If this works, Claude CLI is installed correctly.

### Check PATH

If installed but not found, the CLI may not be in your PATH. Check where it's installed and add to PATH:

```bash
# Find claude
which claude
# or
where claude  # Windows
```

## Authentication errors

Claude CLI needs to be logged in.

### Log in

```bash
claude login
```

Follow the prompts to authenticate.

### Verify authentication

```bash
claude --version
```

If you see version info without errors, you're authenticated.

## Rate limits

Claude may return errors if you've hit rate limits.

### What to do

1. **Wait:** Rate limits reset over time
2. **Smaller tasks:** Break work into pieces to use fewer tokens
3. **Check your plan:** Higher tiers have higher limits

### Signs of rate limiting

- Errors mentioning "rate limit" or "quota"
- Requests failing after working earlier
- Errors during heavy usage

## Connection errors

Network issues between you and Claude's servers.

### Check your connection

```bash
curl https://api.anthropic.com
```

### Common fixes

- Check internet connection
- Check if behind a proxy
- Try again later (server issues)

## Other errors

### Get more info

Run claude directly to see the actual error:

```bash
claude --print "test"
```

### Check Claude status

Claude may have service issues. Check:
- [Anthropic status page](https://status.anthropic.com)

### Update Claude CLI

You may have an outdated version:

```bash
# Check version
claude --version

# Update (method depends on how you installed)
pip install --upgrade claude-cli  # if installed via pip
```

## Still not working?

If Claude CLI works on its own but not with Ralph:

1. Make sure you're in a Ralph-initialized directory
2. Check that PROMPT.md exists and isn't empty
3. Run `ralph status` to see current state
4. Try `ralph reset` and start fresh

## Related

- [Getting started](../getting-started.md) - Initial setup including Claude CLI
- [ralph run](../commands/run.md) - Running Ralph
