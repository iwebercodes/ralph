# Claude Exhaustion Detection

Detect when Claude hits usage limits and remove it from the agent pool reliably.

## Problem

Claude limit errors are currently not reliably detected. Real exhaustion output can appear as a compact line:

`Claude AI usage limit reached|<unix_epoch>`

If detection only inspects stderr, or does not parse this format, exhausted Claude runs may be treated as normal failures instead of pool-removal events.

## Goal

Implement Claude exhaustion detection using stdout pattern recognition, gated by non-zero exit codes.

## References

- `specs/references/claude-exhaustion-detection.md`

## Actual Error Format (Observed)

### Exit Code
```
1
```

### Output
```
Claude AI usage limit reached|1770843600
```

## Success Criteria

### Exit Code Defense

- [ ] Only consider Claude exhaustion if `exit_code != 0`
- [ ] Successful runs (`exit_code == 0`) must never be marked exhausted

### Stdout-Based Detection

- [ ] Claude exhaustion detection must inspect stdout (not stderr-only)
- [ ] Detect `Claude AI usage limit reached|<unix_epoch>` format
- [ ] Accept and parse the reset epoch from the suffix after `|`
- [ ] Return a human-readable exhaustion reason that includes reset timing when available

### False Positive Prevention

- [ ] Do not classify exhaustion from arbitrary prompt text mentions in stdout/stderr
- [ ] Require the Claude exhaustion signature format, not loose generic keywords alone

### Integration Tests

- [ ] Tests cover the real observed format (`Claude AI usage limit reached|1770843600`) with non-zero exit code
- [ ] Tests verify no exhaustion classification when the same text appears with `exit_code == 0`
- [ ] Tests verify pool removal behavior uses the parsed Claude exhaustion reason

## Test Cases

1. **Actual exhaustion**: stdout contains `Claude AI usage limit reached|1770843600`, exit code 1 → agent removed
2. **Exit code guard**: same stdout text with exit code 0 → agent not removed
3. **No signature**: non-zero exit with unrelated error text → not classified as exhaustion
4. **Reset parsing**: parsed epoch is exposed in removal reason as reset hint
