# CodeDeck — Future Scope & System Roadmap

This document summarizes the long-term vision and technical extension goals for **CodeDeck**. For the detailed phase-by-phase roadmap, architectural target state, and component evolution, see [`FUTURE_ROADMAP.md`](file:///d:/agent/docs/FUTURE_ROADMAP.md).

---

## Technical Extension Targets

1. **Automated CI/CD Integration**: Webhook triggers for GitHub Actions, GitLab CI, and Bitbucket Pipelines for pull request verification.
2. **Multi-Framework AI Testing**: Expanding AI test generation beyond FastAPI/Flask to Node.js/Express, Django, Java/Spring Boot, and Go.
3. **Dense Vector Embeddings & Hybrid Search**: Upgrading local hash embeddings to dense neural embeddings (OpenAI `text-embedding-3-small` / `pgvector`) combined with BM25 keyword search and cross-encoder reranking.
4. **Security & Vulnerability Analysis**: Static Analysis Security Testing (SAST) via Semgrep/Bandit, container scanning via Trivy, and automated CVE dependency checking.
5. **Observability Stack**: Native OpenTelemetry collector integration with Prometheus metrics and Grafana dashboards for production pod monitoring.
6. **Managed Cloud Kubernetes**: Support for remote cloud providers (AWS EKS, GCP GKE, Azure AKS) with private container registry pushing (GHCR / ECR).
7. **Production Deployment Strategies**: Advanced blue-green deployments, canary releases, automated metric-driven rollbacks, and human approval gates.
8. **AI DevOps Incident Assistant**: Diagnostic assistant for live cluster incident triage, log root-cause analysis, and human-in-the-loop remediation workflows.
