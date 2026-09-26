import logging
import os
import re
import shutil
import stat
from pathlib import Path
from urllib.parse import urlparse

from git import Repo
from git.exc import GitCommandError

from app.core.config import settings
from app.services.dependency_sanitizer import sanitize_requirements_file

logger = logging.getLogger("deploymind")

GITHUB_URL_RE = re.compile(
    r"^https?://(www\.)?github\.com/[\w.-]+/[\w.-]+/?$",
    re.IGNORECASE,
)


def validate_github_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    if not GITHUB_URL_RE.match(url):
        raise ValueError("Invalid GitHub repository URL")
    return url


def repo_name_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.split("/")[-1]


def _clone_url(url: str) -> str:
    if not settings.github_token:
        return url + ".git"
    # token only used for git auth; never logged
    parsed = urlparse(url)
    return f"https://x-access-token:{settings.github_token}@{parsed.netloc}{parsed.path}.git"


def _handle_remove_readonly(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def cleanup_repository(path: Path) -> None:
    path = Path(path)
    if path.exists():
        try:
            shutil.rmtree(path, onerror=_handle_remove_readonly)
        except Exception:
            shutil.rmtree(path, ignore_errors=True)


def clone_repository(url: str, dest: Path) -> Path:
    url = validate_github_url(url)
    dest = dest.resolve()
    workspace = Path(settings.workspace_dir).resolve()
    if not str(dest).startswith(str(workspace)):
        raise ValueError("Clone destination is outside workspace")

    cleanup_repository(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        Repo.clone_from(_clone_url(url), dest, depth=1, single_branch=True)
        for req_path in dest.rglob("requirements.txt"):
            if req_path.is_file():
                try:
                    removed = sanitize_requirements_file(req_path.parent)
                    if removed:
                        logger.info("Sanitized requirements.txt at %s by removing: %s", req_path, ", ".join(removed))
                except Exception as e:
                    logger.warning("Failed to sanitize requirements.txt at %s: %s", req_path, e)
    except GitCommandError as exc:
        cleanup_repository(dest)
        msg = str(exc)
        if settings.github_token:
            msg = msg.replace(settings.github_token, "***")
        raise RuntimeError(f"Failed to clone repository: {msg}") from exc

    logger.info("repository cloned to %s", dest)
    return dest
