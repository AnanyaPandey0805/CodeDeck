from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import PipelineStep


def upsert_step(
    db: Session,
    project_id: int,
    name: str,
    status: str,
    result: str | None = None,
    error: str | None = None,
) -> PipelineStep:
    step = (
        db.query(PipelineStep)
        .filter(PipelineStep.project_id == project_id, PipelineStep.name == name)
        .first()
    )
    now = datetime.now(timezone.utc)
    if not step:
        step = PipelineStep(project_id=project_id, name=name)
        db.add(step)

    step.status = status
    if status == "running":
        step.started_at = now
        step.completed_at = None
        # Background jobs can provide a live phase (for example, image build
        # or rollout) while remaining in the running state.
        step.result = result
        step.error = None
    elif status in {"completed", "failed", "warning"}:
        step.completed_at = now
        step.result = result
        step.error = error

    db.commit()
    db.refresh(step)
    return step
