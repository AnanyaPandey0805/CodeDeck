import logging
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from app.agents.kubernetes_agent import sanitize_name
from app.core.config import settings
from app.services import docker as docker_svc
from app.services import kubernetes as k8s_svc
from app.services.dependency_sanitizer import choose_python_base_image, sanitize_requirements_file
from app.services.github import cleanup_repository, clone_repository

logger = logging.getLogger("deploymind")


def _prepare_deployment_source(project_id: int, repository_url: str, dest: Path) -> Path:
    cleanup_repository(dest)
    cached_src = Path(settings.workspace_dir) / f"project_{project_id}"
    if cached_src.is_dir():
        try:
            shutil.copytree(cached_src, dest)
            logger.info("Reused local repository cache from %s for project %d deployment", cached_src, project_id)
            return dest
        except Exception as exc:
            logger.warning("Failed to copy cached repository (%s); re-cloning...", exc)
            cleanup_repository(dest)
    return clone_repository(repository_url, dest)


class StagingDeployResult(BaseModel):
    status: str
    environment: str = "staging"
    version: str = "blue"
    image: str = ""
    namespace: str = ""
    app_name: str = ""
    rollout: str = ""
    smoke: dict = Field(default_factory=dict)
    deployment_status: dict = Field(default_factory=dict)
    message: str = ""


def _write_build_context(
    repo_path: Path,
    dockerfile_content: str,
    source_subdir: str | None,
) -> tuple[Path, Path]:
    app_dir = repo_path / source_subdir if source_subdir else repo_path
    if not app_dir.is_dir():
        app_dir = repo_path

    existing_dockerfile = app_dir / "Dockerfile"
    if not existing_dockerfile.exists():
        existing_dockerfile = repo_path / "Dockerfile"

    dockerfile_path = app_dir / "Dockerfile"
    if dockerfile_content.strip():
        dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
    elif existing_dockerfile.exists():
        dockerfile_path = existing_dockerfile
    else:
        raise RuntimeError("No Dockerfile available for build")

    # If building for a nested directory (e.g. backend/), or if root contains
    # root dependencies (package.json, pyproject.toml, docker-compose.yml),
    # the build context MUST be the repository root so COPY instructions work.
    has_root_files = any(
        (repo_path / f).exists() for f in ("package.json", "docker-compose.yml", "pyproject.toml", "requirements.txt")
    )
    context_dir = repo_path if (source_subdir or has_root_files) else app_dir
    return context_dir, dockerfile_path


def _reliable_staging_dockerfile(app_dir: Path, analysis: dict) -> str:
    port = int(analysis.get("port") or 8000)
    entry = analysis.get("entrypoint") or "app.main:app"
    pm = (analysis.get("package_manager") or "").lower()
    lang = (analysis.get("language") or "").lower()
    python_base = choose_python_base_image(app_dir)

    existing_dockerfile = app_dir / "Dockerfile"
    if existing_dockerfile.exists():
        return existing_dockerfile.read_text(encoding="utf-8", errors="ignore")

    if (app_dir / "requirements.txt").exists():
        return f"""FROM {python_base}
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home --uid 1000 appuser
USER appuser
EXPOSE {port}
CMD ["uvicorn", "{entry}", "--host", "0.0.0.0", "--port", "{port}"]
"""

    if (app_dir / "uv.lock").exists() or pm == "uv":
        return f"""FROM {python_base}
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml* uv.lock* ./
RUN uv pip install --system --no-cache . || pip install --no-cache-dir fastapi uvicorn
COPY . .
RUN useradd --create-home --uid 1000 appuser
USER appuser
EXPOSE {port}
CMD ["uvicorn", "{entry}", "--host", "0.0.0.0", "--port", "{port}"]
"""

    if (app_dir / "poetry.lock").exists() or pm == "poetry":
        return f"""FROM {python_base}
WORKDIR /app
RUN pip install --no-cache-dir poetry
COPY pyproject.toml* poetry.lock* ./
RUN poetry config virtualenvs.create false && (poetry install --no-interaction --no-ansi || pip install --no-cache-dir fastapi uvicorn)
COPY . .
RUN useradd --create-home --uid 1000 appuser
USER appuser
EXPOSE {port}
CMD ["uvicorn", "{entry}", "--host", "0.0.0.0", "--port", "{port}"]
"""

    if (app_dir / "pyproject.toml").exists():
        return f"""FROM {python_base}
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir . || pip install --no-cache-dir fastapi uvicorn
COPY . .
RUN useradd --create-home --uid 1000 appuser
USER appuser
EXPOSE {port}
CMD ["uvicorn", "{entry}", "--host", "0.0.0.0", "--port", "{port}"]
"""

    # Delegate to docker_agent for Node, Java, or other frameworks
    from app.agents.docker_agent import generate_dockerfile
    res = generate_dockerfile(app_dir, analysis)
    if res.dockerfile:
        return res.dockerfile

    raise RuntimeError(
        "Unable to generate a Dockerfile. "
        "No existing Dockerfile or supported project configuration found."
    )


