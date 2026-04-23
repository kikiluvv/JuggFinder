from __future__ import annotations

from pathlib import Path


def _format_env_value(value: str) -> str:
    """
    Keep .env output simple and readable.
    - No quoting unless needed (spaces or # which can be comment-like)
    - Escape newlines defensively (we don't expect multiline secrets)
    """
    v = value.replace("\n", "\\n")
    if v == "":
        return ""
    if any(ch.isspace() for ch in v) or "#" in v:
        escaped = v.replace('"', '\\"')
        return f'"{escaped}"'
    return v


def set_env_vars(env_path: str | Path, updates: dict[str, str]) -> None:
    """
    Update or append KEY=VALUE pairs in a .env file.

    - Preserves comments and unknown lines.
    - Only updates keys present in `updates`.
    - Writes a trailing newline.
    """
    path = Path(env_path)
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    remaining = dict(updates)
    out: list[str] = []

    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue

        key, _ = line.split("=", 1)
        key = key.strip()
        if key in remaining:
            out.append(f"{key}={_format_env_value(remaining.pop(key))}")
        else:
            out.append(line)

    if remaining:
        if out and out[-1].strip() != "":
            out.append("")
        for key in sorted(remaining.keys()):
            out.append(f"{key}={_format_env_value(remaining[key])}")

    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
