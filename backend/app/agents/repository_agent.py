import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger("deploymind")

K8S_NAMES = {
    "deployment.yaml",
    "deployment.yml",
    "service.yaml",
    "service.yml",
    "rbac.yaml",
    "rbac.yml",
}


def _find_fastapi_entrypoint(root: Path) -> str:
    """Find the exact FastAPI application entrypoint (module:attr)."""
    # 1. Search for uvicorn.run("...", ...) in startup scripts
    for fname in ("main.py", "app.py", "run.py", "server.py", "wsgi.py", "asgi.py"):
        fpath = root / fname
        if fpath.exists():
            text = _read_text(fpath)
            m = re.search(r'uvicorn\.run\(\s*["\']([^"\']+)["\']', text)
            if m:
                return m.group(1).strip()

    # 2. Search for variable = FastAPI(...) in common and discovered Python files
    candidates: list[Path] = [
        root / "app" / "main.py",
        root / "app" / "api.py",
        root / "app" / "app.py",
        root / "src" / "main.py",
        root / "src" / "app.py",
        root / "src" / "api.py",
        root / "main.py",
        root / "app.py",
        root / "api.py",
    ]
    for folder in (root, root / "app", root / "src", root / "api"):
        if folder.is_dir():
            for f in folder.glob("*.py"):
                if f not in candidates and f.is_file():
                    candidates.append(f)

    for fpath in candidates:
        if fpath.is_file():
            text = _read_text(fpath)
            m = re.search(r'(?m)^([a-zA-Z0-9_]+)\s*=\s*(?:[a-zA-Z0-9_]+\.)?FastAPI\(', text)
            if m:
                var_name = m.group(1)
                try:
                    rel = fpath.relative_to(root).with_suffix("")
                    mod_name = ".".join(rel.parts)
                    return f"{mod_name}:{var_name}"
                except ValueError:
                    pass

    # 3. Fallbacks
    if (root / "app" / "main.py").exists():
        return "app.main:app"
    if (root / "main.py").exists():
        return "main:app"
    return "app.main:app"


class RepositoryAnalysis(BaseModel):
    language: str
    framework: str | None = None
    package_manager: str | None = None
    entrypoint: str | None = None
    test_framework: str | None = None
    test_command: str | None = None
    has_dockerfile: bool = False
    has_kubernetes: bool = False
    supported: bool = True
    message: str = ""
    port: int = 8000
    source_subdir: str | None = None
    top_level_files: list[str] = Field(default_factory=list)
    is_multiservice: bool = False
    detected_services: list[str] = Field(default_factory=list)
    multiservice_notice: str | None = None


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _has_k8s(root: Path) -> bool:
    for folder in (root / "k8s", root / "kubernetes", root / "deploy", root / "manifests"):
        if folder.is_dir():
            for p in folder.rglob("*"):
                if p.suffix in {".yaml", ".yml"}:
                    return True
    for name in K8S_NAMES:
        if (root / name).exists():
            return True
    return False