def _adjust_python_base_image(dockerfile_content: str, app_dir: Path) -> str:
    python_base = choose_python_base_image(app_dir)
    if python_base == "python:3.11-slim":
        return dockerfile_content
    return dockerfile_content.replace("FROM python:3.11-slim", f"FROM {python_base}", 1)



def deploy_staging(
    project_id: int,
    repository_url: str,
    repository_name: str,
    analysis: dict,
    dockerfile: str,
    k8s_files: dict[str, str],
) -> StagingDeployResult:
    app_name = sanitize_name(repository_name or analysis.get("repository_name") or "app")
    namespace = settings.k8s_namespace
    cluster = settings.kind_cluster_name
    image = f"deploymind/{app_name}:staging"
    dest = Path(settings.workspace_dir) / f"project_{project_id}_deploy"

    logger.info("deployment started: staging %s", app_name)

    k8s_svc.prepare_kubeconfig()
    if not k8s_svc.cluster_reachable():
        raise RuntimeError(
            f"Kubernetes cluster not reachable. Create kind cluster first: "
            f"kind create cluster --name {cluster}"
        )

    try:
        _prepare_deployment_source(project_id, repository_url, dest)
        app_dir = dest / analysis.get("source_subdir", "") if analysis.get("source_subdir") else dest
        if not app_dir.is_dir():
            app_dir = dest
        sanitize_requirements_file(app_dir)
        existing_dockerfile = app_dir / "Dockerfile"
        if existing_dockerfile.exists() :
            context_dir=dest
            dockerfile_path=existing_dockerfile
        else:
            staging_content = dockerfile.strip()
            if not staging_content:
                staging_content = _reliable_staging_dockerfile(app_dir, analysis)
            staging_content = _adjust_python_base_image(staging_content, app_dir)
            context_dir, dockerfile_path = _write_build_context(
                dest,
                staging_content,
                analysis.get("source_subdir"),
            )

        docker_svc.build_image(context_dir, dockerfile_path, image,timeout=1800)
        docker_svc.kind_load_image(image, cluster=cluster)

        local_files = {
            k: v
            for k, v in k8s_files.items()
            if k.endswith((".yaml", ".yml"))
        }
        if not local_files:
            raise RuntimeError("No Kubernetes manifests found. Run analysis first.")

        patched = k8s_svc.patch_manifests_for_local(local_files, image=image, app_name=app_name, replicas=1)
        # Keep a staging-named deployment for clarity while reusing service name
        if "deployment.yaml" in patched:
            patched["deployment.yaml"] = patched["deployment.yaml"].replace(
                f"name: {app_name}\n",
                f"name: {app_name}-staging\n",
                1,
            )

        deploy_name = f"{app_name}-staging"
        k8s_svc.apply_manifests(patched, namespace=namespace)
        rollout = k8s_svc.wait_rollout(deploy_name, namespace=namespace, timeout_s=240)
        status = k8s_svc.get_deployment_status(deploy_name, namespace=namespace)
        smoke = k8s_svc.smoke_test(app_name, namespace=namespace)

        if smoke.get("status") != "passed":
            raise RuntimeError(smoke.get("message") or "Smoke test failed")

        logger.info("deployment completed: staging %s", app_name)
        return StagingDeployResult(
            status="healthy",
            image=image,
            namespace=namespace,
            app_name=app_name,
            rollout=rollout,
            smoke=smoke,
            deployment_status=status,
            message=f"Staging healthy ({smoke.get('message')})",
        )
    finally:
        cleanup_repository(dest)


class ProductionDeployResult(BaseModel):
    status: str
    environment: str = "production"
    version: str = "green"
    image: str = ""
    namespace: str = ""
    app_name: str = ""
    rollout: str = ""
    smoke: dict = Field(default_factory=dict)
    deployment_status: dict = Field(default_factory=dict)
    message: str = ""


