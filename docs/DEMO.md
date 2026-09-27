# CodeDeck — Operational Workflow & Execution Guide

This document outlines the step-by-step workflow for operating CodeDeck end-to-end using a sample repository.

---

## Target Workflow Summary

```
GitHub Repository
       ↓
Repository Analysis
       ↓
Repository Indexing / RAG
       ↓
AI Repository Q&A
       ↓
AI-Assisted Testing
       ↓
Deployment Recommendation
       ↓
Docker Build
       ↓
Kubernetes (kind)
       ↓
Smoke Test
       ↓
Deployment Result / Logs
```

---

## Step-by-Step Execution Guide

### 1. System Initialization
1. Ensure your local `kind` cluster is running:
   ```bash
   kind create cluster --name deploymind
   ```
2. Start CodeDeck via Docker Compose:
   ```bash
   docker compose up --build
   ```
3. Open the dashboard at `http://localhost:3000`.

### 2. Creating a Project & Ingestion
1. Paste a public repository URL (e.g. `https://github.com/tiangolo/full-stack-fastapi-template`).
2. Click **Analyze**. CodeDeck will clone the repository, run static detection (language, framework, dependencies, ports, entrypoints), build the RAG index, run existing tests, execute security checks, and generate Docker and Kubernetes manifests.

### 3. Repository Q&A (RAG)
1. Navigate to the **AI Assistant** tab.
2. Ask questions such as *"Where is authentication implemented?"* or *"What API endpoints exist?"*.
3. Inspect the returned answer along with grounded file evidence citations.

### 4. AI-Assisted Testing
1. Navigate to the **Testing** tab.
2. Click **Run AI Tests**. CodeDeck will inspect detected routes, synthesize route-focused pytest code, execute the tests via pytest in a subprocess, and display stdout/stderr.

### 5. Staging Deployment
1. Click **Deploy Staging** in the top navigation bar or from the **Kubernetes** tab.
2. Track rollout status: image build → `kind load` → `kubectl apply` → pod readiness check → HTTP smoke test.
3. View smoke test output (endpoint URL, HTTP status, pass/fail status).
