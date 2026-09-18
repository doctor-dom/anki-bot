"""Resolve repo root and default output directory."""

from __future__ import annotations

from pathlib import Path

DEFAULT_OUTPUT_DIRNAME = "output"
DEFAULT_INPUT_DIRNAME = "input"


def resolve_default_input(cwd: Path | None = None) -> Path:
    """Default input folder anchored to repo root when pyproject.toml is found."""
    working = (cwd or Path.cwd()).resolve()
    repo = find_repo_root(working)
    if repo is not None:
        return (repo / DEFAULT_INPUT_DIRNAME).resolve()
    return (working / DEFAULT_INPUT_DIRNAME).resolve()


def find_repo_root(*starts: Path) -> Path | None:
    """Return directory containing pyproject.toml, walking up from each start path."""
    seen: set[Path] = set()
    for start in starts:
        path = start.resolve()
        if path.is_file():
            path = path.parent
        for candidate in (path, *path.parents):
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if (resolved / "pyproject.toml").is_file():
                return resolved
    return None


def is_default_output_arg(output_arg: str | Path) -> bool:
    normalized = Path(output_arg).as_posix().rstrip("/")
    return normalized == DEFAULT_OUTPUT_DIRNAME


def resolve_output_root(
    output_arg: str | Path,
    *,
    anchor_path: Path,
    cwd: Path | None = None,
) -> Path:
    """
    Resolve -o/--output.

    Default relative ``output`` is anchored to the repo root (pyproject.toml),
    not the shell cwd. Other relative paths resolve from cwd; absolute paths unchanged.
    """
    output = Path(output_arg)
    working = (cwd or Path.cwd()).resolve()
    anchor = anchor_path.resolve()
    if anchor.is_file():
        anchor = anchor.parent

    if output.is_absolute():
        return output.resolve()

    if is_default_output_arg(output):
        repo = find_repo_root(anchor, working)
        if repo is not None:
            return (repo / DEFAULT_OUTPUT_DIRNAME).resolve()
        return (working / DEFAULT_OUTPUT_DIRNAME).resolve()

    return (working / output).resolve()
