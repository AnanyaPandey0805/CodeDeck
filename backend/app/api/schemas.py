from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    repository_url: str


class ProjectOut(BaseModel):
    id: int
    repository_url: str
    repository_name: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisOut(BaseModel):
    project_id: int
    language: str | None = None
    framework: str | None = None
    package_manager: str | None = None
    entrypoint: str | None = None
    test_command: str | None = None
    has_dockerfile: bool = False
    security_score: int | None = None
    analysis_result: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineStepOut(BaseModel):
    name: str
    status: str
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class GeneratedFileOut(BaseModel):
    filename: str
    content: str

    model_config = {"from_attributes": True}


class DeploymentOut(BaseModel):
    id: int
    environment: str
    version: str
    status: str
    deployment_type: str
    details: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    status: str = "failed"
    step: str
    message: str
    details: str | None = None


class QuestionRequest(BaseModel):
    question: str


class SearchSourceOut(BaseModel):
    path: str
    snippet: str
    score: float
    line_start: int
    line_end: int


class RepositoryAnswerOut(BaseModel):
    question: str
    answer: str
    sources: list[SearchSourceOut]
    provider: str | None = None


class EvaluationItemOut(BaseModel):
    question: str
    expected: str
    answer: str
    matched_source: str | None = None
    status: str


class EvaluationOut(BaseModel):
    questions: int
    correct: int
    retrieval_accuracy: float
    results: list[EvaluationItemOut]


class GeneratedTestCaseOut(BaseModel):
    name: str
    rationale: str
    path: str
    code: str


class TestInferenceOut(BaseModel):
    name: str
    target: str
    inference: str


class GeneratedTestRunOut(BaseModel):
    status: str
    message: str
    command: str | None = None
    generated_tests: list[GeneratedTestCaseOut]
    stdout: str = ""
    stderr: str = ""
    failure_analysis: dict | None = None
    test_inferences: list[TestInferenceOut] = []
