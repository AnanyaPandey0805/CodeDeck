# VIVA GUIDE — CodeDeck Midsem

Concise answers for common viva questions.

---

## What is CodeDeck?

CodeDeck is an AI-assisted software delivery platform. It takes a GitHub repository URL and automates the entire journey: stack detection, semantic code retrieval, AI Q&A, test generation, Docker build, and Kubernetes deployment — all visible through a developer IDE-style dashboard.

---

## Why is it needed?

Setting up CI/CD, writing deployment configs, debugging failing tests, and understanding unfamiliar codebases takes significant developer time. CodeDeck automates and explains each step, combining AI understanding with real DevOps tooling.

---

## Where is AI used?

| Feature | AI role |
|---------|---------|
| Repository Q&A | LLM answers questions using retrieved repository context (RAG) |
| Deployment recommendation | LLM summarizes detected stack and suggests steps |
| AI test generation | LLM generates rationale; deterministic code writes pytest file |
| Failure analysis | LLM explains pod logs / test failures in human language |

All other detection (language, framework, port, entry point) is deterministic Python code — no LLM involved.

---

## What is RAG?

RAG = Retrieval-Augmented Generation. Instead of asking the LLM to guess about a repository it has never seen, we:

1. Clone the repository
2. Split files into small chunks
3. Embed each chunk (hash-based local embeddings)
4. When a question arrives, embed the question and find the most similar chunks (semantic search)
5. Pass those chunks as context to the LLM
6. The LLM answers *only* from the provided evidence

This prevents hallucination and makes answers verifiable (the UI shows which files were retrieved).

---

## How does repository indexing work?

- Repository files are split into overlapping chunks (~1400 chars, ~220 overlap)
- Each chunk is embedded using a local hash-based function (no external embedding API required)
- The full index is saved as a JSON file in the workspace
- On subsequent Q&A calls, the index is loaded from cache — no re-indexing

The embedding uses term-frequency hashing (SHA-256 per token, accumulated into a 192-dimensional vector).

---

## How does AI testing work?

1. During analysis, the repository's existing test command is detected and run (e.g. `pytest`)
2. For FastAPI/Flask repositories, CodeDeck generates a minimal pytest file that:
   - Imports the detected application module
   - Creates a test client
   - Sends GET requests to detected routes
   - Asserts status < 500
3. The test file is written to a temporary directory
4. `pytest` is run as a subprocess — the AI does **not** execute tests
5. stdout/stderr are captured and returned
6. If tests fail, the LLM explains the failure using the real error output

---

## How does Docker work?

1. If the repository has an existing Dockerfile, it is used directly
2. If not, CodeDeck generates a minimal Dockerfile for supported stacks (pip/uv/poetry for Python; npm for Node)
3. `docker build` is run as a subprocess with the correct build context
4. The built image is loaded into the kind cluster with `kind load docker-image`

---

## How does Kubernetes work?

1. CodeDeck generates a minimal Deployment + Service YAML using the detected app name and port
2. `kubectl apply` applies the manifests to the `deploymind` namespace
3. `kubectl rollout status` waits for pods to become ready (up to 4 minutes)
4. If the rollout succeeds, a smoke test is run

---

## What is kind?

kind = Kubernetes IN Docker. It runs a full Kubernetes cluster inside Docker containers on your local machine. No cloud provider or VM required. CodeDeck uses kind as the local Kubernetes target for deployments.

---

## How are Kubernetes files created?

The `kubernetes_agent.py` generates YAML based on the detected analysis:
- `Deployment` uses the detected container port and image name
- `Service` exposes the port as NodePort
- `imagePullPolicy: Never` is set so Kubernetes uses the locally loaded image

---

## How many physical machines are required?

One. Everything runs on a single laptop/PC:
- Docker Desktop provides the container runtime
- kind creates a Kubernetes cluster inside Docker
- The backend and frontend run in Docker Compose containers
- kubectl communicates with the kind cluster via kubeconfig

---

## How many Kubernetes nodes?

One (kind default: 1 control-plane node). Sufficient for a development/demo deployment.

---

## What resources are required?

Approximately: 4 GB RAM, 2 CPU cores, 10 GB disk space (for Docker images, kind cluster, and repository workspace).

---

## How is data shared between components?

- Frontend ↔ Backend: REST API over HTTP
- Backend ↔ Database: SQLAlchemy + PostgreSQL (connection pool)
- Backend ↔ Repository workspace: shared Docker volume (`workspace:/tmp/deploymind`)
- Backend ↔ kind cluster: kubeconfig file; Docker socket (`/var/run/docker.sock`) for image operations

---

## What data goes to the LLM?

Only:
- Retrieved repository chunks (for Q&A)
- Detected stack signals (for recommendation)
- Test failure output (for failure analysis)
- Generated test description (for rationale)

Environment variables, secrets, API keys, and raw credentials are never sent to the LLM.

---

## How does monitoring currently work?

The Settings page performs live checks against: backend health endpoint, PostgreSQL, Docker daemon, kubectl, and kind cluster availability. Deployment status (rollout, pod readiness, smoke test) is shown on the Kubernetes page using real `kubectl` output.

---

## What is the difference between current and future monitoring?

**Current (midsem):** Live health checks, kubectl pod status, deployment logs, smoke test result.

**Future:** Prometheus metrics scraping, Grafana dashboards, continuous alerting, SLO tracking, distributed tracing.

---

## What happens when Docker build fails?

1. `docker build` returns a non-zero exit code
2. The combined stdout+stderr is captured (last 5000 chars)
3. The pipeline step is marked `failed` with the real Docker error
4. The UI shows the exact error in the Docker and Kubernetes pages
5. No further deployment steps run

---

## What happens when Kubernetes deployment fails?

1. `kubectl rollout status` times out or returns non-zero
2. Pod logs are collected via `kubectl logs`
3. Deployment and pod status are collected via `kubectl get`
4. These are passed to the LLM for failure analysis
5. The UI shows: likely cause, evidence, suggested fix

---

## What is a smoke test?

A smoke test is a minimal check that the deployed application actually responds to HTTP requests. CodeDeck:

1. Opens a `kubectl port-forward` to the Kubernetes Service
2. Sends GET requests to candidate paths (`/health`, `/`, `/docs`)
3. Accepts any response with status < 500 as "passing"
4. Reports the path, HTTP status code, and pass/fail result

---

## What are the current limitations?

- AI test generation: FastAPI and Flask only (Python)
- Node.js test generation: not yet supported in the midsem build
- Blue-green production deployment: exists in the codebase but not the primary midsem workflow
- Monitoring: health checks only — no Prometheus/Grafana
- Cloud Kubernetes: not supported; kind (local) only

---

## What will be added for end-sem?

1. GitHub Actions CI/CD integration
2. Expanded AI test generation (Node.js, Django)
3. Improved RAG with better chunk ranking
4. Security scanning integration
5. Prometheus + Grafana observability
6. Cloud Kubernetes deployment
7. Advanced deployment strategies (canary, blue-green)
8. Retrieval evaluation metrics
