"""Spec discovery and naming utilities."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class Spec:
    """Represents a discovered spec file."""

    path: Path
    rel_posix: str
    is_prompt: bool


def _rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def discover_specs(root: Path | None = None) -> list[Spec]:
    """Discover spec files in supported locations."""
    if root is None:
        root = Path.cwd()

    specs: list[Spec] = []

    prompt_path = root / "PROMPT.md"
    if prompt_path.exists():
        specs.append(
            Spec(
                path=prompt_path,
                rel_posix=_rel_posix(prompt_path, root),
                is_prompt=True,
            )
        )

    spec_roots = [root / ".ralph" / "specs", root / "specs"]
    for spec_root in spec_roots:
        if not spec_root.exists():
            continue
        for path in spec_root.rglob("*.spec.md"):
            if path.is_file():
                specs.append(
                    Spec(
                        path=path,
                        rel_posix=_rel_posix(path, root),
                        is_prompt=False,
                    )
                )

    specs.sort(key=spec_sort_key)
    return specs


# Regex to match .every-[n].spec.md pattern at the end of a filename.
# The name portion (before .every-) can contain any valid characters.
# If multiple .every-[n] segments exist, we use the last one.
_EVERY_N_RE = re.compile(r"\.every-(\d+)\.spec\.md$")


def parse_every_n(rel_posix: str) -> int:
    """Extract the schedule period from a spec path.

    Matches the pattern ``.every-[n].spec.md`` at the end of the filename.
    If there are multiple ``.every-[n]`` segments, uses the **last** one.
    Returns 1 (regular spec — runs every rotation) when no valid pattern is found.

    Valid: ``cleanup.every-3.spec.md`` -> 3
    Valid: ``a.every-2.b.every-5.spec.md`` -> 5 (last match)
    Invalid: ``my.every.spec.md`` -> 1 (no number after .every-)
    Invalid: ``.every-.spec.md`` -> 1 (no number)
    Invalid: ``.every-0.spec.md`` -> 1 (zero is not valid; not a system spec)
    Invalid: ``.every-1.spec.md`` -> 1 (period of 1 is meaningless; treated as regular)
    """
    matches = _EVERY_N_RE.findall(rel_posix)
    if not matches:
        return 1
    n = int(matches[-1])
    return n if n > 1 else 1


def is_system_spec(rel_posix: str) -> bool:
    """A spec is a 'system spec' if its filename encodes a period > 1.

    System specs run on every n-th iteration before the regular spec phase,
    are stateless (no state.json entry), and use a dedicated prompt template.
    """
    return parse_every_n(rel_posix) > 1


def system_spec_eligible(rel_posix: str, iteration: int) -> bool:
    """Return True if the system spec should fire at this iteration."""
    n = parse_every_n(rel_posix)
    if n <= 1:
        return False
    return iteration % n == 0


def split_specs(specs: list[Spec]) -> tuple[list[Spec], list[Spec]]:
    """Partition discovered specs into (regular, system).

    Regular specs (every_n == 1) flow through the existing 0→3 verification cycle.
    System specs (every_n > 1) are sorted alphabetically by relative path so
    that on iterations where multiple are eligible they fire in a deterministic
    order.
    """
    regular: list[Spec] = []
    system: list[Spec] = []
    for spec in specs:
        if is_system_spec(spec.rel_posix):
            system.append(spec)
        else:
            regular.append(spec)
    system.sort(key=lambda s: s.rel_posix)
    return regular, system


def spec_sort_key(spec: Spec) -> tuple[int, str]:
    """Sort prompt first, then alphabetical by relative path."""
    if spec.is_prompt:
        return (0, "000-prompt.spec.md")
    return (1, spec.rel_posix)


def spec_priority_key(
    spec_path: str,
    last_status: str | None,
    last_hash: str | None,
    current_hash: str | None,
    modified_files: bool = False,
    done_count: int = 0,
) -> tuple[int, int, str]:
    """Return sort key for smart spec sorting.

    Priority tiers (lower is higher priority):
    0 - New specs (no last_status)
    1 - Modified specs (content hash changed)
    2 - Non-DONE last_status (CONTINUE, ROTATE, STUCK, etc.)
    3 - DONE last_status that modified files (more likely to produce changes again)
    4 - DONE last_status that didn't modify files (least likely to produce changes)

    Within tier 4, prefer lower verification count first (e.g., 1/3 before 2/3).
    Within each tier (or same verification count in tier 4), maintain alphabetical order.
    """
    is_new = last_status is None
    is_modified = last_hash is not None and current_hash is not None and last_hash != current_hash

    if is_new:
        return (0, 0, spec_path)
    elif is_modified:
        return (1, 0, spec_path)
    elif last_status != "DONE":
        return (2, 0, spec_path)
    elif modified_files:
        return (3, 0, spec_path)
    else:
        # Tier 4: DONE without file changes - prefer lower done_count
        return (4, done_count, spec_path)


def sort_specs_by_state(
    specs: list[Spec],
    spec_states: dict[str, tuple[str | None, str | None, bool, int]],
    root: Path,
) -> list[Spec]:
    """Sort specs by priority based on their saved state.

    Args:
        specs: List of discovered specs (already sorted alphabetically)
        spec_states: Map of spec path -> (last_status, last_hash, modified_files, done_count)
        root: Project root for computing current hashes

    Returns:
        Specs sorted by priority: new first, modified second, non-DONE third,
        DONE with file changes fourth, DONE without file changes last.
        Within DONE without file changes (tier 4), lower verification count comes first.
        Within each tier (or same verification count), alphabetical order is maintained.
    """

    def sort_key(spec: Spec) -> tuple[int, int, str]:
        state = spec_states.get(spec.rel_posix, (None, None, False, 0))
        last_status, last_hash, modified_files, done_count = state
        current_hash = spec_content_hash(spec.path)
        return spec_priority_key(
            spec.rel_posix, last_status, last_hash, current_hash, modified_files, done_count
        )

    return sorted(specs, key=sort_key)


def spec_hash(rel_posix: str) -> str:
    """Short hash for a spec path using forward slashes (not for security)."""
    normalized = PurePosixPath(rel_posix.replace("\\", "/")).as_posix()
    digest = hashlib.sha1(normalized.encode("utf-8"), usedforsecurity=False).hexdigest()  # nosec B324
    return digest[:6]


def spec_content_hash(path: Path) -> str | None:
    """Return a sha1 hash of the spec content, or None if missing (not for security)."""
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return None
    return hashlib.sha1(content, usedforsecurity=False).hexdigest()  # nosec B324


def is_prompt_path(rel_posix: str) -> bool:
    """Return True if the path represents the root PROMPT.md."""
    return PurePosixPath(rel_posix).as_posix().lower() == "prompt.md"


def spec_base_name(rel_posix: str) -> str:
    """Return the base name for storage (without .md)."""
    if is_prompt_path(rel_posix):
        return "000-prompt"
    normalized = rel_posix.replace("\\", "/")
    name = PurePosixPath(normalized).name
    if name.endswith(".md"):
        name = name[:-3]
    # Replace spaces and tabs with hyphens for filesystem safety
    name = name.replace(" ", "-").replace("\t", "-")
    return name


def spec_resource_key(rel_posix: str) -> str:
    """Return the {name}-{hash} key for per-spec storage."""
    return f"{spec_base_name(rel_posix)}-{spec_hash(rel_posix)}"


def read_spec_content(path: Path) -> str | None:
    """Read spec content, returning None if empty."""
    try:
        content = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return content if content else None