def _detect_python(root: Path, names: set[str]) -> RepositoryAnalysis | None:
    markers = {"requirements.txt", "pyproject.toml", "uv.lock", "poetry.lock", "Pipfile", "setup.py", "manage.py", "app.py", "main.py"}
    if not (names & markers) and not (root / "app").is_dir():
        return None

    pyproject_text = _read_text(root / "pyproject.toml") if "pyproject.toml" in names else ""

    if "uv.lock" in names or "[tool.uv]" in pyproject_text:
        pm = "uv"
    elif "poetry.lock" in names or "[tool.poetry]" in pyproject_text:
        pm = "poetry"
    elif "Pipfile" in names:
        pm = "pipenv"
    else:
        pm = "pip"

    blob = ""
    for fname in ("requirements.txt", "pyproject.toml", "Pipfile"):
        if (root / fname).exists():
            blob += _read_text(root / fname).lower() + "\n"

    for candidate_dir in (root, root / "app", root / "src", root / "api"):
        if candidate_dir.is_dir():
            for py_path in candidate_dir.glob("*.py"):
                blob += _read_text(py_path).lower() + "\n"

    port = 8000
    if "fastapi" in blob:
        framework = "FastAPI"
        entrypoint = _find_fastapi_entrypoint(root)
    elif "django" in blob or "manage.py" in names:
        framework = "Django"
        entrypoint = "manage.py"
    elif "flask" in blob:
        framework = "Flask"
        entrypoint = "app:app" if (root / "app.py").exists() else ("app.main:app" if (root / "app" / "main.py").exists() else "wsgi:app")
        port = 5000
    else:
        framework = "Python"
        entrypoint = "main:app" if (root / "main.py").exists() else None

    test_framework = None
    test_command = None
    if "pytest" in blob or any(root.glob("test_*.py")) or (root / "tests").is_dir():
        test_framework = "pytest"
        test_command = "pytest"
    elif "unittest" in blob:
        test_framework = "unittest"
        test_command = "python -m unittest"

    return RepositoryAnalysis(
        language="Python",
        framework=framework,
        package_manager=pm,
        entrypoint=entrypoint,
        test_framework=test_framework,
        test_command=test_command,
        has_dockerfile=(root / "Dockerfile").exists(),
        has_kubernetes=_has_k8s(root),
        message=f"{framework} project detected ({pm})",
        port=port,
        top_level_files=sorted(names)[:40],
    )


def _detect_node(root: Path, names: set[str]) -> RepositoryAnalysis | None:
    pkg_path = root / "package.json"
    if not pkg_path.exists():
        return None

    try:
        pkg = json.loads(_read_text(pkg_path))
    except json.JSONDecodeError:
        pkg = {}

    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    scripts = pkg.get("scripts") or {}

    if "bun.lock" in names or "bun.lockb" in names:
        pm = "bun"
    elif "pnpm-lock.yaml" in names:
        pm = "pnpm"
    elif "yarn.lock" in names:
        pm = "yarn"
    else:
        pm = "npm"

    framework = "Node.js"
    entrypoint = pkg.get("main") or "index.js"
    port = 3000

    if "react" in deps or "react-scripts" in deps or "vite" in deps:
        framework = "React"
        entrypoint = "npm run build"
    if "express" in deps:
        framework = "Express" if framework == "Node.js" else f"{framework}+Express"
        for candidate in ("server.js", "index.js", "app.js", "src/index.js", "src/server.js"):
            if (root / candidate).exists():
                entrypoint = candidate
                break
        port = 3000
    elif framework == "Node.js":
        for candidate in ("server.js", "index.js", "app.js"):
            if (root / candidate).exists():
                entrypoint = candidate
                break

    test_framework = None
    test_command = None
    if "test" in scripts:
        test_command = f"{pm} test"
        if "jest" in deps:
            test_framework = "jest"
        elif "vitest" in deps:
            test_framework = "vitest"
        else:
            test_framework = pm
    elif "jest" in deps:
        test_framework = "jest"
        test_command = f"{pm} test"

    return RepositoryAnalysis(
        language="JavaScript",
        framework=framework,
        package_manager=pm,
        entrypoint=entrypoint,
        test_framework=test_framework,
        test_command=test_command,
        has_dockerfile=(root / "Dockerfile").exists(),
        has_kubernetes=_has_k8s(root),
        message=f"{framework} project detected ({pm})",
        port=port,
        top_level_files=sorted(names)[:40],
    )


