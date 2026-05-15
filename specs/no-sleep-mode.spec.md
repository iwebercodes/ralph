# No-Sleep Mode

When Ralph runs for extended periods (multi-hour unattended sessions), the computer may enter sleep/hibernate mode, interrupting the loop. No-sleep mode signals to the OS that Ralph is actively working and the system should remain awake.

## Problem

Ralph is designed for long-running, unattended AI agent loops. A typical session can run for hours across multiple iterations. However:

1. Modern OSes (Linux, macOS, Windows) automatically enter sleep/hibernate after inactivity
2. User inactivity (away from keyboard) triggers screensaver, display sleep, or system sleep
3. System sleep kills running processes — including Ralph and its child agent processes
4. A sleeping machine cannot complete multi-hour tasks autonomously
5. Users must either keep the machine awake manually or accept interrupted sessions

## Solution

While Ralph is actively running (inside the main loop), it should prevent the OS from entering sleep mode. When Ralph exits (success, error, max iterations, stuck, or user interrupt), the sleep prevention is automatically released and the OS returns to normal power management.

### Platform Support

| Platform | Mechanism | Notes |
|----------|-----------|-------|
| Linux | `systemd-inhibit --what=sleep` (primary) / `xdg-screensaver suspend` (best-effort, requires WindowID) / `busctl` DBus via `org.freedesktop.login1.Manager.Inhibit` (best-effort, FD released on busctl exit) | Primary: systemd-inhibit holds inhibitor for child lifetime. Fallbacks are attempted for spec compliance but cannot reliably hold the inhibitor in a CLI context. |
| macOS | `caffeinate -dims` | Uses native macOS power management |
| Windows | `ctypes.windll.kernel32.SetThreadExecutionState` | Native Win32 API call |

### Design Decisions

- **Always-on by default** — Ralph's entire purpose is long-running unattended tasks. Preventing sleep is core to that purpose, not an optional feature. No CLI flag needed.
- **No new dependencies** — use existing standard-library or already-available tools. On Linux, prefer DBus calls over installing `dbus-python`. On macOS, use `subprocess` to call `caffeinate`. On Windows, use `ctypes` with `kernel32.dll`.
- **Automatic cleanup** — sleep prevention is released when:
  - Ralph completes successfully (exit 0)
  - Ralph exits with an error code (1, 2, 3, 4)
  - User interrupts with Ctrl+C (SIGINT)
  - Ralph process terminates unexpectedly
- **Per-process scope** — sleep prevention is tied to the Ralph process lifetime. When Ralph dies, prevention stops. No orphaned state.

## Success Criteria

### Always-On Behavior

- [ ] Sleep prevention is active automatically whenever Ralph runs the main loop
- [ ] No CLI flag or configuration needed — always on by default
- [ ] Works with all existing flags and modes (`--max`, `--agents`, `--timeout`, `--filter`, etc.)

### Sleep Prevention Implementation

- [ ] Linux: Uses `systemd-inhibit --what=sleep` as primary mechanism, falls back to `xdg-screensaver suspend` (best-effort), then `busctl` DBus via `org.freedesktop.login1.Manager.Inhibit` (best-effort)
- [ ] macOS: Uses `caffeinate -dims` (prevents system sleep, idle sleep, and display sleep)
- [ ] Windows: Uses `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)` via ctypes
- [ ] If the platform mechanism is unavailable (e.g., no `systemd-inhibit` on headless Linux), log a warning but continue running Ralph normally — do NOT fail
- [ ] Sleep prevention starts before the main loop begins
- [ ] Sleep prevention stops after the main loop ends (all exit paths)

### Automatic Cleanup

- [ ] Normal completion (exit 0) releases sleep prevention
- [ ] Error exit (exit 1) releases sleep prevention
- [ ] Stuck exit (exit 2) releases sleep prevention
- [ ] Max iterations exit (exit 3) releases sleep prevention
- [ ] All agents exhausted exit (exit 4) releases sleep prevention
- [ ] Ctrl+C (SIGINT) releases sleep prevention before process exit
- [ ] If Ralph is killed (SIGKILL, crash), the OS automatically cleans up (no orphaned state)

### Cross-Platform Behavior

- [ ] Works on Linux (tested with X11 and Wayland environments)
- [ ] Works on macOS (tested with recent macOS versions)
- [ ] Works on Windows (tested with Windows 10/11)
- [ ] Platform detection is automatic — no user configuration needed

### Edge Cases

- [ ] If sleep prevention fails on a platform, Ralph continues running with a warning message — does NOT fail the entire run
- [ ] Sleep prevention survives between iterations within the same loop (the prevention handle stays active across the entire run)
- [ ] Multiple concurrent `ralph run` processes: each maintains its own prevention; the last one to exit releases it
- [ ] No sleep prevention is applied when `debug-prompt` mode is used (no agents are invoked, no loop runs)

### Automated Tests

- [ ] Unit tests for sleep prevention on each platform (mocked where needed)
- [ ] Tests verify that cleanup happens on all exit paths
- [ ] Tests verify that sleep prevention IS applied by default when running the loop
- [ ] Tests verify warning is logged when mechanism is unavailable
- [ ] Tests verify sleep prevention is NOT applied in debug-prompt mode
