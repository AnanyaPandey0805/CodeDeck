from app.services.pipeline import upsert_step


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class _Session:
    def __init__(self):
        self.rows = []

    def query(self, _model):
        return _Query(self.rows)

    def add(self, row):
        self.rows.append(row)

    def commit(self):
        pass

    def refresh(self, _row):
        pass


def test_running_pipeline_step_keeps_live_progress_message():
    session = _Session()
    step = upsert_step(session, 1, "Staging", "running", result="Building container image")

    assert step.status == "running"
    assert step.result == "Building container image"
    assert session.rows[0].result == "Building container image"
