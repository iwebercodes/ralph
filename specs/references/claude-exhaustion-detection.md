# Claude Exhaustion Detection (Sanitized Reference)

## Purpose
Reference output for detecting Claude usage-limit exhaustion.

## Invocation Used By Ralph
From `src/ralph/core/agent.py`, Ralph invokes:

```bash
claude -p "<prompt>" --output-format text --dangerously-skip-permissions
```

## Observed Limit-Exhaustion Signature

### Exit code (user-verified)
```text
1
```

### Terminal output (user-confirmed)
```text
Claude AI usage limit reached|1770843600
```

### Parsed meaning
- Prefix: `Claude AI usage limit reached`
- Suffix after `|`: Unix epoch reset time (`1770843600` in this sample)

## Stream/return behavior notes
- In a normal interactive terminal, the limit message can be emitted immediately as a single line.
- User-verified sample returned `RC:1` for the exhaustion case.
- In this sandbox’s non-interactive capture path, we observed only terminal-control bytes and a timeout, so `stdout/stderr` stream placement may differ by environment/TTY.

## What to capture when reproducing
Use this one-liner in the same shell where Claude is rate-limited:

```bash
claude -p "test" --output-format text --dangerously-skip-permissions; echo "RC:$?"
```

Then also split streams explicitly:

```bash
out=$(mktemp); err=$(mktemp)
claude -p "test" --output-format text --dangerously-skip-permissions >"$out" 2>"$err"; rc=$?
echo "RC:$rc"
echo "STDOUT:"; cat "$out"
echo "STDERR:"; cat "$err"
```

Record those values here once captured in your local terminal.
