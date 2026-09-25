from pathlib import Path

from app.agents.repository_agent import analyze_repository


def test_fastapi_detection(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\npytest\n", encoding="utf-8")
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_health.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    result = analyze_repository(tmp_path)
    assert result.supported
    assert result.language == "Python"
    assert result.framework == "FastAPI"
    assert result.package_manager == "pip"
    assert result.entrypoint == "app.main:app"
    assert result.test_command == "pytest"
    assert result.has_dockerfile is False


def test_express_detection(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"name":"demo","dependencies":{"express":"^4.0.0"},"scripts":{"test":"jest"}}',
        encoding="utf-8",
    )
    (tmp_path / "server.js").write_text("const express = require('express')\n", encoding="utf-8")

    result = analyze_repository(tmp_path)
    assert result.language == "JavaScript"
    assert "Express" in (result.framework or "")
    assert result.test_command == "npm test"


def test_spring_boot_detection(tmp_path: Path):
    (tmp_path / "pom.xml").write_text(
        "<project><dependencies><dependency>spring-boot-starter-web</dependency></dependencies></project>",
        encoding="utf-8",
    )
    result = analyze_repository(tmp_path)
    assert result.language == "Java"
    assert result.framework == "Spring Boot"
    assert result.package_manager == "maven"


def test_unsupported(tmp_path: Path):
    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    result = analyze_repository(tmp_path)
    assert result.supported is False
    assert result.language == "Unknown"


def test_monorepo_prefers_backend(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"root","scripts":{"test":"echo ok"}}', encoding="utf-8")
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
    app_dir = backend / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")

    result = analyze_repository(tmp_path)
    assert result.language == "Python"
    assert result.framework == "FastAPI"
    assert "backend/" in result.message


def test_existing_dockerfile(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("flask\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n", encoding="utf-8")
    result = analyze_repository(tmp_path)
    assert result.framework == "Flask"
    assert result.has_dockerfile is True
