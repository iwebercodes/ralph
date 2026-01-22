"""Spec discovery and naming utilities."""

from __future__ import annotations

import hashlib
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


def spec_sort_key(spec: Spec) -> tuple[int, str]:
    """Sort prompt first, then alphabetical by relative path."""
    if spec.is_prompt:
        return (0, "000-prompt.spec.md")
    return (1, spec.rel_posix)


def spec_hash(rel_posix: str) -> str:
    """Short hash for a spec path using forward slashes."""
    normalized = PurePosixPath(rel_posix.replace("\\", "/")).as_posix()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
    return digest[:6]


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
