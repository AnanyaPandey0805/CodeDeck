import hashlib
import json
import logging
import math
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.prompts import (
    DEPLOYMENT_RECOMMENDATION_PROMPT,
    FAILURE_ANALYSIS_PROMPT,
    RAG_QA_PROMPT,
    TEST_GENERATION_PROMPT,
)
from app.services.dependency_sanitizer import sanitize_requirements_file
from app.services.github import cleanup_repository, clone_repository

logger = logging.getLogger("deploymind")

INDEX_VERSION = 1
EMBEDDING_DIMENSIONS = 192
MAX_FILE_SIZE = 180_000
CHUNK_SIZE = 1400
CHUNK_OVERLAP = 220
INCLUDED_FILENAMES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "readme.md",
    ".env.example",
}
TEXT_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".kt",
    ".go",
    ".rb",
    ".php",
    ".rs",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".txt",
    ".md",
    ".html",
    ".css",
    ".sql",
    ".sh",
    ".bash",
    ".dockerignore",
    ".gitignore",
}
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".turbo",
    "coverage",
    ".idea",
    ".vscode",
}
TEST_BLOCKED_ENV = {"OPENAI_API_KEY", "GITHUB_TOKEN", "GHCR_TOKEN", "DATABASE_URL"}


class RepositoryChunk(BaseModel):
    path: str
    content: str
    line_start: int
    line_end: int
    embedding: list[float]


class SearchResult(BaseModel):
    path: str
    snippet: str
    score: float
    line_start: int
    line_end: int


class RepositoryIndexMetadata(BaseModel):
    version: int = INDEX_VERSION
    project_id: int
    repository_url: str
    chunk_count: int
    file_count: int
    indexed_at: str
    files: list[str] = Field(default_factory=list)


class RepositoryAnswer(BaseModel):
    question: str
    answer: str
    sources: list[SearchResult] = Field(default_factory=list)


class DeploymentRecommendation(BaseModel):
    summary: str
    detected: dict[str, str | int | bool | None] = Field(default_factory=dict)
    potential_issues: list[str] = Field(default_factory=list)
    recommendation: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class EvaluationItem(BaseModel):
    question: str
    expected: str
    answer: str
    matched_source: str | None = None
    status: str


class EvaluationReport(BaseModel):
    questions: int
    correct: int
    retrieval_accuracy: float
    results: list[EvaluationItem] = Field(default_factory=list)


class GeneratedTestCase(BaseModel):
    name: str
    rationale: str
    path: str
    code: str


class AITestRun(BaseModel):
    status: str
    message: str
    command: str | None = None
    generated_tests: list[GeneratedTestCase] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    failure_analysis: dict | None = None


def _workspace_generated_dir(project_id: int) -> Path:
    path = Path(settings.workspace_dir) / "generated" / f"project_{project_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_path(project_id: int) -> Path:
    return _workspace_generated_dir(project_id) / "repository_index.json"


def _looks_textual(path: Path) -> bool:
    if path.name.lower() in INCLUDED_FILENAMES:
        return True
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    return path.suffix == "" and path.name.lower() in {"dockerfile", "makefile"}


def _read_text(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_FILE_SIZE:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _iter_repository_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not _looks_textual(path):
            continue
        yield path


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_./:-]{1,63}", text.lower())


