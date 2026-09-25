import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field
from app.services.dependency_sanitizer import choose_python_base_image

logger = logging.getLogger("deploymind")


class DockerResult(BaseModel):
    dockerfile: str
    generated: bool = True
    suggestions: list[str] = Field(default_factory=list)
    message: str = ""
    app_dir: str = "."


def _app_dir(repo_path: Path, analysis: dict) -> Path:
    sub = analysis.get("source_subdir")
    if sub:
        candidate = repo_path / sub
        if candidate.is_dir():
            return candidate
    return repo_path


def _suggest_improvements(text: str) -> list[str]:
    suggestions = []
    if not re.search(r"(?im)^USER\s+\S+", text):
        suggestions.append("Add a non-root USER instruction")
    if not re.search(r"(?im)^HEALTHCHECK\s+", text):
        suggestions.append("Consider adding a HEALTHCHECK")
    if "latest" in text:
        suggestions.append("Pin base image tags instead of :latest")
    return suggestions


def _fastapi_dockerfile(entrypoint: str, port: int, has_requirements: bool, has_pyproject: bool) -> str:
    deps = (
        "COPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt"
        if has_requirements
        else "COPY pyproject.toml* ./ \nRUN pip install --no-cache-dir ."
        if has_pyproject
        else "RUN pip install --no-cache-dir fastapi uvicorn"
    )
    return f"""FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

{deps}

COPY . .

USER appuser
EXPOSE {port}

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \\
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:{port}/health')" || exit 1

CMD ["uvicorn", "{entrypoint}", "--host", "0.0.0.0", "--port", "{port}"]
"""


def _flask_dockerfile(entrypoint: str, port: int, has_requirements: bool) -> str:
    module = entrypoint.split(":")[0] if entrypoint else "app"
    deps = (
        "COPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt gunicorn"
        if has_requirements
        else "RUN pip install --no-cache-dir flask gunicorn"
    )
    return f"""FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

{deps}

COPY . .

USER appuser
EXPOSE {port}

CMD ["gunicorn", "-b", "0.0.0.0:{port}", "{module}:app"]
"""


def _django_dockerfile(port: int, has_requirements: bool) -> str:
    deps = (
        "COPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt gunicorn"
        if has_requirements
        else "RUN pip install --no-cache-dir django gunicorn"
    )
    return f"""FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

{deps}

COPY . .

USER appuser
EXPOSE {port}

CMD ["gunicorn", "-b", "0.0.0.0:{port}", "config.wsgi:application"]
"""


def _node_dockerfile(entrypoint: str, port: int, framework: str) -> str:
    if "React" in framework and "Express" not in framework:
        return f"""FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""
    start = entrypoint if entrypoint.endswith(".js") else "index.js"
    return f"""FROM node:22-alpine

WORKDIR /app

RUN addgroup -S app && adduser -S app -G app

COPY package*.json ./
RUN npm ci --omit=dev

COPY . .

USER app
EXPOSE {port}

CMD ["node", "{start}"]
"""


def _java_dockerfile(port: int) -> str:
    return f"""FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

RUN addgroup -S app && adduser -S app -G app

COPY target/*.jar app.jar

USER app
EXPOSE {port}

ENTRYPOINT ["java", "-jar", "app.jar"]
"""


def generate_dockerfile(repo_path: str | Path, analysis: dict) -> DockerResult:
    root = Path(repo_path)
    app_dir = _app_dir(root, analysis)
    rel = str(app_dir.relative_to(root)) if app_dir != root else "."
    existing = app_dir / "Dockerfile"
    if not existing.exists():
        existing = root / "Dockerfile"

    logger.info("Docker generation for %s", app_dir)

    if existing.exists() and analysis.get("has_dockerfile"):
        text = existing.read_text(encoding="utf-8", errors="ignore")
        suggestions = _suggest_improvements(text)
        msg = "Existing Dockerfile kept"
        if suggestions:
            msg += f" ({len(suggestions)} suggestion(s))"
        return DockerResult(
            dockerfile=text,
            generated=False,
            suggestions=suggestions,
            message=msg,
            app_dir=rel,
        )

    framework = analysis.get("framework") or ""
    language = analysis.get("language") or ""
    entrypoint = analysis.get("entrypoint") or "app.main:app"
    port = int(analysis.get("port") or 8000)
    pm = (analysis.get("package_manager") or "").lower()

    has_req = (app_dir / "requirements.txt").exists()
    has_py = (app_dir / "pyproject.toml").exists()
    has_uv = (app_dir / "uv.lock").exists() or pm == "uv"
    has_poetry = (app_dir / "poetry.lock").exists() or pm == "poetry"
    python_base = choose_python_base_image(app_dir)

    if has_req:
        deps = "COPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt"
    elif has_uv:
        deps = "COPY pyproject.toml* uv.lock* ./\nRUN pip install --no-cache-dir uv && (uv pip install --system --no-cache . || pip install --no-cache-dir fastapi uvicorn)"
    elif has_poetry:
        deps = "COPY pyproject.toml* poetry.lock* ./\nRUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false && (poetry install --no-interaction --no-ansi || pip install --no-cache-dir fastapi uvicorn)"
    elif has_py:
        deps = "COPY pyproject.toml ./\nRUN pip install --no-cache-dir ."
    else:
        deps = "RUN pip install --no-cache-dir fastapi uvicorn"


    if framework == "FastAPI" or (language == "Python" and "fastapi" in framework.lower()):
        content = f"""FROM {python_base}

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

{deps}

COPY . .

USER appuser
EXPOSE {port}

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \\
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:{port}/health')" || exit 1

CMD ["uvicorn", "{entrypoint}", "--host", "0.0.0.0", "--port", "{port}"]
"""
    elif framework == "Flask":
        content = _flask_dockerfile(entrypoint, port, has_req).replace("FROM python:3.11-slim", f"FROM {python_base}", 1)
    elif framework == "Django":
        content = _django_dockerfile(port, has_req).replace("FROM python:3.11-slim", f"FROM {python_base}", 1)
    elif language == "JavaScript":
        content = _node_dockerfile(entrypoint or "index.js", port, framework)
    elif language == "Java":
        content = _java_dockerfile(port)
    elif language == "Python":
        content = f"""FROM {python_base}

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

{deps}

COPY . .

USER appuser
EXPOSE {port}

CMD ["uvicorn", "{entrypoint or 'main:app'}", "--host", "0.0.0.0", "--port", "{port}"]
"""
    else:
        content = _fastapi_dockerfile("app.main:app", 8000, False, False)

    logger.info("Dockerfile generated")
    return DockerResult(
        dockerfile=content.strip() + "\n",
        generated=True,
        message="Dockerfile generated",
        app_dir=rel,
    )
