"""State file management for Ralph."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import NamedTuple

from ralph.core.specs import is_prompt_path, spec_content_hash, spec_resource_key

RALPH_DIR = ".ralph"
HANDOFF_FILE = "handoff.md"
GUARDRAILS_FILE = "guardrails.md"
STATUS_FILE = "status"
ITERATION_FILE = "iteration"
DONE_COUNT_FILE = "done_count"
SNAPSHOT_PREV_FILE = "snapshot_prev"
SNAPSHOT_CURR_FILE = "snapshot_curr"
HISTORY_DIR = "history"
HANDOFF_DIR = "handoffs"
STATE_FILE = "state.json"
STATE_VERSION = 1


class Status(Enum):
    """Status signals for the Ralph loop."""

    IDLE = "IDLE"
    CONTINUE = "CONTINUE"
    ROTATE = "ROTATE"
    DONE = "DONE"
    STUCK = "STUCK"


class RalphState(NamedTuple):
    """Current state of a Ralph loop."""

    iteration: int
    done_count: int
    status: Status


@dataclass(frozen=True)
class SpecProgress:
    """Progress tracking for a single spec."""

    path: str
    done_count: int = 0
    last_status: str | None = None  # Last status signal (e.g., "DONE", "CONTINUE")
    last_hash: str | None = None  # Content hash from last processed run
    modified_files: bool = False  # Whether files were modified when last processed


@dataclass(frozen=True)
class MultiSpecState:
    """Full multi-spec state stored in state.json."""

    version: int
    iteration: int
    status: Status
    current_index: int
    specs: list[SpecProgress]


HANDOFF_TEMPLATE = """# Handoff

## Completed

## In Progress

## Next Steps

## Notes
"""

GUARDRAILS_TEMPLATE = """# Guardrails
"""

PROMPT_TEMPLATE = """# Goal

Describe what you want to accomplish.

# Context

Any relevant background information.

# Success Criteria

- [ ] Criterion 1
- [ ] Criterion 2

# Constraints

