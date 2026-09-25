from pathlib import Path

from app.agents.security_agent import run_security_scan
from app.agents.testing_agent import _is_allowed, run_tests


def test_security_finds_env_and_key(tmp_path: Path):
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text('API_KEY = "sk-abcdefghijklmnopqrstuvwxyz123456"\n', encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\nCMD python app.py\n", encoding="utf-8")

    result = run_security_scan(tmp_path)
    assert result.score < 100
    assert any(f.file == ".env" for f in result.findings)
    assert any("API" in f.message or "secret" in f.message.lower() or "key" in f.message.lower() for f in result.findings)
    assert any("USER" in f.message for f in result.findings)


def test_security_k8s_privileged(tmp_path: Path):
    k8s = tmp_path / "k8s"
    k8s.mkdir()
    (k8s / "deploy.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nspec:\n  template:\n    spec:\n      containers:\n        - name: app\n          securityContext:\n            privileged: true\n",
        encoding="utf-8",
    )
    result = run_security_scan(tmp_path)
    assert any(f.severity == "HIGH" for f in result.findings)


def test_test_command_allowlist():
    assert _is_allowed("pytest")
    assert _is_allowed("pytest -q")
    assert _is_allowed("npm test")
    assert not _is_allowed("rm -rf /")
    assert not _is_allowed("curl http://evil")


def test_run_tests_passes(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")

    result = run_tests(
        tmp_path,
        {"language": "Python", "test_command": "pytest"},
        timeout=120,
    )
    assert result.status == "passed"
    assert result.exit_code == 0


def test_run_tests_skips_when_missing():
    result = run_tests("/tmp/does-not-matter", {"language": "Python", "test_command": None})
    assert result.skipped
    assert result.status == "skipped"
