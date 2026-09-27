# CodeDeck — Technical Reference Notes

This document provides technical reference notes for CodeDeck. For the comprehensive defense guide containing 80+ Q&A pairs, see [`VIVA_GUIDE.md`](file:///d:/agent/docs/VIVA_GUIDE.md).

---

## Key Architectural Reference Answers

### Q1: What problem does CodeDeck solve?
**Answer**: CodeDeck automates the end-to-end software delivery lifecycle for GitHub repositories. It integrates repository analysis, RAG code intelligence, AI-assisted test generation, Docker containerization, Kubernetes manifest generation, local cluster deployment, and rollout verification into a single unified control plane.

### Q2: Why use `kind` instead of Minikube or Cloud Kubernetes?
**Answer**: `kind` (Kubernetes-in-Docker) runs Kubernetes nodes as Docker containers on a single physical host. This provides a lightweight, local Kubernetes environment with fast cluster startup times and zero cloud infrastructure costs.

### Q3: How does CodeDeck handle long-running deployment tasks?
**Answer**: Deployment operations run asynchronously using FastAPI `BackgroundTasks`. The API returns an initial pending response immediately, allowing clients to poll `/api/projects/{id}/pipeline` or `/api/projects/{id}` for real-time progress without HTTP 504 gateway timeouts.

### Q4: How are Docker build contexts handled for nested projects?
**Answer**: CodeDeck detects nested repository layouts (e.g., `backend/` or `server/`) and passes the appropriate subdirectory as the Docker build context while keeping parent context references intact.

### Q5: How are secrets protected?
**Answer**: API keys and tokens are stored in environment variables (`.env`) and filtered out before executing tests or logging subprocess output.
