# Codex Exhaustion Detection (Sanitized Reference)

## Purpose
Reference output for detecting Codex usage-limit exhaustion without false positives.

## Invocation
```bash
codex exec -C /path/to/project \\
  --skip-git-repo-check \\
  --dangerously-bypass-approvals-and-sandbox \\
  "Say hello"
```

## Observed Limit-Exhaustion Signature

### Exit code
```text
1
```

### Stdout
```text
(empty)
```

### Stderr (sanitized)
```text
OpenAI Codex vX.Y.Z (research preview)
--------
workdir: /path/to/project
model: gpt-5.x-codex
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: auto
session id: <redacted-session-id>
--------
user
<user prompt text>
mcp startup: no servers
<timestamp> ERROR codex_api::endpoint::responses: error=http 429 Too Many Requests: Some("{\"error\":{\"type\":\"usage_limit_reached\",\"message\":\"The usage limit has been reached\",\"plan_type\":\"<redacted>\",\"resets_at\":<unix_ts>,\"resets_in_seconds\":<seconds>}}")
ERROR: You've hit your usage limit. Upgrade to Pro (...), visit ... or try again at <time>.
```

## Reliable Detection Markers
- `usage_limit_reached`
- `429 Too Many Requests`
- `You've hit your usage limit`

## Notes
- Codex prints substantial non-error content to `stderr` (banner and echoed user block).
- Detection should avoid matching prompt echo text; prefer runtime error lines.
- `resets_in_seconds` can be extracted for user-facing reset-time hints.
