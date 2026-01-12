# ralph history

View logs from previous rotations.

## Usage

```bash
ralph history [ROTATION] [--list] [--tail N]
```

## What It Does

Each rotation is logged to `.ralph/history/N.log`. This command helps you:
- See what happened in previous rotations
- Debug why a task is stuck
- Understand what Claude did and when

## Options

| Option | Description |
|--------|-------------|
| `ROTATION` | Specific rotation number to view |
| `--list`, `-l` | Show summary of all rotations |
| `--tail`, `-n` | Show only last N lines |

## Examples

**View most recent rotation:**
```bash
ralph history
```

**View specific rotation:**
```bash
ralph history 3
```

**List all rotations with summary:**
```bash
ralph history --list
```

Output:
```
Rotation  Time       Signal    Files
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1         14:23:01   CONTINUE  3
2         14:24:15   CONTINUE  2
3         14:25:30   DONE      0
4         14:26:45   DONE      0
5         14:27:58   DONE      0 (complete)
```

**Show last 50 lines of a rotation:**
```bash
ralph history 3 --tail 50
```

## Reading the Logs

Each log contains:

```
RALPH ROTATION 3 - 2024-01-15T14:25:30

Signal: DONE
Files Changed: 0

---

[Full Claude output from this rotation]
```

Key things to look for:
- **Signal** - What Claude signaled at the end
- **Files Changed** - How many files were modified
- **Output** - What Claude actually did

## Debugging with History

**Task keeps running but not finishing:**
1. Run `ralph history --list` to see the pattern
2. Look at recent rotations - is work being repeated?
3. Check if Claude is making progress or going in circles

**Understanding a past run:**
1. Run `ralph history 1` to see the first rotation
2. Walk through each rotation to understand the progression

**Finding when something went wrong:**
1. List rotations with `ralph history --list`
2. Find where the pattern changed
3. Read that rotation's full log

## Related

- [Troubleshooting](../troubleshooting/index.md) - Using history to debug issues
- [Rotations](../concepts/rotations.md) - What rotations are and how they work
