"""JSON-path-lite: `a.b[*].c`, `a.b[0].c`. No eval, no regex over user data beyond key splitting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PathResult:
    found: bool
    values: list[Any] = field(default_factory=list)


def _split(path: str) -> list[str | int | None]:
    """'a.b[*].c' -> ['a', 'b', None, 'c']; 'a[2]' -> ['a', 2]. None is the wildcard."""
    parts: list[str | int | None] = []
    for segment in path.split("."):
        if not segment:
            continue
        head, _, rest = segment.partition("[")
        if head:
            parts.append(head)
        while rest:
            index, _, rest = rest.partition("]")
            if index == "*":
                parts.append(None)
            elif index.isdigit():
                parts.append(int(index))
            else:
                raise ValueError(f"unsupported path segment [{index}]")
            rest = rest.lstrip(".")
            if rest and not rest.startswith("["):
                # 'a[0]b' is malformed; a key after an index must be dotted, handled by the outer split
                raise ValueError("malformed path")
            if rest.startswith("["):
                rest = rest[1:]
    return parts


def _lookup_key(obj: Any, key: str) -> tuple[bool, Any]:
    if isinstance(obj, dict):
        if key in obj:
            return True, obj[key]
        lowered = key.lower()
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() == lowered:
                return True, v
    return False, None


def get_path(obj: Any, path: str) -> PathResult:
    """Resolve a dotted path. `[*]` fans out; `found` is True only when every step resolved for at least one value."""
    current: list[Any] = [obj]
    for part in _split(path):
        next_values: list[Any] = []
        for value in current:
            if part is None:
                if isinstance(value, list):
                    next_values.extend(value)
            elif isinstance(part, int):
                if isinstance(value, list) and 0 <= part < len(value):
                    next_values.append(value[part])
            else:
                ok, v = _lookup_key(value, part)
                if ok:
                    next_values.append(v)
        if not next_values:
            return PathResult(False, [])
        current = next_values
    return PathResult(True, current)
