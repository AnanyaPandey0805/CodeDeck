# Future Scope — CodeDeck

Features planned for the end-semester and beyond. **Not implemented in the midsem build.**

## End-Semester Targets

### 1. GitHub Actions CI/CD
- Trigger CodeDeck pipeline from push events
- Status reported back to GitHub commit status API

### 2. Expanded AI Test Generation
- Node.js / Express (supertest or jest)
- Django (pytest-django)
- Automatic test scaffolding for common patterns

### 3. Improved RAG
- OpenAI Ada-002 or text-embedding-3-small embeddings for better accuracy
- Re-ranking with BM25 hybrid search
- Retrieval evaluation with automated scoring

### 4. Security Scanning
- Integration with Bandit (Python) / npm audit (Node.js)
- Structured findings with severity, file, line
- Block deployment on HIGH findings (configurable)

### 5. Prometheus + Grafana Observability
- Export deployment metrics to Prometheus
- Grafana dashboards: deployment success rate, rollout duration, smoke test latency
- Alerting on failed deployments

### 6. Cloud Kubernetes
- Support EKS, GKE, AKS via kubeconfig injection
- Namespace-scoped deployment with RBAC
- Image push to container registry (GHCR / ECR)

### 7. Advanced Deployment Strategies
- Full blue-green with health gate
- Canary deployments with traffic splitting
- Automatic rollback on failed smoke test

### 8. AI DevOps Chat
- Multi-turn conversation about repository
- Suggest fixes from pod logs
- Explain Kubernetes errors in plain language

### 9. Multi-service Support
- Deploy backend + frontend as separate services
- Shared namespace, internal DNS
- Combined smoke test across services

### 10. Evaluation Metrics
- Track retrieval accuracy over time
- AI answer quality scoring
- Deployment success/failure rates per repository type
