# Verification Counter Behavior

## Overview

Ralph tracks verification progress for each spec using a counter that increments when agents report DONE without changing files. This ensures implementations are properly reviewed and verified before considering a spec complete.

## Counter States

- **0/3**: Agent is working on implementation (not DONE yet)
- **1/3**: Agent reported DONE (files may have been changed)
- **2/3**: Agent verified and reported DONE again (no files changed)
- **3/3**: Agent verified twice without changes - spec is complete

## Counter Rules

### Increment Rules
The counter increments when:
- Agent returns status `DONE`
- No tracked files were changed during the rotation

### Reset to 1/3
The counter resets to 1/3 when:
- Agent returns status `DONE`
- AND tracked files were changed during the rotation

### Reset to 0/3
The counter resets to 0/3 when:
- Agent returns non-DONE status (CONTINUE, ROTATE, STUCK)
- AND tracked files were changed during the rotation

### No Change
The counter remains unchanged when:
- Agent returns non-DONE status (CONTINUE, ROTATE, STUCK)
- AND no tracked files were changed

### Multi-Spec Change Propagation Rule
When ANY spec causes tracked file changes:
- The active spec resets based on its own status: DONE -> 1/3, non-DONE -> 0/3
- Other specs are not fully reset
- Other specs at 3/3 downgrade to 2/3
- Other specs at 0/3, 1/3, or 2/3 remain unchanged
- This forces one extra verification pass for previously fully verified specs while preserving in-progress work

## Examples

1. **Implementation + Verification**
   - Rotation 1: Agent implements feature, returns DONE → 1/3
   - Rotation 2: Agent reviews code, returns DONE (no changes) → 2/3
   - Rotation 3: Agent reviews again, returns DONE (no changes) → 3/3 ✓

2. **Rotation without completion**
   - Rotation 1: Agent works on feature, returns ROTATE → 0/3 (unchanged)
   - Rotation 2: Agent continues work, returns DONE → 1/3
   - Rotation 3: Agent reviews, returns DONE (no changes) → 2/3

3. **Found issue during verification**
   - Rotation 1: Agent implements, returns DONE → 1/3
   - Rotation 2: Agent reviews, finds bug, fixes it, returns DONE → 1/3 (reset due to changes)
   - Rotation 3: Agent reviews, returns DONE (no changes) → 2/3

4. **Context exhaustion during verification**
   - Rotation 1: Agent implements, returns DONE → 1/3
   - Rotation 2: Agent reviews, returns DONE (no changes) → 2/3
   - Rotation 3: Agent reviews, returns ROTATE (no changes) → 2/3 (unchanged)
   - Rotation 4: Different agent reviews, returns DONE (no changes) → 3/3 ✓

5. **Selective propagation in multi-spec mode**
   - Spec A: At 3/3 (fully verified)
   - Spec B: At 2/3 (in verification)
   - Spec C: At 0/3 (new work)
   - Active Spec D: Works on implementation, changes files, returns DONE
   - Result: Spec D -> 1/3, Spec A -> 2/3, Spec B -> 2/3, Spec C -> 0/3

## Acceptance Criteria

- [ ] Counter starts at 0/3 for new specs
- [ ] Counter increments only on DONE status without file changes
- [ ] Counter resets to 1/3 on DONE status with file changes
- [ ] Counter resets to 0/3 on non-DONE status with file changes
- [ ] Counter remains unchanged on non-DONE status without file changes
- [ ] Counter never exceeds 3/3
- [ ] Counter state persists across Ralph restarts
- [ ] Each spec maintains its own independent counter
- [ ] In multi-spec mode, when one spec changes files: active spec resets by status (DONE -> 1/3, non-DONE -> 0/3), other specs only downgrade 3/3 -> 2/3
- [ ] Automated tests verify all counter behavior scenarios described in this spec