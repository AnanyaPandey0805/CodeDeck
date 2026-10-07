"""
CodeDeck — RAG Evaluation Runner
=================================
Run this script to generate quantitative results comparing heuristic-only mode
vs. LLM+RAG mode for the CodeDeck repository Q&A pipeline.

Usage:
    cd d:\\agent
    python backend/run_evaluation.py

Output:
    A results table showing accuracy, per-question status, and provider info.
    Use the output as evidence for project evaluation / presentation.
"""
import os
import sys
import tempfile
import textwrap
from pathlib import Path

# Ensure the backend package is importable
_backend = Path(__file__).parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

import app.core.config as _cfg
from app.services.repository_ai import (
    answer_repository_question,
    build_repository_index,
    evaluate_repository_index,
    generate_deployment_recommendation,
    get_active_ai_provider,
)

# ── Sample repository fixture ────────────────────────────────────────────────

def _make_sample_repo(root: Path) -> None:
    """Create a minimal FastAPI repository for evaluation."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "requirements.txt").write_text(
        "fastapi\nuvicorn\npytest\nhttpx\n", encoding="utf-8"
    )
    (root / "README.md").write_text(
        "# Sample FastAPI Demo\n\nPort: 8000\nFramework: FastAPI\n",
        encoding="utf-8",
    )
    app_dir = root / "app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "main.py").write_text(
        textwrap.dedent("""\
            from fastapi import FastAPI

            app = FastAPI(title="Demo API")


            @app.get("/")
            def root():
                return {"message": "hello world"}


            @app.get("/health")
            def health():
                return {"status": "ok"}


            @app.get("/items/{item_id}")
            def get_item(item_id: int):
                return {"id": item_id, "name": "widget"}
        """),
        encoding="utf-8",
    )


ANALYSIS = {
    "framework": "FastAPI",
    "language": "Python",
    "package_manager": "pip",
    "entrypoint": "app.main:app",
    "port": 8000,
    "has_dockerfile": False,
    "has_kubernetes": False,
    "repository_url": "https://github.com/sample/demo",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _sep(char="=", width=80):
    return char * width


def _run_evaluation(project_id: int, label: str):
    report = evaluate_repository_index(project_id, ANALYSIS)
    print(f"\n{_sep()}")
    print(f"  MODE: {label}")
    print(f"  Result: {report.correct}/{report.questions} correct  "
          f"({report.retrieval_accuracy}% retrieval accuracy)")
    print(_sep("-"))
    print(f"  {'Question':<52} {'Expected':<12} Status")
    print(_sep("-"))
    for item in report.results:
        q = item.question[:51]
        e = item.expected[:11]
        icon = "PASS" if item.status == "correct" else "FAIL"
        print(f"  [{icon}] {q:<52} {e:<12} {item.status}")
    print(_sep("-"))
    return report


def _run_qa_sample(project_id: int, label: str) -> None:
    """Show sample Q&A answers to demonstrate LLM vs heuristic quality."""
    sample_questions = [
        "What framework does this repository use?",
        "What port does the application run on?",
        "What API routes are exposed by this application?",
    ]
    print(f"\n{_sep()}")
    print(f"  SAMPLE Q&A ANSWERS -- {label}")
    print(_sep("-"))
    for question in sample_questions:
        answer = answer_repository_question(project_id, question, ANALYSIS)
        print(f"\n  Q: {question}")
        print(f"  A: {answer.answer[:300]}")
        print(f"  Provider: {answer.provider}  |  Sources: {len(answer.sources)}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{_sep()}")
    print("  CodeDeck RAG Evaluation -- Quantitative Results")
    print(_sep())

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        repo = Path(tmp) / "sample_repo"
        _make_sample_repo(repo)

        # Point settings at our temp workspace
        _cfg.settings.workspace_dir = str(workspace)

        # Build the index once (shared between both modes)
        meta = build_repository_index(repo, project_id=99, repository_url=ANALYSIS["repository_url"])
        print(f"\n  Index built: {meta.file_count} files, {meta.chunk_count} chunks")
        print(f"  Indexed at:  {meta.indexed_at}")

        # Mode 1: Heuristic (no LLM)
        original_key = _cfg.settings.openai_api_key
        original_grok = _cfg.settings.grok_api_key
        original_groq = _cfg.settings.groq_api_key

        _cfg.settings.openai_api_key = ""
        _cfg.settings.grok_api_key = ""
        _cfg.settings.groq_api_key = ""

        heuristic_provider = get_active_ai_provider()
        print(f"\n  [Heuristic] Provider: {heuristic_provider['provider']} / {heuristic_provider['model']}")
        heuristic_report = _run_evaluation(99, "HEURISTIC (no LLM)")
        _run_qa_sample(99, "HEURISTIC")

        # Mode 2: LLM + RAG
        _cfg.settings.openai_api_key = original_key
        _cfg.settings.grok_api_key = original_grok
        _cfg.settings.groq_api_key = original_groq

        llm_provider = get_active_ai_provider()
        print(f"\n  [LLM+RAG] Provider: {llm_provider['provider']} / {llm_provider['model']}")
        llm_report = _run_evaluation(99, f"LLM + RAG ({llm_provider['provider']})")
        _run_qa_sample(99, f"LLM+RAG ({llm_provider['provider']})")

        # Deployment Recommendation
        print(f"\n{_sep()}")
        print("  AI DEPLOYMENT RECOMMENDATION")
        print(_sep("-"))
        rec = generate_deployment_recommendation(99, ANALYSIS)
        print(f"  Framework detected: {rec.detected.get('framework')}")
        print(f"  Port:               {rec.detected.get('port')}")
        print(f"  Potential issues ({len(rec.potential_issues)}):")
        for issue in rec.potential_issues:
            print(f"    - {issue}")
        print(f"\n  Recommendation steps:")
        for r in rec.recommendation:
            print(f"    * {r}")

        # Final Comparison
        print(f"\n{_sep()}")
        print("  FINAL COMPARISON SUMMARY")
        print(_sep("-"))
        print(f"  {'Mode':<40} {'Correct':<10} {'Accuracy'}")
        print(_sep("-"))
        print(f"  {'Heuristic (no LLM)':<40} "
              f"{heuristic_report.correct}/{heuristic_report.questions:<8} "
              f"{heuristic_report.retrieval_accuracy}%")
        print(f"  {(llm_provider['provider'] + ' + RAG'):<40} "
              f"{llm_report.correct}/{llm_report.questions:<8} "
              f"{llm_report.retrieval_accuracy}%")
        delta = llm_report.retrieval_accuracy - heuristic_report.retrieval_accuracy
        print(_sep("-"))
        print(f"  AI augmentation delta: {'+' if delta >= 0 else ''}{delta:.1f}%")
        print(_sep() + "\n")


if __name__ == "__main__":
    main()
