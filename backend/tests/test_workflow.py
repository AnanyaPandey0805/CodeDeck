from app.graph.state import DeployMindState
from app.graph.workflow import after_analyze, build_workflow


def test_after_analyze_routing():
    assert after_analyze({"status": "failed"}) == "end"
    assert after_analyze({"status": "analyzed"}) == "continue"


def test_workflow_compiles():
    graph = build_workflow()
    assert graph is not None


def test_state_shape():
    state: DeployMindState = {
        "project_id": 1,
        "repository_url": "https://github.com/acme/demo",
        "errors": [],
        "status": "started",
    }
    assert state["project_id"] == 1
