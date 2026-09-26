# DeployMind — Comprehensive Project Explanation

DeployMind is an AI-assisted software delivery platform designed to streamline software containerization, configuration generation, local Kubernetes deployment, and Blue-Green traffic management.

---

## 1. Project Overview & Motivation

Deploying modern applications requires multiple discrete steps: analyzing source code dependencies, authoring Dockerfiles, configuring Kubernetes manifests, verifying container health, and managing zero-downtime production rollouts. 

DeployMind automates this pipeline by acting as an intelligent developer assistant. Given a GitHub repository URL, DeployMind inspects the codebase, selects the appropriate containerization strategy, generates valid Kubernetes manifests, deploys to a local `kind` cluster, and provides human-in-the-loop Blue-Green deployment controls.

---

## 2. Architecture Diagram

```text
+-----------------------------------------------------------------------------+
|                                User (Browser)                               |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                      React + TypeScript Frontend (Vite)                     |
+-----------------------------------------------------------------------------+
                                       |
                                       v REST / JSON
+-----------------------------------------------------------------------------+
|                           FastAPI Backend Service                           |
|                                                                             |
|  +---------------------+  +----------------------+  +--------------------+  |
|  |  Repository Agent   |  |     Docker Agent     |  |  Kubernetes Agent  |  |
|  +---------------------+  +----------------------+  +--------------------+  |
|  |    Testing Agent    |  |    Security Agent    |  |  Deployment Agent  |  |
|  +---------------------+  +----------------------+  +--------------------+  |
+-----------------------------------------------------------------------------+
          |                            |                            |
          v                            v                            v
+------------------+         +------------------+         +-------------------+
|  PostgreSQL DB   |         | Docker Engine    |         | local kind Cluster|
| (State/History)  |         | (Image Build)    |         | (Staging & Prod)  |
+------------------+         +------------------+         +-------------------+
```

---

## 3. Technology Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy (ORM), Pydantic, PostgreSQL
- **Orchestration**: LangGraph, OpenAI SDK
- **Infrastructure & Containerization**: Docker Engine API, local `kind` Kubernetes cluster, `kubectl`
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS

---

## 4. Key Subsystems & Workflow Steps

### Step 1: Repository Analysis
The `Repository Agent` inspects the cloned workspace to identify programming languages, frameworks, entrypoints, package managers (`pip`, `uv`, `poetry`, `npm`, `yarn`, `pnpm`, `bun`, `maven`, `gradle`), and existing Docker/Kubernetes configurations. It also identifies multi-service structures (e.g. `backend/` and `frontend/`).

### Step 2: Automated Testing & Security Scan
The `Testing Agent` executes allowlisted test commands (`pytest`, `npm test`, `./mvnw test`) safely. The `Security Agent` performs static code analysis to check for exposed secrets, root Docker users, and missing Kubernetes security contexts.

### Step 3: Containerization & Manifest Generation
The `Docker Agent` reuses existing Dockerfiles or generates production-ready container specifications. The `Kubernetes Agent` generates `Deployment`, `Service`, and namespace-restricted `RBAC` manifests with resource limits and probes.

### Step 4: Staging Deployment
The `Deployment Agent` builds the container image, loads it directly into the local `kind` cluster via `kind load docker-image`, applies manifests into namespace `deploymind`, waits for rollout, and runs automated smoke tests via port forwarding.

### Step 5: Blue-Green Production Deployment & Rollback
1. **GREEN Deployment**: Deploys a new Deployment resource (`<app>-green`) tagged `version: green` with 2 replicas.
2. **Health Verification**: Runs isolated health checks against the GREEN pods.
3. **Human Approval**: Pauses rollout and sets state to `production_awaiting_approval`.
4. **Traffic Switch**: Upon approval, patches the live Kubernetes Service selector (`spec.selector.version = green`).
5. **Rollback**: Provides instant traffic rollback (`spec.selector.version = blue`) if issues arise.

---

## 5. Security & Safety Design

1. **No Unrestricted Command Execution**: Arbitrary shell endpoints are strictly forbidden; commands are bounded to specific functions (`build_image`, `apply_manifests`, `smoke_test`).
2. **Namespace Isolation**: Applications deploy into dedicated Kubernetes namespaces (`deploymind`).
3. **Non-Root Execution**: Generated Dockerfiles use dedicated unprivileged users (`appuser`).