def _detect_java(root: Path, names: set[str]) -> RepositoryAnalysis | None:
    if "pom.xml" not in names and "build.gradle" not in names and "build.gradle.kts" not in names:
        return None

    blob = ""
    for fname in ("pom.xml", "build.gradle", "build.gradle.kts"):
        if (root / fname).exists():
            blob += _read_text(root / fname).lower()

    framework = "Spring Boot" if "spring-boot" in blob or "springframework" in blob else "Java"
    if "pom.xml" in names:
        pm = "maven"
        test_command = "./mvnw test" if (root / "mvnw").exists() else "mvn test"
    else:
        pm = "gradle"
        test_command = "./gradlew test" if (root / "gradlew").exists() else "gradle test"

    return RepositoryAnalysis(
        language="Java",
        framework=framework,
        package_manager=pm,
        entrypoint=None,
        test_framework="junit",
        test_command=test_command,
        has_dockerfile=(root / "Dockerfile").exists(),
        has_kubernetes=_has_k8s(root),
        message=f"{framework} project detected ({pm})",
        port=8080,
        top_level_files=sorted(names)[:40],
    )


def analyze_repository(repo_path: str | Path) -> RepositoryAnalysis:
    root = Path(repo_path)
    if not root.is_dir():
        raise FileNotFoundError(f"Repository path not found: {root}")

    names = {p.name for p in root.iterdir()}
    logger.info("analysis started for %s", root)

    # Detect multi-service structures (e.g. backend/ and frontend/)
    subdirs = {p.name.lower() for p in root.iterdir() if p.is_dir()}
    detected_services = []
    if "backend" in subdirs or "server" in subdirs or "api" in subdirs:
        backend_dir_name = "backend" if "backend" in subdirs else ("server" if "server" in subdirs else "api")
        detected_services.append(backend_dir_name)
    if "frontend" in subdirs or "client" in subdirs or "web" in subdirs:
        frontend_dir_name = "frontend" if "frontend" in subdirs else ("client" if "client" in subdirs else "web")
        detected_services.append(frontend_dir_name)

    is_multi = len(detected_services) > 1
    multiservice_notice = None
    if is_multi:
        multiservice_notice = f"Multi-service repository detected ({', '.join(detected_services)}). DeployMind containerizes the primary backend service for Kubernetes deployment."

    # Full-stack repos often have a root package.json plus a Python backend/
    for sub in ("backend", "server", "api"):
        sub_dir = root / sub
        if sub_dir.is_dir() and (
            (sub_dir / "requirements.txt").exists()
            or (sub_dir / "pyproject.toml").exists()
            or (sub_dir / "app").is_dir()
            or (sub_dir / "main.py").exists()
        ):
            nested = analyze_repository(sub_dir)
            if nested.supported and nested.language == "Python":
                nested.message = f"{nested.message} ({sub}/)"
                nested.source_subdir = sub
                nested.top_level_files = sorted(names)[:40]
                nested.is_multiservice = is_multi
                nested.detected_services = detected_services
                nested.multiservice_notice = multiservice_notice
                logger.info("analysis completed: %s / %s (%s/)", nested.language, nested.framework, sub)
                return nested

    python = _detect_python(root, names)
    node = _detect_node(root, names)
    java = _detect_java(root, names)

    for candidate in (python, java, node):
        if candidate and candidate.framework in {"FastAPI", "Flask", "Django", "Spring Boot", "Express", "React"}:
            candidate.is_multiservice = is_multi
            candidate.detected_services = detected_services
            candidate.multiservice_notice = multiservice_notice
            logger.info("analysis completed: %s / %s", candidate.language, candidate.framework)
            return candidate

    for candidate in (python, java, node):
        if candidate is not None:
            candidate.is_multiservice = is_multi
            candidate.detected_services = detected_services
            candidate.multiservice_notice = multiservice_notice
            logger.info("analysis completed: %s / %s", candidate.language, candidate.framework)
            return candidate

    unsupported = RepositoryAnalysis(
        language="Unknown",
        supported=False,
        has_dockerfile=(root / "Dockerfile").exists(),
        has_kubernetes=_has_k8s(root),
        message="Unsupported project type. DeployMind supports Python (FastAPI/Flask/Django), JavaScript (Node/Express/React), and Java (Spring Boot).",
        top_level_files=sorted(names)[:40],
        is_multiservice=is_multi,
        detected_services=detected_services,
        multiservice_notice=multiservice_notice,
    )
    logger.info("analysis completed: unsupported")
    return unsupported

