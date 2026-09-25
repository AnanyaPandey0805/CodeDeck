# DeployMind

DeployMind is an AI-assisted DevOps course project that turns a GitHub repository into a local Kubernetes deployment workflow. It analyzes repository structure, builds grounded repository Q&A context, generates deployment recommendations, validates Docker and Kubernetes configuration, deploys to a local `kind` cluster, runs smoke checks, supports blue-green promotion with approval, and provides rollback and failure analysis.

## What It Demonstrates

- AI-assisted repository understanding
- Lightweight repository RAG and grounded code Q&A
- Deployment recommendations from retrieved repository context
- AI-assisted test generation and test-failure explanation
- Docker build and local Kubernetes deployment automation
- Blue-green production deployment with approval, traffic switch, and rollback
- Retrieval evaluation with predefined repository questions
- Simple CI with GitHub Actions

## High-Level Architecture

```text
GitHub repository
    |
    v
FastAPI backend
    |
    +--> Repository analysis agent
    |       |
    |       +--> Repository chunking + local embeddings + semantic search
    |       +--> Deployment recommendation
    |       +--> Retrieval evaluation
    |       +--> AI-generated test runner
    |
    +--> Docker + Kubernetes deployment agents
            |
            +--> Staging rollout + smoke test
            +--> GREEN production deployment
            +--> Approval + traffic switch
            +--> Rollback
            +--> Failure analysis
    |
    v
React frontend
```

More detail:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/AI_PIPELINE.md](docs/AI_PIPELINE.md)
- [docs/DEMO.md](docs/DEMO.md)

## Core Flow

```text
Repository URL
  -> Analysis
  -> Repository index / retrieval
  -> Deployment recommendation
  -> Dockerfile + Kubernetes manifests
  -> Staging deploy
  -> Smoke test
  -> GREEN deploy
  -> Approval
  -> Traffic switch
  -> Rollback if needed
```

## Main Features

### Repository Analysis

- Detects language, framework, package manager, entrypoint, port, test command, Dockerfile presence, and multi-service repositories.
- Stores analysis results in PostgreSQL.

### Repository RAG / Q&A

- Reads repository source files and docs
- Splits them into chunks
- Builds lightweight local embeddings
- Persists the repository index in the DeployMind workspace
- Runs semantic search over indexed chunks
- Answers repository questions with retrieved evidence

Example questions:

- What framework does this repository use?
- Where is authentication implemented?
- What is the deployment entrypoint?
- What database does this application use?

### Deployment Recommendation

After analysis, DeployMind generates a grounded recommendation that includes:

- detected stack
- likely deployment risks
- health endpoint detection
- database dependency hints
- suggested deployment steps

### AI-Assisted Testing

- Runs the repository's existing detected test command during analysis
- Adds a small AI-generated route test flow for supported FastAPI and Flask repositories
- Returns execution logs and a short failure explanation when generated tests fail

### Deployment Automation

- Builds Docker images
- Loads images into a local `kind` cluster
- Applies Kubernetes manifests
- Waits for rollout
- Performs smoke tests through `kubectl port-forward`
- Deploys GREEN production
- Switches traffic only after approval
- Supports rollback to BLUE

### Failure Analysis

When a deployment fails, DeployMind collects:

- deployment error text
- pod and deployment status
- recent pod logs when available

It then returns:

- likely cause
- evidence
- safest suggested next step

### Evaluation

DeployMind runs a lightweight retrieval evaluation using predefined repository questions and reports:

- number of questions
- relevant/correct count
- retrieval accuracy percentage

## Tech Stack

- Backend: FastAPI, SQLAlchemy, Pydantic, PostgreSQL
- AI/Workflow: LangGraph, OpenAI SDK, local hashed embeddings
- Deployment: Docker, `kind`, `kubectl`
- Frontend: React, TypeScript, Vite

## Local Setup

### 1. Configure environment

Copy the example file and set values as needed:

```bash
cp .env.example .env
```

Optional but recommended:

- `OPENAI_API_KEY` for LLM-generated wording and explanations
- `GITHUB_TOKEN` for private repository cloning or higher GitHub rate limits

### 2. Start dependencies

Ensure Docker Desktop, `kind`, and `kubectl` are installed.

Create the cluster:

```bash
kind create cluster --name deploymind
kubectl cluster-info --context kind-deploymind
```

### 3. Run the stack

```bash
docker compose up --build
```

Default local endpoints:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5433`

## How To Use

1. Open the frontend.
2. Paste a GitHub repository URL.
3. Run repository analysis.
4. Review framework, language, entrypoint, port, recommendation, and evaluation.
5. Ask a repository Q&A question and inspect the retrieved evidence.
6. Run AI-generated tests if the repository is supported.
7. Deploy staging.
8. Deploy GREEN production.
9. Approve traffic switch.
10. Roll back if required.

## CI

The repository includes a GitHub Actions workflow at `.github/workflows/deploymind.yml` that:

- installs backend dependencies
- runs backend tests
- installs frontend dependencies
- builds the frontend

## Notes

- Existing deployment flow was preserved and extended rather than replaced.
- LLM output is treated as guidance and explanation, not executable shell instructions.
- `.env` stays outside source control and secrets are not logged intentionally.
