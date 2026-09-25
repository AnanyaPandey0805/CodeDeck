import re
from pathlib import Path

SUSPICIOUS_REQUIREMENT_NAMES = {"install"}
LEGACY_PYTHON_310_PACKAGES = {
    "greenlet": (2, 0),
    "httptools": (0, 5),
    "orjson": (3, 8),
}


def _requirement_name(line: str) -> str | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith(("-", "git+", "http://", "https://")):
        return None
    text = text.split(";", 1)[0].strip()
    text = re.split(r"[<>=!~]", text, maxsplit=1)[0].strip()
    text = text.split("[", 1)[0].strip()
    if not text:
        return None
    return text.lower()


def sanitize_requirements_file(repo_dir: Path) -> list[str]:
    path = repo_dir / "requirements.txt"
    if not path.is_file():
        return []

    original = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    kept: list[str] = []
    removed: list[str] = []
    for line in original:
        name = _requirement_name(line)
        if name in SUSPICIOUS_REQUIREMENT_NAMES:
            removed.append(line.strip())
            continue
        kept.append(line)

    if removed:
        content = "\n".join(kept).rstrip()
        path.write_text((content + "\n") if content else "", encoding="utf-8")
    return removed


def _parse_requirement_version(line: str) -> tuple[str | None, tuple[int, ...] | None]:
    text = line.strip()
    if not text or text.startswith("#"):
        return None, None
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*==\s*([0-9][0-9A-Za-z_.-]*)", text)
    if not match:
        return None, None
    name = match.group(1).lower()
    version_parts: list[int] = []
    for part in match.group(2).split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        version_parts.append(int(digits))
    return name, tuple(version_parts) if version_parts else None


def choose_python_base_image(repo_dir: Path, default_tag: str = "3.11-slim") -> str:
    path = repo_dir / "requirements.txt"
    if not path.is_file():
        return f"python:{default_tag}"

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        name, version = _parse_requirement_version(line)
        threshold = LEGACY_PYTHON_310_PACKAGES.get(name or "")
        if threshold and version and version < threshold:
            return "python:3.10-slim"
    return f"python:{default_tag}"
