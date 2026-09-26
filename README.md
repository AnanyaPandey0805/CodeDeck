# CodeDeck — AI-Assisted Software Development & DevOps Platform

CodeDeck takes a GitHub repository through a complete AI-assisted delivery pipeline: repository analysis, semantic code retrieval, AI Q&A, AI-assisted test generation, Docker build, Kubernetes (kind) deployment, and smoke test — all from a single developer IDE-style dashboard.

## Workflow

```
GitHub Repository
    ↓
Repository Analysis      (language, framework, port, entry point, Dockerfile)
    ↓
Repository Indexing      (chunking, hash embeddings, local semantic index)
    ↓
AI Repository Q&A        (RAG — retrieve → LLM → grounded answer)
    ↓
AI Test Generation       (FastAPI / Flask — generate → pytest → PASS/FAIL)
    ↓
Deployment Recommendation (grounded from repository context)
    ↓
Docker Build             (use existing Dockerfile or generate one)
    ↓
kind Kubernetes Deploy   (Deployment + Service applied to local kind cluster)
    ↓
Smoke Test               (kubectl port-forward → HTTP → validate response)
    ↓
Result + Logs
```

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, FastAPI, SQLAlchemy |
| Database | PostgreSQL |
| AI / RAG | OpenAI GPT-4.1-mini, local hash embeddings |
| Orchestration | LangGraph workflow |
| Containerization | Docker |
| Kubernetes | kind (local), kubectl |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4 |

## Quick Start

### Prerequisites

- Docker Desktop (with Docker socket available)
- [kind](https://kind.sigs.k8s.io/) installed
- kubectl installed
- An OpenAI API key (optional but required for LLM-enhanced answers)

### 1. Create kind cluster

```bash
kind create cluster --name deploymind
kubectl cluster-info --context kind-deploymind
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 3. Start the stack

```bash
docker compose up --build
```

### 4. Open the dashboard

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### 5. Run the demo script (PowerShell)

```powershell
.\scripts\run_demo.ps1
```

## Supported Repository Types

| Type | Analysis | AI Q&A | AI Tests | Docker | K8s |
|------|----------|--------|----------|--------|-----|
| Python FastAPI | ✓ | ✓ | ✓ | ✓ | ✓ |
| Python Flask | ✓ | ✓ | ✓ | ✓ | ✓ |
| Python Django | ✓ | ✓ | — | ✓ | ✓ |
| Node.js / Express | ✓ | ✓ | — | ✓ | ✓ |
| Java / Spring Boot | ✓ | ✓ | — | if Dockerfile present | ✓ |
| Any repo with Dockerfile | ✓ | ✓ | — | ✓ | ✓ |

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Viva Guide](docs/VIVA_GUIDE.md)
- [Future Scope](docs/FUTURE_SCOPE.md)

## Environment Variables

See [.env.example](.env.example).

## Notes

- The local kind cluster must be running before deploying.
- LLM calls are only made for Q&A, test rationale, deployment recommendation, and failure analysis. All other detection is deterministic code.
- The repository index is cached per project — analysis does not re-index unless you create a new project.
