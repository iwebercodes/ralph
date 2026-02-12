# Agent CLI Crash Handling

When an agent CLI crashes or fails unexpectedly, Ralph should recover gracefully and continue working.

## Goal

Detect agent crashes and treat them as rotation triggers, preserving crash context for the next agent.

## Success Criteria

### Crash Detection

- [ ] Non-zero exit codes from agent CLI are detected as crashes
- [ ] Empty agent output (no stdout) is detected as a crash

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
