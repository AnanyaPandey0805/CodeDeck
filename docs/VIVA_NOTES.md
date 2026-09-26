# DeployMind — Viva & Technical Interview Notes

Quick-reference answers for university project viva evaluations and technical interviews.

---

### Q1: What problem does DeployMind solve?
**Answer**: DeployMind bridges the gap between source code repositories and production Kubernetes deployments. It automates application stack detection, Docker containerization, Kubernetes manifest generation, staging verification, and Blue-Green zero-downtime traffic switching with human-in-the-loop approval.

---

### Q2: Why use `kind` (Kubernetes in Docker) instead of Minikube or Cloud K8s?
**Answer**: `kind` runs lightweight Kubernetes nodes as Docker containers on the developer machine. It requires zero cloud infrastructure cost, provisions in seconds, and provides a real Kubernetes API server for local testing.

---

### Q3: How does DeployMind prevent long-running deployment requests from timing out (HTTP 504)?
**Answer**: DeployMind uses FastAPI `BackgroundTasks`. Deployment requests (`POST /deploy/staging`) record status as `deploying`, trigger asynchronous background execution, and immediately return HTTP 202. The frontend polls status endpoints every 3 seconds to show real-time progress without blocking connection sockets.

---

### Q4: Explain the Blue-Green Deployment workflow in DeployMind.
**Answer**:
1. Current live version is `BLUE` (`spec.selector.version = blue`).
2. A new `GREEN` deployment (`<app>-green`) is created with updated container image and 2 replicas.
3. Automated smoke tests verify `GREEN` pod readiness.
4. Deployment state changes to `production_awaiting_approval`.
5. Human administrator clicks **Approve Production**.
6. The Kubernetes Service selector is patched to `version: green` instantly routing live user traffic to `GREEN`.
7. If an error occurs, clicking **Rollback** patches the Service selector back to `version: blue`.

---

### Q5: How does Docker build context handling work for nested repositories?
**Answer**: If a repository contains nested directories (e.g. `backend/Dockerfile`), but root-level configuration files exist (such as root `package.json` or `pyproject.toml`), DeployMind sets the Docker build context to the repository root directory while passing the exact Dockerfile path. This prevents `COPY failed: file not found` errors.

---

### Q6: How are secrets and security handled?
**Answer**:
- API tokens, passwords, and `.env` files are excluded from logs.
- Generated Dockerfiles enforce unprivileged user execution (`USER appuser`).
- Generated Kubernetes RBAC uses least-privilege role bindings scoped strictly to target namespaces.
- Arbitrary shell command execution is prohibited.

---

### Q7: What are the primary project limitations?
**Answer**:
- Designed primarily for single-service container deployments per pipeline run (multi-service repositories transparently select the main backend service).
- Local cluster deployment relies on `kind` running on the host Docker daemon.
- Requires human approval before production traffic switching.
