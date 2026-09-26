---
title: CodeDeck — Architecture (Midsem)
---

# Architecture

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                    │
│  React + Vite (port 3000)                                  │
│  IDE-style dashboard with 8 pages                          │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP REST
┌──────────────────────▼──────────────────────────────────────┐
│  FastAPI Backend (port 8000)                                │
│                                                             │
│  Routers                                                    │
│  ├── /api/projects   — CRUD, list                          │
│  ├── /api/projects/{id}/analyze  — workflow trigger        │
│  ├── /api/projects/{id}/qa       — RAG Q&A                 │
│  ├── /api/projects/{id}/ai-tests — AI test generation      │
│  ├── /api/projects/{id}/deploy/* — staging/production      │
│  ├── /api/projects/{id}/pipeline — pipeline steps          │
│  └── /api/system/status          — system health           │
│                                                             │
│  LangGraph Workflow (Analysis pipeline)                     │
│  ├── clone_and_analyze           → repository_agent.py     │
│  ├── repository_intelligence     → repository_ai.py        │
│  ├── run_tests                   → testing_agent.py        │
│  ├── security_scan               → security_agent.py       │
│  ├── generate_docker             → docker_agent.py         │
│  └── generate_kubernetes         → kubernetes_agent.py     │
│                                                             │
│  Services                                                   │
│  ├── github.py        — clone, validate URL                │
│  ├── docker.py        — docker build, kind load            │
│  ├── kubernetes.py    — apply, rollout, smoke test         │
│  ├── repository_ai.py — RAG index, search, LLM Q&A        │
│  └── pipeline.py      — upsert pipeline steps              │
└──────┬───────────────────────┬─────────────────────────────┘
       │                       │
┌──────▼──────┐      ┌────────▼────────────────────────────┐
│ PostgreSQL  │      │  Local Filesystem Workspace          │
│ (port 5432) │      │  /tmp/deploymind/                   │
│             │      │  ├── project_{id}/    (cloned repo) │
│  projects   │      │  ├── generated/       (index, files)│
│  analyses   │      │  └── kubeconfig                     │
│  deployments│      └──────────────┬──────────────────────┘
│  pipeline   │                     │
│  generated  │      ┌──────────────▼──────────────────────┐
│  files      │      │  Docker / kind                      │
└─────────────┘      │  ├── Docker daemon (via socket)     │
                     │  ├── kind cluster (deploymind)       │
                     │  └── kubectl → K8s API              │
                     └────────────────────────────────────-┘
```

## Analysis Pipeline (LangGraph)

```
clone_and_analyze
    ↓
repository_intelligence    (index files, generate recommendation)
    ↓
run_tests                  (detect and run existing tests)
    ↓
security_scan              (basic pattern scan)
    ↓
generate_docker            (use or generate Dockerfile)
    ↓
generate_kubernetes        (generate Deployment + Service YAML)
```

## RAG Pipeline

```
Repository files
    ↓ _iter_repository_files() — skip binaries, skip .git etc.
    ↓ _chunk_text()            — split into ~1400 char chunks with overlap
    ↓ _hash_embedding()        — SHA-256 per token → 192-dim vector
    ↓ save to repository_index.json (cached per project)
    ↓
Query
    ↓ _hash_embedding(query)
    ↓ cosine similarity against all chunks
    ↓ top-K results
    ↓ → LLM prompt (or heuristic if no API key)
    ↓ → Answer + sources
```

## Deployment Pipeline

```
Deploy Staging button
    → background task
    → clone repo (or use cache)
    → sanitize requirements
    → docker build (use existing or generated Dockerfile)
    → kind load docker-image
    → kubectl apply (Deployment + Service)
    → kubectl rollout status (wait up to 4 min)
    → smoke test (port-forward → HTTP)
    → store result in DB
    → update pipeline steps
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Local hash embeddings | No external embedding API required; fast, deterministic |
| LangGraph workflow | Clean node-by-node pipeline with conditional edges |
| kind (not cloud K8s) | Runs on a single laptop; no cloud credentials required |
| PostgreSQL | JSONB columns store flexible analysis results |
| Background tasks | Deployment is long-running; FastAPI BackgroundTasks avoid HTTP timeout |
| Heuristic fallback | If no OpenAI key, deterministic answers are returned — app still works |

## Current Midsem Scope

- GitHub → Analysis → RAG → Q&A → AI Testing → Docker → kind → Smoke Test

## Not Yet Implemented (Future Scope)

- Cloud Kubernetes (GKE, EKS, AKS)
- Prometheus / Grafana monitoring
- GitHub Actions CI/CD
- Advanced blue-green (separate from staging — midsem)
- Security scanning (beyond basic pattern detection)
- Node.js / Java AI test generation
