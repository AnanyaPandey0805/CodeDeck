from app.db.database import SessionLocal, init_db
from app.db.models import Analysis, Project
from app.services.repository_ai import run_ai_generated_tests

# Initialize the in‑memory SQLite database and ensure required tables exist
init_db()

# Create a new session
db = SessionLocal()

# Ensure a Project entry exists for the test
project = db.get(Project, 1)
if not project:
    project = Project(id=1, repository_url='https://github.com/octocat/Hello-World.git', repository_name='Hello-World', status='created')
    db.add(project)
    db.commit()

# Ensure an Analysis entry exists for the project
analysis = db.query(Analysis).filter(Analysis.project_id == 1).first()
if not analysis:
    analysis = Analysis(project_id=1, analysis_result={})
    db.add(analysis)
    db.commit()

# Prepare payload for AI‑generated tests
payload = dict(analysis.analysis_result or {})
payload["repository_url"] = project.repository_url

# Run the AI‑generated tests
result = run_ai_generated_tests(1, project.repository_url, payload)
print(f"STATUS: {result.status}")
print(f"MSG: {result.message}")
if result.stdout:
    print("STDOUT:", result.stdout[-1500:])
if result.stderr:
    print("STDERR:", result.stderr[-1500:])
