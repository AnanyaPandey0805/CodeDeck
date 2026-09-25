from typing import TypedDict


class DeployMindState(TypedDict, total=False):
    project_id: int
    repository_url: str
    repository_name: str
    repository_path: str
    analysis: dict
    test_result: dict
    security_result: dict
    dockerfile: str
    kubernetes_files: dict
    validation_result: dict
    errors: list
    status: str