def _hash_embedding(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    vec = [0.0] * dimensions
    for token, count in Counter(_tokenize(text)).items():
        idx = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % dimensions
        vec[idx] += float(count)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _chunk_text(path: Path, text: str) -> list[RepositoryChunk]:
    lines = text.splitlines()
    if not lines:
        return []

    chunks: list[RepositoryChunk] = []
    start = 0
    while start < len(lines):
        end = start
        size = 0
        while end < len(lines) and size < CHUNK_SIZE:
            size += len(lines[end]) + 1
            end += 1

        chunk_lines = lines[start:end]
        chunk_text = "\n".join(chunk_lines).strip()
        if chunk_text:
            chunks.append(
                RepositoryChunk(
                    path=str(path).replace("\\", "/"),
                    content=chunk_text,
                    line_start=start + 1,
                    line_end=end,
                    embedding=_hash_embedding(chunk_text),
                )
            )

        if end >= len(lines):
            break

        overlap_lines = 0
        overlap_size = 0
        while overlap_lines < len(chunk_lines) and overlap_size < CHUNK_OVERLAP:
            overlap_size += len(chunk_lines[-(overlap_lines + 1)]) + 1
            overlap_lines += 1
        start = max(end - overlap_lines, start + 1)
    return chunks


def _trim_snippet(text: str, limit: int = 380) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _load_index_payload(project_id: int) -> dict:
    path = _index_path(project_id)
    if not path.is_file():
        raise FileNotFoundError("Repository index not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_index_payload(project_id: int, payload: dict) -> None:
    path = _index_path(project_id)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_repository_index(repo_path: str | Path, project_id: int, repository_url: str) -> RepositoryIndexMetadata:
    root = Path(repo_path)
    files: list[str] = []
    chunks: list[dict] = []
    for path in _iter_repository_files(root):
        text = _read_text(path)
        if not text.strip():
            continue
        rel = path.relative_to(root).as_posix()
        file_chunks = _chunk_text(Path(rel), text)
        if not file_chunks:
            continue
        files.append(rel)
        chunks.extend(chunk.model_dump() for chunk in file_chunks)

    metadata = RepositoryIndexMetadata(
        project_id=project_id,
        repository_url=repository_url,
        chunk_count=len(chunks),
        file_count=len(files),
        indexed_at=datetime.utcnow().isoformat() + "Z",
        files=sorted(files)[:400],
    )
    payload = {"metadata": metadata.model_dump(), "chunks": chunks}
    _save_index_payload(project_id, payload)
    return metadata


def ensure_repository_index(project_id: int, repository_url: str) -> RepositoryIndexMetadata:
    path = _index_path(project_id)
    if path.is_file():
        payload = _load_index_payload(project_id)
        return RepositoryIndexMetadata.model_validate(payload["metadata"])

    temp_dir = Path(settings.workspace_dir) / f"project_{project_id}_index"
    try:
        clone_repository(repository_url, temp_dir)
        return build_repository_index(temp_dir, project_id, repository_url)
    finally:
        cleanup_repository(temp_dir)


def _all_chunks(project_id: int) -> list[RepositoryChunk]:
    payload = _load_index_payload(project_id)
    return [RepositoryChunk.model_validate(chunk) for chunk in payload.get("chunks", [])]


def search_repository(project_id: int, query: str, limit: int = 4) -> list[SearchResult]:
    chunks = _all_chunks(project_id)
    if not chunks:
        return []
    qvec = _hash_embedding(query)
    ranked = sorted(
        (
            SearchResult(
                path=chunk.path,
                snippet=_trim_snippet(chunk.content),
                score=round(_cosine(qvec, chunk.embedding), 4),
                line_start=chunk.line_start,
                line_end=chunk.line_end,
            )
            for chunk in chunks
        ),
        key=lambda item: item.score,
        reverse=True,
    )
    deduped: list[SearchResult] = []
    seen: set[tuple[str, int]] = set()
    for item in ranked:
        key = (item.path, item.line_start)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _safe_chat(prompt: str) -> str | None:
    if not settings.openai_api_key:
        return None
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        res = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You are a grounded repository assistant. Answer only from provided evidence."},
                {"role": "user", "content": prompt},
            ],
        )
        text = res.choices[0].message.content if res.choices else None
        if isinstance(text, str):
            return text.strip()
    except Exception:
        logger.warning("openai completion failed", exc_info=True)
    return None


def _detect_database(chunks: list[RepositoryChunk]) -> str | None:
    joined = "\n".join(chunk.content.lower() for chunk in chunks[:250])
    patterns = [
        ("PostgreSQL", ("postgres", "psycopg", "sqlalchemy", "postgresql")),
        ("SQLite", ("sqlite",)),
        ("MySQL", ("mysql", "pymysql")),
        ("MongoDB", ("mongodb", "pymongo", "mongoose")),
        ("Redis", ("redis",)),
    ]
    for name, terms in patterns:
        if all(term in joined for term in terms[:1]):
            return name
    return None


