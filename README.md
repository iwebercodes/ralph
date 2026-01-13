# Ralph

<p align="center">
  <img src="ralph.png" alt="Ralph - the supervisor" width="200">
</p>

Stop cleaning up after your AI coding agent.

Ralph supervises Claude Code (and other agents soon) to actually finish what they start.
When Claude loses track, declares "done" prematurely, or forgets earlier decisions -- Ralph catches it.

## Who This Is For

- You use Claude Code or similar AI coding tools
- You're building real projects, not just experimenting
- You've been frustrated by half-finished AI output
- You want better results, even if it costs more tokens

## Quick Start

1. **Install and initialize**
   ```bash
   pipx install ralph-loop
   ralph init
   ```

2. **Describe what you want built** (in PROMPT.md)
   ```markdown
   # Goal
   Add a contact form that emails submissions to me.

   # Success Criteria
   - [ ] Form has name, email, message fields
   - [ ] Validates email format before sending
   - [ ] Shows success message after submission
   - [ ] Emails go to contact@mysite.com
   ```

3. **Let Ralph supervise the build**
   ```bash
   ralph run
   ```
   Ralph keeps Claude working until all criteria are actually met. Verified 3 times to make sure nothing was missed.

## How It Works

Claude Code is powerful, but on bigger tasks it can:
- **Lose context** as the conversation grows
- **Forget decisions** made earlier in the session
- **Declare "done"** when things clearly aren't

Ralph solves this by **breaking big tasks into fresh-context chunks**.

After each chunk, Ralph:
1. Saves what Claude learned and accomplished (so nothing is lost)
2. Starts a fresh session (so context stays clean)
3. Hands off the state (so Claude picks up where it left off)

When Claude says "done", Ralph doesn't just trust it. It verifies 3 times with fresh eyes. If anything was missed, work continues.

**Result:** Tasks that used to fail halfway through now complete reliably.

## The Tradeoff

Ralph uses more tokens than running Claude directly. Each rotation is a fresh API call, and verification adds more.

**But:** You'll spend less time debugging, less time re-prompting, and less time cleaning up half-finished work. For many tasks, the extra tokens are worth it.

## Commands

| Command | Description |
|---------|-------------|
| `ralph init` | Initialize Ralph in the current directory |
| `ralph run` | Supervise Claude until the goal is complete |
| `ralph status` | Show current progress |
| `ralph reset` | Start fresh |
| `ralph history` | View logs from previous sessions |

## Configuration

The `.ralph/` directory contains local state and should not be committed:

```
# .gitignore
.ralph/
```

## Documentation

- [Getting Started](./docs/getting-started.md) - Full setup guide
- [Writing Effective Prompts](./docs/writing-prompts.md) - Get better results
- [Troubleshooting](./docs/troubleshooting/index.md) - When things go wrong
- [Full Documentation](./docs/README.md) - Everything else

## Built By

Ralph was created by [Ilja Weber](https://linkedin.com/in/ilja-weber-bb7135b5) to solve my own frustrations with AI coding agents declaring "done" too early.

Follow for updates:
- [LinkedIn](https://www.linkedin.com/in/ilja-weber-bb7135b5)
- [Twitter/X](https://x.com/iwebercodes)

## License

MIT
