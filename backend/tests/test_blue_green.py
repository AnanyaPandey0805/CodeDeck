import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import Project
from app.main import app
from app.services.kubernetes import patch_manifests_for_blue_green

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_patch_manifests_for_blue_green():
    files = {
        "deployment.yaml": """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo
  template:
    metadata:
      labels:
        app: demo
    spec:
      containers:
        - name: demo
          image: original:latest
""".lstrip(),
        "service.yaml": """
apiVersion: v1
kind: Service
metadata:
  name: demo
spec:
  selector:
    app: demo
  ports:
    - port: 80
      targetPort: 8000
""".lstrip(),
    }

    patched = patch_manifests_for_blue_green(
        files,
        image="deploymind/demo:green",
        app_name="demo",
        version="green",
        replicas=2,
    )

    dep = patched["deployment.yaml"]
    svc = patched["service.yaml"]

    assert "name: demo-green" in dep
    assert "image: deploymind/demo:green" in dep
    assert "replicas: 2" in dep
    assert "version: green" in dep
    assert "version: green" in svc


def test_deployments_api_endpoints():
    # 404 for non-existent project
    res = client.post("/api/projects/999999/deploy/production")
    assert res.status_code == 404

    db = TestingSessionLocal()
    p = Project(repository_url="https://github.com/acme/demo", repository_name="demo", status="created")
    db.add(p)
    db.commit()
    db.refresh(p)

    # Missing analysis returns 400
    res = client.post(f"/api/projects/{p.id}/deploy/production")
    assert res.status_code == 400
    data = res.json()
    assert data["status"] == "failed"
    assert "Run analysis" in data["message"]

    # History endpoint returns list
    res = client.get(f"/api/projects/{p.id}/deployments")
    assert res.status_code == 200
    assert res.json() == []
    db.close()
