import logging
import os
import re
import subprocess
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("deploymind")

# Patterns that indicate a Dockerfile requires BuildKit (--mount) or complex
# multi-stage tooling (bun, uv sync --frozen, etc.) that won't work with the
# legacy builder inside the CodeDeck container.
_BUILDKIT_REQUIRED_PATTERNS = re.compile(
    r"--mount=type="
    r"|RUN\s+--mount"
    r"|FROM\s+oven/bun"
    r"|FROM\s+ghcr\.io/astral-sh/uv"
    r"|uv\s+sync\s+--frozen"
    r"|bun\s+install"
    r"|bun\s+run\s+build",
    re.IGNORECASE,
)
_PREBUILT_JAVA_ARTIFACT_PATTERN = re.compile(
    r"\b(?:COPY|ADD)\s+(?:--\S+\s+)*(?:target/|build/libs/)",
    re.IGNORECASE,
)


def has_complex_dockerfile(path: Path) -> bool:
    """Return True if the Dockerfile uses BuildKit-only features or multi-stage
    tooling (bun, uv --frozen mounts) that CodeDeck cannot build as-is."""
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return bool(_BUILDKIT_REQUIRED_PATTERNS.search(text))
    except OSError:
        return False


def requires_prebuilt_java_artifact(path: Path) -> bool:
    """Return True when a Dockerfile expects CI to have built a JAR first."""
    if not path.is_file():
        return False
    try:
        return bool(_PREBUILT_JAVA_ARTIFACT_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")))
    except OSError:
        return False


def run_cmd(args: list[str], cwd: str | Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    logger.info("running: %s", " ".join(args))
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"
    env["BUILDKIT_PROGRESS"] = "plain"
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def build_image(context_dir: Path, dockerfile: Path, image: str, timeout: int | None = None) -> str:
    effective_timeout = timeout if timeout is not None else settings.docker_build_timeout

    if not context_dir.is_dir():
        raise RuntimeError(f"Build context directory not found: {context_dir}")
    if not dockerfile.is_file():
        raise RuntimeError(f"Dockerfile not found: {dockerfile}")

    logger.info(
        "Docker build starting for image '%s' (context='%s', dockerfile='%s', timeout=%ds)",
        image,
        context_dir,
        dockerfile,
        effective_timeout,
    )

    try:
        proc = run_cmd(
            [
                "docker",
                "build",
                "-t",
                image,
                "-f",
                str(dockerfile),
                str(context_dir),
            ],
            timeout=effective_timeout,
        )
    except FileNotFoundError as exc:
        msg = "Docker CLI not found. Install Docker Desktop and ensure 'docker' is in PATH."
        logger.error(msg)
        raise RuntimeError(msg) from exc
    except subprocess.TimeoutExpired as exc:
        msg = f"Docker build timed out after {effective_timeout} seconds."
        logger.error(msg)
        raise RuntimeError(msg) from exc
    if proc.returncode != 0:
        # Combine stdout and stderr — Docker sends build output to stdout, errors to stderr
        combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        detail = combined[-5000:]
        msg = f"Docker build failed:\n{detail}"
        logger.error("Docker build failed for %s:\n%s", image, detail)
        raise RuntimeError(msg)

    logger.info("Docker image built successfully: %s", image)
    return image


def kind_load_image(image: str, cluster: str = "deploymind") -> None:
    logger.info("Loading docker image '%s' into kind cluster '%s'...", image, cluster)

    # 1. Try standard kind load
    try:
        proc = run_cmd(["kind", "load", "docker-image", image, "--name", cluster], timeout=300)
        if proc.returncode == 0:
            logger.info("Image successfully loaded into kind cluster '%s': %s", cluster, image)
            return
        logger.warning(
            "kind load failed: %s. Falling back to direct containerd import...",
            (proc.stderr or proc.stdout or "").strip()[:500],
        )
    except Exception as exc:
        logger.warning("kind load invocation error (%s). Falling back to direct containerd import...", exc)

    # 2. Robust fallback: pipe docker save directly into kind node's containerd
    node_name = f"{cluster}-control-plane"
    try:
        save_proc = subprocess.Popen(["docker", "save", image], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        import_proc = subprocess.Popen(
            ["docker", "exec", "-i", node_name, "ctr", "--namespace=k8s.io", "images", "import", "-"],
            stdin=save_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if save_proc.stdout:
            save_proc.stdout.close()
        out, err = import_proc.communicate(timeout=300)
        save_proc.wait(timeout=30)
        if import_proc.returncode == 0:
            logger.info("Image successfully loaded into kind via containerd import: %s", image)
            return
        raise RuntimeError(f"containerd import failed: {(err or out).strip()[:1000]}")
    except Exception as exc:
        msg = f"Failed to load image into kind node '{node_name}': {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc


