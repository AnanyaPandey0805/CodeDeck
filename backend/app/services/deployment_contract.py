"""Vercel-style deployment readiness metadata for DeployMind's local target."""

from pydantic import BaseModel, Field

from app.agents.validate import validate_dockerfile


class DeploymentContractCheck(BaseModel):
    name: str
    status: str
    message: str


class DeploymentContract(BaseModel):
    status: str
    target: str = "local-kind"
    preview_path: str
    entrypoint: str | None = None
    checks: list[DeploymentContractCheck] = Field(default_factory=list)
    summary: str


def build_deployment_contract(
    project_id: int,
    analysis: dict,
    files: dict[str, str],
) -> DeploymentContract:
    """Describe whether generated artifacts form a deployable local preview.

    Warnings are intentionally non-blocking: staging remains the final runtime
    verification, while invalid generated configuration is blocked early.
    """
    checks: list[DeploymentContractCheck] = []
    framework = str(analysis.get("framework") or "Unknown")
    language = str(analysis.get("language") or "Unknown")
    entrypoint = analysis.get("entrypoint")
    dockerfile = files.get("Dockerfile", "")

    checks.append(
        DeploymentContractCheck(
            name="Runtime",
            status="passed" if language != "Unknown" else "blocked",
            message=f"{framework} runtime detected" if language != "Unknown" else "No supported runtime was detected",
        )
    )

    if framework in {"FastAPI", "Flask", "Django"}:
        entry_status = "passed" if isinstance(entrypoint, str) and ":" in entrypoint else "blocked"
        entry_message = (
            f"Application entrypoint: {entrypoint}"
            if entry_status == "passed"
            else "A Python web entrypoint could not be determined"
        )
        checks.append(DeploymentContractCheck(name="Entrypoint", status=entry_status, message=entry_message))

    if language == "Java":
        build_tool = analysis.get("package_manager")
        checks.append(
            DeploymentContractCheck(
                name="Build tool",
                status="passed" if build_tool in {"maven", "gradle"} else "blocked",
                message=f"{build_tool} source build will run in staging"
                if build_tool in {"maven", "gradle"}
                else "Spring/Java projects need pom.xml or build.gradle",
            )
        )

    database = analysis.get("database")
    if database:
        checks.append(
            DeploymentContractCheck(
                name="Staging database",
                status="passed",
                message=f"An ephemeral {database} service will be created inside the staging namespace",
            )
        )

    docker_errors = validate_dockerfile(dockerfile) if dockerfile else ["Dockerfile is empty"]
    checks.append(
        DeploymentContractCheck(
            name="Container",
            status="passed" if not docker_errors else "blocked",
            message="Generated Dockerfile is valid" if not docker_errors else "; ".join(docker_errors[:2]),
        )
    )

    required_manifests = {"deployment.yaml", "service.yaml"}
    missing_manifests = sorted(required_manifests - set(files))
    checks.append(
        DeploymentContractCheck(
            name="Kubernetes",
            status="passed" if not missing_manifests else "blocked",
            message="Deployment and Service manifests are ready"
            if not missing_manifests
            else f"Missing manifest(s): {', '.join(missing_manifests)}",
        )
    )

    test_result = analysis.get("test_result") or {}
    test_status = test_result.get("status")
    if test_status == "passed":
        checks.append(DeploymentContractCheck(name="Repository tests", status="passed", message="Detected tests passed"))
    elif test_status:
        checks.append(
            DeploymentContractCheck(
                name="Repository tests",
                status="warning",
                message=str(test_result.get("message") or f"Tests {test_status}"),
            )
        )

    security = analysis.get("security_result") or {}
    findings = security.get("findings") or []
    high_findings = [item for item in findings if str(item.get("severity", "")).upper() == "HIGH"]
    if high_findings:
        checks.append(
            DeploymentContractCheck(
                name="Security",
                status="warning",
                message=f"{len(high_findings)} high-severity finding(s) require review before promotion",
            )
        )

    if analysis.get("is_multiservice"):
        services = ", ".join(analysis.get("detected_services") or [])
        checks.append(
            DeploymentContractCheck(
                name="Service scope",
                status="warning",
                message=f"Local preview deploys the primary backend only ({services or 'multi-service repository'})",
            )
        )

    blocked = [check for check in checks if check.status == "blocked"]
    warnings = [check for check in checks if check.status == "warning"]
    status = "blocked" if blocked else "attention" if warnings else "ready"
    summary = (
        "Deployment artifacts are ready for a local staging preview."
        if status == "ready"
        else "Deployment can proceed with operational warnings."
        if status == "attention"
        else "Deployment is blocked until the required configuration is generated."
    )
    return DeploymentContract(
        status=status,
        preview_path=f"/api/projects/{project_id}/preview/",
        entrypoint=entrypoint if isinstance(entrypoint, str) else None,
        checks=checks,
        summary=summary,
    )