def _detect_routes(chunks: list[RepositoryChunk], limit: int = 8) -> list[str]:
    patterns = [
        re.compile(r'@(?:app|router)\.(?:get|post|put|patch|delete)\("([^"]+)"'),
        re.compile(r"@(?:app|router)\.(?:get|post|put|patch|delete)\('([^']+)'"),
        re.compile(r'app\.(?:get|post|put|patch|delete)\("([^"]+)"'),
        re.compile(r"app\.(?:get|post|put|patch|delete)\('([^']+)'"),
        re.compile(r'route\("([^"]+)"'),
        re.compile(r"route\('([^']+)'"),
    ]
    found: list[str] = []
    for chunk in chunks:
        for pattern in patterns:
            for match in pattern.findall(chunk.content):
                if match not in found:
                    found.append(match)
                if len(found) >= limit:
                    return found
    return found


def _detect_health_endpoint(routes: list[str], chunks: list[RepositoryChunk]) -> bool:
    if any("health" in route.lower() for route in routes):
        return True
    return any("health" in chunk.content.lower() for chunk in chunks[:120])


def _detect_auth_files(chunks: list[RepositoryChunk]) -> list[str]:
    files = []
    for chunk in chunks:
        lowered = chunk.content.lower()
        if any(token in lowered for token in ("jwt", "oauth", "authentication", "authorization", "login", "token")):
            if chunk.path not in files:
                files.append(chunk.path)
    return files[:4]


def _collect_signals(project_id: int, analysis: dict) -> dict:
    chunks = _all_chunks(project_id)
    routes = _detect_routes(chunks)
    database = _detect_database(chunks)
    auth_files = _detect_auth_files(chunks)
    has_health = _detect_health_endpoint(routes, chunks)
    return {
        "database": database,
        "routes": routes,
        "auth_files": auth_files,
        "has_health_endpoint": has_health,
        "entrypoint": analysis.get("entrypoint"),
        "framework": analysis.get("framework"),
        "language": analysis.get("language"),
        "package_manager": analysis.get("package_manager"),
        "has_dockerfile": bool(analysis.get("has_dockerfile")),
        "has_kubernetes": bool(analysis.get("has_kubernetes") or analysis.get("kubernetes_result")),
        "port": analysis.get("port") or 8000,
        "source_subdir": analysis.get("source_subdir"),
    }


def _heuristic_answer(question: str, analysis: dict, signals: dict, sources: list[SearchResult]) -> str:
    q = question.lower()
    if "framework" in q:
        return f"The repository appears to use {analysis.get('framework') or 'an unknown framework'}."
    if "language" in q:
        return f"The primary language looks like {analysis.get('language') or 'unknown'}."
    if "database" in q:
        if signals.get("database"):
            return f"The repository shows signs of using {signals['database']}."
        return "I did not find strong database evidence in the indexed repository files."
    if "entrypoint" in q or "start" in q:
        if analysis.get("entrypoint"):
            return f"The deployment entrypoint is {analysis['entrypoint']}."
        return "I did not find a clear application entrypoint."
    if "port" in q:
        return f"The detected application port is {analysis.get('port') or 8000}."
    if "auth" in q:
        auth_files = signals.get("auth_files") or []
        if auth_files:
            return f"Authentication-related code likely lives in {', '.join(auth_files[:2])}."
        return "I did not find a clear authentication implementation in the indexed snippets."
    if "api" in q or "route" in q:
        routes = signals.get("routes") or []
        if routes:
            return f"I found routes such as {', '.join(routes[:4])}."
    if sources:
        top = sources[0]
        return f"The strongest repository evidence is in {top.path}, which appears relevant to your question."
    return "I do not have enough indexed repository context to answer that confidently."


