# CodeDeck — System Architecture

CodeDeck is an AI-assisted software development and DevOps platform. This document outlines the current system architecture, components, workflows, and database schemas.

## Component Architecture

```text
+----------------+      +-------------------+      +-----------------------+
|                |      |                   |      |                       |
|   Browser /    +----->+  Nginx (Frontend) +----->+ FastAPI (Backend)     |
|   Client       |      |                   |      |                       |
+----------------+      +-------------------+      +----+---------+--------+
                                                        |         |
                                                        v         v
                                           +------------+--+   +--+------------+
                                           |               |   |               |
                                           | PostgreSQL    |   | Docker & kind |
                                           | (Relational)  |   | (Deployment)  |
                                           +---------------+   +---------------+
```

## Backend Router Structure

The backend exposes several modular routers to handle different domains of the platform:

- `POST /projects/`: Create a new project integration.
- `GET /projects/`: List all projects.
- `GET /projects/{project_id}`: Retrieve project details.
- `POST /projects/{project_id}/analyze`: Trigger repository analysis.
- `GET /projects/{project_id}/status`: Check analysis and deployment status.
- `POST /projects/{project_id}/qa`: Interact with the RAG Q&A system.
- `POST /projects/{project_id}/tests`: Generate AI tests for the project.
- `POST /projects/{project_id}/deploy`: Trigger staging deployment (Docker & Kubernetes).
- `GET /health`: System health and status check.

## Core Workflow (LangGraph Pipeline)

The system orchestrates operations using a LangGraph sequential pipeline. Each node represents a distinct phase of the project processing lifecycle.

```text
[Analyze] -> [Intelligence] -> [Tests] -> [Security] -> [Docker] -> [Kubernetes]
```

1. **Analyze**: Clones the repository, analyzes structure, and extracts metadata.
2. **Intelligence**: Builds the semantic RAG index (chunking, hash embeddings).
3. **Tests**: Identifies application endpoints and generates test suites (FastAPI/Flask).
4. **Security**: Scans for secrets, Dockerfile root-user issues, and Kubernetes privileges.
5. **Docker**: Builds the application container image.
6. **Kubernetes**: Loads the image into the local `kind` cluster and applies manifests.

## RAG Pipeline Detail

Our Retreival-Augmented Generation pipeline powers the intelligent Q&A and analysis features:

1. **File Selection**: Identifies relevant source code and documentation files.
2. **Chunking**: Splits files into manageable context windows.
3. **Hash Embeddings**: Generates 192-dimensional hash-based embeddings for chunks.
4. **Cosine Search**: Computes cosine similarity between the user query and chunk embeddings.
5. **Context Assembly**: Retrieves the highest-scoring chunks.
6. **LLM Invocation**: Passes the context and query to OpenAI `gpt-4.1-mini`.
7. **Answer Generation**: Returns the synthesized answer to the user.

## Deployment Pipeline Detail

The DevOps automation pipeline executes the following sequence:

1. **Clone**: Fetches the latest source code from the repository.
2. **Sanitize**: Ensures the workspace is clean and ready.
3. **Docker Build**: Builds the container image using the detected or provided Dockerfile.
4. **Kind Load**: Loads the built image into the local `kind` (Kubernetes in Docker) cluster.
5. **Kubectl Apply**: Generates and applies Kubernetes manifests (Deployment, Service).
6. **Rollout**: Waits for the deployment rollout to complete successfully.
7. **Smoke Test**: Verifies application health via a temporary `port-forward`.

## Database Schema

The platform uses PostgreSQL with SQLAlchemy for data persistence.

| Table | Purpose |
|-------|---------|
| `Project` | Stores project metadata, repository URLs, and current state. |
| `Analysis` | Records the outcome of the repository analysis phase. |
| `Deployment` | Tracks deployment attempts, environment status, and URLs. |
| `PipelineStep` | Logs granular details, status, and output of each pipeline node. |
| `GeneratedFile` | Stores AI-generated artifacts such as tests, manifests, and scripts. |

## Configuration

System settings are managed via `config.py`, loading variables from the environment:
- `DATABASE_URL`: PostgreSQL connection string.
- `OPENAI_API_KEY`: Key for LLM services.
- `WORKSPACE_DIR`: Local directory for cloning and processing repositories.
- `KIND_CLUSTER_NAME`: Name of the local `kind` cluster.

## Security Model

**Currently Implemented:**
- Regex-based secret scanning in repositories.
- Dockerfile non-root user verification.
- Kubernetes manifest privilege checks.
- Environment variable filtering to prevent credential leakage.

**Not Yet Implemented (Future Scope):**
- User authentication and authorization.
- Role-Based Access Control (RBAC).
- Multi-tenant data isolation at the database level.

## Extension Points

The architecture is designed for extensibility:
- **Language Support**: Adding new languages requires extending the `Analyze` node parsers.
- **LLM Providers**: The RAG pipeline abstracts embedding and generation, allowing integration with other models.
- **Deployment Targets**: Additional environments (e.g., AWS, GCP) can be added as new nodes in the LangGraph pipeline.

## Design Decisions

| Technology | Reason for Selection |
|------------|----------------------|
| **FastAPI** | High performance, async support, and auto-generated OpenAPI documentation. |
| **React & Vite** | Fast build times, robust ecosystem, and modular component design. |
| **LangGraph** | Provides a resilient, stateful workflow execution engine for complex pipelines. |
| **Kind** | Lightweight, local Kubernetes testing without cloud infrastructure costs. |
| **Hash Embeddings** | Deterministic, fast, and completely local embedding generation for source code. |

## Current vs. Future Scope

**Current Scope:**
- Full pipeline execution for supported Python frameworks (FastAPI, Flask) and standard Dockerfiles.
- Local Kubernetes deployment via `kind`.
- AI-assisted Q&A and test generation.

**Future Scope:**
- Cloud provider integrations (EKS, GKE, AKS).
- Advanced static application security testing (SAST).
- Full CI/CD integration with GitHub Actions / GitLab CI.
- Multi-user collaboration features.
