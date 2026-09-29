from app.services.deployment_contract import build_deployment_contract


def test_deployment_contract_is_ready_for_valid_fastapi_artifacts():
    result = build_deployment_contract(
        7,
        {"language": "Python", "framework": "FastAPI", "entrypoint": "app.main:app"},
        {
            "Dockerfile": "FROM python:3.11-slim\nCMD [\"uvicorn\", \"app.main:app\"]\n",
            "deployment.yaml": "apiVersion: apps/v1\nkind: Deployment\n",
            "service.yaml": "apiVersion: v1\nkind: Service\n",
        },
    )

    assert result.status == "ready"
    assert result.preview_path == "/api/projects/7/preview/"
    assert any(check.name == "Entrypoint" and check.status == "passed" for check in result.checks)


def test_deployment_contract_blocks_missing_fastapi_entrypoint():
    result = build_deployment_contract(
        7,
        {"language": "Python", "framework": "FastAPI"},
        {
            "Dockerfile": "FROM python:3.11-slim\nCMD [\"python\", \"main.py\"]\n",
            "deployment.yaml": "kind: Deployment\n",
            "service.yaml": "kind: Service\n",
        },
    )

    assert result.status == "blocked"
    assert any(check.name == "Entrypoint" and check.status == "blocked" for check in result.checks)