def answer_repository_question(project_id: int, question: str, analysis: dict) -> RepositoryAnswer:
    ensure_repository_index(project_id, analysis.get("repository_url", ""))
    sources = search_repository(project_id, question, limit=4)
    signals = _collect_signals(project_id, analysis)

    source_block = "\n\n".join(
        f"[{src.path}:{src.line_start}-{src.line_end}]\n{src.snippet}" for src in sources
    )
    prompt = (
        f"{RAG_QA_PROMPT}\n\n"
        f"Question: {question}\n\n"
        f"Detected analysis: {json.dumps(signals, indent=2)}\n\n"
        f"Retrieved snippets:\n{source_block}"
    )
    answer = _safe_chat(prompt) or _heuristic_answer(question, analysis, signals, sources)
    return RepositoryAnswer(question=question, answer=answer, sources=sources)


def generate_deployment_recommendation(project_id: int, analysis: dict) -> DeploymentRecommendation:
    ensure_repository_index(project_id, analysis.get("repository_url", ""))
    signals = _collect_signals(project_id, analysis)
    chunks = _all_chunks(project_id)
    sources = search_repository(project_id, "health endpoint docker kubernetes deployment database", limit=4)

    issues: list[str] = []
    if signals.get("database"):
        issues.append(f"Database dependency detected: {signals['database']}.")
    if not signals.get("has_health_endpoint"):
        issues.append("No obvious health endpoint was detected in the indexed files.")
    if not signals.get("has_dockerfile"):
        issues.append("A Dockerfile was not detected, so DeployMind should generate one.")
    if not signals.get("has_kubernetes"):
        issues.append("Kubernetes manifests were not detected, so DeployMind should generate them.")

    recommendation = [
        f"Deploy the primary {signals.get('framework') or signals.get('language') or 'application'} service to Kubernetes.",
        f"Use port {signals.get('port') or 8000} for the container and Service configuration.",
        "Run a staging rollout and smoke test before promoting a green production version.",
    ]
    if signals.get("database"):
        recommendation.append("Verify database environment variables and connectivity before rollout.")
    if not signals.get("has_health_endpoint"):
        recommendation.append("Add or confirm a lightweight health endpoint for safer rollout checks.")

    detected = {
        "framework": signals.get("framework"),
        "language": signals.get("language"),
        "package_manager": signals.get("package_manager"),
        "port": signals.get("port"),
        "entrypoint": signals.get("entrypoint"),
        "dockerfile_detected": signals.get("has_dockerfile"),
        "kubernetes_detected": signals.get("has_kubernetes"),
        "database": signals.get("database"),
        "health_endpoint_detected": signals.get("has_health_endpoint"),
    }
    summary = (
        f"Detected {signals.get('framework') or signals.get('language') or 'application'}"
        f" with port {signals.get('port') or 8000}. "
        "Recommended flow: generate or validate container + Kubernetes config, deploy to staging, smoke test, then promote green production."
    )
    source_block = "\n".join(f"{src.path}:{src.line_start}-{src.line_end}" for src in sources)
    prompt = (
        f"{DEPLOYMENT_RECOMMENDATION_PROMPT}\n\n"
        f"Detected signals: {json.dumps(detected, indent=2)}\n"
        f"Issues: {json.dumps(issues, indent=2)}\n"
        f"Relevant files:\n{source_block}"
    )
    llm_summary = _safe_chat(prompt)
    if llm_summary:
        summary = llm_summary
    return DeploymentRecommendation(
        summary=summary,
        detected=detected,
        potential_issues=issues,
        recommendation=recommendation,
        evidence=[f"{src.path}:{src.line_start}-{src.line_end}" for src in sources] or [chunk.path for chunk in chunks[:2]],
    )


