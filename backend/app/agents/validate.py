import logging

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger("deploymind")


class ValidationResult(BaseModel):
    valid: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


def validate_dockerfile(content: str) -> list[str]:
    errors = []
    if not content.strip():
        return ["Dockerfile is empty"]
    if not any(line.strip().upper().startswith("FROM ") for line in content.splitlines()):
        errors.append("Dockerfile missing FROM")
    has_cmd = any(
        line.strip().upper().startswith(("CMD ", "ENTRYPOINT "))
        for line in content.splitlines()
    )
    if not has_cmd:
        errors.append("Dockerfile missing CMD or ENTRYPOINT")
    return errors


def validate_k8s_yaml(filename: str, content: str) -> list[str]:
    errors = []
    try:
        docs = list(yaml.safe_load_all(content))
    except yaml.YAMLError as exc:
        return [f"{filename}: invalid YAML ({exc})"]

    docs = [d for d in docs if d]
    if not docs:
        return [f"{filename}: empty document"]

    for doc in docs:
        kind = doc.get("kind")
        if not kind:
            errors.append(f"{filename}: missing kind")
            continue
        if not doc.get("metadata", {}).get("name"):
            errors.append(f"{filename}: missing metadata.name")

        if kind == "Deployment":
            spec = doc.get("spec") or {}
            if not spec.get("selector"):
                errors.append(f"{filename}: Deployment missing selector")
            template = (spec.get("template") or {}).get("spec") or {}
            containers = template.get("containers") or []
            if not containers:
                errors.append(f"{filename}: Deployment has no containers")
            else:
                c = containers[0]
                if not c.get("image"):
                    errors.append(f"{filename}: container missing image")
                if not c.get("resources"):
                    errors.append(f"{filename}: container missing resources")
                is_managed_database = doc.get("metadata", {}).get("labels", {}).get("managed-by") == "deploymind"
                if not is_managed_database and not ((c.get("securityContext") or {}).get("runAsNonRoot") or (template.get("securityContext") or {}).get("runAsNonRoot")):
                    errors.append(f"{filename}: missing non-root securityContext")
                if not c.get("readinessProbe"):
                    errors.append(f"{filename}: missing readinessProbe")
                if not c.get("livenessProbe"):
                    errors.append(f"{filename}: missing livenessProbe")

        if kind == "Service":
            spec = doc.get("spec") or {}
            if not spec.get("selector"):
                errors.append(f"{filename}: Service missing selector")
            if not spec.get("ports"):
                errors.append(f"{filename}: Service missing ports")

        if kind == "Role":
            if not doc.get("rules"):
                errors.append(f"{filename}: Role missing rules")

    return errors


def validate_configuration(dockerfile: str, k8s_files: dict[str, str]) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(validate_dockerfile(dockerfile))
    for name, content in k8s_files.items():
        errors.extend(validate_k8s_yaml(name, content))

    if "USER" not in dockerfile.upper():
        warnings.append("Dockerfile has no USER directive")

    valid = len(errors) == 0
    if valid:
        message = "Configuration validated"
        if warnings:
            message += f" ({len(warnings)} warning(s))"
    else:
        message = f"Validation failed ({len(errors)} error(s))"

    logger.info(message)
    return ValidationResult(valid=valid, errors=errors, warnings=warnings, message=message)