Any limitations or requirements.
"""


def get_state_path(root: Path | None = None) -> Path:
    """Get the path to state.json."""
    return get_ralph_dir(root) / STATE_FILE


def _coerce_int(value: object, default: int) -> int:
    if isinstance(value, (int, str)):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _spec_progress_from_dict(data: dict[str, object]) -> SpecProgress | None:
    path_raw = data.get("path")
    if not isinstance(path_raw, str):
        return None
    done_count = _coerce_int(data.get("done_count", 0), 0)
    last_status_raw = data.get("last_status")
    last_status = str(last_status_raw) if isinstance(last_status_raw, str) else None
    last_hash_raw = data.get("last_hash")
    last_hash = str(last_hash_raw) if isinstance(last_hash_raw, str) else None
    modified_files = bool(data.get("modified_files", False))
    return SpecProgress(
        path=path_raw,
        done_count=done_count,
        last_status=last_status,
        last_hash=last_hash,
        modified_files=modified_files,
    )


def _state_from_dict(data: dict[str, object]) -> MultiSpecState | None:
    version = _coerce_int(data.get("version", 0), 0)
    iteration = _coerce_int(data.get("iteration", 0), 0)
    status_raw = str(data.get("status", "IDLE")).upper()
    current_index = _coerce_int(data.get("current_index", 0), 0)
    specs_raw = data.get("specs", [])

    try:
        status = Status(status_raw)
    except ValueError:
        status = Status.CONTINUE

    if not isinstance(specs_raw, list):
        return None

    specs: list[SpecProgress] = []
    for item in specs_raw:
        if not isinstance(item, dict):
            continue
        spec = _spec_progress_from_dict(item)
        if spec:
            specs.append(spec)

    return MultiSpecState(
        version=version,
        iteration=iteration,
        status=status,
        current_index=current_index,
        specs=specs,
    )


def _state_to_dict(state: MultiSpecState) -> dict[str, object]:
    specs_data = []
    for spec in state.specs:
        spec_dict: dict[str, object] = {"path": spec.path, "done_count": spec.done_count}
        if spec.last_status is not None:
            spec_dict["last_status"] = spec.last_status
        if spec.last_hash is not None:
            spec_dict["last_hash"] = spec.last_hash
        if spec.modified_files:
            spec_dict["modified_files"] = spec.modified_files
        specs_data.append(spec_dict)
    return {
        "version": state.version,
        "iteration": state.iteration,
        "status": state.status.value,
        "current_index": state.current_index,
        "specs": specs_data,
    }


def read_multi_state(root: Path | None = None) -> MultiSpecState | None:
    """Read multi-spec state from state.json."""
    path = get_state_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return _state_from_dict(data)


def write_multi_state(state: MultiSpecState, root: Path | None = None) -> None:
    """Write multi-spec state to state.json."""
    path = get_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_state_to_dict(state), indent=2), encoding="utf-8")


def _legacy_int(path: Path, default: int = 0) -> int:
    content = read_file(path, str(default))
    try:
        return int(content)
    except ValueError:
        return default


def _legacy_status(path: Path, default: str = "IDLE") -> Status:
    content = read_file(path, default).upper()
    try:
        return Status(content)
    except ValueError:
        return Status.CONTINUE


def _legacy_state(root: Path) -> RalphState:
    ralph_dir = get_ralph_dir(root)
    return RalphState(
        iteration=_legacy_int(ralph_dir / ITERATION_FILE, 0),
        done_count=_legacy_int(ralph_dir / DONE_COUNT_FILE, 0),
        status=_legacy_status(ralph_dir / STATUS_FILE, "IDLE"),
    )


def _ensure_dirs(root: Path) -> None:
    ralph_dir = get_ralph_dir(root)
    (ralph_dir / HANDOFF_DIR).mkdir(parents=True, exist_ok=True)
    (ralph_dir / HISTORY_DIR).mkdir(parents=True, exist_ok=True)


def _ensure_spec_resources(spec_paths: list[str], root: Path) -> None:
    legacy_handoff = get_handoff_path(None, root)
    single_prompt = len(spec_paths) == 1 and is_prompt_path(spec_paths[0])
    skip_prompt_handoff = single_prompt and legacy_handoff.exists()
    for spec_path in spec_paths:
        if not (skip_prompt_handoff and is_prompt_path(spec_path)):
            handoff_path = get_handoff_path(spec_path, root)
            if not handoff_path.exists():
                write_file(handoff_path, HANDOFF_TEMPLATE)
        get_history_dir(root, spec_path).mkdir(parents=True, exist_ok=True)


def ensure_state(
    spec_paths: list[str],
    root: Path | None = None,
) -> MultiSpecState:
    """Load state.json and sync with the current spec list."""
    if root is None:
        root = Path.cwd()

    _ensure_dirs(root)

    state = read_multi_state(root)
    spec_set = set(spec_paths)

    if state is None:
        legacy = _legacy_state(root)
        specs = [SpecProgress(path=path, done_count=0, last_hash=None) for path in spec_paths]
        if len(specs) == 1:
            specs[0] = SpecProgress(path=specs[0].path, done_count=legacy.done_count)
        state = MultiSpecState(
            version=STATE_VERSION,
            iteration=legacy.iteration,
            status=legacy.status,
            current_index=0,
            specs=specs,
        )
        write_multi_state(state, root)
        _migrate_legacy_assets(spec_paths, root)
        _ensure_spec_resources(spec_paths, root)
        return state

    existing_paths = [spec.path for spec in state.specs]
    existing_set = set(existing_paths)
    spec_set_changed = spec_set != existing_set

    current_path = None
    if state.specs and 0 <= state.current_index < len(state.specs):
        current_path = state.specs[state.current_index].path

    # Preserve existing order for existing specs; append new specs in discovery order.
    path_order = [path for path in existing_paths if path in spec_set]
    path_order.extend(path for path in spec_paths if path not in existing_set)

    new_specs: list[SpecProgress] = []
    existing_map = {spec.path: spec for spec in state.specs}
    migrated_hashes = False
    spec_infos: list[tuple[str, int, str | None, str | None, bool, bool]] = []
    for path in path_order:
        existing = existing_map.get(path)
        done_count = existing.done_count if existing else 0
        last_status = existing.last_status if existing else None
        last_hash = existing.last_hash if existing else None
        modified_files = existing.modified_files if existing else False
        current_hash = spec_content_hash(root / path)
        spec_modified = (
            last_hash is not None and current_hash is not None and current_hash != last_hash
        )
        if existing is not None and last_hash is None and current_hash is not None:
            last_hash = current_hash
            migrated_hashes = True
        spec_infos.append((path, done_count, last_status, last_hash, modified_files, spec_modified))

    for path, done_count, last_status, last_hash, modified_files, spec_modified in spec_infos:
        if spec_modified:
            done_count = 0
        if spec_modified:
            last_status = None
            modified_files = False
        new_specs.append(
            SpecProgress(
                path=path,
                done_count=done_count,
                last_status=last_status,
                last_hash=last_hash,
                modified_files=modified_files,
            )
        )

    current_index = path_order.index(current_path) if current_path in path_order else 0

    updated = MultiSpecState(
        version=state.version,
        iteration=state.iteration,
        status=state.status,
        current_index=current_index,
        specs=new_specs,
    )

    if spec_set_changed or current_index != state.current_index or migrated_hashes:
        write_multi_state(updated, root)

    _ensure_spec_resources(spec_paths, root)
    return updated


def _migrate_legacy_assets(spec_paths: list[str], root: Path) -> None:
    ralph_dir = get_ralph_dir(root)
    legacy_handoff = ralph_dir / HANDOFF_FILE

    prompt_spec = None
    for spec_path in spec_paths:
        if is_prompt_path(spec_path):
            prompt_spec = spec_path
            break

    if prompt_spec and legacy_handoff.exists():
        spec_handoff = get_handoff_path(prompt_spec, root)
        if not spec_handoff.exists():
            write_file(spec_handoff, read_file(legacy_handoff, HANDOFF_TEMPLATE))

    history_dir = get_history_dir(root)
    if history_dir.exists():
        log_files = list(history_dir.glob("*.log"))
        has_subdirs = any(path.is_dir() for path in history_dir.iterdir())
        if log_files and not has_subdirs and len(spec_paths) == 1:
            spec_history_dir = get_history_dir(root, spec_paths[0])
            spec_history_dir.mkdir(parents=True, exist_ok=True)
            for log_file in log_files:
                shutil.move(str(log_file), str(spec_history_dir / log_file.name))


def get_ralph_dir(root: Path | None = None) -> Path:
    """Get the .ralph directory path."""
    if root is None:
        root = Path.cwd()
    return root / RALPH_DIR


def is_initialized(root: Path | None = None) -> bool:
    """Check if Ralph is initialized in the given directory."""
    return get_ralph_dir(root).exists()


def read_file(path: Path, default: str = "") -> str:
    """Read a file, returning default if it doesn't exist."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return default