def evaluate_repository_index(project_id: int, analysis: dict) -> EvaluationReport:
    ensure_repository_index(project_id, analysis.get("repository_url", ""))
    signals = _collect_signals(project_id, analysis)
    questions: list[tuple[str, str]] = [
        ("What framework does this repository use?", str(analysis.get("framework") or "unknown")),
        ("What language does this repository use?", str(analysis.get("language") or "unknown")),
        ("What package manager does this repository use?", str(analysis.get("package_manager") or "unknown")),
        ("What is the deployment entrypoint?", str(analysis.get("entrypoint") or "unknown")),
        ("What port does the application use?", str(analysis.get("port") or 8000)),
    ]
    if signals.get("database"):
        questions.append(("What database does this application use?", str(signals["database"])))
    if signals.get("auth_files"):
        questions.append(("Which file contains authentication-related code?", str(signals["auth_files"][0])))

    results: list[EvaluationItem] = []
    correct = 0
    for question, expected in questions[:8]:
        answer = answer_repository_question(project_id, question, analysis)
        matched_source = answer.sources[0].path if answer.sources else None
        haystack = f"{answer.answer} {matched_source or ''}".lower()
        ok = expected.lower() in haystack
        if not ok and expected.isdigit():
            ok = expected in haystack
        results.append(
            EvaluationItem(
                question=question,
                expected=expected,
                answer=answer.answer,
                matched_source=matched_source,
                status="correct" if ok else "needs_review",
            )
        )
        if ok:
            correct += 1

    total = len(results)
    accuracy = round((correct / total) * 100, 1) if total else 0.0
    return EvaluationReport(
        questions=total,
        correct=correct,
        retrieval_accuracy=accuracy,
        results=results,
    )


def _entrypoint_module_and_attr(entrypoint: str | None) -> tuple[str | None, str | None]:
    if not entrypoint or ":" not in entrypoint:
        return None, None
    module, attr = entrypoint.split(":", 1)
    return module.strip(), attr.strip()


def _route_candidates(project_id: int) -> list[str]:
    chunks = _all_chunks(project_id)
    routes = [route for route in _detect_routes(chunks) if route and route.startswith("/")]
    ordered: list[str] = []
    for route in ["/", "/health", *routes]:
        if route not in ordered:
            ordered.append(route)
    return ordered[:4]


def _python_test_file(framework: str, module_name: str, app_attr: str, routes: list[str]) -> str:
    checked = routes[:4] or ["/", "/health"]
    if framework == "Flask":
        checks = "\n\n".join(
            f"def test_{i}_route(client):\n    response = client.get({route!r})\n    assert response.status_code < 500\n"
            for i, route in enumerate(checked, start=1)
        )
        return f"""import sys
from pathlib import Path

import pytest
from {module_name} import {app_attr}


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client():
    with {app_attr}.test_client() as c:
        yield c


{checks}
"""

    checks = "\n\n".join(
        f"def test_{i}_route(client):\n    response = client.get({route!r})\n    assert response.status_code < 500\n"
        for i, route in enumerate(checked, start=1)
    )
    return f"""import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from {module_name} import {app_attr}


@pytest.fixture
def client():
    return TestClient({app_attr})


{checks}
"""


def _child_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in TEST_BLOCKED_ENV}


def _run_install(command: str, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_child_env(),
    )


def _minimal_python_test_dependencies(framework: str) -> str:
    if framework == "Flask":
        return "pip install flask pytest httpx -q"
    return "pip install fastapi pytest httpx -q"


def _prepare_python_repo(repo_dir: Path, timeout: int, framework: str = "") -> str | None:
    install_cmds: list[str] = []
    # Look for requirements.txt or pyproject.toml in repo_dir or its parent
    req = repo_dir / "requirements.txt"
    pyproject = repo_dir / "pyproject.toml"
    if not req.exists() and not pyproject.exists():
        # Also check one level up (when repo_dir is backend/ inside a monorepo)
        req = repo_dir.parent / "requirements.txt"
        pyproject = repo_dir.parent / "pyproject.toml"
    if req.exists():
        install_cmds.append(f"pip install -r {req} pytest -q")
    elif pyproject.exists():
        install_cmds.append(f"pip install {pyproject.parent} pytest -q")

    if framework in {"FastAPI", "Flask"}:
        install_cmds.append(_minimal_python_test_dependencies(framework))

    if not install_cmds:
        return None

    errors: list[str] = []
    try:
        for command in install_cmds:
            proc = _run_install(command, repo_dir, timeout)
            if proc.returncode == 0:
                return None
            errors.append((proc.stderr or proc.stdout or f"Install failed: {command}")[:4000])
    except subprocess.TimeoutExpired:
        return "Dependency install timed out"
    return "\n\n".join(errors)[-4000:]


