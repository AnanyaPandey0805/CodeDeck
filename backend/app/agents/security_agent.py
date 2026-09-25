import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger("deploymind")

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    "target",
}

SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"), "HIGH", "Private key material found"),
    (re.compile(r"(?i)(api[_-]?key|apikey|secret[_-]?key)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}"), "HIGH", "Possible hardcoded API key"),
    (re.compile(r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"\s]{4,}"), "HIGH", "Possible hardcoded password"),
    (re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*\S+"), "HIGH", "Possible AWS secret key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "HIGH", "Possible GitHub personal access token"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "HIGH", "Possible OpenAI-style secret key"),
]

CODE_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rb",
    ".env",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".properties",
    ".sh",
    "",
}


class SecurityFinding(BaseModel):
    severity: str
    file: str
    message: str


class SecurityResult(BaseModel):
    findings: list[SecurityFinding] = Field(default_factory=list)
    score: int = 100
    summary: str = "Basic security analysis completed"
    label: str = "basic"


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in CODE_SUFFIXES and path.name not in {".env", "Dockerfile", ".env.example"}:
            if path.name != "Dockerfile":
                continue
        if path.stat().st_size > 500_000:
            continue
        yield path


def _scan_secrets(root: Path) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for path in _iter_files(root):
        name = path.name
        rel = _rel(root, path)

        if name == ".env" or (name.startswith(".env") and name != ".env.example"):
            findings.append(
                SecurityFinding(
                    severity="HIGH",
                    file=rel,
                    message="Environment file present — may contain secrets",
                )
            )

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for pattern, severity, message in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(SecurityFinding(severity=severity, file=rel, message=message))
                break
    return findings


def _scan_dockerfile(root: Path) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for path in list(root.glob("Dockerfile")) + list(root.glob("**/Dockerfile")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = _rel(root, path)
        if re.search(r"(?im)^USER\s+root\s*$", text):
            findings.append(SecurityFinding(severity="MEDIUM", file=rel, message="Container explicitly runs as root"))
        elif not re.search(r"(?im)^USER\s+\S+", text):
            findings.append(SecurityFinding(severity="MEDIUM", file=rel, message="Dockerfile has no USER directive (likely runs as root)"))
        if re.search(r"(?i)--privileged", text):
            findings.append(SecurityFinding(severity="HIGH", file=rel, message="Privileged Docker setting detected"))
    return findings


def _scan_kubernetes(root: Path) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    yaml_files: list[Path] = []
    for folder in ("k8s", "kubernetes", "deploy", "manifests"):
        d = root / folder
        if d.is_dir():
            yaml_files.extend(d.rglob("*.y*ml"))
    yaml_files.extend(root.glob("*.yaml"))
    yaml_files.extend(root.glob("*.yml"))

    for path in yaml_files:
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = _rel(root, path)
        if "kind: Deployment" not in text and "kind: Pod" not in text:
            continue
        if re.search(r"(?i)privileged:\s*true", text):
            findings.append(SecurityFinding(severity="HIGH", file=rel, message="Privileged Kubernetes container"))
        if "securityContext" not in text:
            findings.append(
                SecurityFinding(
                    severity="MEDIUM",
                    file=rel,
                    message="Kubernetes manifest missing securityContext",
                )
            )
    return findings


def _score(findings: list[SecurityFinding]) -> int:
    score = 100
    for f in findings:
        if f.severity == "HIGH":
            score -= 15
        elif f.severity == "MEDIUM":
            score -= 8
        else:
            score -= 3
    return max(0, min(100, score))


def run_security_scan(repo_path: str | Path) -> SecurityResult:
    root = Path(repo_path)
    logger.info("security scan started for %s", root)

    findings = _scan_secrets(root) + _scan_dockerfile(root) + _scan_kubernetes(root)

    # de-dupe by file+message
    seen: set[tuple[str, str]] = set()
    unique: list[SecurityFinding] = []
    for f in findings:
        key = (f.file, f.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)

    score = _score(unique)
    high = sum(1 for f in unique if f.severity == "HIGH")
    medium = sum(1 for f in unique if f.severity == "MEDIUM")
    if not unique:
        summary = "No issues found (basic scan)"
    else:
        summary = f"{len(unique)} finding(s): {high} high, {medium} medium - basic security analysis"

    logger.info("security scan completed: score=%s findings=%s", score, len(unique))
    return SecurityResult(findings=unique, score=score, summary=summary, label="basic")