def deploy_green(
    project_id: int,
    repository_url: str,
    repository_name: str,
    analysis: dict,
    dockerfile: str,
    k8s_files: dict[str, str],
) -> ProductionDeployResult:
    app_name = sanitize_name(repository_name or analysis.get("repository_name") or "app")
    namespace = settings.k8s_namespace
    cluster = settings.kind_cluster_name
    image = f"deploymind/{app_name}:green"
    dest = Path(settings.workspace_dir) / f"project_{project_id}_prod_deploy"

    logger.info("deployment started: green production %s", app_name)

    k8s_svc.prepare_kubeconfig()
    if not k8s_svc.cluster_reachable():
        raise RuntimeError(
            f"Kubernetes cluster not reachable. Create kind cluster first: "
            f"kind create cluster --name {cluster}"
        )

    try:
        _prepare_deployment_source(project_id, repository_url, dest)
        app_dir = dest / analysis.get("source_subdir", "") if analysis.get("source_subdir") else dest
        if not app_dir.is_dir():
            app_dir = dest
        sanitize_requirements_file(app_dir)

        existing_dockerfile = app_dir / "Dockerfile"
        if existing_dockerfile.exists() :
            context_dir=dest
            dockerfile_path=existing_dockerfile 
        else:
            staging_content = dockerfile.strip()
            if not staging_content:
                 staging_content = _reliable_staging_dockerfile(app_dir, analysis)
            staging_content = _adjust_python_base_image(staging_content, app_dir)
            context_dir, dockerfile_path = _write_build_context(
                dest,
                staging_content,
                analysis.get("source_subdir"),
            )

        docker_svc.build_image(context_dir, dockerfile_path, image, timeout=1800)
        docker_svc.kind_load_image(image, cluster=cluster)

        local_files = {
            k: v
            for k, v in k8s_files.items()
            if k.endswith((".yaml", ".yml"))
        }
        if not local_files:
            raise RuntimeError("No Kubernetes manifests found.")

        patched = k8s_svc.patch_manifests_for_blue_green(
            local_files, image=image, app_name=app_name, version="green", replicas=2
        )

        deploy_name = f"{app_name}-green"
        k8s_svc.apply_manifests(patched, namespace=namespace)
        rollout = k8s_svc.wait_rollout(deploy_name, namespace=namespace, timeout_s=240)
        status = k8s_svc.get_deployment_status(deploy_name, namespace=namespace)

        # Ensure blue deployment exists as rollback fallback
        blue_status = k8s_svc.get_deployment_status(f"{app_name}-blue", namespace=namespace)
        if not blue_status.get("ready"):
            blue_patched = k8s_svc.patch_manifests_for_blue_green(
                local_files, image=f"deploymind/{app_name}:staging", app_name=app_name, version="blue", replicas=1
            )
            k8s_svc.apply_manifests(blue_patched, namespace=namespace)

        smoke = k8s_svc.smoke_test(app_name, namespace=namespace)

        logger.info("green deployment ready: %s, awaiting approval", app_name)
        return ProductionDeployResult(
            status="awaiting_approval",
            image=image,
            namespace=namespace,
            app_name=app_name,
            rollout=rollout,
            smoke=smoke,
            deployment_status=status,
            message="GREEN version deployed and healthy. Awaiting production approval.",
        )
    finally:
        cleanup_repository(dest)


def switch_traffic(app_name: str, namespace: str | None = None) -> dict:
    ns = namespace or settings.k8s_namespace
    msg = k8s_svc.switch_traffic(app_name, ns, "green")
    smoke = k8s_svc.smoke_test(app_name, ns)
    return {
        "status": "healthy",
        "version": "green",
        "message": f"{msg}. Smoke test: {smoke.get('message')}",
        "smoke": smoke,
    }


def rollback(app_name: str, namespace: str | None = None) -> dict:
    ns = namespace or settings.k8s_namespace
    msg = k8s_svc.rollback(app_name, ns)
    smoke = k8s_svc.smoke_test(app_name, ns)
    return {
        "status": "rolled_back",
        "version": "blue",
        "message": f"{msg}. Smoke test: {smoke.get('message')}",
        "smoke": smoke,
    }


def get_deployment_status(deployment_name: str, namespace: str | None = None) -> dict:
    ns = namespace or settings.k8s_namespace
    return k8s_svc.get_deployment_status(deployment_name, ns)


def run_smoke_test(service_name: str, namespace: str | None = None) -> dict:
    ns = namespace or settings.k8s_namespace
    return k8s_svc.smoke_test(service_name, ns)