def explain_failure(error: str, evidence: list[str] | None = None) -> dict:
    evidence = evidence or []
    text = " ".join(evidence + [error]).lower()
    if "kubernetes cluster not reachable" in text or "kind create cluster" in text or "no kind clusters found" in text:
        cause = "DeployMind could not reach the local kind Kubernetes cluster."
        fix = f"Start or create the cluster first with: kind create cluster --name {settings.kind_cluster_name}"
    elif "no module named 'app'" in text or 'no module named "app"' in text:
        cause = "The generated test ran from the wrong import root for the repository layout."
        fix = "Retry after using the repository root or backend root as the Python import path for generated tests."
    elif "could not find a version that satisfies the requirement" in text or "no matching distribution found" in text:
        cause = "Repository dependency installation failed before the generated tests could run."
        fix = "Check the repository dependency file for invalid or private-only packages, then retry the AI-generated tests."
    elif "crashloopbackoff" in text or "module not found" in text:
        cause = "The application is starting but crashing during boot."
        fix = "Check the entrypoint module, dependency installation, and startup logs."
    elif "imagepullbackoff" in text or "errimagepull" in text:
        cause = "Kubernetes could not start the image that was built or loaded."
        fix = "Verify the Docker build succeeded and that the image was loaded into the kind cluster."
    elif "port-forward exited early" in text or "connection refused" in text:
        cause = "The service became reachable before the application was actually ready, or the wrong port is exposed."
        fix = "Confirm the container port, readiness behavior, and health endpoint path."
    elif "database" in text or "postgres" in text or "sql" in text:
        cause = "The deployment likely depends on a database configuration that is missing or unreachable."
        fix = "Check database environment variables, secrets, and network access."
    else:
        cause = "Insufficient information to determine the root cause."
        fix = "Review the error output, rollout status, and the most recent pod logs."

    prompt = (
        f"{FAILURE_ANALYSIS_PROMPT}\n\n"
        f"Error: {error}\n\n"
        f"Evidence: {json.dumps(evidence, indent=2)}"
    )
    llm_text = _safe_chat(prompt)
    summary = llm_text or cause
    return {
        "failure": error,
        "likely_cause": summary,
        "evidence": evidence,
        "suggested_fix": fix,
    }


