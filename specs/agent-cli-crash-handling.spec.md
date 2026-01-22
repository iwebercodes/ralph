# Agent CLI Crash Handling

When an agent CLI crashes or fails unexpectedly, Ralph should recover gracefully and continue working.

## Goal

Detect agent crashes and treat them as rotation triggers, preserving crash context for the next agent.

## Success Criteria

### Crash Detection

- [ ] Non-zero exit codes from agent CLI are detected as crashes
- [ ] Empty agent output (no stdout) is detected as a crash
- [ ] Common error patterns in stderr are detected (e.g., "No messages returned", "ECONNRESET", "ETIMEDOUT")

### Real-Time Stderr Monitoring

Some agent CLIs (e.g., Claude CLI) may not exit cleanly after errors - they log the error but hang with threads still running. To handle this:

- [ ] Monitor stderr in real-time during agent execution
- [ ] If a crash pattern is detected in stderr, kill the agent process immediately
- [ ] Proceed with rotation after killing the hung process

### Recovery Behavior

- [ ] Crashes are treated as ROTATE (not CONTINUE or STUCK)
- [ ] The iteration counter increments normally
- [ ] Ralph continues with the next rotation without halting

### Crash Context Preservation

- [ ] Crash details are appended to the handoff file
- [ ] The next agent sees a note like: "Previous rotation crashed: {error summary}"
- [ ] Crash details are logged in history for debugging

### No False Positives

- [ ] Agents that exit successfully with zero exit code are not flagged as crashed
- [ ] Agents that produce output but write non-standard status are not flagged as crashed

### Exhaustion vs Crash

Rate limit / quota exhaustion is distinct from crashes:

- [ ] **Crash**: Agent stays in pool, available for future rotations
- [ ] **Exhaustion**: Agent is removed from pool until limits reset

A crashed agent is assumed to be healthy and can retry. An exhausted agent cannot work until external limits are lifted.

## Validation

To verify crash handling works:

1. Simulate an agent crash (e.g., kill the agent process mid-run)
2. Ralph should detect the crash and continue to next rotation
3. The handoff should contain crash context
4. History log should show the crash occurred
