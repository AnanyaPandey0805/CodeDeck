# CodeDeck — AI-Assisted Software Development & DevOps Platform

CodeDeck is an integrated platform that accelerates software development by combining AI-driven code analysis, intelligent RAG Q&A, and automated Kubernetes deployments.

## Core Workflow

```text
GitHub Repo -> Analysis -> RAG Q&A -> AI Testing -> Docker Build -> Kubernetes Deploy -> Smoke Test -> Results
```

## Technology Stack

| Domain | Technologies |
|--------|--------------|
| **Backend** | FastAPI, Python, PostgreSQL (SQLAlchemy), LangGraph |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4 |
| **AI / NLP** | OpenAI `gpt-4.1-mini`, Hash-based Embeddings (192-dim), Cosine Similarity |
| **DevOps** | Docker, kind (Kubernetes in Docker), kubectl |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- `kind` CLI installed
- `kubectl` CLI installed
- OpenAI API Key

### Setup Instructions

1. **Ensure the kind cluster is running:**
   ```bash
   kind create cluster --name codedeck-cluster
   ```

2. **Start the platform:**
   ```bash
   docker compose up -d --build
   ```

3. **Access the application:**
   - Frontend Dashboard: `http://localhost:3000`
   - Backend API Docs: `http://localhost:8000/docs`

## Supported Repository Types

| Framework / Environment | Support Level | Features |
|-------------------------|---------------|----------|
| Python (FastAPI/Flask/Django) | Excellent | Analysis, RAG, AI Tests, Auto-Deploy |
| Node.js (Express) | Good | Analysis, RAG, Auto-Deploy |
| Java (Spring Boot) | Good | Analysis, RAG, Auto-Deploy |
| Generic Dockerfile | Standard | Auto-Deploy |

## Project Structure

- `/backend`: FastAPI application, LangGraph workflows, and database models.
- `/frontend`: React dashboard, Vite configuration, and Tailwind styling.
- `/docs`: Architecture and system documentation.
- `/scripts`: Automation and workflow scripts.

## Documentation References

- [System Architecture](docs/ARCHITECTURE.md): Detailed component breakdown, RAG pipeline, and schemas.

## Architecture Notes

CodeDeck employs a sequential LangGraph orchestration pipeline to guarantee deterministic progression from code analysis to deployment. It uses a bespoke hash-based embedding mechanism for source code indexing, enabling fast and localized RAG Q&A without excessive API overhead. Deployment is securely isolated within a local `kind` cluster, featuring automated readiness checks and rollout verifications.