def run_ai_generated_tests(project_id: int, repository_url: str, analysis: dict, timeout: int = 180) -> AITestRun:
    ensure_repository_index(project_id, repository_url)
    framework = (analysis.get("framework") or "").strip()
    if framework not in {"FastAPI", "Flask"}:
        return AITestRun(
            status="skipped",
            message="AI-generated execution is currently implemented for FastAPI and Flask repositories.",
        )

    module_name, app_attr = _entrypoint_module_and_attr(analysis.get("entrypoint"))
    if not module_name or not app_attr:
        return AITestRun(
            status="skipped",
            message="A Python entrypoint is required before AI-generated tests can run.",
        )

    temp_dir = Path(settings.workspace_dir) / f"project_{project_id}_ai_tests"
    app_dir = temp_dir / (analysis.get("source_subdir") or "")
    routes = _route_candidates(project_id)
    code = _python_test_file(framework, module_name, app_attr, routes)
    prompt = (
        f"{TEST_GENERATION_PROMPT}\n\n"
        f"Framework: {framework}\nEntrypoint: {analysis.get('entrypoint')}\nRoutes: {json.dumps(routes)}"
    )
    llm_text = _safe_chat(prompt)
    rationale = llm_text or "Generated route checks from the detected Python entrypoint and indexed routes."
    case = GeneratedTestCase(
        name="generated_api_checks",
        rationale=rationale,
        path=".deploymind_generated/test_ai_generated.py",
        code=code,
    )

    try:
        clone_repository(repository_url, temp_dir)
        if not app_dir.is_dir():
            app_dir = temp_dir

        # Resolve the directory that actually contains the Python 'app' package.
        # If app_dir itself has app/__init__.py that's the right place.
        # If not, search one level of subdirectories (e.g. backend/app/).
        module_pkg = module_name.split(".")[0]
        python_path = app_dir
        if not (app_dir / module_pkg).is_dir():
            for sub in sorted(app_dir.iterdir()):
                if sub.is_dir() and (sub / module_pkg).is_dir():
                    python_path = sub
                    break

        removed_requirements = sanitize_requirements_file(python_path)

        gen_dir = python_path / ".deploymind_generated"
        gen_dir.mkdir(parents=True, exist_ok=True)
        test_file = gen_dir / "test_ai_generated.py"
        test_file.write_text(code, encoding="utf-8")

        # Install deps from the correct directory
        prepare_error = _prepare_python_repo(python_path, timeout=min(timeout, 240), framework=framework)
        if prepare_error:
            analysis = explain_failure("Dependency install failed before AI tests", [prepare_error])
            return AITestRun(
                status="failed",
                message="Dependency install failed before AI-generated tests",
                generated_tests=[case],
                stderr=prepare_error,
                failure_analysis=analysis,
            )

        command = "pytest .deploymind_generated/test_ai_generated.py -q"
        env = {**_child_env(), "PYTHONPATH": str(python_path)}
        proc = subprocess.run(
            command,
            cwd=python_path,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        stdout = (proc.stdout or "")[-6000:]
        stderr = (proc.stderr or "")[-6000:]
        if proc.returncode == 0:
            message = "AI-generated tests passed"
            if removed_requirements:
                message += f" after ignoring suspicious requirement lines: {', '.join(removed_requirements[:3])}"
            return AITestRun(
                status="passed",
                message=message,
                command=command,
                generated_tests=[case],
                stdout=stdout,
                stderr=stderr,
            )
        failure = explain_failure("AI-generated tests failed", [stdout, stderr])
        return AITestRun(
            status="failed",
            message="AI-generated tests failed",
            command=command,
            generated_tests=[case],
            stdout=stdout,
            stderr=stderr,
            failure_analysis=failure,
        )
    except subprocess.TimeoutExpired:
        failure = explain_failure("AI-generated tests timed out")
        return AITestRun(
            status="failed",
            message=f"AI-generated tests timed out after {timeout}s",
            generated_tests=[case],
            failure_analysis=failure,
        )
    finally:
        cleanup_repository(temp_dir)


def _kubectl(args: list[str], timeout: int = 30) -> str:
    env = os.environ.copy()
    if settings.kubeconfig:
        env["KUBECONFIG"] = settings.kubeconfig
    proc = subprocess.run(
        ["kubectl", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or "").strip()
    return (proc.stdout or "").strip()


def analyze_deployment_failure(app_name: str, namespace: str, error_message: str) -> dict:
    evidence: list[str] = []
    try:
        pods = _kubectl(["get", "pods", "-n", namespace, "-o", "wide"], timeout=20)
        if pods:
            evidence.append(pods[:2000])
        deploy = _kubectl(["get", "deployments", "-n", namespace], timeout=20)
        if deploy:
            evidence.append(deploy[:1500])
        if app_name:
            pod_names = _kubectl(
                ["get", "pods", "-n", namespace, "-l", f"app={app_name}", "-o", "jsonpath={.items[*].metadata.name}"],
                timeout=20,
            )
            first_pod = next((name for name in pod_names.split() if name.strip()), "")
            if first_pod:
                logs = _kubectl(["logs", "-n", namespace, first_pod, "--tail=40"], timeout=20)
                if logs:
                    evidence.append(logs[:2000])
    except Exception:
        logger.warning("deployment failure evidence collection failed", exc_info=True)
    return explain_failure(error_message, evidence)
