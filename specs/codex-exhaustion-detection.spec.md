# Codex Exhaustion Detection

Detect when Codex hits its usage limit and remove it from the agent pool.

## Problem

The current exhaustion detection patterns are too broad and trigger false positives. Patterns like `r"token.?limit"` match informational stderr output (e.g., discussions about context windows), causing Codex to be incorrectly removed from the pool when it's still functional.

Codex writes extensive output to stderr during normal operation:
- Version/config header
- Thinking blocks
- Execution logs
- Status messages

Any mention of "token limit" in this output would incorrectly trigger removal.

## Goal

Replace broad patterns with specific ones that only match actual exhaustion errors, and add exit code checking for defense in depth.

## References

- `specs/references/codex-exhaustion-detection.md`

## Actual Error Format

When Codex hits its usage limit, this is the actual output:

### Exit Code
```
1
```

### Stdout
```
(empty)
```

### Stderr
```
OpenAI Codex v0.88.0 (research preview)
--------
workdir: /path/to/project
model: gpt-5.2-codex
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: auto
session id: <session-uuid>
--------
user
Say hello
mcp startup: no servers
2026-01-29T23:21:37.939876Z ERROR codex_api::endpoint::responses: error=http 429 Too Many Requests: Some("{\"error\":{\"type\":\"usage_limit_reached\",\"message\":\"The usage limit has been reached\",\"plan_type\":\"plus\",\"resets_at\":1769730918,\"resets_in_seconds\":2021}}")
ERROR: You've hit your usage limit. Upgrade to Pro (https://openai.com/chatgpt/pricing), visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at 12:55 AM.
```

### Structured Error (JSON in stderr)
```json
{
  "error": {
    "type": "usage_limit_reached",
    "message": "The usage limit has been reached",
    "plan_type": "plus",
    "resets_at": 1769730918,
    "resets_in_seconds": 2021
  }
}
```

## Success Criteria

### Pattern Specificity

- [ ] Use `usage_limit_reached` pattern (exact API error type from JSON response)
- [ ] Use `429 Too Many Requests` pattern (HTTP status code)
- [ ] Use `You've hit your usage limit` pattern (unambiguous error message)
- [ ] Remove broad patterns: `rate.?limit`, `token.?limit`, `usage.?limit`

### Exit Code Defense

- [ ] Only consider exhaustion if `exit_code != 0`
- [ ] Successful runs (exit_code == 0) never trigger exhaustion, regardless of stderr content

### Detection Scope (Ignore Echoed User Block)

- [ ] Exhaustion pattern recognition must NOT scan the echoed `user` block in stderr
- [ ] Pattern recognition must run only on the runtime/error portion after the `user` block
- [ ] In practice, detect from the first runtime error anchor (e.g., `codex_api::endpoint::responses`) onward
- [ ] If no runtime error anchor exists, do not classify as exhaustion from echoed prompt text alone

### Extraction of Reset Information

- [ ] Extract `resets_in_seconds` from JSON error when available
- [ ] Display human-readable reset time in removal message (e.g., "Codex removed (usage limit, resets in 34 minutes)")

### Integration Tests

- [ ] Integration tests verify exhaustion detection with real stderr samples
- [ ] Integration tests verify no false positives with normal operational output
- [ ] Tests cover all three specific patterns

## Test Cases

1. **Actual exhaustion**: Stderr contains `usage_limit_reached` with exit code 1 → agent removed
2. **False positive prevention**: Stderr contains "token limit" discussion with exit code 0 → agent NOT removed
3. **Pattern matching**: Each specific pattern correctly identifies exhaustion
4. **Reset time extraction**: JSON error with `resets_in_seconds` shows formatted time in output
5. **User-block immunity**: Stderr echoed prompt contains exhaustion keywords before runtime error block → agent NOT removed