def write_file(path: Path, content: str) -> None:
    """Write content to a file, creating parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_iteration(root: Path | None = None) -> int:
    """Read the current iteration number."""
    state = read_multi_state(root)
    if state:
        return state.iteration
    ralph_dir = get_ralph_dir(root)
    return _legacy_int(ralph_dir / ITERATION_FILE, 0)


def write_iteration(iteration: int, root: Path | None = None) -> None:
    """Write the iteration number."""
    ralph_dir = get_ralph_dir(root)
    write_file(ralph_dir / ITERATION_FILE, str(iteration))
    state = read_multi_state(root)
    if state:
        updated = MultiSpecState(
            version=state.version,
            iteration=iteration,
            status=state.status,
            current_index=state.current_index,
            specs=state.specs,
        )
        write_multi_state(updated, root)


def read_done_count(root: Path | None = None) -> int:
    """Read the done count."""
    state = read_multi_state(root)
    if state and state.specs and 0 <= state.current_index < len(state.specs):
        return state.specs[state.current_index].done_count
    ralph_dir = get_ralph_dir(root)
    return _legacy_int(ralph_dir / DONE_COUNT_FILE, 0)


def write_done_count(count: int, root: Path | None = None) -> None:
    """Write the done count."""
    ralph_dir = get_ralph_dir(root)
    write_file(ralph_dir / DONE_COUNT_FILE, str(count))
    state = read_multi_state(root)
    if state and state.specs and 0 <= state.current_index < len(state.specs):
        specs = list(state.specs)
        current = specs[state.current_index]
        specs[state.current_index] = SpecProgress(
            path=current.path,
            done_count=count,
            last_status=current.last_status,
            last_hash=current.last_hash,
            modified_files=current.modified_files,
        )
        updated = MultiSpecState(
            version=state.version,
            iteration=state.iteration,
            status=state.status,
            current_index=state.current_index,
            specs=specs,
        )
        write_multi_state(updated, root)


def read_status(root: Path | None = None) -> Status:
    """Read the current status."""
    ralph_dir = get_ralph_dir(root)
    content = read_file(ralph_dir / STATUS_FILE, "IDLE").upper()
    try:
        return Status(content)
    except ValueError:
        return Status.CONTINUE


def write_status(status: Status, root: Path | None = None) -> None:
    """Write the status."""
    ralph_dir = get_ralph_dir(root)
    write_file(ralph_dir / STATUS_FILE, status.value)


def read_state(root: Path | None = None) -> RalphState:
    """Read the complete Ralph state."""
    return RalphState(
        iteration=read_iteration(root),
        done_count=read_done_count(root),
        status=read_status(root),
    )


def get_handoff_path(spec_path: str | None, root: Path | None = None) -> Path:
    """Get the handoff path for a spec or legacy handoff."""
    ralph_dir = get_ralph_dir(root)
    if spec_path is None:
        return ralph_dir / HANDOFF_FILE
    key = spec_resource_key(spec_path)
    return ralph_dir / HANDOFF_DIR / f"{key}.md"


def read_handoff(root: Path | None = None, spec_path: str | None = None) -> str:
    """Read the handoff file content."""
    path = get_handoff_path(spec_path, root)
    if spec_path is not None and not path.exists():
        legacy_path = get_handoff_path(None, root)
        if legacy_path.exists():
            return read_file(legacy_path, HANDOFF_TEMPLATE)
    return read_file(path, HANDOFF_TEMPLATE)


def write_handoff(content: str, root: Path | None = None, spec_path: str | None = None) -> None:
    """Write the handoff file."""
    path = get_handoff_path(spec_path, root)
    write_file(path, content)


def read_guardrails(root: Path | None = None) -> str:
    """Read the guardrails file content."""
    ralph_dir = get_ralph_dir(root)
    return read_file(ralph_dir / GUARDRAILS_FILE, GUARDRAILS_TEMPLATE)


def write_guardrails(content: str, root: Path | None = None) -> None:
    """Write the guardrails file."""
    ralph_dir = get_ralph_dir(root)
    write_file(ralph_dir / GUARDRAILS_FILE, content)


def get_history_dir(root: Path | None = None, spec_path: str | None = None) -> Path:
    """Get the history directory path."""
    base = get_ralph_dir(root) / HISTORY_DIR
    if spec_path is None:
        return base
    key = spec_resource_key(spec_path)
    return base / key


def get_history_file(
    iteration: int, root: Path | None = None, spec_path: str | None = None
) -> Path:
    """Get the path for a specific iteration's log file."""
    return get_history_dir(root, spec_path) / f"{iteration:03d}.log"


def write_history(
    iteration: int, content: str, root: Path | None = None, spec_path: str | None = None
) -> None:
    """Write a history log file."""
    path = get_history_file(iteration, root, spec_path)
    write_file(path, content)


def read_prompt_md(root: Path | None = None) -> str | None:
    """Read PROMPT.md if it exists."""
    if root is None:
        root = Path.cwd()
    prompt_path = root / "PROMPT.md"
    if not prompt_path.exists():
        return None
    content = prompt_path.read_text(encoding="utf-8").strip()
    return content if content else None
