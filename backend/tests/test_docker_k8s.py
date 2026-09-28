from app.agents.deployment_agent import (
    _adjust_python_base_image,
    _align_fastapi_dockerfile_entrypoint,
    _refresh_fastapi_entrypoint,
)
from app.agents.docker_agent import generate_dockerfile
from app.agents.kubernetes_agent import generate_kubernetes, sanitize_name
from app.agents.validate import validate_configuration, validate_dockerfile


def test_sanitize_name():
    assert sanitize_name("My App!") == "my-app"
    assert sanitize_name("") == "app"


def test_generate_fastapi_dockerfile(tmp_path):
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    result = generate_dockerfile(
        tmp_path,
        {
            "language": "Python",
            "framework": "FastAPI",
            "entrypoint": "app.main:app",
            "port": 8000,
            "has_dockerfile": False,
        },
    )
    assert result.generated
    assert "FROM python:3.11-slim" in result.dockerfile
    assert "USER appuser" in result.dockerfile
    assert "uvicorn" in result.dockerfile
    assert validate_dockerfile(result.dockerfile) == []


def test_generate_legacy_fastapi_dockerfile_uses_python_310(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "fastapi==0.75.1\norjson==3.6.7\ngreenlet==1.1.2\nhttptools==0.2.0\n",
        encoding="utf-8",
    )
    result = generate_dockerfile(
        tmp_path,
        {
            "language": "Python",
            "framework": "FastAPI",
            "entrypoint": "app.main:app",
            "port": 8000,
            "has_dockerfile": False,
        },
    )
    assert "FROM python:3.10-slim" in result.dockerfile


def test_adjust_python_base_image_rewrites_old_generated_dockerfile(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "fastapi==0.75.1\norjson==3.6.7\ngreenlet==1.1.2\nhttptools==0.2.0\n",
        encoding="utf-8",
    )
    dockerfile = "FROM python:3.11-slim\nWORKDIR /app\n"
    adjusted = _adjust_python_base_image(dockerfile, tmp_path)
    assert adjusted.startswith("FROM python:3.10-slim")


def test_staging_aligns_existing_fastapi_dockerfile_with_detected_entrypoint(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "api.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    dockerfile = 'FROM python:3.11-slim\nCMD ["uvicorn", "main:app", "--host", "0.0.0.0"]\n'

    analysis = _refresh_fastapi_entrypoint(tmp_path, {"framework": "FastAPI", "entrypoint": "main:app"})
    updated = _align_fastapi_dockerfile_entrypoint(dockerfile, analysis["entrypoint"])

    assert analysis["entrypoint"] == "app.api:app"
    assert '"app.api:app"' in updated
    assert '"main:app"' not in updated


def test_keeps_existing_dockerfile(tmp_path):
    existing = "FROM python:3.11\nCMD [\"python\", \"app.py\"]\n"
    (tmp_path / "Dockerfile").write_text(existing, encoding="utf-8")
    result = generate_dockerfile(
        tmp_path,
        {"language": "Python", "framework": "Flask", "has_dockerfile": True, "port": 5000},
    )
    assert result.generated is False
    assert result.dockerfile == existing
    assert result.suggestions


def test_generate_kubernetes_and_validate():
    docker = generate_dockerfile(
        ".",
        {
            "language": "Python",
            "framework": "FastAPI",
            "entrypoint": "app.main:app",
            "port": 8000,
            "has_dockerfile": False,
        },
    ).dockerfile
    k8s = generate_kubernetes(
        {"port": 8000, "framework": "FastAPI"},
        app_name="demo-api",
    )
    assert set(k8s.files) == {"deployment.yaml", "service.yaml", "rbac.yaml"}
    assert "replicas: 2" in k8s.files["deployment.yaml"]
    assert "readinessProbe" in k8s.files["deployment.yaml"]
    assert "ServiceAccount" in k8s.files["rbac.yaml"]

    validation = validate_configuration(docker, k8s.files)
    assert validation.valid, validation.errors


def test_validation_rejects_bad_dockerfile():
    errors = validate_dockerfile("echo hello")
    assert errors
